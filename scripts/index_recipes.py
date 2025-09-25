"""
Build a LanceDB database from a Parquet dataset of recipes.

Inputs
- Parquet file with columns at least: `id` (optional), `title`, `text`, `embedding` (list[float])

What it does
- Loads the parquet into a Pandas DataFrame
- Connects to a LanceDB database directory (created if needed)
- Creates/overwrites a table and writes the data
- Builds an IVF_FLAT vector index on `embedding`
- Builds a full-text search index on `title`, `description`, and `text`

Usage
  pip install lancedb pandas pyarrow
  python scripts/index_recipes.py --parquet recipes.parquet --db ./recipes.db --table recipes --overwrite

Notes
- Requires a recent LanceDB version with IVF_FLAT vector indexing and Tantivy-based FTS.
- Default vector metric is "cosine". Choose "dot" only when embeddings are unit-normalized.
- Full-text indexing is optimized for French recipe content.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, List


def _require_deps():
    try:
        import pandas as pd  # noqa: F401
    except Exception:
        print("Error: pandas is required. Install with: pip install pandas", file=sys.stderr)
        raise
    try:
        import lancedb  # noqa: F401
    except Exception:
        print("Error: lancedb is required. Install with: pip install lancedb", file=sys.stderr)
        raise


def _to_list(vec: Any) -> List[float] | None:
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None  # Optional dependency

    if vec is None:
        return None
    if isinstance(vec, list):
        return [float(x) for x in vec]
    if isinstance(vec, tuple):
        return [float(x) for x in vec]
    if np is not None and isinstance(vec, (np.ndarray,)):
        return [float(x) for x in vec.tolist()]
    # PyArrow list-like may show up as arrays; last resort
    try:
        return [float(x) for x in list(vec)]
    except Exception:
        return None


def _ensure_embeddings(df):
    if "embedding" not in df.columns:
        raise ValueError("Column 'embedding' not found in the Parquet file.")
    df["embedding"] = df["embedding"].apply(_to_list)
    # Drop rows with missing/invalid embeddings
    before = len(df)
    df = df.dropna(subset=["embedding"]).reset_index(drop=True)
    if len(df) < before:
        print(f"Dropped {before - len(df)} rows with invalid embeddings")
    # Validate consistent dimensionality
    dims = {len(v) for v in df["embedding"]}
    if len(dims) != 1:
        raise ValueError(f"Inconsistent embedding dimensions detected: {sorted(dims)}")
    return df


def main():
    _require_deps()
    import pandas as pd
    import lancedb

    parser = argparse.ArgumentParser(description="Index recipes in LanceDB from a Parquet file")
    parser.add_argument("--parquet", default='recipes.parquet', help="Path to recipes.parquet with 'embedding' column")
    parser.add_argument("--db", default="./recipes.db", help="Directory to store LanceDB database")
    parser.add_argument("--table", default="recipes", help="LanceDB table name")
    parser.add_argument(
        "--metric",
        default="cosine",
        choices=["cosine", "l2", "dot"],
        help="Vector metric (default: cosine). Use 'dot' only if embeddings are unit-normalized.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing table if present")

    args = parser.parse_args()
    parquet_path = Path(args.parquet)
    db_path = Path(args.db)

    if not parquet_path.exists():
        print(f"Parquet file not found: {parquet_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading DataFrame from: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    expected_cols = {"title", "description", "text", "embedding"}
    missing = expected_cols - set(df.columns)
    if missing:
        print(f"Warning: Parquet missing columns: {sorted(missing)}")

    df = _ensure_embeddings(df)
    print(f"Loaded {len(df)} rows. Embedding dim: {len(df['embedding'].iloc[0])}")

    print(f"Connecting LanceDB at: {db_path}")
    db = lancedb.connect(str(db_path))

    mode = "overwrite" if args.overwrite else "create"
    if args.overwrite:
        try:
            db.drop_table(args.table)
            print(f"Dropped existing table: {args.table}")
        except Exception:
            pass

    print(f"Creating table '{args.table}' (mode={mode})...")
    tbl = db.create_table(args.table, data=df, mode="overwrite" if args.overwrite else "create")

    print("Building IVF_FLAT vector index on 'embedding'...")
    tbl.create_index(
        vector_column_name="embedding",
        index_type="IVF_FLAT",
        metric=args.metric,
    )

    fts_columns = []
    for col in df.columns:
        for prefix in ("title_", "description_", "text_"):
            if col.startswith(prefix):
                fts_columns.append(col)
    print(f"Creating French FTS index on {fts_columns}...")
    tbl.create_fts_index(
        field_names=fts_columns,
        use_tantivy=True,
    )

    # Persist is implicit; LanceDB writes to disk on table operations
    print(f"Database ready at: {db_path} (table: {args.table})")


if __name__ == "__main__":
    main()
