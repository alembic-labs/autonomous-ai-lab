#!/usr/bin/env bash
# Copy deploy artifacts + sources to VPS, then compose up.
# Usage (from repo root):
#   ./deploy/sync-to-server.sh root@178.18.240.104 /opt/alembic
set -euo pipefail

SERVER="${1:?usage: sync-to-server.sh user@host /remote/repo/path}"
DEST="${2:?usage: sync-to-server.sh user@host /remote/repo/path}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ rsync to ${SERVER}:${DEST}"
rsync -avz \
  "${ROOT}/deploy/" \
  "${SERVER}:${DEST}/deploy/" \
  --exclude '__pycache__'

rsync -avz \
  "${ROOT}/alembic-labs-backend/" \
  "${SERVER}:${DEST}/alembic-labs-backend/" \
  --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc'

rsync -avz \
  "${ROOT}/alembic-labs-frontend/" \
  "${SERVER}:${DEST}/alembic-labs-frontend/" \
  --exclude 'node_modules' --exclude '.next'

rsync -avz \
  "${ROOT}/alembic-lab-3d/" \
  "${SERVER}:${DEST}/alembic-lab-3d/" \
  --exclude 'node_modules' --exclude 'dist'

echo "→ remote compose up (${SERVER})"
ssh "${SERVER}" "cd '${DEST}/deploy' && docker compose up -d --build"
