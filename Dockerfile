# Stage 1: Build React + MapLibre 3D Studio
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Unified FastAPI + Live Relate Graph Engine
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NABD_EPHEMERAL_DATA=1 \
    PORT=7860

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bin/relate /usr/local/bin/relate
RUN chmod +x /usr/local/bin/relate

COPY backend/ ./backend/
COPY data/*.rl data/*.json data/*.sha256 ./data/
COPY scripts/ ./scripts/
COPY README.md LICENSE NOTICE ./
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 7860

CMD ["sh", "-c", "uvicorn backend.api.server:app --host 0.0.0.0 --port ${PORT:-7860}"]
