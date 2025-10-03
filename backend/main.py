"""FastAPI backend for recipes with optional LanceDB search.

This module keeps a single `RecipeStore` responsible for loading data,
handling translations, and performing localized lookups.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import warnings

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    import lancedb  # type: ignore
except Exception:  # pragma: no cover - optional dependency handled at runtime
    lancedb = None  # type: ignore


DEFAULT_PARQUET = os.environ.get("RECIPES_PARQUET", "data/recipes.parquet")
DEFAULT_LANCEDB_URI = os.environ.get("RECIPES_LANCEDB", "data/recipes.db")
DEFAULT_TABLE = os.environ.get("RECIPES_TABLE", "recipes")
DEFAULT_IMAGES_DIR = os.environ.get("RECIPES_IMAGES", "data/images")
DEFAULT_TRANSLATIONS_DIR = os.environ.get("RECIPES_TRANSLATIONS", "data/translated_recipes")

DEFAULT_LANGUAGE = "fr"
RECIPE_FIELDS = ("title", "description", "text")


class Recipe(BaseModel):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    text: str
    image_url: Optional[str] = None
    n_tokens: Optional[int] = None
    language: str = DEFAULT_LANGUAGE


class RecipeListResponse(BaseModel):
    total: int
    items: List[Recipe]


class LanguageListResponse(BaseModel):
    languages: List[str]


class RecipeStore:
    """Loads recipes from parquet and optionally backs searches with LanceDB."""

    def __init__(
        self,
        parquet_path: Path,
        lancedb_uri: Optional[Path] = None,
        table_name: str = "recipes",
        images_dir: Optional[Path] = None,
        translations_dir: Optional[Path] = None,
    ) -> None:
        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

        self.default_language = DEFAULT_LANGUAGE
        self.translations_dir = translations_dir

        self.df = pd.read_parquet(parquet_path)
        if "id" not in self.df.columns:
            # Fall back to filename stem or index if missing
            if "path" in self.df.columns:
                self.df["id"] = self.df["path"].apply(lambda p: Path(str(p)).stem)
            else:
                self.df["id"] = self.df.index.astype(str)
        # Normalise to string ids and drop duplicates
        self.df["id"] = self.df["id"].astype(str)
        self.df = self.df.drop_duplicates(subset=["id"]).reset_index(drop=True)

        translation_languages: Set[str] = set()
        if translations_dir is not None and translations_dir.exists():
            translation_languages = self._apply_translations(translations_dir)

        language_columns = [
            col for col in self.df.columns if self._is_language_column(col)
        ]
        other_columns = [
            col
            for col in ["title", "description", "text", "path", "n_tokens"]
            if col in self.df.columns
        ]
        base_order = ["id", *language_columns, *other_columns]
        seen: Set[str] = set()
        filtered_wanted: List[str] = []
        for col in base_order:
            if col in self.df.columns and col not in seen:
                filtered_wanted.append(col)
                seen.add(col)
        if filtered_wanted:
            self.df = self.df[filtered_wanted]

        column_languages = self._collect_languages_from_columns(language_columns)
        self.supported_languages: Set[str] = set(column_languages)
        self.supported_languages.add(self.default_language)
        self.supported_languages.update(translation_languages)
        if not self.supported_languages:
            self.supported_languages.add(self.default_language)

        self.images_dir = images_dir
        self.table = None
        if lancedb and lancedb_uri is not None:
            try:
                db = lancedb.connect(str(lancedb_uri))
                self.table = db.open_table(table_name)
            except Exception as exc:  # pragma: no cover - optional path
                warnings.warn(
                    f"Unable to open LanceDB table '{table_name}': {exc}"
                )
                self.table = None

    # Helper -----------------------------------------------------------------
    def _apply_translations(self, translations_dir: Path) -> Set[str]:
        languages: Set[str] = set()
        translations: Dict[str, Dict[str, str]] = {}

        for path in sorted(translations_dir.glob("*.json")):
            if not path.is_file():
                continue
            try:
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except Exception as exc:  # pragma: no cover - best-effort logging
                print(f"Warning: Unable to load translations from {path}: {exc}")
                continue

            if not isinstance(payload, dict):
                continue

            recipe_id = path.stem
            if not recipe_id:
                continue

            record = translations.setdefault(recipe_id, {})
            for key, value in payload.items():
                if not isinstance(value, str):
                    continue
                record[key] = value
                lang = self._extract_language_from_column(key)
                if lang:
                    languages.add(lang)

        if not translations:
            return languages

        df = self.df.set_index("id", drop=False)
        for recipe_id, fields in translations.items():
            if recipe_id not in df.index:
                # Skip translations for unknown recipes
                continue
            for column, value in fields.items():
                df.loc[recipe_id, column] = value
        self.df = df.reset_index(drop=True)

        return languages

    @staticmethod
    def _extract_language_from_column(column: str) -> Optional[str]:
        for field in RECIPE_FIELDS:
            prefix = f"{field}_"
            if column.startswith(prefix):
                suffix = column[len(prefix) :]
                if suffix:
                    return suffix.lower()
        return None

    @classmethod
    def _is_language_column(cls, column: str) -> bool:
        return cls._extract_language_from_column(column) is not None

    def _collect_languages_from_columns(self, columns: List[str]) -> Set[str]:
        languages: Set[str] = set()
        for column in columns:
            lang = self._extract_language_from_column(column)
            if lang:
                languages.add(lang)
        return languages

    @staticmethod
    def _unique_preserve_order(values: List[str]) -> List[str]:
        seen: Set[str] = set()
        out: List[str] = []
        for v in values:
            if v not in seen:
                out.append(v)
                seen.add(v)
        return out

    def normalize_language(self, lang: Optional[str]) -> str:
        if not lang:
            return self.default_language
        normalized = lang.lower()
        return normalized if normalized in self.supported_languages else self.default_language

    def _language_preference(self, primary: str) -> List[str]:
        preferences = [primary, self.default_language, "en", *sorted(self.supported_languages)]
        filtered = [c for c in preferences if c in self.supported_languages]
        return self._unique_preserve_order(filtered)

    def get_supported_languages(self) -> List[str]:
        preferences = [self.default_language, "en", *sorted(self.supported_languages)]
        filtered = [c for c in preferences if c in self.supported_languages]
        return self._unique_preserve_order(filtered)

    def _attach_image_url(self, row: Dict[str, Any]) -> Dict[str, Any]:
        if not self.images_dir:
            row["image_url"] = None
            return row
        rid = row.get("id")
        if not rid:
            row["image_url"] = None
            return row
        for ext in (".png", ".jpg", ".jpeg"):
            candidate = self.images_dir / f"{rid}{ext}"
            if candidate.exists():
                row["image_url"] = f"/images/{candidate.name}"
                break
        else:
            row["image_url"] = None
        return row

    def _hydrate_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        recipe_id = row.get("id")
        if recipe_id is None:
            return row
        str_id = str(recipe_id)
        match = self.df[self.df["id"] == str_id]
        if match.empty:
            return row
        base = match.iloc[0].to_dict()
        for key, value in row.items():
            if key not in base:
                base[key] = value
        return base

    def _localize_row(self, row: Dict[str, Any], lang: str) -> Dict[str, Any]:
        normalized = self.normalize_language(lang)
        preferences = self._language_preference(normalized)

        def pick(field: str) -> Optional[str]:
            for code in preferences:
                key = f"{field}_{code}"
                value = row.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            value = row.get(field)
            if isinstance(value, str) and value.strip():
                return value
            return None

        localized: Dict[str, Any] = {
            "id": row.get("id"),
            "language": normalized,
            "title": pick("title"),
            "description": pick("description"),
            "text": pick("text") or "",
        }

        if "n_tokens" in row and row["n_tokens"] is not None:
            try:
                localized["n_tokens"] = int(row["n_tokens"])
            except (TypeError, ValueError):
                pass

        if row.get("image_url") is not None:
            localized["image_url"] = row["image_url"]

        return localized

    def _columns_for_search(self, lang: str) -> List[str]:
        normalized = self.normalize_language(lang)
        preferences = self._language_preference(normalized)
        columns: List[str] = []
        for field in RECIPE_FIELDS:
            for code in preferences:
                candidate = f"{field}_{code}"
                if candidate in self.df.columns and candidate not in columns:
                    columns.append(candidate)
            if field in self.df.columns and field not in columns:
                columns.append(field)
        return columns

    def list_recipes(
        self, limit: int = 24, offset: int = 0, lang: str = DEFAULT_LANGUAGE
    ) -> Tuple[List[Dict[str, Any]], int]:
        normalized = self.normalize_language(lang)
        total = len(self.df)
        subset = self.df.iloc[offset : offset + limit].copy()
        rows = subset.to_dict(orient="records")
        localized = [self._localize_row(row, normalized) for row in rows]
        items = [self._attach_image_url(row) for row in localized]
        return items, total

    def get_recipe(
        self, recipe_id: str, lang: str = DEFAULT_LANGUAGE
    ) -> Optional[Dict[str, Any]]:
        normalized = self.normalize_language(lang)
        match = self.df[self.df["id"] == recipe_id]
        if match.empty:
            return None
        row = match.iloc[0].to_dict()
        localized = self._localize_row(row, normalized)
        return self._attach_image_url(localized)

    def search(
        self, query: str, limit: int = 24, lang: str = DEFAULT_LANGUAGE
    ) -> List[Dict[str, Any]]:
        normalized = self.normalize_language(lang)
        results = None
        if self.table is not None:
            try:
                results = self.table.search(query).limit(limit).to_pandas()
            except Exception as exc:  # pragma: no cover - optional path
                warnings.warn(f"LanceDB search failed; falling back to pandas: {exc}")

        if results is None or getattr(results, "empty", True):
            # Simple fallback: case-insensitive containment
            columns = self._columns_for_search(normalized)
            if columns:
                mask = pd.Series(False, index=self.df.index)
                for col in columns:
                    mask |= self.df[col].fillna("").str.contains(query, case=False, na=False)
                results = self.df.loc[mask].head(limit)
            else:
                results = pd.DataFrame([])

        rows = results.to_dict(orient="records") if results is not None else []
        hydrated = [self._hydrate_row(row) for row in rows]
        localized = [self._localize_row(row, normalized) for row in hydrated]
        return [self._attach_image_url(row) for row in localized]


# Dependency -----------------------------------------------------------------

def get_store() -> RecipeStore:
    if not hasattr(get_store, "_instance"):
        parquet_path = Path(DEFAULT_PARQUET)
        lancedb_uri = Path(DEFAULT_LANCEDB_URI) if DEFAULT_LANCEDB_URI else None
        images_dir_path = Path(DEFAULT_IMAGES_DIR)
        images_dir = images_dir_path if images_dir_path.exists() else None
        translations_dir = Path(DEFAULT_TRANSLATIONS_DIR) if DEFAULT_TRANSLATIONS_DIR else None
        get_store._instance = RecipeStore(
            parquet_path=parquet_path,
            lancedb_uri=lancedb_uri,
            table_name=DEFAULT_TABLE,
            images_dir=images_dir,
            translations_dir=translations_dir,
        )
    return get_store._instance  # type: ignore[attr-defined]


app = FastAPI(title="Recipe Gallery API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

images_dir_path = Path(DEFAULT_IMAGES_DIR)
if images_dir_path.exists():
    app.mount("/images", StaticFiles(directory=images_dir_path), name="images")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/languages", response_model=LanguageListResponse)
def list_languages(store: RecipeStore = Depends(get_store)) -> LanguageListResponse:
    return LanguageListResponse(languages=store.get_supported_languages())


@app.get("/recipes", response_model=RecipeListResponse)
def list_recipes(
    limit: int = Query(24, ge=1, le=200),
    offset: int = Query(0, ge=0),
    lang: Optional[str] = Query(
        DEFAULT_LANGUAGE,
        min_length=2,
        max_length=15,
        description="Language code",
    ),
    store: RecipeStore = Depends(get_store),
) -> RecipeListResponse:
    normalized_lang = store.normalize_language(lang)
    items, total = store.list_recipes(limit=limit, offset=offset, lang=normalized_lang)
    return RecipeListResponse(total=total, items=[Recipe(**item) for item in items])


@app.get("/recipes/{recipe_id}", response_model=Recipe)
def get_recipe(
    recipe_id: str,
    lang: Optional[str] = Query(
        DEFAULT_LANGUAGE,
        min_length=2,
        max_length=15,
        description="Language code",
    ),
    store: RecipeStore = Depends(get_store),
) -> Recipe:
    normalized_lang = store.normalize_language(lang)
    item = store.get_recipe(recipe_id, lang=normalized_lang)
    if not item:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return Recipe(**item)


@app.get("/search", response_model=List[Recipe])
def search_recipes(
    q: str = Query(..., min_length=1, description="Search text"),
    limit: int = Query(24, ge=1, le=100),
    lang: Optional[str] = Query(
        DEFAULT_LANGUAGE,
        min_length=2,
        max_length=15,
        description="Language code",
    ),
    store: RecipeStore = Depends(get_store),
) -> List[Recipe]:
    normalized_lang = store.normalize_language(lang)
    items = store.search(q, limit=limit, lang=normalized_lang)
    return [Recipe(**item) for item in items]


@app.exception_handler(FileNotFoundError)
def handle_missing_file(_: FileNotFoundError):  # pragma: no cover - simple passthrough
    return JSONResponse(status_code=500, content={"detail": "Required dataset not found."})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
