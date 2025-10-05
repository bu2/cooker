#!/usr/bin/env bash
set -Eeuo pipefail

# Deploy the Cooker app to a Scaleway Ubuntu instance and sync the
# frontend static site (Vite build) to a Scaleway Object Storage bucket.
#
# Requirements on your local machine:
# - docker (used to build the image and run aws-cli container)
# - ssh + scp (to configure the instance and copy artifacts)
# - network access to your Scaleway instance and object storage
#
# Usage:
#   1) Create an env file `.env.scaleway` at repo root (see template below)
#   2) Run: scripts/deploy_scaleway.sh
#
# `.env.scaleway` template:
#   SCW_SSH_HOST=1.2.3.4                 # required: instance public IP or hostname
#   SCW_SSH_USER=ubuntu                  # optional (default: ubuntu)
#   SCW_SSH_PORT=22                      # optional (default: 22)
#   SCW_SSH_KEY=~/.ssh/id_rsa            # optional private key path; if omitted, use default ssh config
#
#   SCW_S3_BUCKET=my-cooker-site         # required: object storage bucket name
#   SCW_S3_REGION=nl-ams                 # optional (default: nl-ams)
#   SCW_S3_ENDPOINT=https://s3.nl-ams.scw.cloud   # optional; derived from SCW_S3_REGION when omitted
#
#   PUBLIC_API_BASE_URL=https://api.example.com   # required: URL your frontend will call (your instance URL)
#
#   # AWS credentials with access to the bucket (S3-compatible; created in Scaleway console)
#   AWS_ACCESS_KEY_ID=AKIAXXXXX
#   AWS_SECRET_ACCESS_KEY=xxxxxxxx
#
#   # Optional toggles
#   SYNC_IMAGES=false                    # optionally upload local data/images to the instance (default: false)
#   DOCKER_IMAGE_TAG=cooker:latest       # tag for the application image (default)
#   REMOTE_APP_DIR=/opt/cooker           # where to place data on the instance (default)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$REPO_ROOT"

# Load environment if present
if [[ -f .env.scaleway ]]; then
  # shellcheck disable=SC1091
  source .env.scaleway
fi

# Defaults
SCW_SSH_USER=${SCW_SSH_USER:-ubuntu}
SCW_SSH_PORT=${SCW_SSH_PORT:-22}
SCW_S3_REGION=${SCW_S3_REGION:-nl-ams}
SCW_S3_ENDPOINT=${SCW_S3_ENDPOINT:-"https://s3.${SCW_S3_REGION}.scw.cloud"}
DOCKER_IMAGE_TAG=${DOCKER_IMAGE_TAG:-cooker:latest}
REMOTE_APP_DIR=${REMOTE_APP_DIR:-/opt/cooker}
SYNC_IMAGES=${SYNC_IMAGES:-false}

# Validation
require() { if [[ -z "${!1:-}" ]]; then echo "Missing required env: $1" >&2; exit 2; fi; }
require SCW_SSH_HOST
require SCW_S3_BUCKET
require PUBLIC_API_BASE_URL
require AWS_ACCESS_KEY_ID
require AWS_SECRET_ACCESS_KEY

# Normalise PUBLIC_API_BASE_URL (drop trailing slash)
PUBLIC_API_BASE_URL=${PUBLIC_API_BASE_URL%%/}

echo "==> Config"
echo "  SSH:   ${SCW_SSH_USER}@${SCW_SSH_HOST}:${SCW_SSH_PORT}"
echo "  S3:    bucket=${SCW_S3_BUCKET} region=${SCW_S3_REGION} endpoint=${SCW_S3_ENDPOINT}"
echo "  Image: ${DOCKER_IMAGE_TAG}"
echo "  API:   ${PUBLIC_API_BASE_URL}"
echo "  Remote:${REMOTE_APP_DIR} (images sync: ${SYNC_IMAGES})"

SSH_BASE=(ssh -p "$SCW_SSH_PORT")
SCP_BASE=(scp -P "$SCW_SSH_PORT")
if [[ -n "${SCW_SSH_KEY:-}" ]]; then
  SSH_BASE+=(-i "$SCW_SSH_KEY")
  SCP_BASE+=(-i "$SCW_SSH_KEY")
fi
SSH_BASE+=("${SCW_SSH_USER}@${SCW_SSH_HOST}")

tmpdir="${REPO_ROOT}/scripts/.deploy_tmp"
rm -rf "$tmpdir" && mkdir -p "$tmpdir"

echo "\n==> Building Docker image locally (for backend + to extract frontend dist)"
docker build \
  --build-arg "VITE_API_BASE_URL=${PUBLIC_API_BASE_URL}" \
  -t cooker-local-build \
  .
docker tag cooker-local-build "$DOCKER_IMAGE_TAG"

echo "\n==> Extracting built frontend from image"
rm -rf "$tmpdir/website" && mkdir -p "$tmpdir/website"
cid=$(docker create cooker-local-build)
trap 'docker rm -f "$cid" >/dev/null 2>&1 || true' EXIT
docker cp "$cid":/usr/share/nginx/html/. "$tmpdir/website/"
docker rm -f "$cid" >/dev/null 2>&1 || true
trap - EXIT

echo "\n==> Syncing frontend to Scaleway Object Storage (using aws-cli in Docker)"
AWS_DOCKER=(docker run --rm \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e AWS_DEFAULT_REGION="$SCW_S3_REGION" \
  -v "$tmpdir/website:/website:ro" \
  amazon/aws-cli)

# Sync all but index.html with long cache TTL
"${AWS_DOCKER[@]}" s3 sync /website "s3://${SCW_S3_BUCKET}" \
  --endpoint-url "$SCW_S3_ENDPOINT" \
  --delete \
  --acl public-read \
  --exclude "index.html" \
  --cache-control 'public, max-age=31536000, immutable'

# Upload index.html with no-cache
"${AWS_DOCKER[@]}" s3 cp /website/index.html "s3://${SCW_S3_BUCKET}/index.html" \
  --endpoint-url "$SCW_S3_ENDPOINT" \
  --acl public-read \
  --cache-control 'no-cache' \
  --content-type text/html

# Try to enable static website hosting (ignored if unsupported)
"${AWS_DOCKER[@]}" s3 website "s3://${SCW_S3_BUCKET}" \
  --index-document index.html --error-document index.html \
  --endpoint-url "$SCW_S3_ENDPOINT" || true

echo "\n==> Preparing artifacts for instance"
image_tar="$tmpdir/cooker-image.tar"
echo "   - Exporting image → $image_tar"
docker save -o "$image_tar" "$DOCKER_IMAGE_TAG"

echo "   - Staging dataset"
db_src="${REPO_ROOT}/recipes.db"
if [[ -d "$db_src" ]]; then
  tar -C "$REPO_ROOT" -czf "$tmpdir/recipes.db.tgz" recipes.db
else
  echo "WARNING: recipes.db directory not found; backend will fail unless present on server" >&2
fi

if [[ "$SYNC_IMAGES" == "true" ]]; then
  if [[ -d "${REPO_ROOT}/data/images" ]]; then
    tar -C "$REPO_ROOT" -czf "$tmpdir/images.tgz" data/images
  else
    echo "WARNING: data/images not found; skipping images upload" >&2
  fi
fi

echo "\n==> Copying artifacts to instance"
"${SCP_BASE[@]}" "$image_tar" "${SCW_SSH_USER}@${SCW_SSH_HOST}:/tmp/cooker-image.tar"
if [[ -f "$tmpdir/recipes.db.tgz" ]]; then
  "${SCP_BASE[@]}" "$tmpdir/recipes.db.tgz" "${SCW_SSH_USER}@${SCW_SSH_HOST}:/tmp/recipes.db.tgz"
fi
if [[ -f "$tmpdir/images.tgz" ]]; then
  "${SCP_BASE[@]}" "$tmpdir/images.tgz" "${SCW_SSH_USER}@${SCW_SSH_HOST}:/tmp/images.tgz"
fi

echo "\n==> Configuring instance and running container"
"${SSH_BASE[@]}" bash -s <<REMOTE
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "Installing Docker if missing..."
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y docker.io
fi
sudo systemctl enable --now docker

echo "Preparing app directories..."
sudo mkdir -p ${REMOTE_APP_DIR}
sudo mkdir -p ${REMOTE_APP_DIR}/images

echo "Loading Docker image..."
sudo docker load -i /tmp/cooker-image.tar
rm -f /tmp/cooker-image.tar || true

if [[ -f /tmp/recipes.db.tgz ]]; then
  echo "Unpacking recipes.db..."
  sudo tar -C ${REMOTE_APP_DIR} -xzf /tmp/recipes.db.tgz
  rm -f /tmp/recipes.db.tgz
fi

if [[ -f /tmp/images.tgz ]]; then
  echo "Unpacking images... (this can take a while)"
  sudo tar -C / -xzf /tmp/images.tgz
  # After extract, images land at /data/images → move to /opt/cooker/images
  if [[ -d /data/images ]]; then
    sudo cp -a /data/images/. ${REMOTE_APP_DIR}/images/
    sudo rm -rf /data/images
    sudo rmdir /data || true
  fi
  rm -f /tmp/images.tgz
fi

echo "(Re)starting container..."
sudo docker rm -f cooker >/dev/null 2>&1 || true
sudo docker run -d --name cooker \
  --restart unless-stopped \
  -p 80:80 \
  -e PORT=8000 \
  -e RECIPES_LANCEDB=/app/recipes.db \
  -e RECIPES_TABLE=recipes \
  -e RECIPES_IMAGES=/app/data/images \
  -v ${REMOTE_APP_DIR}/recipes.db:/app/recipes.db \
  -v ${REMOTE_APP_DIR}/images:/app/data/images \
  ${DOCKER_IMAGE_TAG}

echo "Container status:"
sudo docker ps --filter "name=cooker" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
REMOTE

echo "\n==> Done"
echo "Frontend URL (object storage):"
echo "  - Try static website endpoint if enabled in Scaleway console."
echo "  - Direct object endpoint: https://${SCW_S3_BUCKET}.s3.${SCW_S3_REGION}.scw.cloud (use /index.html)"
echo "API base URL: ${PUBLIC_API_BASE_URL}"

echo "\nNotes:"
echo "- Ensure your bucket is public or has a CDN/website enabled."
echo "- Open TCP/80 in the instance security group."
echo "- Re-run this script after changes; it will update the site and container."
