import json
import os
import sys
import time
from typing import Dict

try:
    import ollama
except Exception:
    print("Error: The 'ollama' Python package is required to run this script.")
    print("Install with: pip install ollama")
    raise

try:
    import tiktoken
except Exception:
    print("Error: The 'tiktoken' Python package is required to run this script.")
    print("Install with: pip install tiktoken")
    raise


TRANSLATOR_LLM = "qwen2.5"
TOKENIZER = "cl100k_base"

tokenizer = tiktoken.get_encoding(TOKENIZER)


def translate_field(model: str, field_name: str, text: str) -> str:
    """Translate a single field while preserving Markdown structure."""

    prompt = (
        "You are a professional bilingual translator.\n\n"
        f"Translate the following French `{field_name}` into natural English:\n--\n"
        + text + "\n--\n"
        "Preserve Markdown formatting when present.\n"
        "Return only the translated text without additional commentary.\n\n"
    )

    ntokens = len(tokenizer.encode(prompt))
    num_ctx = 1 << (ntokens - 1).bit_length()

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            num_ctx=num_ctx,
        )
        translated = response.get("message", {}).get("content", "").strip()
        if translated:
            return translated
    except Exception:
        pass

    # Fallback to the generate API if chat isn't available
    response = ollama.generate(model=model, prompt=prompt)
    return response.get("response", "").strip()


def translate_recipe(model: str, recipe: Dict[str, str]) -> Dict[str, str]:
    title_fr = recipe.get("title", "").strip()
    description_fr = recipe.get("description", "").strip()
    text_fr = recipe.get("text", "").strip()

    if not title_fr and not description_fr and not text_fr:
        raise ValueError("Recipe JSON is missing 'title', 'description', and 'text' fields.")

    title_en = translate_field(model, "title", title_fr) if title_fr else ""
    description_en = translate_field(model, "description", description_fr) if description_fr else ""
    text_en = translate_field(model, "recipe text", text_fr) if text_fr else ""

    return {
        "title_fr": title_fr,
        "description_fr": description_fr,
        "text_fr": text_fr,
        "title_en": title_en,
        "description_en": description_en,
        "text_en": text_en,
    }


def main() -> None:
    model = os.environ.get("OLLAMA_MODEL", TRANSLATOR_LLM)
    source_dir = os.environ.get("RECIPES_DIR", "json_recipes")
    output_dir = os.environ.get("OUTPUT_DIR", "translated_recipes")

    if not os.path.isdir(source_dir):
        print(f"Source directory not found: {source_dir}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    recipe_files = [
        os.path.join(source_dir, name)
        for name in sorted(os.listdir(source_dir))
        if name.endswith(".json")
    ]

    total = len(recipe_files)
    if total == 0:
        print("No recipe files found to translate.")
        return

    for idx, recipe_path in enumerate(recipe_files, start=1):
        filename = os.path.basename(recipe_path)
        output_path = os.path.join(output_dir, filename)

        if os.path.exists(output_path):
            print(f"[{idx}/{total}] Skipping (exists): {filename}")
            continue

        print(f"[{idx}/{total}] Translating: {filename}")
        start = time.perf_counter()

        try:
            with open(recipe_path, "r", encoding="utf-8") as f:
                recipe_data = json.load(f)

            translated = translate_recipe(model, recipe_data)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(translated, f, ensure_ascii=False, indent=2)

            elapsed = time.perf_counter() - start
            print(f"   Saved to {output_path} in {elapsed:.2f}s")
        except KeyboardInterrupt:
            print("Interrupted by user. Exiting…")
            sys.exit(1)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            print(f"   Error translating '{filename}' after {elapsed:.2f}s: {exc}")
            continue

        time.sleep(0.1)

    print("Done.")


if __name__ == "__main__":
    main()
