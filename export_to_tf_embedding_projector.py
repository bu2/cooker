"""
Export embeddings to TensorFlow Embedding Projector format (two TSV files).

Outputs
- Vectors TSV: one row per item, tab-separated float components, no header.
- Metadata TSV: first row is a header; first column is the title by default.

Usage
  python export_to_tf_embedding_projector.py \
      --parquet recipes.parquet \
      --vectors-tsv projector_vectors.tsv \
      --metadata-tsv projector_metadata.tsv \
      --meta-cols title id n_tokens

Notes
- The metadata file must include a header row. This script always writes one.
- The vectors file must not include a header row.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Any
import sys


def _require_deps():
    try:
        import pandas as pd  # noqa: F401
    except Exception:
        print("Error: pandas is required. Install with: pip install pandas", file=sys.stderr)
        raise


def _to_list(vec: Any) -> List[float] | None:
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None

    if vec is None:
        return None
    if isinstance(vec, list):
        try:
            return [float(x) for x in vec]
        except Exception:
            return None
    if isinstance(vec, tuple):
        try:
            return [float(x) for x in vec]
        except Exception:
            return None
    if np is not None and isinstance(vec, (np.ndarray,)):
        try:
            return [float(x) for x in vec.tolist()]
        except Exception:
            return None
    try:
        return [float(x) for x in list(vec)]
    except Exception:
        return None


def _sanitize_meta(value: Any) -> str:
    # Ensure no tabs or newlines in metadata fields
    s = "" if value is None else str(value)
    return s.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def main():
    _require_deps()
    import pandas as pd

    parser = argparse.ArgumentParser(description="Export embeddings and metadata to TSV for TF Embedding Projector")
    parser.add_argument("--parquet", default="recipes.parquet", type=str, help="Input Parquet file with 'embedding' column")
    parser.add_argument("--vectors-tsv", default="projector_vectors.tsv", type=str, help="Output TSV file for vectors (no header)")
    parser.add_argument("--metadata-tsv", default="projector_metadata.tsv", type=str, help="Output TSV file for metadata (with header)")
    parser.add_argument(
        "--meta-cols",
        nargs="*",
        default=["title"],
        help="Metadata columns to include (first should be 'title'). Defaults to: title",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of rows to export")

    args = parser.parse_args()

    parquet_path = Path(args.parquet)
    if not parquet_path.exists():
        print(f"Parquet file not found: {parquet_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading DataFrame from: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    if "embedding" not in df.columns:
        print("Error: 'embedding' column not found in Parquet file.", file=sys.stderr)
        sys.exit(1)

    # Normalize/validate embedding column
    df = df.copy().reset_index(drop=True)
    df["embedding"] = df["embedding"].apply(_to_list)
    before = len(df)
    df = df.dropna(subset=["embedding"]).reset_index(drop=True)
    if len(df) < before:
        print(f"Dropped {before - len(df)} rows with missing/invalid embeddings")
    if df.empty:
        print("No rows with valid embeddings to export.")
        sys.exit(0)

    dims = {len(v) for v in df["embedding"]}
    if len(dims) != 1:
        print(f"Error: Inconsistent embedding dimensions detected: {sorted(dims)}", file=sys.stderr)
        sys.exit(1)
    dim = next(iter(dims))

    # Apply optional limit
    if args.limit is not None and args.limit >= 0:
        df = df.head(args.limit)

    # Ensure meta columns exist; create empty ones if not
    meta_cols = list(args.meta_cols) if args.meta_cols else ["title"]
    if meta_cols[0] != "title":
        print("Warning: first metadata column is not 'title'. Proceeding as requested.")
    for c in meta_cols:
        if c not in df.columns:
            df[c] = ""

    vectors_path = Path(args.vectors_tsv)
    metadata_path = Path(args.metadata_tsv)

    print(f"Exporting {len(df)} rows with dim={dim} →\n  Vectors:  {vectors_path}\n  Metadata: {metadata_path}")

    # Write vectors (no header) and metadata (with header) in matching order
    with vectors_path.open("w", encoding="utf-8", newline="\n") as vf, metadata_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as mf:
        # Metadata header
        mf.write("\t".join(meta_cols) + "\n")

        for _, row in df.iterrows():
            vec = row["embedding"]
            # Write vector line
            vf.write("\t".join(str(float(x)) for x in vec) + "\n")

            # Write metadata line
            metas = [
                _sanitize_meta(row[c]) for c in meta_cols
            ]
            mf.write("\t".join(metas) + "\n")

    print("Done.")


if __name__ == "__main__":
    main()

