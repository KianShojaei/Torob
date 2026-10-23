# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Torbgard — one container: FastAPI serves the API *and* the built PWA.
# Build:  docker build -t torbgard .
# Run:    docker run -p 8000:8000 -v torbgard_data:/data -e DB_PATH=/data/app.db torbgard
# ---------------------------------------------------------------------------

# ---------- stage 1: build the static PWA ----------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---------- stage 2: python runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Tehran

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/ ./backend/
COPY --from=web /web/out ./backend/static
COPY scripts/ ./scripts/
COPY data/README.md ./data/README.md

# Ship prebuilt serving artifacts: the synthetic demo DB is baked in, so cold start
# never re-runs the ETL. Mount a volume at /data and run `make data` to override.
ENV DB_PATH=/app/backend/var/app.db \
    DATA_DIR=/app/data \
    SNAPSHOT_DATE=2026-10-13 \
    LLM_PROVIDER=none \
    DEMO_MODE=true \
    DEMO_TIME_SCALE=20 \
    CONTACT_TIMEOUT_SECONDS=45

RUN cd backend \
    && python -m app.etl.synthetic --out /app/data --shops 1200 --products 30000 --offers 60000 \
    && python -m app.etl.build --data /app/data --db /app/backend/var/app.db \
    && rm -f /app/data/*.csv

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
