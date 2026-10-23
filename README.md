# ترب‌گرد · Torbgard

**An agentic assistant for _in-person_ shopping in Tehran.**

Torob tells you what a product costs online. Torbgard answers the question that actually
decides whether you leave the house:

> **«آیا ارزش دارد برای این محصول، الان، به این مغازه بروم؟»**
> *Is it worth going to this shop, right now?*

It turns a Persian sentence («هدفون بلوتوثی زیر ۳ میلیون، نزدیک ونک، قسطی») into a decision:
which model, which nearby shop, what the listed price really means, whether the shop is open
**when you arrive**, how to find the unit inside the mall — and what to do when nobody answers.

---

## Why this is not another shop finder

| Most shopping apps | Torbgard |
|---|---|
| Show *a price* | Shows **price + when it was recorded + availability**, as three separate facts |
| Assume the shop is open | Computes open/closed **at your arrival time**, handles cross-midnight shifts, treats `unsupported` as unknown |
| Assume "installment" | Shows «قسطی» only when the seller's payment data proves an in-person plan; `0/0` limits mean *no information*, not *no limit* |
| List shops by distance | Rank with a **visible score breakdown** (price, distance, hours, freshness, installment) and a reason for every claim |
| Stop when nobody answers | **Automatically suggest alternatives** and rebuild the trip |
| Print a long address | Parse mall / floor / unit / landmark, show an **in-mall guide with a confidence label** |
| Let an LLM write numbers | Every number comes from a tool; a **guardrail deletes any sentence with an unverified number** |

Unknown data is shown as **«نامشخص»** — never guessed, never hidden.

---

## What it does (the five-step loop)

1. **Understand** — Persian NLU extracts category, brand, budget, neighbourhood, usage and the
   installment constraint, then asks *one* clarifying question if the need is still fuzzy.
2. **Shortlist models** — search + recommend with specs and market position, not a wall of results.
3. **Find nearby shops** — distance / walk time, price age & availability, opening hours at your ETA,
   installment evidence, in-mall location.
4. **Confirm with the seller** — a contact thread with a live status timeline; the reply is parsed
   into price / stock / hours; silence or "out of stock" triggers alternatives.
5. **Go** — an ordered visit plan with warnings, a route link and a copyable in-mall guide.

Every step exists both as an **agent turn** and as a **card/button path** — the chat is an
accelerator, never the only way to do something.

---

## Screens

خانه · نتایج · مقایسهٔ محصولات · فروشگاه‌های نزدیک (لیست + نقشه) · جزئیات فروشگاه ·
مقایسهٔ فروشگاه‌ها · مرکز تماس · برنامهٔ سفر · ذخیره‌شده‌ها · دستیار

Mobile-first, RTL, Persian typography (Vazirmatn), Persian digits, installable as a PWA.

---

## Architecture

```
┌───────────────────────────────┐        ┌───────────────────────────────────────────┐
│  Next.js 15 (static export)   │  /api  │  FastAPI                                  │
│  React 19 · Tailwind · RTL    │◀──────▶│  ├── REST  (search, stores, contact, …)   │
│  Leaflet map · SSE client     │  SSE   │  ├── agent orchestrator                   │
└───────────────────────────────┘        │  │     understand → tools → compose       │
                                          │  │     ↳ LLM (optional) + guardrails      │
                                          │  ├── services (hours, address, pricing)   │
                                          │  ├── seller simulator (personas, timers)  │
                                          │  └── SQLite + FTS5 (prebuilt serving DB)  │
                                          └───────────────────────────────────────────┘
```

* **One container.** The PWA is a static export served by FastAPI; one process, one port, no Node
  at runtime. Cold start ~2 s because the database is built at image build time.
* **Provider-agnostic LLM.** `LLM_PROVIDER=none|anthropic|openai` (+ `LLM_BASE_URL` for any
  OpenAI-compatible gateway). With `none` the same flows run deterministically — the demo never
  depends on a key. The UI labels that state honestly.
* **Serving DB.** SQLite + FTS5 (bm25) with Persian folding and synonyms. The schema is plain SQL;
  a Postgres migration path is documented in `docs/DATA.md`.

---

## Quick start

Requirements: Python 3.11+, Node 20+.

```bash
make setup        # venv + pip + npm install
make synthetic    # demo dataset (1,200 shops · 30,000 products · 60k offers)
make data         # build backend/var/app.db  (~15 s) and validate invariants
make frontend     # build the PWA into backend/static
make serve        # http://localhost:8000
```

Development loop with hot reload:

```bash
make api          # terminal 1 → :8000
make dev          # terminal 2 → :3000 (proxies /api to :8000)
```

### With the real challenge dataset

```bash
# put shops.csv / products.csv / offers.csv into ./data
make data         # real CSVs are detected automatically
make frontend && make serve
```

`make data` prints an ETL validation report and writes `backend/var/etl-report.json`.
A bundled `.zip` works too: `python scripts/prepare_dataset.py data/starcoach.zip`.

### Docker / Liara

```bash
docker build -t torbgard .
docker run --rm -p 8000:8000 --env-file .env torbgard
```

Liara (one Docker app, free plan is enough): see **[docs/DEPLOY.md](docs/DEPLOY.md)**.

### Demo

* **[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)** — the 5-minute recording script with exact clicks,
  timings and fallbacks.
* **[docs/JUDGING.md](docs/JUDGING.md)** — rubric → screen → file, for a judge in a hurry.
* `python scripts/seed_demo.py` — picks a good product and prints which seller answers, which stays
  silent, and how long the reply takes.

---

## Configuration

Everything is optional; see `.env.example`.

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `none` | `none` · `anthropic` · `openai` |
| `LLM_API_KEY` | – | provider key (never committed) |
| `LLM_MODEL` | `claude-sonnet-4-5` | model id |
| `LLM_BASE_URL` | – | OpenAI-compatible gateway base URL |
| `SNAPSHOT_DATE` | `2026-10-13` | reference date for price age and hours |
| `DEMO_NOW` | – | freeze the open/closed clock for a recording (e.g. `2026-10-21T17:30:00+03:30`) |
| `DEMO_TIME_SCALE` | `20` | 1 simulated minute = 3 real seconds |
| `CONTACT_TIMEOUT_SECONDS` | `45` | when a silent seller becomes "no reply" |
| `DEFAULT_LAT` / `DEFAULT_LON` | Tehran centre | fallback location |
| `MAP_TILE_URL` | OSM tiles | any free tile server |
| `DB_PATH` | `backend/var/app.db` | serving database |

---

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health`, `/api/healthz` | liveness + DB readiness |
| GET | `/api/ready` | counts (shops, products, offers, malls) |
| GET | `/api/meta` | dataset mode, demo flags, LLM state, tiles, default location |
| GET | `/api/categories`, `/api/neighbourhoods`, `/api/malls` | reference data |
| POST | `/api/search` | products + price stats + key specs |
| POST | `/api/stores` | ranked shops for a product, with transparency fields |
| GET | `/api/shops/{id}` | full shop detail incl. hours, contacts, mall guide |
| POST | `/api/compare/stores`, `/api/compare/products` | comparison matrices |
| POST | `/api/contact` → GET `/api/contact/{id}` | seller thread + polling status |
| POST | `/api/alternatives` | replacement shops / models |
| POST | `/api/plan` | ordered visit plan |
| POST | `/api/agent`, `/api/agent/stream` | agent (JSON / SSE) |
| POST | `/api/events` | anonymous UX events |
| GET | `/api/docs` | OpenAPI UI |

SSE event kinds: `text_delta`, `tool_status`, `card`, `state_update`, `done`, `error`.

---

## Quality

```bash
make test                         # 100 tests
python scripts/smoke.sh           # post-deploy contract check (10 checks)
python scripts/journey.py         # 46-assertion end-to-end user journey
python scripts/seed_demo.py       # data for the demo recording
```

* **100 tests**: normalization, ETL (readers, pipeline on a real-shaped fixture), contact flow,
  agent NLU, agent eval scenarios (tool call + no-hallucinated-number assertions), API contract.
* **ETL validation** fails the build on duplicates, cap violations, geo outside Tehran, FTS drift,
  implausible price validity.
* **CI** runs backend tests, ETL validation, `tsc --noEmit`, the PWA build and the container build.

---

## Repository layout

```
backend/
  app/
    api/        REST + SSE
    agent/      understand · llm · tools · guardrails · compose · orchestrator
    services/   normalize · hours · address · pricing · geo · search · stores
    simulator/  persona · parser · engine
    etl/        readers · taxonomy · synthetic · build · validate
  app/tests/    unit, ETL, API and agent-eval suites
frontend/
  app/          App Router entry + layout
  components/   screens and UI primitives
  lib/          api client, state store, formatting
docs/           data, deploy, demo script, judging map
scripts/        smoke test, end-to-end journey
data/           CSV drop-in folder (never committed)
```

---

## Honest limitations

* The bundled dataset is **synthetic but schema-faithful** (same columns, same pathologies, same
  rates). `/api/meta` and the UI say so. Real CSVs are a drop-in replacement.
* **Seller contact is simulated.** Every contact screen carries a «شبیه‌سازی» badge and the README
  says it. Real channels (`tel:`, `wa.me`, Bale deep links) sit behind the same interface.
* Phone numbers and shop names in the dataset are demo values; they are never looked up externally.
* Travel time is haversine × mode factor (no routing key required); the UI calls it approximate.
* Installment is shown only when confirmed; where the source has `0/0` limits the app says
  «نامشخص» instead of inventing a plan.

---

## License

MIT — see [LICENSE](LICENSE).
