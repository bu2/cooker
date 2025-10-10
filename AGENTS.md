# Repository Guidelines

## Project Structure & Module Organization
- `backend/`: FastAPI service (`backend/main.py`), configured by `RECIPES_*` env vars; serves `/health`, `/languages`, `/recipes`, `/search`, and optionally `/images`.
- `frontend/`: Vite + React + TypeScript app (`frontend/src/**`, assets in `frontend/src/assets/`). Build output goes to `frontend/dist/`.
- `data/`: Local datasets (e.g., `recipes.db/` for LanceDB, optional `images/`).
- `scripts/`: Python utilities to generate, embed, and index recipes (see `README.md`).
- `docker/` + `Dockerfile`: Nginx config and entrypoint for the combined image.

## Build, Test, and Development Commands
- Backend (dev): `pip install -r backend/requirements.txt && uvicorn backend.main:app --reload`
- Frontend (dev): `cd frontend && npm ci && npm run dev`
- Full stack (Docker): `docker build -t cooker:latest . && docker run -p 8080:80 -v "$PWD/data:/app/data" cooker:latest`
- Index data: `python scripts/index_recipes.py --parquet data/recipes.parquet --db recipes.db --table recipes`
- Health check: `curl http://localhost:8000/health` (dev) or `http://localhost:8080/health` (Docker)

## Coding Style & Naming Conventions
- Python: 4‑space indent, type hints, `snake_case` for modules/functions. Keep routes and `RecipeStore` logic cohesive in `backend/main.py`.
- TypeScript/React: functional components; `PascalCase` for components (e.g., `App.tsx`), `camelCase` for variables; assets under `frontend/src/assets/`.
- Env vars in `UPPER_SNAKE_CASE`; keep paths relative to repo root in docs/scripts.

## Testing Guidelines
- No formal test suite yet. Smoke‑test API endpoints: `/health`, `/languages`, `/recipes`, `/search`.
- If adding tests, prefer `pytest`; place files under `backend/tests/` with `test_*.py`. Target API contracts and data localization logic.

## Commit & Pull Request Guidelines
- Commits: short, imperative verbs (e.g., “Add”, “Fix”, “Refactor”) and optional scope (`frontend/`, `backend/`, `scripts/`).
- PRs: include purpose, before/after notes, run instructions, and curl output or screenshots for UI/API changes. Link issues and flag breaking changes.

## Security & Configuration Tips
- Don’t commit secrets. Copy `.env.scaleway.example` to `.env.scaleway` locally; configure env at deploy time.
- Set `PUBLIC_IMAGES_BASE_URL` when serving images from CDN; bind‑mount `data/images` during local runs.

## Agent‑Specific Instructions
- Prefer minimal diffs; avoid renames/restructures without justification. Keep Docker/nginx aligned with backend routes.
- Validate changes via health check and a sample search: `curl 'http://localhost:8000/search?q=chocolate'`.

## Scaleway Deploy (for agents)
- Script: `scripts/deploy_scaleway.sh` builds the Docker image, extracts the frontend, syncs to Scaleway Object Storage, then updates containers on the instance (app + optional Caddy TLS).
- Env file: copy `.env.scaleway.example` to `.env.scaleway` locally and populate. Do NOT commit `.env.scaleway`.
- Quick redeploy: run `bash scripts/deploy_scaleway.sh` from repo root.
- Verification:
  - API: `curl -s https://api.<domain>/health` and `/languages`.
  - Static: `curl -sSI https://<bucket>.s3.<region>.scw.cloud/index.html`.
- Remote logs (via SSH):
  - `ssh ubuntu@<SCW_SSH_HOST>` then `docker ps`, `docker logs -f cooker`, `docker logs -f caddy`.
- Requirements: Local Docker with Buildx; dataset present at `data/recipes.db/` or the backend may fail.
