SHELL := /bin/bash
PY := ./.deps/python/bin/python
PIP := ./.deps/python/bin/pip
NODE_ENV ?= development

.DEFAULT_GOAL := help

.PHONY: help setup synthetic data build dev api test lint fmt docker smoke clean

help: ## show targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## create the python venv + install deps (idempotent)
	@test -d .deps/python || python3 -m venv .deps/python
	@$(PIP) install -q -r backend/requirements.txt
	@test -d frontend/node_modules || (cd frontend && npm ci --no-audit --no-fund)

synthetic: ## generate a schema-faithful demo dataset into ./data (fast)
	@cd backend && ../$(PY) -m app.etl.synthetic --out ../data --shops 1200 --products 30000 --offers 60000

data: ## build the serving DB from ./data (real CSVs if present, else synthetic)
	@cd backend && ../$(PY) -m app.etl.build --data ../data --db var/app.db

build: ## build the PWA into backend/static
	@cd frontend && npm run build
	@rm -rf backend/static && cp -r frontend/out backend/static
	@echo "static → backend/static"

dev: ## Next dev server (port 3000) proxying /api to :8000
	@cd frontend && npm run dev

api: ## FastAPI only (port 8000)
	@cd backend && ../$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

serve: build ## production-like: one process serving API + PWA
	@cd backend && ../$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

test: ## backend unit + API + eval tests
	@cd backend && ../$(PY) -m pytest -q

docker: ## build the container image
	docker build -t torbgard:latest .

smoke: ## post-deploy smoke test against a running instance
	@./scripts/smoke.sh $${BASE_URL:-http://127.0.0.1:8000}

clean: ## remove build outputs and the local DB
	@rm -rf frontend/.next frontend/out backend/static backend/var .pytest_cache
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
