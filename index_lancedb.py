"""
Build a LanceDB database from a Parquet dataset of recipes.

Inputs
- Parquet file with columns at least: `id` (optional), `title`, `text`, `embedding` (list[float])

What it does
- Loads the parquet into a Pandas DataFrame
- Connects to a LanceDB database directory (created if needed)
- Creates/overwrites a table and writes the data
- Builds a vector index on `embedding` (prefers HNSW, falls back to IVF-based if needed)
- Builds a full-text search index on `text`

Usage
  pip install lancedb pandas pyarrow
  python index_lancedb.py --parquet recipes.parquet --db ./lancedb_recipes --table recipes --overwrite

Notes
- HNSW and FTS APIs can differ between lancedb versions; this script tries
  the most common signatures and degrades gracefully with warnings.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable, List


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


def _create_vector_index(tbl, column: str, metric: str = "cosine"):
    """
    Create a vector index in a way that works across LanceDB versions without noisy
    error output. We try a list of preferred index types and several keyword
    variants, only printing when we actually succeed (or once if everything fails).
    """
    import inspect

    def _attempt(index_type: str) -> bool:
        # Preferred: explicit keyword for vector column name
        try:
            tbl.create_index(index_type=index_type, vector_column_name=column, metric=metric)
            print(f"Created {index_type} index on '{column}' (metric={metric})")
            return True
        except Exception:
            pass

        # Fallback: some versions expect `column=` instead of `vector_column_name=`
        try:
            tbl.create_index(index_type=index_type, column=column, metric=metric)
            print(f"Created {index_type} index on '{column}' (metric={metric})")
            return True
        except Exception:
            pass

        # Last resort: introspect the signature to pick accepted kw names
        try:
            f = getattr(tbl, "create_index", None)
            if not callable(f):
                return False
            sig = inspect.signature(f)
            kwargs = {}
            # Pick a column kw that exists
            for cname in ("vector_column_name", "column", "vector_col", "vector_column", "col_name"):
                if cname in sig.parameters:
                    kwargs[cname] = column
                    break
            # Pick a metric kw that exists
            for mname in ("metric", "distance", "distance_type"):
                if mname in sig.parameters:
                    kwargs[mname] = metric
                    break
            # Index type kw
            if "index_type" in sig.parameters:
                kwargs["index_type"] = index_type
            elif "type" in sig.parameters:
                kwargs["type"] = index_type

            f(**kwargs)
            print(f"Created {index_type} index on '{column}' (metric={metric})")
            return True
        except Exception:
            return False

    # Try in order of preference; choose the first that works without emitting errors
    for idx_type in ("IVF_HNSW_SQ", "IVF_PQ"):
        if _attempt(idx_type):
            return

    raise RuntimeError("Unable to create a vector index; unsupported LanceDB version?")


def _create_fts_index(tbl, column: str = "text"):
    # Prefer explicit FTS API if available
    f = getattr(tbl, "create_fts_index", None)
    if callable(f):
        try:
            # Accept either str or list[str]
            try:
                f(column)
            except TypeError:
                f([column])
            print(f"Created FTS index on '{column}'")
            return
        except Exception as e:
            print(f"FTS via create_fts_index failed: {e}")

    # Fallback: try generic create_index with index_type
    try:
        try:
            tbl.create_index(column=column, index_type="FTS")
        except TypeError:
            tbl.create_index(column, index_type="FTS")  # type: ignore[arg-type]
        print(f"Created FTS index on '{column}' via create_index")
    except Exception as e:
        print(f"Warning: Unable to create FTS index on '{column}': {e}")


def main():
    _require_deps()
    import pandas as pd
    import lancedb

    parser = argparse.ArgumentParser(description="Index recipes in LanceDB from a Parquet file")
    parser.add_argument("--parquet", required=True, help="Path to recipes.parquet with 'embedding' column")
    parser.add_argument("--db", default="./lancedb_recipes", help="Directory to store LanceDB database")
    parser.add_argument("--table", default="recipes", help="LanceDB table name")
    parser.add_argument("--metric", default="cosine", choices=["cosine", "l2", "dot"], help="Vector metric")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing table if present")

    args = parser.parse_args()
    parquet_path = Path(args.parquet)
    db_path = Path(args.db)

    if not parquet_path.exists():
        print(f"Parquet file not found: {parquet_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading DataFrame from: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    expected_cols = {"title", "text", "embedding"}
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

    print(f"Creating table '{args.table}' (mode={mode})…")
    tbl = db.create_table(args.table, data=df, mode="overwrite" if args.overwrite else "create")

    print("Building vector index on 'embedding'…")
    _create_vector_index(tbl, column="embedding", metric=args.metric)

    print("Creating FTS index on 'text'…")
    _create_fts_index(tbl, column="text")

    # Persist is implicit; LanceDB writes to disk on table operations
    print(f"Database ready at: {db_path} (table: {args.table})")


if __name__ == "__main__":
    main()
