#!/usr/bin/env bash
set -Eeuo pipefail

export PYTHONUNBUFFERED=1
echo "Starting Recipe Gallery: backend (uvicorn) + frontend (nginx)"

# Ensure nginx runtime dirs exist
mkdir -p /run/nginx

term_handler() {
  echo "Shutting down processes..."
  if [[ -n "${UVICORN_PID:-}" ]] && kill -0 "$UVICORN_PID" 2>/dev/null; then
    kill -TERM "$UVICORN_PID" 2>/dev/null || true
    wait "$UVICORN_PID" 2>/dev/null || true
  fi
  if [[ -n "${NGINX_PID:-}" ]] && kill -0 "$NGINX_PID" 2>/dev/null; then
    kill -TERM "$NGINX_PID" 2>/dev/null || true
    wait "$NGINX_PID" 2>/dev/null || true
  fi
}
trap term_handler SIGTERM SIGINT

# Start FastAPI backend
python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${UVICORN_WORKERS:-1}" \
  --proxy-headers \
  --forwarded-allow-ips "*" \
  --log-level "${LOG_LEVEL:-info}" &
UVICORN_PID=$!
echo "uvicorn started with PID ${UVICORN_PID}"

# Start nginx (foreground)
nginx -g "daemon off;" &
NGINX_PID=$!
echo "nginx started with PID ${NGINX_PID}"

# Wait until either exits, then clean up
wait -n "$UVICORN_PID" "$NGINX_PID"
EXIT_CODE=$?
term_handler || true
exit "$EXIT_CODE"
