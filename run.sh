#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Portable port-8001 cleanup (works on both macOS and Linux)
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -ti tcp:8001 2>/dev/null || true)"
  if [ -n "$PIDS" ]; then
    kill -9 $PIDS 2>/dev/null || true
  fi
elif command -v fuser >/dev/null 2>&1; then
  fuser -k 8001/tcp 2>/dev/null || true
fi

cleanup() {
  local pids
  pids="$(jobs -p 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "⚡ Starting Nabd Backend (http://127.0.0.1:8001)..."
uvicorn backend.api.server:app --reload --port 8001 &

echo "⚡ Starting Nabd 3D Studio (http://localhost:5173)..."
(cd frontend && npm run dev) &

wait
