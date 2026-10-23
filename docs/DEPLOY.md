# Deploy

Three paths, same image. Nothing here needs a paid service or an API key.

---

## 0. What ships

```
torbgard:latest
├── /app/backend          FastAPI (API + SSE)
│   ├── static/           PWA build (Next.js static export)
│   └── var/app.db        prebuilt SQLite DB (ETL already done)
└── uvicorn :8000         one process, ~90 MB idle
```

Cold start is ~1.5 s: no migration, no ETL, no external dependency.

---

## 1. Liara (public instance)

Liara runs a Dockerfile and exposes the container's port. One app, one container.

```bash
# once
npm i -g @liara/cli
liara login

# in the repository root (Dockerfile present)
liara create --app torbgard --platform docker --plan free
liara deploy --app torbgard --platform docker --port 8000
```

`liara.json` (already in the repo):

```json
{
  "platform": "docker",
  "app": "torbgard",
  "port": 8000,
  "healthCheck": { "command": "curl -fsS http://localhost:8000/api/health" },
  "env": {
    "LLM_PROVIDER": "none",
    "SNAPSHOT_DATE": "2026-10-13",
    "DEMO_TIME_SCALE": "20",
    "CONTACT_TIMEOUT_SECONDS": "45"
  }
}
```

Then:

```bash
liara env set LLM_PROVIDER=anthropic LLM_API_KEY=sk-ant-... LLM_MODEL=claude-sonnet-4-5
liara env set -a torbgard LLM_PROVIDER=anthropic   # or use the dashboard
liara deploy --app torbgard --platform docker --port 8000
```

Notes that matter on free/tiny plans:

* **Keep SQLite.** The image ships a read-mostly `app.db`; only the contact simulator writes.
  If you switch to PostgreSQL (Liara DB), set `DB_URL` and run `python -m app.etl.build` once as a
  one-off job — the code path already supports it, but there is no reason to spend RAM on it here.
* **One worker.** `--workers 1`; the simulator schedules replies in the DB and does not need shared
  memory, but SQLite writes are happier with one process.
* **Volume (optional).** Mount a disk at `/data` and set `DB_PATH=/data/app.db` if you want contact
  threads to survive a redeploy. Without it the DB resets — which is fine for a demo.
* **Port.** Liara's health check expects the app on `$PORT`; the Dockerfile hardcodes 8000 and
  `liara.json` maps it. If your plan injects `PORT`, change the CMD to
  `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.

### Verify the deployment

```bash
BASE_URL=https://torbgard.liara.run ./scripts/smoke.sh
```

The script checks: health, ready, PWA HTML, search, stores payload, contact creation, agent cards.
It exits non-zero on the first broken contract, so it is safe to run in CI after deploy.

---

## 2. Any Docker host

```bash
docker build -t torbgard .
docker run -p 8000:8000 -e LLM_PROVIDER=none torbgard
```

or

```bash
docker compose up --build
```

## 3. Local development

```bash
make setup && make synthetic && make data
make api      # terminal 1 — FastAPI on :8000
make dev      # terminal 2 — Next dev on :3000 with /api proxied
```

`next.config.mjs` only adds the `/api` rewrite when `NODE_ENV=development`, so the static export
stays clean (the build prints a harmless "rewrites will not be applied" warning — expected).

---

## Environment reference

| Var | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `none` | `none` · `anthropic` · `openai` |
| `LLM_API_KEY` | – | provider key (never committed) |
| `LLM_MODEL` | `claude-sonnet-4-5` | model id; any model of the provider |
| `LLM_BASE_URL` | – | for OpenAI-compatible gateways / proxies |
| `DATA_DIR` | `./data` | CSV drop-in folder |
| `DB_PATH` | `./backend/var/app.db` | serving DB |
| `DB_URL` | – | PostgreSQL URL (optional alternative) |
| `SNAPSHOT_DATE` | `2026-10-13` | reference date for price age / hours |
| `DEMO_MODE` | `true` | exposes simulation badges and the time scale |
| `DEMO_TIME_SCALE` | `20` | 1 simulated minute = 3 real seconds |
| `CONTACT_TIMEOUT_SECONDS` | `45` | when a simulated seller is declared silent |
| `DEFAULT_LAT` / `DEFAULT_LON` | 35.6949 / 51.4071 | Tehran fallback for distance |
| `MAP_TILE_URL` | OSM raster | swap for any free tile server |
| `CORS_ORIGINS` | `*` | comma separated |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/api/ready` → 503 | DB not built | `make data` (or check `backend/var/app.db` exists) |
| Home shows no products | empty search index | rebuild: `make data` |
| Agent says «حالت بدون مدل زبانی» | `LLM_PROVIDER=none` or bad key | set the key, or accept degraded mode (demo-safe) |
| 404 on deep links | static export served without catch-all | in this repo FastAPI's catch-all handles it; check `backend/static/index.html` exists |
| Map tiles grey in Iran | OSM blocked/slow | set `MAP_TILE_URL` to a reachable tile server; the list view always works |
| Contacts never time out | `CONTACT_TIMEOUT_SECONDS` too high for the demo | lower it to 20–30 |
