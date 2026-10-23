# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Torbgard — one container: FastAPI serves the API *and* the built PWA.
#
#   docker build -t torbgard .
#   docker run -p 8000:8000 torbgard
#
# The serving database is built at image build time, so cold start is ~2s.
# If ./data contains the challenge CSVs they are used; otherwise a synthetic
# dataset with the same schema is generated (the UI labels it as demo data).
# ---------------------------------------------------------------------------

# ---------- stage 1: PWA ----------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---------- stage 2: runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Tehran

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/ ./backend/
COPY --from=web /web/out ./backend/static
COPY data/ ./data/
COPY scripts/ ./scripts/

# Build the serving DB at image time (fast cold start, no ETL on boot).
RUN cd backend \
 && if [ ! -f ../data/shops.csv ] || [ ! -f ../data/offers.csv ]; then \
        echo "no CSVs found: generating the synthetic dataset"; \
        python -m app.etl.synthetic --out ../data --shops 1200 --products 30000 --offers 60000; \
    else \
        echo "building from the provided dataset"; \
    fi \
 && python -m app.etl.build --data ../data --db var/app.db \
 && python -m app.etl.validate --db var/app.db

RUN useradd -m -u 10001 app && chown -R app:app /app/backend/var /app/data
USER app

ENV DB_PATH=/app/backend/var/app.db \
    DATA_DIR=/app/data \
    LLM_PROVIDER=none \
    DEMO_MODE=true \
    SNAPSHOT_DATE=2026-10-13 \
    PORT=8000

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

WORKDIR /app/backend
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
