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
    - `PUBLIC_IMAGES_BASE_URL` (optional) absolute base URL to serve images from Object Storage/CDN, e.g. `https://www.example.com`
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

**Run Locally with Docker**
- Build: `docker build -t cooker:latest .`
- Run (mount LanceDB and images, and align env path):
  - `docker rm -f cooker >/dev/null 2>&1 || true`
  - `docker run -d --name cooker \
      -p 8080:80 \
      -e RECIPES_LANCEDB=/app/data/recipes.db \
      -e RECIPES_TABLE=recipes \
      -e RECIPES_IMAGES=/app/data/images \
      -v "$PWD/data/recipes.db:/app/data/recipes.db" \
      -v "$PWD/data/images:/app/data/images" \
      cooker:latest`
- Test: open `http://localhost:8080/` and `http://localhost:8080/health`.

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
    - Required: `SCW_SSH_HOST`, `SCW_S3_BUCKET`, `PUBLIC_API_BASE_URL`, S3 credentials (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`).
    - Recommended: `PUBLIC_IMAGES_BASE_URL` set to your website origin (CDN), e.g. `https://www.latambouille.fr`.
    - Optional: `SYNC_IMAGES=true` to upload `data/images` to Object Storage under `s3://$SCW_S3_BUCKET/images`.
  - Run `bash scripts/deploy_scaleway.sh`.
- What it does:
  - Builds the Docker image locally (backend + Nginx) and extracts the Vite `dist`.
  - Uploads the frontend static site to your Scaleway Object Storage bucket with proper cache headers (immutable assets long‑cache; `index.html` no‑cache).
  - If `SYNC_IMAGES=true`, uploads `data/images` to `s3://$SCW_S3_BUCKET/images` and the backend serves absolute image URLs using `PUBLIC_IMAGES_BASE_URL`.
  - Loads the Docker image onto the instance and runs it. The LanceDB database (`data/recipes.db`) is packaged and unpacked to `${REMOTE_APP_DIR}/recipes.db` and bind‑mounted into the container.
  - If `PUBLIC_API_BASE_URL` is `https://…`, the script also runs Caddy as a TLS reverse proxy (auto‑cert via Let’s Encrypt) in front of the container.
- After deploy:
  - Frontend (Object Storage/CDN): serve your site from a CDN custom domain (recommended) or the direct bucket endpoint `https://<bucket>.s3.<region>.scw.cloud/index.html`.
  - API base URL: `PUBLIC_API_BASE_URL` from `.env.scaleway` (e.g., `https://api.latambouille.fr`).
  - Images: public URLs under `${PUBLIC_IMAGES_BASE_URL}/images/<id>.jpg` (or `.png`).

**Scaleway CDN + DNS (recommended)**
- In Scaleway Console:
  - Create a CDN service with origin = your bucket (HTTPS origin).
  - Set SPA fallback: index and error document to `index.html`.
  - Add custom domains: `latambouille.fr` and `www.latambouille.fr`, enable TLS.
- At your DNS provider (example: Gandi):
  - `@` (apex): ALIAS to the CDN hostname (or use Gandi Web Forwarding A 217.70.184.55 to 301 redirect to `https://www.latambouille.fr` if ALIAS is not available).
  - `www`: CNAME to the CDN hostname.
  - `api`: A record to your instance IP (e.g., `51.15.119.6`).
- Set `PUBLIC_IMAGES_BASE_URL=https://www.latambouille.fr` in `.env.scaleway` and redeploy.

**Verification**
- API: `curl -s https://api.<your-domain>/health` → `{"status":"ok"}`
- Languages: `curl -s https://api.<your-domain>/languages`
- Site: open `https://www.<your-domain>/` (ensure assets load and API calls succeed in devtools)
