# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Torbgard — one container: FastAPI serves the API *and* the built PWA.
#
#   docker build -t torbgard .
#   docker run -p 8000:8000 torbgard
#
# If ./data contains shops.csv + products.csv + offers.csv they are baked in;
# otherwise a schema-faithful synthetic dataset is generated at build time.
# Either way the serving DB is precomputed — cold start never runs the ETL.
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
COPY data/ ./data/

# Build the serving DB: real CSVs when present, synthetic otherwise.
RUN cd backend \
    && if [ -f /app/data/shops.csv ] && [ -f /app/data/products.csv ] && [ -f /app/data/offers.csv ]; then \
         echo "building from real dataset"; \
         python -m app.etl.build --data /app/data --db /app/backend/var/app.db; \
       else \
         echo "building synthetic dataset"; \
         python -m app.etl.synthetic --out /app/data --shops 1200 --products 30000 --offers 60000; \
         python -m app.etl.build --data /app/data --db /app/backend/var/app.db; \
       fi \
    && python -m app.etl.validate --db /app/backend/var/app.db \
    && rm -f /app/data/*.csv

ENV DB_PATH=/app/backend/var/app.db \
    DATA_DIR=/app/data \
    SNAPSHOT_DATE=2026-10-13 \
    LLM_PROVIDER=none \
    DEMO_MODE=true \
    DEMO_TIME_SCALE=20 \
    CONTACT_TIMEOUT_SECONDS=45

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/api/health" || exit 1

WORKDIR /app/backend
# Copy the baked DB into a mounted volume on first run, then serve.
CMD ["sh", "-c", "if [ -n \"$DB_PATH\" ] && [ ! -f \"$DB_PATH\" ] && [ -f /app/backend/var/app.db ]; then cp /app/backend/var/app.db \"$DB_PATH\"; fi; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
