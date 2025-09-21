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
    records: List[Dict[str, Any]] = []
    for p in files:
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Skipping unreadable JSON {p}: {e}")
            continue

        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        text = (data.get("text") or "").strip()
        text = re.sub(r"^```markdown\n|\n```$", "", text)
        if not text:
            print(f"Skipping empty text in {p}")
            continue

        records.append({
            "id": p.stem,
            "title": title,
            "description": description,
            "text": text,
            "path": str(p),
        })

    if not records:
        return pd.DataFrame(columns=["id", "title", "description", "text", "path"])  # empty

    df = pd.DataFrame.from_records(records)
    # Drop duplicate ids or texts if any
    df = df.drop_duplicates(subset=["id"]).reset_index(drop=True)
    return df


def embed_texts(df: "pd.DataFrame", model_name: str, batch_size: int = 32, normalize: bool = True) -> "pd.DataFrame":
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    texts = df["text"].tolist()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=normalize,
    )

    # Convert to list-of-lists for DataFrame storage
    emb_list = [row.tolist() for row in embeddings]
    out = df.copy()
    out["embedding"] = emb_list
    return out


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
        "--no-normalize",
        action="store_true",
        help="Disable embedding normalization (L2)",
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

    # Count tokens per recipe text using tiktoken
    import tiktoken
    try:
        enc = tiktoken.get_encoding(args.token_encoding)
    except Exception:
        try:
            # Fallback: allow passing a model name
            enc = tiktoken.encoding_for_model(args.token_encoding)
        except Exception as e:
            print(f"Failed to initialize tiktoken encoding '{args.token_encoding}': {e}", file=sys.stderr)
            raise

    def _count_tokens(text: str) -> int:
        if not isinstance(text, str):
            return 0
        try:
            return len(enc.encode(text))
        except Exception:
            return 0

    df["n_tokens"] = df["text"].apply(_count_tokens)
    total_tokens = int(df["n_tokens"].sum())
    avg_tokens = float(total_tokens) / max(1, len(df))

    print(
        f"Loaded {len(df)} recipes. Total tokens: {total_tokens} (avg {avg_tokens:.1f}/recipe) using encoding '{args.token_encoding}'."
    )
    print(f"Embedding with model: {args.model}")
    df_emb = embed_texts(df, model_name=args.model, batch_size=args.batch_size, normalize=not args.no_normalize)

    # Report embedding dimensionality
    first_vec = df_emb["embedding"].iloc[0]
    dim = len(first_vec) if isinstance(first_vec, list) else None
    print(f"Embeddings created. Dimension: {dim}. DataFrame shape: {df_emb.shape}")

    df_emb.to_parquet('recipes.parquet')
    print('Results saved to recipes.parquet.')


if __name__ == "__main__":
    df = main()
