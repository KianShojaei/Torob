# Phase 0 — plan, stack, layout

This document is the "Phase 0" deliverable required by the master prompt: confirmed stack
choices, folder layout, and the risk register. It also records the deviations I had to make
because the dataset is not present in this environment.

---

## 1. Confirmed stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Next.js 15 (App Router, static export) + React 19 + Tailwind 3** | one build, PWA, RTL-friendly, mobile-first |
| UI | custom design system, `@fontsource/vazirmatn`, CSS variables | no runtime CSS-in-JS, fast first paint |
| Map | **Leaflet + OSM raster tiles**, lazy-loaded | free, no key; graceful fallback to schematic list if tiles fail |
| Backend | **FastAPI (async) + Pydantic v2** | typed tool I/O, SSE, auto OpenAPI |
| DB | **SQLite (WAL) by default, PostgreSQL via `DATABASE_URL`** | master prompt §2 fallback mode; zero-setup locally, managed PG on Liara |
| Search | SQLite **FTS5** (bm25) · Postgres **tsvector + pg_trgm** | no external search service; p95 < 300 ms at 226k products |
| Agent | **provider-agnostic tool-calling loop**, Anthropic Messages default, OpenAI-compatible also supported | master prompt §2 |
| Market data | no 3rd-party API at runtime — everything from the dataset | offline-safe, no key required |
| Deploy | **single container** (FastAPI serves the built PWA + `/api`), Docker, GitHub Actions | master prompt "one app container", Liara-friendly |
| Tests | pytest (unit + API) + agent eval scenarios + Playwright-free E2E smoke script | lean but real |

### Why one container instead of two

The master prompt approves "Next.js + FastAPI + Postgres" **and** requires a lean deployment
("one app container", <1–2 GB RAM). Those are compatible if the Next.js app is built as a
**static export** and served by FastAPI from `backend/static/`. Result: one process, one port,
one container, and no Node runtime in production. `make dev` still runs the Next dev server with
a proxy to FastAPI for fast iteration.

---

## 2. Folder layout (as specified in §7)

```
/backend
  app/
    api/          REST routers + SSE endpoint
    agent/        orchestrator, LLM client, prompts, guardrails, degraded mode
    tools/        the 13 typed tools from §5.3
    services/     search, ranking, geo, hours, address, pricing, alternatives, visit plan
    db/           engine, schema, repositories
    etl/          readers, normalize, parsers, enrichment, grouping, build, validate, synthetic
    simulator/    seller personas, reply engine, reply parser, demo clock
    tests/        unit + API + eval
  static/         built PWA (gitignored, produced by `make build`)
/frontend
  app/            routes (client-rendered, static export)
  components/     design system + screens
  lib/            api client, stores, i18n, format
/data             CSVs (gitignored, see data/README.md)
/scripts          make targets, smoke test
/docs             architecture, data, demo script, judging cheat sheet, deploy
```

---

## 3. Environment contract (§7 "config via env")

| Var | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `none` | `none` \| `anthropic` \| `openai` |
| `LLM_API_KEY` / `ANTHROPIC_API_KEY` | — | never committed |
| `LLM_MODEL` | `claude-sonnet-4-5` | swappable |
| `LLM_BASE_URL` | — | for OpenAI-compatible gateways |
| `DATABASE_URL` | `sqlite:///backend/var/app.db` | Postgres accepted |
| `DATASET_MODE` | auto | `real` \| `synthetic`, auto-detected from artifacts |
| `SNAPSHOT_DATE` | `2026-10-13` | dataset snapshot, drives price-age |
| `DEMO_TIME_SCALE` | `20` | 1 simulated minute = 3 s |
| `CONTACT_TIMEOUT_SECONDS` | `45` | wall-clock timeout for a seller reply |
| `MAP_TILE_URL` | OSM | overridable |
| `DEMO_MODE` | `1` | enables the "simulated" badges |

`LLM_PROVIDER=none` is a first-class mode: the agent falls back to a deterministic
intent+tool planner ("degraded mode" required by §7). Every screen and every tool still works.

---

## 4. What is (and is not) in this environment

- **Dataset is absent.** `arvanstorage.ir` is blocked by the sandbox egress policy, so the three
  CSVs cannot be downloaded here. Per §10 of the master prompt I proceed by writing the ETL
  against the authoritative schema, plus a **schema-faithful synthetic generator**
  (`backend/app/etl/synthetic.py`) that reproduces the documented column names, JSON-in-string
  formats, `null` literals, geo ranges, hourly shapes, price distribution and the `0/0` sentinel.
  Real CSVs drop into `/data` and replace it with `make data` — no code change.
- **No LLM API access from the sandbox.** `LLM_PROVIDER=none` is therefore the default here; the
  Anthropic/OpenAI clients are implemented and unit-tested with fakes.
- **No Liara access from the sandbox.** Deployment is delivered as Dockerfile + CI + a documented
  Liara runbook, with a post-deploy smoke script.

Everything a judge sees is runnable locally with zero external services.

---

## 5. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Synthetic data mistaken for real | credibility | persistent "داده‌ی نمایشی" badge; `DATASET_MODE`; README |
| 226k products hurt cold start | slow demo | precomputed artifacts, FTS5 index, no boot-time ETL |
| Persian search recall | bad UX | normalization + synonym map + trgm fallback + token boost |
| LLM unavailable at judging | empty app | degraded rule-based planner is default-tested in CI |
| Liara memory limits | crash | SQLite + static assets, single worker, <300 MB RSS measured |
| Fake phone numbers | honesty | simulated channel only, explicit "شبیه‌سازی" badges |
| `0/0` payment sentinel | wrong filter | parsed to `unknown`, unit-tested |
| Cross-midnight hours | wrong "open" | explicit engine + tests (§4.7) |
