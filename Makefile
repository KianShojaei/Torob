SHELL := /bin/bash
PY ?= .deps/python/bin/python
NPM ?= npm
PORT ?= 8000

.PHONY: help setup synthetic data build frontend dev api serve test test-fast docker smoke clean reset-db

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup:  ## create the venv, install backend + frontend dependencies
	python3 -m venv .deps/python
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r backend/requirements.txt
	cd frontend && $(NPM) install --no-audit --no-fund

synthetic:  ## generate a schema-faithful demo dataset into ./data
	$(PY) -m app.etl.synthetic --out ../data --shops 1200 --products 30000 --offers 60000
	@cd backend && true

data:  ## build the serving database from ./data (real CSVs if present)
	cd backend && ../$(PY) -m app.etl.build --data ../data --db var/app.db
	cd backend && ../$(PY) -m app.etl.validate --db var/app.db

frontend:  ## build the PWA and copy it into backend/static
	cd frontend && $(NPM) run build
	rm -rf backend/static && cp -r frontend/out backend/static

build: frontend  ## alias

api:  ## run the API only (auto-reload)
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --host 0.0.0.0 --port $(PORT)

dev:  ## run the Next.js dev server (proxies /api to :8000)
	cd frontend && $(NPM) run dev

serve:  ## production-like: one process serving API + built PWA
	cd backend && ../$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port $(PORT)

test:  ## full backend suite
	cd backend && ../$(PY) -m pytest -q

test-fast:  ## unit tests only (no database needed)
	cd backend && ../$(PY) -m pytest -q -m "not db"

docker:  ## build the single container
	docker build -t torbgard:latest .

docker-run:  ## run the container on :8000
	docker run --rm -p 8000:8000 --env-file .env torbgard:latest

smoke:  ## post-deploy smoke test (BASE_URL=... make smoke)
	./scripts/smoke.sh $${BASE_URL:-http://127.0.0.1:8000}

clean:  ## remove build output and caches (keeps ./data and the venv)
	rm -rf frontend/.next frontend/out backend/static backend/var/*.db
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

reset-db:  ## delete the serving database (rebuild with `make data`)
	rm -f backend/var/app.db backend/var/app.db-wal backend/var/app.db-shm
