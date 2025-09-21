"""
Generate a picture for each recipe using OpenAI's gpt-image-1.

Behavior
- Reads recipes from a Parquet file (default: recipes.parquet) or JSON files in a directory.
- For each recipe, generates one image using the recipe text plus an instruction:
  "Generate a picture of the recipe as if it was in your plate."
- Saves images to an output directory using the recipe ID as filename.

Notes
- Requires: pip install openai pandas pyarrow
- Set OPENAI_API_KEY in your environment for authentication.
- The OpenAI Batch API does not currently support image generation; this script will
  fall back to concurrent requests even if --use-batch is provided.

Usage examples
  python scripts/generate_recipe_images.py
  python scripts/generate_recipe_images.py --parquet recipes.parquet --images-dir recipe_images
  python scripts/generate_recipe_images.py --json-dir json_recipes --overwrite
  python scripts/generate_recipe_images.py --concurrency 4 --size 512x512
"""

from __future__ import annotations

import argparse
import base64
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sys


def _require_deps():
    try:
        import pandas as pd  # noqa: F401
    except Exception:
        print("Error: pandas is required. Install with: pip install pandas", file=sys.stderr)
        raise
    try:
        from openai import OpenAI  # noqa: F401
    except Exception:
        print("Error: openai is required. Install with: pip install openai", file=sys.stderr)
        raise


def _load_from_parquet(path: Path) -> "pd.DataFrame":
    import pandas as pd
    df = pd.read_parquet(path)
    # Expect columns: id, text (title optional)
    if "id" not in df.columns:
        print("Warning: 'id' column not found in parquet; attempting to derive from 'path' or index.")
        if "path" in df.columns:
            df["id"] = df["path"].apply(lambda p: Path(str(p)).stem)
        else:
            df["id"] = df.index.astype(str)
    if "text" not in df.columns:
        raise ValueError("Parquet must contain a 'text' column.")
    return df[[c for c in ["id", "title", "text", "path"] if c in df.columns]].copy()


def _load_from_json_dir(dir_path: Path) -> "pd.DataFrame":
    import pandas as pd
    import json

    files = sorted(dir_path.rglob("*.json"))
    rows: List[Dict[str, Any]] = []
    for p in files:
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Skipping unreadable JSON {p}: {e}")
            continue
        text = (data.get("text") or "").strip()
        if not text:
            continue
        rows.append({
            "id": p.stem,
            "title": (data.get("title") or "").strip(),
            "text": text,
            "path": str(p),
        })
    return pd.DataFrame.from_records(rows) if rows else pd.DataFrame(columns=["id", "title", "text", "path"])  # type: ignore[name-defined]


def _ensure_outdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _build_prompt(text: str) -> str:
    suffix = "\n\nGenerate a picture of the recipe as if it was in your plate."
    return f"{text.strip()}" + suffix


def _gen_image_bytes(client, prompt: str, size: str, quality: str) -> bytes:
    # Use Images API to generate an image.
    resp = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=size,
        quality=quality,
        n=1,
    )
    b64 = resp.data[0].b64_json  # type: ignore[attr-defined]
    return base64.b64decode(b64)


def _save_image(path: Path, data: bytes) -> None:
    with path.open("wb") as f:
        f.write(data)


def _worker(client, row: Dict[str, Any], outdir: Path, size: str, quality: str, fmt: str, overwrite: bool, retries: int) -> Tuple[str, bool, Optional[str]]:
    rid = str(row.get("id", "")).strip() or str(row.get("title", "")).strip()
    if not rid:
        return ("<missing-id>", False, "missing id/title")
    filename = f"{rid}.{fmt}"
    out_path = outdir / filename
    if out_path.exists() and not overwrite:
        return (rid, True, "skipped (exists)")

    prompt = _build_prompt(str(row.get("text", "")))
    last_err: Optional[str] = None
    for attempt in range(retries + 1):
        try:
            img = _gen_image_bytes(client, prompt=prompt, size=size, quality=quality)
            _save_image(out_path, img)
            return (rid, True, None)
        except Exception as e:
            last_err = str(e)
    return (rid, False, last_err)


def main():
    _require_deps()
    from openai import OpenAI
    import pandas as pd

    parser = argparse.ArgumentParser(description="Generate images for recipes using gpt-image-1")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--parquet", type=str, default="recipes.parquet", help="Parquet file containing recipes (id, text)")
    src.add_argument("--json-dir", type=str, default=None, help="Directory of JSON recipe files")

    parser.add_argument("--images-dir", type=str, default="images", help="Output directory for images")
    parser.add_argument("--format", type=str, default="jpg", choices=["png", "jpg", "jpeg"], help="Image file format")
    parser.add_argument("--size", type=str, default="1024x1024", help="Image size, e.g., 1024x1024 or 1536x1024 or 1024x1536")
    parser.add_argument("--quality", type=str, default="low", choices=["low", "medium", "high", "auto"], help="Image quality for generation")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing image files")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of images to generate")
    parser.add_argument("--concurrency", type=int, default=4, help="Parallel request workers")
    parser.add_argument("--retries", type=int, default=2, help="Retry attempts per image on failure")
    parser.add_argument("--use-batch", action="store_true", help="Attempt to use OpenAI Batch API (falls back to concurrency)")

    args = parser.parse_args()

    outdir = Path(args.images_dir)
    _ensure_outdir(outdir)

    # Load data
    df = None
    if args.json_dir:
        dir_path = Path(args.json_dir)
        if not dir_path.exists():
            print(f"JSON directory not found: {dir_path}", file=sys.stderr)
            sys.exit(1)
        df = _load_from_json_dir(dir_path)
    else:
        pq_path = Path(args.parquet)
        if not pq_path.exists():
            print(f"Parquet file not found: {pq_path}", file=sys.stderr)
            sys.exit(1)
        df = _load_from_parquet(pq_path)

    if df is None or df.empty:
        print("No recipes found to generate images.")
        sys.exit(0)

    # Select columns
    cols = [c for c in ["id", "title", "text"] if c in df.columns]
    df = df[cols].copy()

    # Apply limit
    if args.limit is not None and args.limit >= 0:
        df = df.head(args.limit)

    total = len(df)
    print(f"Generating images for {total} recipes → {outdir} (size={args.size}, quality={args.quality})")

    if args.use_batch:
        print("Note: OpenAI Batch API does not support images; using concurrent requests instead.")

    client = OpenAI()

    successes = 0
    skips = 0
    failures: List[Tuple[str, Optional[str]]] = []

    # Kick off workers
    with ThreadPoolExecutor(max_workers=max(1, int(args.concurrency))) as ex:
        futures = [
            ex.submit(
                _worker,
                client,
                row._asdict() if hasattr(row, "_asdict") else row.to_dict(),
                outdir,
                args.size,
                args.quality,
                args.format if args.format != "jpeg" else "jpg",
                args.overwrite,
                args.retries,
            )
            for _, row in df.iterrows()
        ]
        for fut in as_completed(futures):
            rid, ok, err = fut.result()
            if ok and err is None:
                successes += 1
                if successes % 10 == 0:
                    print(f"  {successes}/{total} done…")
            elif ok and err and "skipped" in err:
                skips += 1
            else:
                failures.append((rid, err))

    print(f"Done. Generated: {successes}, Skipped: {skips}, Failed: {len(failures)}")
    if failures:
        preview = ", ".join(f"{rid}: {msg}" for rid, msg in failures[:10])
        print(f"Example failures (first 10): {preview}")


if __name__ == "__main__":
    main()
