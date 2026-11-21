#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
fuser -k 8001/tcp 2>/dev/null || true
trap 'kill 0' EXIT

echo "⚡ Starting Nabd Backend (http://127.0.0.1:8001)..."
uvicorn backend.api.server:app --reload --port 8001 &

echo "⚡ Starting Nabd 3D Studio (http://localhost:5173)..."
(cd frontend && npm run dev) &

wait
