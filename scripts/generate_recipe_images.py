"""
Generate a picture for each recipe using OpenAI's gpt-image-1.

Behavior
- Reads recipes from JSON files in a directory.
- For each recipe, generates one image using the recipe text plus an instruction:
  "Generate a picture of the recipe as if it was in your plate."
- Saves images to an output directory using the recipe ID as filename.

Notes
- Requires: pip install openai pandas pyarrow
- Set OPENAI_API_KEY in your environment for authentication.

Usage examples
  python scripts/generate_recipe_images.py
  python scripts/generate_recipe_images.py --images-dir data/images
  python scripts/generate_recipe_images.py --json-dir data/json_recipes --overwrite
"""

from __future__ import annotations

import argparse
import base64
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
            "description": (data.get("description") or "").strip(),
            "text": text,
            "path": str(p),
        })
    return pd.DataFrame.from_records(rows) if rows else pd.DataFrame(columns=["id", "title", "description", "text", "path"])  # type: ignore[name-defined]


def _ensure_outdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _build_prompt(text: str) -> str:
    suffix = "\n\nGenerate a picture of the recipe as if it was in your plate. Do not show any text."
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


def main():
    _require_deps()
    from openai import OpenAI
    import pandas as pd

    parser = argparse.ArgumentParser(description="Generate images for recipes using gpt-image-1")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--json-dir", type=str, default="data/json_recipes", help="Directory of JSON recipe files")

    parser.add_argument("--images-dir", type=str, default="data/images", help="Output directory for images")
    parser.add_argument("--format", type=str, default="jpg", choices=["png", "jpg", "jpeg"], help="Image file format")
    parser.add_argument("--size", type=str, default="1024x1024", help="Image size, e.g., 1024x1024 or 1536x1024 or 1024x1536")
    parser.add_argument("--quality", type=str, default="low", choices=["low", "medium", "high", "auto"], help="Image quality for generation")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing image files")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of images to generate")


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

    if df is None or df.empty:
        print("No recipes found to generate images.")
        sys.exit(0)

    # Apply limit
    if args.limit is not None and args.limit >= 0:
        df = df.head(args.limit)

    total = len(df)
    print(f"Generating images for {total} recipes → {outdir} (size={args.size}, quality={args.quality})")

    client = OpenAI()
    successes = 0
    skips = 0
    failures: List[Tuple[str, Optional[str]]] = []

    img_fmt = args.format if args.format != "jpeg" else "jpg"

    for _, row in df.iterrows():
        rid = str(row.get("id", "")).strip() or str(row.get("title", "")).strip()
        if not rid:
            failures.append(("<missing-id>", "missing id/title"))
            continue

        out_path = outdir / f"{rid}.{img_fmt}"
        if out_path.exists() and not args.overwrite:
            print(f"Skip {row["title"]} ({out_path})...")
            skips += 1
            continue

        print(f"Generate image for {row["title"]} ({rid})...")
        prompt = _build_prompt(f"{row['title']}\n{row['description']}\n{row['text']}")
        try:
            img = _gen_image_bytes(client, prompt=prompt, size=args.size, quality=args.quality)
            _save_image(out_path, img)
            successes += 1
        except Exception as e:
            failures.append((rid, str(e)))

    print(f"Done. Generated: {successes}, Skipped: {skips}, Failed: {len(failures)}")
    if failures:
        preview = ", ".join(f"{rid}: {msg}" for rid, msg in failures[:10])
        print(f"Example failures (first 10): {preview}")


if __name__ == "__main__":
    main()
