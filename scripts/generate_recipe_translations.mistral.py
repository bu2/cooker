import argparse
import json
import os
import sys
import time
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from mistralai import Mistral
    from mistralai.models.file import File
except Exception:
    print("Error: The 'mistralai' Python package is required to run this script.")
    print("Install with: pip install mistralai")
    raise


TRANSLATOR_LLM = "mistral-small-latest"
API_KEY_ENV = "MISTRAL_API_KEY"
BATCH_POLL_INTERVAL_ENV = "MISTRAL_BATCH_POLL_INTERVAL"
BATCH_TIMEOUT_MINUTES_ENV = "MISTRAL_BATCH_TIMEOUT_MINUTES"
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


def _get_env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


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


def extract_text_from_response_body(body: Dict[str, Any]) -> str:
    if not isinstance(body, dict):
        return ""

    choices = body.get("choices")
    if not isinstance(choices, list):
        return ""

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if isinstance(message, dict):
            translated = _coerce_message_content(message.get("content"))
            if translated:
                return translated

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


def build_translation_prompt(field_name: str, text: str, language_code: str) -> str:
    target_language = describe_language(language_code)
    return (
        "You are a professional bilingual translator.\n\n"
        f"Translate the following French `{field_name}` into {target_language}:\n--\n"
        + text + "\n--\n"
        "Preserve Markdown formatting when present.\n"
        "Return only the translated text without additional commentary.\n\n"
    )


def translate_field(client: Mistral, model: str, field_name: str, text: str, language_code: str) -> str:
    """Translate a single field while preserving Markdown structure."""

    prompt = build_translation_prompt(field_name, text, language_code)

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


def translate_recipes_batch(
    client: Mistral,
    model: str,
    entries: List[Dict[str, Any]],
    languages: List[str],
    total: int,
    poll_interval: float,
    timeout_minutes: float,
) -> None:
    if not entries:
        print("Batch mode: nothing to translate.")
        return

    prepared_entries: List[Dict[str, Any]] = []
    request_lines: List[str] = []
    tasks: Dict[str, Dict[str, Any]] = {}

    for entry in entries:
        position = entry["position"]
        filename = entry["filename"]
        print(f"[{position}/{total}] Translating: {filename}")

        entry["start_time"] = time.perf_counter()

        try:
            with open(entry["recipe_path"], "r", encoding="utf-8") as f:
                recipe_data = json.load(f)
        except Exception as exc:
            elapsed = time.perf_counter() - entry["start_time"]
            print(f"   Error preparing '{filename}' for batch after {elapsed:.2f}s: {exc}")
            continue

        title_fr = recipe_data.get("title", "").strip()
        description_fr = recipe_data.get("description", "").strip()
        text_fr = recipe_data.get("text", "").strip()

        if not title_fr and not description_fr and not text_fr:
            elapsed = time.perf_counter() - entry["start_time"]
            print(
                f"   Error translating '{filename}' after {elapsed:.2f}s: Recipe JSON is missing 'title', 'description', and 'text' fields."
            )
            continue

        entry["recipe_data"] = recipe_data
        entry["translations"] = {
            "title_fr": title_fr,
            "description_fr": description_fr,
            "text_fr": text_fr,
        }
        entry["pending_keys"] = set()
        entry["needs_fallback"] = False
        prepared_entries.append(entry)

        fields: List[Tuple[str, str, str]] = [
            ("title", "title", title_fr),
            ("description", "description", description_fr),
            ("text", "recipe text", text_fr),
        ]

        for language_code in languages:
            code = language_code.lower()
            if code == "fr":
                continue

            for key_prefix, prompt_name, source_text in fields:
                if not source_text:
                    continue

                result_key = f"{key_prefix}_{code}"
                entry["pending_keys"].add(result_key)
                custom_id = f"{position}|{result_key}"
                prompt = build_translation_prompt(prompt_name, source_text, code)
                body = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                }

                request_lines.append(
                    json.dumps(
                        {
                            "custom_id": custom_id,
                            "method": "POST",
                            "url": "/v1/chat/completions",
                            "body": body,
                        },
                        ensure_ascii=False,
                    )
                )

                tasks[custom_id] = {
                    "entry": entry,
                    "result_key": result_key,
                }

    if not prepared_entries:
        return

    if not request_lines:
        for entry in prepared_entries:
            elapsed = time.perf_counter() - entry["start_time"]
            try:
                with open(entry["output_path"], "w", encoding="utf-8") as f:
                    json.dump(entry["translations"], f, ensure_ascii=False, indent=2)
                print(f"   Saved to {entry['output_path']} in {elapsed:.2f}s")
            except Exception as exc:
                print(f"   Error writing '{entry['filename']}': {exc}")
        return

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as tmp_file:
        tmp_file.write("\n".join(request_lines) + "\n")
        batch_path = tmp_file.name

    processed_ids: set[str] = set()

    try:
        with open(batch_path, "rb") as fh:
            upload = client.files.upload(
                file=File(
                    fileName=os.path.basename(batch_path),
                    content=fh,
                    content_type="application/jsonl",
                ),
                purpose="batch",
            )

        job = client.batch.jobs.create(
            endpoint="/v1/chat/completions",
            model=model,
            input_files=[upload.id],
        )
        print(
            f"Created batch job {job.id} for {len(request_lines)} translation requests (status: {job.status})."
        )

        deadline: Optional[float] = None
        if timeout_minutes > 0:
            deadline = time.perf_counter() + timeout_minutes * 60

        interval = poll_interval if poll_interval > 0 else 5.0

        while job.status in ("QUEUED", "RUNNING"):
            if deadline and time.perf_counter() >= deadline:
                print("   Batch wait timeout reached, leaving remaining recipes for fallback.")
                break
            time.sleep(interval)
            job = client.batch.jobs.get(job_id=job.id)
            print(
                f"   Status: {job.status} ({job.completed_requests}/{job.total_requests} completed)"
            )

        if job.status != "SUCCESS" or not job.output_file:
            print(f"Batch job {job.id} finished with status {job.status}.")
            if job.error_file:
                try:
                    error_response = client.files.download(file_id=job.error_file)
                    error_text = error_response.read().decode("utf-8", errors="ignore")
                    for line in error_text.splitlines():
                        if line.strip():
                            print(f"   Error detail: {line}")
                except Exception as error_exc:
                    print(f"   Failed to download error file: {error_exc}")

            for entry in prepared_entries:
                entry["needs_fallback"] = True
        else:
            output_response = client.files.download(file_id=job.output_file)
            output_text = output_response.read().decode("utf-8", errors="ignore")

            for raw_line in output_text.splitlines():
                if not raw_line.strip():
                    continue

                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError:
                    print(f"   Warning: unable to parse batch line: {raw_line[:80]}…")
                    continue

                custom_id = payload.get("custom_id")
                if not isinstance(custom_id, str):
                    continue

                processed_ids.add(custom_id)
                task = tasks.get(custom_id)
                if not task:
                    continue

                entry = task["entry"]
                result_key = task["result_key"]

                error_info = payload.get("error")
                if error_info is not None:
                    message = error_info
                    if isinstance(error_info, dict):
                        message = error_info.get("message") or error_info
                    print(
                        f"   Batch error for '{entry['filename']}' ({result_key}): {message}"
                    )
                    entry["needs_fallback"] = True
                    continue

                response_obj = payload.get("response")
                body: Optional[Dict[str, Any]] = None
                status_code: Optional[int] = None

                if isinstance(response_obj, dict):
                    body = response_obj.get("body")
                    status_code = response_obj.get("status_code")
                    if isinstance(status_code, str):
                        try:
                            status_code = int(status_code)
                        except ValueError:
                            status_code = None
                    if isinstance(status_code, int) and status_code >= 400:
                        print(
                            f"   Batch HTTP {status_code} for '{entry['filename']}' ({result_key}), falling back to realtime call."
                        )
                        entry["needs_fallback"] = True
                        continue
                    if isinstance(body, str):
                        try:
                            body = json.loads(body)
                        except json.JSONDecodeError:
                            body = None

                if not isinstance(body, dict):
                    print(
                        f"   Missing batch response for '{entry['filename']}' ({result_key}), falling back."
                    )
                    entry["needs_fallback"] = True
                    continue

                translated = extract_text_from_response_body(body)
                if not translated:
                    print(
                        f"   Empty batch response for '{entry['filename']}' ({result_key}), falling back."
                    )
                    entry["needs_fallback"] = True
                    continue

                if result_key.startswith("text_"):
                    if translated.startswith("```"):
                        translated = translated[translated.find("\n") + 1 :]
                    if translated.strip().endswith("```"):
                        translated = translated[: translated.rfind("\n")]

                entry["translations"][result_key] = translated
                entry["pending_keys"].discard(result_key)

        for custom_id, task in tasks.items():
            if custom_id not in processed_ids:
                task["entry"]["needs_fallback"] = True

        for entry in prepared_entries:
            if entry["pending_keys"]:
                entry["needs_fallback"] = True

        for entry in prepared_entries:
            if entry["needs_fallback"]:
                continue

            elapsed = time.perf_counter() - entry["start_time"]
            try:
                with open(entry["output_path"], "w", encoding="utf-8") as f:
                    json.dump(entry["translations"], f, ensure_ascii=False, indent=2)
                print(f"   Saved to {entry['output_path']} in {elapsed:.2f}s")
            except Exception as exc:
                print(f"   Error writing '{entry['filename']}': {exc}")

    except KeyboardInterrupt:
        print("Interrupted by user. Exiting…")
        sys.exit(1)
    except Exception as exc:
        print(f"Batch translation failed: {exc}")
        for entry in prepared_entries:
            entry["needs_fallback"] = True
    finally:
        try:
            os.remove(batch_path)
        except OSError:
            pass

    fallback_entries = [entry for entry in prepared_entries if entry.get("needs_fallback")]
    if not fallback_entries:
        return

    print(f"Falling back to realtime translation for {len(fallback_entries)} recipes…")

    for entry in fallback_entries:
        position = entry["position"]
        filename = entry["filename"]
        print(f"[{position}/{total}] Translating: {filename} (fallback)")
        start = time.perf_counter()
        try:
            translated = translate_recipe(client, model, entry["recipe_data"], languages)
            with open(entry["output_path"], "w", encoding="utf-8") as f:
                json.dump(translated, f, ensure_ascii=False, indent=2)
            elapsed = time.perf_counter() - start
            print(f"   Saved to {entry['output_path']} in {elapsed:.2f}s")
        except KeyboardInterrupt:
            print("Interrupted by user. Exiting…")
            sys.exit(1)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            print(f"   Error translating '{filename}' after {elapsed:.2f}s: {exc}")
            continue

        time.sleep(0.1)

def main() -> None:
    parser = argparse.ArgumentParser(description="Translate recipe JSON files into multiple languages.")
    parser.add_argument(
        "-l",
        "--languages",
        nargs="+",
        help="ISO language codes to translate to (e.g. en es de).",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Use the Mistral batch API for pending translations to reduce API calls.",
    )
    parser.add_argument(
        "--batch-poll-interval",
        type=float,
        default=_get_env_float(BATCH_POLL_INTERVAL_ENV, 5.0),
        help="Seconds between batch status checks.",
    )
    parser.add_argument(
        "--batch-timeout-minutes",
        type=float,
        default=_get_env_float(BATCH_TIMEOUT_MINUTES_ENV, 30.0),
        help="Maximum minutes to wait for a batch job before falling back (0 to disable).",
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

    entries: List[Dict[str, Any]] = []
    for position, recipe_path in enumerate(recipe_files, start=1):
        filename = os.path.basename(recipe_path)
        output_path = os.path.join(output_dir, filename)

        if os.path.exists(output_path):
            print(f"[{position}/{total}] Skipping (exists): {filename}")
            continue

        entries.append(
            {
                "position": position,
                "filename": filename,
                "recipe_path": recipe_path,
                "output_path": output_path,
            }
        )

    if args.batch:
        translate_recipes_batch(
            client=client,
            model=model,
            entries=entries,
            languages=languages,
            total=total,
            poll_interval=args.batch_poll_interval,
            timeout_minutes=args.batch_timeout_minutes,
        )
        print("Done.")
        return

    for entry in entries:
        position = entry["position"]
        filename = entry["filename"]
        print(f"[{position}/{total}] Translating: {filename}")
        start = time.perf_counter()

        try:
            with open(entry["recipe_path"], "r", encoding="utf-8") as f:
                recipe_data = json.load(f)

            translated = translate_recipe(client, model, recipe_data, languages)

            with open(entry["output_path"], "w", encoding="utf-8") as f:
                json.dump(translated, f, ensure_ascii=False, indent=2)

            elapsed = time.perf_counter() - start
            print(f"   Saved to {entry['output_path']} in {elapsed:.2f}s")
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
