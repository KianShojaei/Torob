# Deploy

The whole product is **one container**: FastAPI serves the REST/SSE API *and* the built PWA.
No Node runtime, no separate web server, no external service at runtime.

| Fact | Value |
|---|---|
| Image | `python:3.12-slim`, ~340 MB with the prebuilt database |
| Cold start | ~2 s (the ETL runs at image build time, not at boot) |
| RAM | ~120 MB steady, fits any free plan |
| Port | `8000` (`PORT` is honoured) |
| State | the serving DB is rebuilt at image build; contact threads are ephemeral unless you mount a volume |

---

## 1. Local

```bash
make setup && make synthetic && make data && make frontend && make serve
# → http://localhost:8000
```

## 2. Docker

```bash
docker build -t torbgard .
docker run --rm -p 8000:8000 --env-file .env torbgard
```

The image build **detects the dataset**:

* if `data/shops.csv` and `data/offers.csv` exist → they are used;
* otherwise a synthetic dataset is generated so the demo always boots.

To ship the real dataset, put the CSVs in `./data` before `docker build` (they are not committed to
git, but they are part of the local build context).

---

## 3. Liara

Liara runs a Dockerfile and gives you an HTTPS subdomain. One app is enough.

```bash
# once
npm i -g @liara/cli
liara login

# from the repository root
liara create --platform docker --plan free
liara deploy --platform docker --port 8000
```

`liara.json` in the repo pins the platform, the port and the health check:

```json
{
  "platform": "docker",
  "port": 8000,
  "healthCheck": { "command": "curl -fsS http://127.0.0.1:8000/api/health" }
}
```

### Environment

Set these in the Liara dashboard (or `liara env set`). Only the LLM key is optional — the app is
fully functional without it.

| Key | Value | Required |
|---|---|---|
| `LLM_PROVIDER` | `none` · `anthropic` · `openai` | no (default `none`) |
| `LLM_API_KEY` | provider key | only if provider ≠ none |
| `LLM_MODEL` | e.g. `claude-sonnet-4-5` | no |
| `LLM_BASE_URL` | OpenAI-compatible gateway | no |
| `SNAPSHOT_DATE` | `2026-10-13` | no |
| `CONTACT_TIMEOUT_SECONDS` | `45` | no |
| `DEMO_TIME_SCALE` | `20` | no |

```bash
liara env set LLM_PROVIDER=anthropic LLM_API_KEY=sk-ant-... LLM_MODEL=claude-sonnet-4-5
```

### Persistent contact threads (optional)

Replies are stored in SQLite. On an ephemeral filesystem they disappear on redeploy, which is fine
for a demo. To keep them, mount a disk at `/data` and set:

```bash
liara env set DB_PATH=/data/app.db
```

### After deploy

```bash
BASE_URL=https://<your-app>.liara.run ./scripts/smoke.sh
```

You should see ten green checks: health, database, demo flags, simulation disclosure, search,
transparency fields, availability, agent cards, tool calls.

---

## 4. CI

`.github/workflows/ci.yml` runs on every push:

1. **backend** — generates a small dataset, builds the DB, runs `etl.validate`, then `pytest` (100 tests).
2. **frontend** — `npm ci`, `tsc --noEmit`, `next build`.
3. **docker** — builds the image (proves the ETL-at-build-time path).

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/api/health` says `db_ready:false` | the DB was not built | run `make data` locally / rebuild the image |
| The app shows the synthetic badge with real data | `data/synthetic_truth.json` survived | delete it (`scripts/prepare_dataset.py` does this) |
| Contact never leaves `sent` | `CONTACT_TIMEOUT_SECONDS` too long for the demo | lower it to 20–30 |
| Installment filter returns nothing | the snapshot has only 266 shops with payment data | that is correct behaviour; the sheet explains the hard filter |
| Map tiles blank | the tile server is blocked | the list view is the primary path; set `MAP_TILE_URL` to a reachable server |
| Agent answers feel templated | `LLM_PROVIDER=none` | set a provider + key; the deterministic path stays as fallback |

---

## 6. Cost

Everything used at runtime is free: OSM tiles, haversine distance, SQLite. A Liara free plan or any
512 MB container is sufficient; the LLM is optional and only consumes tokens for the chat turns.
