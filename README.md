**Quickstart**
- Step 1: Generate recipe texts with `generate_recipes.py`.
- Step 2: Create embeddings with `embed_recipes.py`.
- Step 3: Index into LanceDB with `index_recipes.py`.

**Prerequisites**
- Python 3 and `pip` installed.
- Install deps: `pip install -U ollama pandas sentence-transformers lancedb pyarrow`
- Ensure Ollama is installed and running if using local LLM generation.

**Step 1 — Generate**
- Purpose: Create JSON files in `json_recipes/` from titles in `recipes.txt` using an Ollama chat model.
- Command: `python generate_recipes.py`
- Environment options:
  - `OLLAMA_MODEL` to choose the Ollama model (default `mistral-small`). Example: ``export OLLAMA_MODEL=mistral``
  - `OUTPUT_DIR` to change output directory (default `json_recipes`).
- Output: One JSON per recipe title: `json_recipes/<hash>.json` with keys `title`, `text`.

**Step 2 — Embed**
- Purpose: Load JSON recipes and generate vector embeddings.
- Command: `python embed_recipes.py`
- Useful options:
  - `--input-dir json_recipes` to read a different folder.
  - `--model Snowflake/snowflake-arctic-embed-l-v2.0` to pick the SentenceTransformers model.
  - `--batch-size 32` and `--no-normalize` to tune embedding.
  - `--output embedded_recipes.pkl` to also save a pickle of the DataFrame.
- Output: Writes a Parquet dataset `recipes.parquet` containing `id`, `title`, `text`, `path`, `embedding`.
- Note: The first model load may download weights (requires network).

**Step 3 — Index**
- Purpose: Build a LanceDB database with vector and full‑text indexes.
- Command: `python index_recipes.py --parquet recipes.parquet --db ./recipes.db --table recipes --overwrite`
- Options:
  - `--metric` for vector distance (`cosine`|`l2`|`dot`). Default is `dot`.
  - Omit `--overwrite` to keep an existing table.
- Output: A LanceDB database directory at `recipes.db` with a `recipes` table and indexes.

Note: Use `dot` when your embeddings are unit‑normalized (Step 2 normalizes by default unless you pass `--no-normalize`). If not normalized, prefer `cosine` or `l2`.

**Recipe Gallery Web App**
- Backend (FastAPI):
  - Install deps: `pip install -r gallery_backend/requirements.txt`
  - Optional env vars:
    - `RECIPES_PARQUET` (default `recipes.parquet`)
    - `RECIPES_LANCEDB` (default `recipes.db`)
    - `RECIPES_TABLE` (default `recipes`)
    - `RECIPES_IMAGES` (default `recipe_images`) for generated pictures
  - Run locally: `uvicorn gallery_backend.main:app --reload`
  - Static images served at `/images/<recipe-id>.png` if files exist.
- Frontend (Vite + React):
  - `cd gallery_frontend`
  - `npm install`
  - Start dev server: `npm run dev` (default http://localhost:5173)
  - Configure backend URL via `.env` (e.g., `VITE_API_BASE_URL=http://localhost:8000`).
- Features: list recipes, search via LanceDB full-text index, view full recipe & image in modal.
- Build for production: `npm run build` → static assets in `gallery_frontend/dist/`.

**Files**
- `recipes.txt`: One recipe title per line.
- `json_recipes/`: Generated JSON recipes from Step 1.
- `recipes.parquet`: Embedded dataset from Step 2.
- `recipes.db/`: LanceDB database created in Step 3.

**Troubleshooting**
- Missing packages: reinstall with `pip install -U ollama pandas sentence-transformers lancedb pyarrow`.
- Ollama model: set `OLLAMA_MODEL` to a model you have locally, e.g. ``export OLLAMA_MODEL=mistral``.
- First embedding run may be slow due to model download.
