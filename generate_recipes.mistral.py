import os
import json
import time
import hashlib
import sys

try:
    from mistralai import Mistral
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
        "- Si tu ne connais pas la recette, dis-le moi directement. N'invente pas une recette imaginaire.\n"
    )

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


def main():
    model = os.environ.get("MISTRAL_MODEL", CHEF_LLM)
    output_dir = os.environ.get("OUTPUT_DIR", "json_recipes")
    os.makedirs(output_dir, exist_ok=True)

    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        print(f"Error: set the {API_KEY_ENV} environment variable with your Mistral API key.")
        sys.exit(1)

    recipes = pd.read_csv('recipes.csv')
    recipes['description'] = [d[:-1] if d.endswith('.') else d for d in recipes['description']]

    total = len(recipes)
    for i in range(total):
        title = recipes['title'].iloc[i]
        description = recipes['description'].iloc[i]

        file_hash = hash_title(title)
        out_path = os.path.join(output_dir, f"{file_hash}.json")

        if os.path.exists(out_path):
            print(f"[{i+1}/{total}] Skipping (exists): {title}")
            continue

        print(f"[{i+1}/{total}] Generating: {title}")
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

        # Gentle pacing to avoid hitting rate limits
        time.sleep(0.1)

    print("Done.")


if __name__ == "__main__":
    main()
