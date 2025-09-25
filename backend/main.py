"""FastAPI backend serving recipe data and search powered by LanceDB."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


DEFAULT_PARQUET = os.environ.get("RECIPES_PARQUET", "recipes.parquet")
DEFAULT_LANCEDB_URI = os.environ.get("RECIPES_LANCEDB", "recipes.db")
DEFAULT_TABLE = os.environ.get("RECIPES_TABLE", "recipes")
DEFAULT_IMAGES_DIR = os.environ.get("RECIPES_IMAGES", "images")


SUPPORTED_LANGUAGES = {"fr", "en"}


def normalize_language(lang: Optional[str]) -> str:
    if not lang:
        return "fr"
    normalized = lang.lower()
    return normalized if normalized in SUPPORTED_LANGUAGES else "fr"


class Recipe(BaseModel):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    text: str
    image_url: Optional[str] = None
    n_tokens: Optional[int] = None
    language: str = "fr"


class RecipeListResponse(BaseModel):
    total: int
    items: List[Recipe]


class RecipeStore:
    """Loads recipes from parquet and optionally backs searches with LanceDB."""

    def __init__(
        self,
        parquet_path: Path,
        lancedb_uri: Optional[Path] = None,
        table_name: str = "recipes",
        images_dir: Optional[Path] = None,
    ) -> None:
        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

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

        # Keep only relevant columns to avoid large payloads
        language_columns = [
            "title_fr",
            "description_fr",
            "text_fr",
            "title_en",
            "description_en",
            "text_en",
        ]
        optional_language = [c for c in language_columns if c in self.df.columns]
        other_columns = [c for c in ["title", "description", "text", "path", "n_tokens"] if c in self.df.columns]
        wanted = ["id", *optional_language, *other_columns]
        seen = set()
        filtered_wanted = []
        for col in wanted:
            if col not in seen:
                filtered_wanted.append(col)
                seen.add(col)
        self.df = self.df[filtered_wanted]

        self.images_dir = images_dir
        self.table = None
        if lancedb and lancedb_uri is not None:
            try:
                db = lancedb.connect(str(lancedb_uri))
                self.table = db.open_table(table_name)
            except Exception as exc:  # pragma: no cover - optional path
                print(f"Warning: Unable to open LanceDB table '{table_name}': {exc}")
                self.table = None

    # Helper -----------------------------------------------------------------
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

    def _localize_row(self, row: Dict[str, Any], lang: str) -> Dict[str, Any]:
        normalized = normalize_language(lang)
        fallback = "fr" if normalized != "fr" else "en"

        def pick(field: str) -> Optional[str]:
            for code in (normalized, fallback):
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
        normalized = normalize_language(lang)
        fallback = "fr" if normalized != "fr" else "en"
        columns: List[str] = []
        for field in ("title", "description", "text"):
            for code in (normalized, fallback):
                candidate = f"{field}_{code}"
                if candidate in self.df.columns and candidate not in columns:
                    columns.append(candidate)
            if field in self.df.columns and field not in columns:
                columns.append(field)
        return columns

    def list_recipes(
        self, limit: int = 24, offset: int = 0, lang: str = "fr"
    ) -> Tuple[List[Dict[str, Any]], int]:
        lang = normalize_language(lang)
        total = len(self.df)
        subset = self.df.iloc[offset : offset + limit].copy()
        rows = subset.to_dict(orient="records")
        localized = [self._localize_row(row, lang) for row in rows]
        items = [self._attach_image_url(row) for row in localized]
        return items, total

    def get_recipe(self, recipe_id: str, lang: str = "fr") -> Optional[Dict[str, Any]]:
        lang = normalize_language(lang)
        match = self.df[self.df["id"] == recipe_id]
        if match.empty:
            return None
        row = match.iloc[0].to_dict()
        localized = self._localize_row(row, lang)
        return self._attach_image_url(localized)

    def search(self, query: str, limit: int = 24, lang: str = "fr") -> List[Dict[str, Any]]:
        lang = normalize_language(lang)
        results: Optional[pd.DataFrame] = None
        if self.table is not None:
            try:
                search_obj = self.table.search(query).limit(limit)
                if hasattr(search_obj, "to_pandas"):
                    results = search_obj.to_pandas()
                elif hasattr(search_obj, "to_df"):
                    results = search_obj.to_df()  # type: ignore[assignment]
                elif hasattr(search_obj, "to_list"):
                    results = pd.DataFrame(search_obj.to_list())
            except Exception as exc:
                print(f"Warning: LanceDB search failed: {exc}")
                results = None

        if results is None or results.empty:
            # Simple fallback: case-insensitive containment
            columns = self._columns_for_search(lang)
            if columns:
                mask = pd.Series(False, index=self.df.index)
                for col in columns:
                    mask |= self.df[col].fillna("").str.contains(query, case=False, na=False)
                results = self.df.loc[mask].head(limit)
            else:
                results = pd.DataFrame([])

        rows = results.to_dict(orient="records") if results is not None else []
        localized = [self._localize_row(row, lang) for row in rows]
        return [self._attach_image_url(row) for row in localized]


# Dependency -----------------------------------------------------------------

def get_store() -> RecipeStore:
    if not hasattr(get_store, "_instance"):
        parquet_path = Path(DEFAULT_PARQUET)
        lancedb_uri = Path(DEFAULT_LANCEDB_URI) if DEFAULT_LANCEDB_URI else None
        images_dir = Path(DEFAULT_IMAGES_DIR)
        if not images_dir.exists():
            images_dir = None
        get_store._instance = RecipeStore(
            parquet_path=parquet_path,
            lancedb_uri=lancedb_uri,
            table_name=DEFAULT_TABLE,
            images_dir=images_dir,
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


@app.get("/recipes", response_model=RecipeListResponse)
def list_recipes(
    limit: int = Query(24, ge=1, le=200),
    offset: int = Query(0, ge=0),
    lang: Optional[str] = Query("fr", min_length=2, max_length=5, description="Language code (fr or en)"),
    store: RecipeStore = Depends(get_store),
) -> RecipeListResponse:
    normalized_lang = normalize_language(lang)
    items, total = store.list_recipes(limit=limit, offset=offset, lang=normalized_lang)
    return RecipeListResponse(total=total, items=[Recipe(**item) for item in items])


@app.get("/recipes/{recipe_id}", response_model=Recipe)
def get_recipe(
    recipe_id: str,
    lang: Optional[str] = Query("fr", min_length=2, max_length=5, description="Language code (fr or en)"),
    store: RecipeStore = Depends(get_store),
) -> Recipe:
    normalized_lang = normalize_language(lang)
    item = store.get_recipe(recipe_id, lang=normalized_lang)
    if not item:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return Recipe(**item)


@app.get("/search", response_model=List[Recipe])
def search_recipes(
    q: str = Query(..., min_length=1, description="Search text"),
    limit: int = Query(24, ge=1, le=100),
    lang: Optional[str] = Query("fr", min_length=2, max_length=5, description="Language code (fr or en)"),
    store: RecipeStore = Depends(get_store),
) -> List[Recipe]:
    normalized_lang = normalize_language(lang)
    items = store.search(q, limit=limit, lang=normalized_lang)
    return [Recipe(**item) for item in items]


@app.exception_handler(FileNotFoundError)
def handle_missing_file(_: FileNotFoundError):  # pragma: no cover - simple passthrough
    return JSONResponse(status_code=500, content={"detail": "Required dataset not found."})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("gallery_backend.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
