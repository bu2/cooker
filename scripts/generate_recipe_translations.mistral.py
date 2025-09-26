import argparse
import json
import os
import sys
import time
from typing import Dict, Iterable, List

try:
    from mistralai import Mistral
except Exception:
    print("Error: The 'mistralai' Python package is required to run this script.")
    print("Install with: pip install mistralai")
    raise


TRANSLATOR_LLM = "mistral-small-latest"
API_KEY_ENV = "MISTRAL_API_KEY"
DEFAULT_TARGET_LANGUAGES = []


LANGUAGE_NAMES = {
    "ar": "Arabic",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "sv": "Swedish",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "zh": "Chinese",
}


def _coerce_message_content(content: object) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue

            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
                continue

            inner_content = getattr(item, "content", None)
            if isinstance(inner_content, str):
                parts.append(inner_content)

        combined = "".join(parts).strip()
        if combined:
            return combined

    return ""


def parse_languages(values: Iterable[str]) -> List[str]:
    """Normalise target language codes while preserving order."""

    seen = set()
    result: List[str] = []
    for value in values:
        if not value:
            continue
        parts = [part.strip().lower() for part in value.replace(";", ",").split(",")]
        expanded: List[str] = []
        for part in parts:
            if not part:
                continue
            expanded.extend(segment.strip().lower() for segment in part.split())
        for code in expanded:
            if not code or code in seen:
                continue
            seen.add(code)
            result.append(code)
    return result


def describe_language(language_code: str) -> str:
    language_name = LANGUAGE_NAMES.get(language_code)
    if language_name:
        return f"natural {language_name} ({language_code})"
    return f"the language indicated by the ISO 639-1 code '{language_code}'"


def translate_field(client: Mistral, model: str, field_name: str, text: str, language_code: str) -> str:
    """Translate a single field while preserving Markdown structure."""

    target_language = describe_language(language_code)
    prompt = (
        "You are a professional bilingual translator.\n\n"
        f"Translate the following French `{field_name}` into {target_language}:\n--\n"
        + text + "\n--\n"
        "Preserve Markdown formatting when present.\n"
        "Return only the translated text without additional commentary.\n\n"
    )

    response = client.chat.complete(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

    choices = getattr(response, "choices", None)
    if not choices:
        return ""

    for choice in choices:
        message = getattr(choice, "message", None)
        if not message:
            continue

        translated = _coerce_message_content(getattr(message, "content", None))
        if translated:
            return translated

    return ""


def translate_recipe(client: Mistral, model: str, recipe: Dict[str, str], languages: List[str]) -> Dict[str, str]:
    title_fr = recipe.get("title", "").strip()
    description_fr = recipe.get("description", "").strip()
    text_fr = recipe.get("text", "").strip()

    if not title_fr and not description_fr and not text_fr:
        raise ValueError("Recipe JSON is missing 'title', 'description', and 'text' fields.")

    translated = {
        "title_fr": title_fr,
        "description_fr": description_fr,
        "text_fr": text_fr,
    }

    for language_code in languages:
        code = language_code.lower()
        if code == "fr":
            continue

        if title_fr:
            translated[f"title_{code}"] = translate_field(client, model, "title", title_fr, code)
        if description_fr:
            translated[f"description_{code}"] = translate_field(client, model, "description", description_fr, code)
        if text_fr:
            text = translate_field(client, model, "recipe text", text_fr, code)
            if text.startswith("```"):
                text = text[text.find("\n")+1:]
            if text.strip().endswith("```"):
                text = text[:text.rfind("\n")]
            translated[f"text_{code}"] = text

    return translated


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate recipe JSON files into multiple languages.")
    parser.add_argument(
        "-l",
        "--languages",
        nargs="+",
        help="ISO language codes to translate to (e.g. en es de).",
    )

    args = parser.parse_args()

    model = os.environ.get("MISTRAL_MODEL", TRANSLATOR_LLM)
    source_dir = os.environ.get("RECIPES_DIR", "json_recipes")
    output_dir = os.environ.get("OUTPUT_DIR", "translated_recipes")
    env_languages = os.environ.get("TRANSLATION_LANGUAGES")

    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        print(f"Error: set the {API_KEY_ENV} environment variable with your Mistral API key.")
        sys.exit(1)

    client = Mistral(api_key=api_key)

    languages: List[str] = []
    if args.languages:
        languages = parse_languages(args.languages)
    elif env_languages:
        languages = parse_languages([env_languages])

    if not languages:
        languages = DEFAULT_TARGET_LANGUAGES.copy()

    if not os.path.isdir(source_dir):
        print(f"Source directory not found: {source_dir}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    print("Target languages:", ", ".join(languages))

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

            translated = translate_recipe(client, model, recipe_data, languages)

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
