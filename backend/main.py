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


class Recipe(BaseModel):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    text: str
    image_url: Optional[str] = None


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
        wanted = [c for c in ["id", "title", "description", "text", "path"] if c in self.df.columns]
        self.df = self.df[wanted]

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

    def list_recipes(self, limit: int = 24, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        total = len(self.df)
        subset = self.df.iloc[offset : offset + limit].copy()
        rows = subset.to_dict(orient="records")
        rows = [self._attach_image_url(row) for row in rows]
        return rows, total

    def get_recipe(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        match = self.df[self.df["id"] == recipe_id]
        if match.empty:
            return None
        row = match.iloc[0].to_dict()
        return self._attach_image_url(row)

    def search(self, query: str, limit: int = 24) -> List[Dict[str, Any]]:
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
            mask = (
                self.df["title"].fillna("").str.contains(query, case=False, na=False)
                | self.df["text"].fillna("").str.contains(query, case=False, na=False)
            )
            results = self.df.loc[mask].head(limit)

        rows = results.to_dict(orient="records")
        rows = [self._attach_image_url(row) for row in rows]
        return rows


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
    store: RecipeStore = Depends(get_store),
) -> RecipeListResponse:
    items, total = store.list_recipes(limit=limit, offset=offset)
    return RecipeListResponse(total=total, items=[Recipe(**item) for item in items])


@app.get("/recipes/{recipe_id}", response_model=Recipe)
def get_recipe(recipe_id: str, store: RecipeStore = Depends(get_store)) -> Recipe:
    item = store.get_recipe(recipe_id)
    if not item:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return Recipe(**item)


@app.get("/search", response_model=List[Recipe])
def search_recipes(
    q: str = Query(..., min_length=1, description="Search text"),
    limit: int = Query(24, ge=1, le=100),
    store: RecipeStore = Depends(get_store),
) -> List[Recipe]:
    items = store.search(q, limit=limit)
    return [Recipe(**item) for item in items]


@app.exception_handler(FileNotFoundError)
def handle_missing_file(_: FileNotFoundError):  # pragma: no cover - simple passthrough
    return JSONResponse(status_code=500, content={"detail": "Required dataset not found."})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("gallery_backend.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
