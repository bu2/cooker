# Multi-stage build for recipe gallery (frontend + backend)

# --- Frontend build stage (Node) ---
FROM node:20 AS frontend-builder
WORKDIR /app/frontend

# Install deps first (better cache)
COPY frontend/package*.json ./
RUN npm ci

# Build static assets
# Allow overriding API base at build time for static hosting
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
COPY frontend/ ./
RUN npm run build


# --- Runtime stage (Ubuntu) ---
FROM ubuntu:22.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive

# Base packages: Python, pip, nginx, tini for proper signal handling
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    python3 python3-pip ca-certificates nginx tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend code
COPY backend /app/backend

# Copy data (LanceDB + optional data dir)
# If these do not exist at build time, remove or override at runtime.
COPY recipes.db /app/recipes.db
COPY data /app/data

# Copy built frontend to nginx web root
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

# Nginx config and entrypoint
COPY docker/nginx.conf /etc/nginx/conf.d/recipe.conf
COPY docker/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
 && rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default || true

# Defaults (override at `docker run -e VAR=value` time if needed)
ENV PORT=8000 \
    RECIPES_LANCEDB=/app/recipes.db \
    RECIPES_TABLE=recipes \
    RECIPES_IMAGES=/app/data/images

EXPOSE 80

# Lightweight healthcheck through Nginx → FastAPI
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python3 -c "import sys,urllib.request; r=urllib.request.urlopen('http://127.0.0.1/health', timeout=3); sys.exit(0 if getattr(r,'status',200)==200 else 1)"

ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["/entrypoint.sh"]
