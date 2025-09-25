"""
Load generated recipe JSON files into a Pandas DataFrame and add text embeddings
using sentence-transformers.

Usage examples:
  python scripts/embed_recipes.py
  python scripts/embed_recipes.py --input-dir json_recipes --model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

Notes:
- Install dependencies: pip install pandas sentence-transformers tiktoken
- The first model load may download weights (requires network).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import List, Dict, Any


def _require_deps():
    try:
        import pandas as pd  # noqa: F401
    except Exception:
        print("Error: pandas is required. Install with: pip install pandas", file=sys.stderr)
        raise
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
    except Exception:
        print(
            "Error: sentence-transformers is required. Install with: pip install sentence-transformers",
            file=sys.stderr,
        )
        raise
    try:
        import tiktoken  # noqa: F401
    except Exception:
        print(
            "Error: tiktoken is required for token counting. Install with: pip install tiktoken",
            file=sys.stderr,
        )
        raise


def load_recipes(input_dir: Path) -> "pd.DataFrame":
    import pandas as pd

    files = sorted(input_dir.rglob("*.json"))
    records = []
    for p in files:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)

        data = {k:data[k].strip() for k in data}
        records.append({"id": p.stem, **data})

    return pd.DataFrame.from_records(records)


def embed_texts(texts: str, model_name: str, batch_size: int = 32, normalize: bool = False) -> "pd.DataFrame":
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=normalize,
    )
    return embeddings


def main():
    _require_deps()

    parser = argparse.ArgumentParser(description="Load recipe JSON, count tokens, and embed text with sentence-transformers.")
    parser.add_argument("--input-dir", default="json_recipes", type=str, help="Directory containing recipe JSON files")
    parser.add_argument(
        "--model",
        default="Snowflake/snowflake-arctic-embed-l-v2.0",
        type=str,
        help="SentenceTransformers model name",
    )
    parser.add_argument("--batch-size", default=32, type=int, help="Batch size for embedding")
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Enable embedding normalization (L2)",
    )
    parser.add_argument(
        "--token-encoding",
        default="cl100k_base",
        type=str,
        help="tiktoken encoding to use for token counting (e.g., cl100k_base, o200k_base)",
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading recipes from: {input_dir}")
    df = load_recipes(input_dir)
    if df.empty:
        print("No recipes found to embed.")
        sys.exit(0)

    texts = df["text_fr"]
    cleaned = []
    for t in texts:
        if t.startswith("```"):
            t = t[t.index("\n")+1:]
        if t.strip().endswith("```"):
            t = t[:t.rfind("\n")]
        cleaned.append(t)
    df["text_fr"] = cleaned

    import tiktoken
    enc = tiktoken.get_encoding(args.token_encoding)

    def _count_tokens(text: str) -> int:
        if not isinstance(text, str):
            return 0
        try:
            return len(enc.encode(text))
        except Exception:
            return 0

    texts = df["title_fr"] + ": " + df["description_fr"] + "\n" + df["text_fr"]

    n_tokens = texts.apply(_count_tokens)
    total_tokens = int(n_tokens.sum())
    avg_tokens = float(total_tokens) / max(1, len(df))

    print(
        f"Loaded {len(df)} recipes. Total tokens: {total_tokens} (avg {avg_tokens:.1f}/recipe) using encoding '{args.token_encoding}'."
    )
    print(f"Embedding with model: {args.model}")
    embeddings = embed_texts(texts, model_name=args.model, batch_size=args.batch_size, normalize=args.normalize)
    df["embedding"] = list(embeddings)

    # Report embedding dimensionality
    first_vec = df["embedding"].iloc[0]
    dim = len(first_vec) if isinstance(first_vec, list) else None
    print(f"Embeddings created. Dimension: {dim}. DataFrame shape: {df.shape}")

    df.to_parquet('recipes.parquet')
    print('Results saved to recipes.parquet.')


if __name__ == "__main__":
    df = main()
