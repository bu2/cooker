import os
import json
import time
import hashlib
import sys

try:
    import ollama
except Exception as e:
    print("Error: The 'ollama' Python package is required to run this script.")
    print("Install with: pip install ollama")
    raise


CHEF_LLM = 'mistral-small'


def hash_title(title: str) -> str:
    return hashlib.sha256(title.encode('utf-8')).hexdigest()


def build_prompt(title: str) -> str:
    return (
        "You are a skilled French chef. Write a complete, high-quality recipe for the dish titled '"
        + title
        + "'.\n"
        "Requirements:\n"
        "- Start with a one-sentence description.\n"
        "- Provide clear sections: Ingredients and Steps.\n"
        "- Give realistic quantities and measurements.\n"
        "- Include prep time, cook time, and servings.\n"
        "- Use concise, precise instructions.\n"
        "Output plain text only (no markdown)."
    )


def generate_recipe_text(model: str, title: str) -> str:
    prompt = build_prompt(title)
    try:
        # Prefer chat for better instruction-following
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.get("message", {}).get("content", "").strip()
    except Exception:
        # Fallback to generate API if chat fails
        resp = ollama.generate(model=model, prompt=prompt)
        return resp.get("response", "").strip()


def main():
    model = os.environ.get("OLLAMA_MODEL", CHEF_LLM)
    output_dir = os.environ.get("OUTPUT_DIR", "generated_recipes")
    os.makedirs(output_dir, exist_ok=True)

    with open('recipes.txt', encoding='utf-8') as f:
        recipes = [l.strip() for l in f if l.strip()]
    print(f"{len(recipes)} recipes to generate using model '{model}'…")

    total = len(recipes)
    for idx, title in enumerate(recipes, start=1):
        file_hash = hash_title(title)
        out_path = os.path.join(output_dir, f"{file_hash}.json")

        if os.path.exists(out_path):
            print(f"[{idx}/{total}] Skipping (exists): {title}")
            continue

        print(f"[{idx}/{total}] Generating: {title}")
        try:
            text = generate_recipe_text(model, title)
            if not text:
                print(f"   Warning: empty response for '{title}', retrying once…")
                time.sleep(0.5)
                text = generate_recipe_text(model, title)

            data = {"title": title, "text": text}
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except KeyboardInterrupt:
            print("Interrupted by user. Exiting…")
            sys.exit(1)
        except Exception as e:
            print(f"   Error generating '{title}': {e}")
            continue

        # Gentle pacing so we don't hammer the local model
        time.sleep(0.1)

    print("Done.")


if __name__ == "__main__":
    main()
