import argparse
import os
import json
import time
import hashlib
import sys
import tempfile
from typing import Dict, List, Optional, TypedDict

try:
    from mistralai import Mistral
    from mistralai.models.file import File
except Exception:
    print("Error: The 'mistralai' Python package is required to run this script.")
    print("Install with: pip install mistralai")
    raise

try:
    import pandas as pd
except Exception as e:
    print("Error: The 'pandas' Python package is required to run this script.")
    print("Install with: pip install pandas")
    raise

CHEF_LLM = 'mistral-small-latest'
API_KEY_ENV = "MISTRAL_API_KEY"


client = Mistral(api_key=os.environ.get("MISTRAL_API_KEY", ""))


class RecipeEntry(TypedDict):
    index: int
    title: str
    description: str
    out_path: str
    file_hash: str


def _get_env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def hash_title(title: str) -> str:
    return hashlib.sha256(title.encode('utf-8')).hexdigest()


def build_prompt(title: str, description: str) -> str:
    return (
        "Tu es un chef cuisinier français.\n\n"

        f"Rédige une recette simple mais savoureuse de \"{title}\" ({description})\n\n"

        "Consignes à respecter:\n"
        "- Commence par une phrase de description.\n"
        "- Structure ta recette avec des sections claires : temps (préparation, cuisson, repos, etc.), nombre de portions, ingrédients et étapes.\n"
        "- Précise les quantités pour chaque ingrédient.\n"
        "- Donne des instructions concises et précises.\n"
        "- Écris en français.\n"
        "- Utilise le format Markdown.\n"
        "- Évite les tables.\n"
        "- Si tu ne connais pas la recette, dis-le moi directement. N'invente pas une recette imaginaire.\n"
    )

def extract_text_from_response_body(body: Dict) -> str:
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
            content = message.get("content")
            if isinstance(content, str):
                content = content.strip()
                if content:
                    return content
            elif isinstance(content, list):
                text_parts: List[str] = []
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text") or item.get("content")
                        if isinstance(text, str):
                            text_parts.append(text)
                    elif isinstance(item, str):
                        text_parts.append(item)
                combined = "".join(text_parts).strip()
                if combined:
                    return combined

    return ""


def generate_recipe_text(model: str, title: str, description: str) -> str:
    prompt = build_prompt(title, description)
    response = client.chat.complete(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

    if not getattr(response, "choices", None):
        return ""

    for choice in response.choices:
        message = getattr(choice, "message", None)
        if message and getattr(message, "content", None):
            return message.content.strip()

    return ""


def generate_recipes_single(entries: List[RecipeEntry], model: str, total: int, sleep_between: float = 0.1) -> None:
    for entry in entries:
        idx_display = entry["index"] + 1
        title = entry["title"]
        description = entry["description"]
        out_path = entry["out_path"]

        if os.path.exists(out_path):
            print(f"[{idx_display}/{total}] Skipping (exists): {title}")
            continue

        print(f"[{idx_display}/{total}] Generating: {title}")
        start = time.perf_counter()
        try:
            text = generate_recipe_text(model, title, description)
            if not text:
                print(f"   Warning: empty response for '{title}', retrying once…")
                time.sleep(0.5)
                text = generate_recipe_text(model, title, description)

            data = {"title": title, "description": description, "text": text}
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            elapsed = time.perf_counter() - start
            print(f"   Saved to {out_path} in {elapsed:.2f}s")
        except KeyboardInterrupt:
            print("Interrupted by user. Exiting…")
            sys.exit(1)
        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"   Error generating '{title}' after {elapsed:.2f}s: {e}")
            continue

        if sleep_between > 0:
            time.sleep(sleep_between)



def generate_recipes_batch(
    entries: List[RecipeEntry],
    model: str,
    total: int,
    poll_interval: float,
    timeout_minutes: float,
) -> List[RecipeEntry]:
    pending = [entry for entry in entries if not os.path.exists(entry["out_path"])]
    if not pending:
        print("Batch mode: nothing to generate.")
        return []

    pending_map: Dict[str, RecipeEntry] = {entry["file_hash"]: entry for entry in pending}
    request_lines: List[str] = []
    for entry in pending:
        body = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": build_prompt(entry["title"], entry["description"]),
                }
            ],
        }
        request_lines.append(
            json.dumps(
                {
                    "custom_id": entry["file_hash"],
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": body,
                },
                ensure_ascii=False,
            )
        )

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as tmp_file:
        tmp_file.write("\n".join(request_lines) + "\n")
        batch_path = tmp_file.name

    fallback_entries: List[RecipeEntry] = []
    fallback_ids: set[str] = set()

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
        print(f"Created batch job {job.id} for {len(pending)} recipes (status: {job.status}).")

        deadline: Optional[float] = None
        if timeout_minutes > 0:
            deadline = time.perf_counter() + timeout_minutes * 60

        poll_interval = poll_interval if poll_interval > 0 else 5.0

        while job.status in ("QUEUED", "RUNNING"):
            if deadline and time.perf_counter() >= deadline:
                print("   Batch wait timeout reached, leaving remaining recipes for fallback.")
                break
            time.sleep(poll_interval)
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
            return pending

        output_response = client.files.download(file_id=job.output_file)
        output_text = output_response.read().decode("utf-8", errors="ignore")

        processed_ids: set[str] = set()
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
            entry = pending_map.get(custom_id)
            if not entry:
                continue

            error_info = payload.get("error")
            if error_info is not None:
                message = error_info
                if isinstance(error_info, dict):
                    message = error_info.get("message") or error_info
                print(f"   Batch error for '{entry['title']}': {message}")
                if entry["file_hash"] not in fallback_ids:
                    fallback_entries.append(entry)
                    fallback_ids.add(entry["file_hash"])
                continue

            response_obj = payload.get("response")
            body = None
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
                        f"   Batch HTTP {status_code} for '{entry['title']}', falling back to realtime call."
                    )
                    if entry["file_hash"] not in fallback_ids:
                        fallback_entries.append(entry)
                        fallback_ids.add(entry["file_hash"])
                    continue
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                    except json.JSONDecodeError:
                        body = None

            if not isinstance(body, dict):
                print(f"   Missing batch response for '{entry['title']}', falling back.")
                if entry["file_hash"] not in fallback_ids:
                    fallback_entries.append(entry)
                    fallback_ids.add(entry["file_hash"])
                continue

            text = extract_text_from_response_body(body)
            if not text:
                print(f"   Empty batch response for '{entry['title']}', falling back.")
                if entry["file_hash"] not in fallback_ids:
                    fallback_entries.append(entry)
                    fallback_ids.add(entry["file_hash"])
                continue

            if text.startswith("```"):
                text = text[text.find("\n")+1:]
            if text.strip().endswith("```"):
                text = text[:text.rfind("\n")]

            data = {
                "title": entry["title"],
                "description": entry["description"],
                "text": text,
            }
            with open(entry["out_path"], "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[{entry['index'] + 1}/{total}] Saved from batch: {entry['title']}")

        for entry in pending:
            if entry["file_hash"] not in processed_ids and entry["file_hash"] not in fallback_ids:
                fallback_entries.append(entry)
                fallback_ids.add(entry["file_hash"])

        return fallback_entries

    except KeyboardInterrupt:
        print("Interrupted by user. Exiting…")
        sys.exit(1)
    except Exception as exc:
        print(f"Batch generation failed: {exc}")
        return pending
    finally:
        try:
            os.remove(batch_path)
        except OSError:
            pass

def main():
    parser = argparse.ArgumentParser(description="Generate recipe JSON files with Mistral AI.")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Use the Mistral batch API for pending recipes to reduce costs.",
    )
    parser.add_argument(
        "--batch-poll-interval",
        type=float,
        default=_get_env_float("MISTRAL_BATCH_POLL_INTERVAL", 5.0),
        help="Seconds between batch status checks.",
    )
    parser.add_argument(
        "--batch-timeout-minutes",
        type=float,
        default=_get_env_float("MISTRAL_BATCH_TIMEOUT_MINUTES", 30.0),
        help="Maximum minutes to wait for a batch job before falling back (0 to disable).",
    )
    args = parser.parse_args()

    model = os.environ.get("MISTRAL_MODEL", CHEF_LLM)
    output_dir = os.environ.get("OUTPUT_DIR", "data/json_recipes")
    os.makedirs(output_dir, exist_ok=True)

    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        print(f"Error: set the {API_KEY_ENV} environment variable with your Mistral API key.")
        sys.exit(1)

    recipes = pd.read_csv("recipes.csv")
    recipes["description"] = [d[:-1] if isinstance(d, str) and d.endswith('.') else d for d in recipes["description"]]

    total = len(recipes)
    entries: List[RecipeEntry] = []
    for i in range(total):
        title = recipes["title"].iloc[i]
        description = recipes["description"].iloc[i]
        file_hash = hash_title(title)
        out_path = os.path.join(output_dir, f"{file_hash}.json")
        entries.append(
            {
                "index": i,
                "title": title,
                "description": description,
                "out_path": out_path,
                "file_hash": file_hash,
            }
        )

    if args.batch:
        fallback_entries = generate_recipes_batch(
            entries=entries,
            model=model,
            total=total,
            poll_interval=args.batch_poll_interval,
            timeout_minutes=args.batch_timeout_minutes,
        )
        if fallback_entries:
            print(f"Falling back to realtime generation for {len(fallback_entries)} recipes…")
            generate_recipes_single(fallback_entries, model, total)
    else:
        generate_recipes_single(entries, model, total)

    print("Done.")


if __name__ == "__main__":
    main()
