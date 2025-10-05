**Quickstart**
- Step 1: Generate recipe texts with `scripts/generate_recipes.*.py`.
- Step 2: Create embeddings with `scripts/embed_recipes.py`.
- Step 3: Index into LanceDB with `scripts/index_recipes.py`.

**Prerequisites**
- Python 3 and `pip` installed.
- Install deps: `pip install -U ollama pandas sentence-transformers lancedb pyarrow`
- Ensure Ollama is installed and running if using local LLM generation.

**Step 1 — Generate**
- Purpose: Create JSON files in `data/json_recipes/` from titles in `recipes.txt` using an Ollama chat model.
- Command: `python scripts/generate_recipes.ollama.py`
- Environment options:
  - `OLLAMA_MODEL` to choose the Ollama model (default `mistral-small`). Example: ``export OLLAMA_MODEL=mistral``
  - `OUTPUT_DIR` to change output directory (default `data/json_recipes`).
- Output: One JSON per recipe title: `data/json_recipes/<hash>.json` with keys `title`, `text`.

**Step 2 — Embed**
- Purpose: Load JSON recipes and generate vector embeddings.
- Command: `python scripts/embed_recipes.py`
- Useful options:
  - `--input-dir data/json_recipes` to read a different folder.
  - `--model Snowflake/snowflake-arctic-embed-l-v2.0` to pick the SentenceTransformers model.
  - `--batch-size 32` and `--no-normalize` to tune embedding.
- Output: Writes a Parquet dataset `recipes.parquet` containing `id`, `title`, `text`, `path`, `embedding`.
- Note: The first model load may download weights (requires network).

**Step 3 — Index**
- Purpose: Build a LanceDB database with vector and full‑text indexes.
- Command: `python scripts/index_recipes.py --parquet recipes.parquet --db ./recipes.db --table recipes --overwrite`
- Options:
  - `--metric` for vector distance (`cosine`|`l2`|`dot`). Default is `dot`.
  - Omit `--overwrite` to keep an existing table.
- Output: A LanceDB database directory at `recipes.db` with a `recipes` table and indexes.

Note: Use `dot` when your embeddings are unit‑normalized (Step 2 normalizes by default unless you pass `--no-normalize`). If not normalized, prefer `cosine` or `l2`.

**Recipe Gallery Web App**
- Backend (FastAPI):
  - Install deps: `pip install -r backend/requirements.txt`
  - Optional env vars:
    - `RECIPES_PARQUET` (default `recipes.parquet`)
    - `RECIPES_LANCEDB` (default `recipes.db`)
    - `RECIPES_TABLE` (default `recipes`)
    - `RECIPES_IMAGES` (default `data/images`) for generated pictures
  - Run locally: `uvicorn backend.main:app --reload`
  - Static images served at `/images/<recipe-id>.png` if files exist.
- Frontend (Vite + React):
  - `cd frontend`
  - `npm install`
  - Start dev server: `npm run dev` (default http://localhost:5173)
  - API base URL:
    - Dev: no config needed; Vite proxies `/api` and `/images` to `http://localhost:8000`.
    - Prod: set `VITE_API_BASE_URL` in `.env` or your hosting env (e.g., `VITE_API_BASE_URL=https://api.example.com`). See `frontend/.env.example`.
- Features: list recipes, search via LanceDB full-text index, view full recipe & image in modal.
- Build for production: `npm run build` → static assets in `frontend/dist/`.

**Files**
- `recipes.txt`: One recipe title per line.
- `data/json_recipes/`: Generated JSON recipes from Step 1.
- `data/recipes.parquet`: Embedded dataset from Step 2.
- `recipes.db/`: LanceDB database created in Step 3.

**Troubleshooting**
- Missing packages: reinstall with `pip install -U ollama pandas sentence-transformers lancedb pyarrow`.
- Ollama model: set `OLLAMA_MODEL` to a model you have locally, e.g. ``export OLLAMA_MODEL=mistral``.
- First embedding run may be slow due to model download.

**Deploy to Scaleway**
- Prerequisites:
  - A Scaleway Ubuntu Noble instance (Amsterdam 1) reachable via SSH.
  - A Scaleway Object Storage bucket in region `nl-ams` (or adjust).
  - Local Docker installed. You do not need Node or AWS CLI locally; the script uses Dockerized builders/tools.
- Steps:
  - Copy `.env.scaleway.example` to `.env.scaleway` and fill in required values:
    - `SCW_SSH_HOST`, `SCW_S3_BUCKET`, `PUBLIC_API_BASE_URL`, and S3 credentials (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`).
    - Optional: set `SYNC_IMAGES=true` to upload `data/images` to the instance.
  - Run `bash scripts/deploy_scaleway.sh`.
- What it does:
  - Builds the Docker image locally (backend + Nginx) and extracts the Vite `dist`.
  - Uploads the frontend static site to your Scaleway Object Storage bucket with proper cache headers.
  - Loads the Docker image onto the instance and runs it on port 80, mounting `recipes.db` and `data/images` from `/opt/cooker`.
- After deploy:
  - Frontend (Object Storage): `https://<bucket>.s3.<region>.scw.cloud/index.html` (or the website endpoint if enabled).
  - API base URL: `PUBLIC_API_BASE_URL` from your `.env.scaleway` (e.g., `https://your-instance`), serving `/languages`, `/recipes`, `/search`, and `/images`.
