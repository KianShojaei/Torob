# Judging map — where each rubric point lives

> Scoring per the brief: Product 75 · UX 75 · Intelligence 50 · Deployment 40 · Technical 40 ·
> Dataset 20. This page is a fast path: **claim → screen → file**.

## 60-second verification

```bash
make serve          # or open the deployed Liara URL
./scripts/smoke.sh  # 10 contract checks, non-zero on failure
```

Then, on a phone-sized window:

1. Home → «هدفون بلوتوثی زیر ۳ میلیون» → results.
2. Any card → «فروشگاه‌ها» → filter «فقط باز الان».
3. Open a shop → «راهنمای مسیر داخل پاساژ» (or its low-confidence variant).
4. «پرسش قیمت و موجودی» → watch the timeline → parsed chips.
5. Let a silent shop time out → alternatives appear.
6. «برنامه سفر» → ordered stops + warnings.

If those six work, the core rubric is satisfied.

---

## Product (75)

| Expectation | Where | Code |
|---|---|---|
| Problem understood, not just a shop list | home copy + the price→decision loop | `components/Home.tsx` |
| Guided discovery, not a blank search box | category chips, budget/usage chips, one clarifying question | `agent/understand.py`, `components/Home.tsx` |
| Model shortlist with reasons | results cards + «چرا این؟» sheet | `agent/tools.py::recommend_models` |
| Nearby shops with real constraints | distance, ETA, hours at arrival, installment, price age | `services/stores.py` |
| Comparison | products and stores, cheapest highlighted | `components/CompareStores.tsx` |
| Live confirmation | contact thread + parsed reply | `simulator/engine.py` |
| Graceful failure | timeout → alternatives → back to the list | `components/ContactCenter.tsx` |
| In-mall guidance | floor/unit/landmark + confidence + ask sentence | `services/address.py` |
| Visit plan | ordered stops, warnings, route link | `components/Plan.tsx` |

## UX (75)

| Expectation | Where |
|---|---|
| Persian, RTL, mobile-first | `app/layout.tsx` (`dir="rtl"`), `app/globals.css`, Vazirmatn |
| Persian digits and money format | `lib/format.ts` (`fa`, `money`) |
| Thumb-reachable navigation | bottom nav + full-width actions (`components/Shell.tsx`) |
| Price shown as **price + age + availability** | `components/ui.tsx::PriceBlock` |
| Empty / loading / error states | skeletons, empty-state suggestions, toasts |
| Every claim explainable | score breakdown + reasons chips on each store card |
| No dead ends | alternatives sheet, «شعاع را زیاد کنم؟» empty state |
| Installable PWA | `public/manifest.webmanifest`, `public/sw.js` |

## Intelligence (50)

| Expectation | Where |
|---|---|
| Agent, not a chatbot | tool-calling orchestrator with 11 typed tools |
| Visible reasoning | SSE `tool_status` chips in the chat |
| Grounded numbers | `agent/guardrails.py` (any number not in tool output → sentence removed) |
| Persian NLU | category/brand/budget/neighborhood/usage/installment extraction, ZWNJ-safe |
| Follow-ups | thread status, alternatives, plan |
| Honest degradation | `LLM_PROVIDER=none` → deterministic composer, `degraded: true` in `done` |
| Evaluation | `app/tests/test_agent.py` — extracts → tools → cards → no invented numbers |

## Deployment (40)

| Expectation | Where |
|---|---|
| Public instance | Liara runbook: `docs/DEPLOY.md` |
| One container | `Dockerfile` (Next static export served by FastAPI) |
| Fast cold start | DB built at image build; ~2 s boot |
| Low footprint | SQLite, no worker, ~120 MB RSS |
| Observability | `/api/health`, `/api/ready`, structured logs, `/api/meta` |
| Safe defaults | runs with no API keys; demo flags explicit |

## Technical (40)

| Expectation | Where |
|---|---|
| Clean layering | `api / agent / services / simulator / etl` |
| Typed boundaries | Pydantic models for every tool and request body |
| Tests | 100 tests: unit, ETL pipeline, API contract, agent evals |
| Data build reproducible | `make synthetic && make data` (fixed seed), `etl/validate` |
| Failure handling | tool errors never leak; API returns typed errors; SSE `error` event |
| Docs | `docs/DATA.md`, `docs/DEPLOY.md`, `docs/DEMO_SCRIPT.md`, this file |

## Dataset (20)

| Pathology | Handling | Proof |
|---|---|---|
| `null` strings, broken JSON | tolerant readers with counters | `etl/readers.py`, tests |
| 20k duplicate offers | keep newest, validated in CI | `etl/build.py`, `etl/validate.py` |
| 15k null prices, absurd ranges | `price_valid` flag, never fatal | `services/pricing.py` |
| Partial/`unsupported` hours | unknown ≠ closed, cross-midnight, day aliases | `services/hours.py` |
| 3.4k category strings | 17 canonical + verbatim fallback | `etl/taxonomy.py` |
| 74.5 % missing brands | `NULL`, never inferred | `etl/enrich.py` |
| `0/0` payment limits | «نامشخص», not "unlimited" | `services/pricing.py` |
| 19 malls, free-text addresses | parser + confidence + fallback ask sentence | `services/address.py` |

---

## The three answers that matter

**«چرا نباید به اینترنت/API بیرونی وصل شوی؟»**
برای اینکه قیمت و موجودی متغیر است و در دیتاست تاریخ دارد؛ هر چیز بیرونی هم بدون سند است. تنها
جایی که داده «تأیید» می‌شود، پاسخ فروشنده است.

**«اگر مدل زبانی جواب ندهد؟»**
همان مسیر با ترکیب‌کنندهٔ قاعده‌محور اجرا می‌شود؛ خروجی SSE یکی است و در UI با برچسب
«حالت بدون مدل زبانی» اعلام می‌شود.

**«چرا فاصله پیاده‌روی است؟»**
چون بدون کلید مسیریابی هم کار می‌کند؛ هاورساین × ضریب حالت. در UI «تقریبی» علامت می‌خورد.
