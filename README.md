# ترب‌گرد · Torbgard

**An agentic shopping assistant for _in-person_ shopping in Tehran.**
Not "find me a product online" — but **"is it worth walking into this shop, right now?"**

Torbgard turns Torob's price listings into a decision: *which model*, *which shop nearby*,
*is the listed price still real*, *is it open when I arrive*, *can I pay in installments*,
*which floor of the mall*, and *what do I do if nobody answers*.

> The slogan: **«قبل از اینکه راه بیفتی، مطمئن شو.»**
> Built for the **Starcoach / Torob** hackathon. Persian UI, RTL, mobile-first.
> The dataset shipped with the challenge is a demo snapshot — every price is shown with its
> age and availability status, and unknown facts are shown as **«نامشخص»**, never invented.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  نیاز: «هدفون بلوتوثی تا ۳ میلیون، نزدیک ونک، قسطی»                        │
│        │                                                                │
│        ├─ محصول  → ۳ مدل با دلیل انتخاب (مشخصات، بازهٔ قیمت، امتیاز)         │
│        ├─ فروشگاه → ۵ مغازه، مرتب‌شده با فاصله + قیمت + ساعت کاری + قسط     │
│        ├─ مقایسه  → جدول قیمت/فاصله/ساعت/گارانتی/قسط                     │
│        ├─ تماس    → «قیمت و موجودی همین مدل رو دارید؟» (شبیه‌سازی)          │
│        ├─ جایگزین → اگر جواب نداد یا موجود نبود، ۳ گزینهٔ دیگر               │
│        └─ سفر     → مسیر + طبقه/واحد داخل پاساژ + لیست خرید                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 1. What makes it different

| Common "shop finder" | Torbgard |
|---|---|
| Shows a price | Shows **price + date of that price + availability**, as three separate facts |
| Assumes the shop is open | Computes open/closed **at your arrival time**, handles cross-midnight hours, treats `unsupported` as unknown |
| Assumes installment | Only shows «قسطی» when the shop's payment data actually supports it; `0/0` limits mean *no information*, not *no limit* |
| Lists shops | **Explains** the ranking (distance, price, freshness, hours, installment) with a visible score breakdown |
| Stops when nobody replies | **Automatically suggests alternatives** and can rebuild the trip plan |
| "Address: Tehran, ..." | Parses floor/unit/landmark and shows an **in-mall guide with a confidence label** |
| Numbers from an LLM | Every number on screen comes from a tool result; a **guardrail strips any sentence with an unverified number** |

Honesty is a feature here, not a disclaimer. See [`docs/AGENT.md`](docs/AGENT.md) and
[`backend/app/agent/guardrails.py`](backend/app/agent/guardrails.py).

---

## 2. Quick start (60 seconds, no keys required)

```bash
git clone https://github.com/KianShojaei/Torob && cd Torob

make setup        # python venv + npm install
make synthetic    # demo dataset (schema-faithful; use real CSVs if you have them)
make data         # build the serving DB  (~10 s)
make build        # build the PWA into backend/static
make serve        # http://localhost:8000
```

No LLM key? The agent runs in **deterministic mode** (`LLM_PROVIDER=none`) and every flow still
works. With a key:

```bash
cp .env.example .env
# LLM_PROVIDER=anthropic  LLM_API_KEY=sk-ant-...  LLM_MODEL=claude-sonnet-4-5
make serve
```

### With real Torob data

Put `shops.csv`, `products.csv`, `offers.csv` into `./data/` and rerun `make data`.
The ETL is written against the documented schema ([`docs/DATA.md`](docs/DATA.md)) and is defensive:
broken JSON, `null` strings, duplicate `(shop, product)` rows, prices outside `10k…5e9`,
`unsupported` opening hours, missing brands, and 3,428 categories are all handled.

### Docker / Liara

```bash
docker compose up --build          # one container, API + PWA on :8000
```

Liara deployment (Dockerfile → `liara deploy --platform docker`) is described step by step in
[`docs/DEPLOY.md`](docs/DEPLOY.md).

---

## 3. How it works

```
Next.js 15 PWA (static export)  ──  served by FastAPI  ──  SQLite (FTS5) / PostgreSQL
        │                                  │
        │  REST + SSE                      ├── agent/orchestrator   (planner → tools → copy)
        └──────────────────────────────▶   │     ├─ understand   (Persian NLU: needle → Need)
                                           │     ├─ llm          (Anthropic | OpenAI-compat | none)
                                           │     ├─ tools        (11 tools, typed I/O)
                                           │     ├─ guardrails   (numbers must come from tools)
                                           │     └─ compose      (Persian answers + cards)
                                           └── simulator         (seller persona, replies, timeouts)
```

* **One container.** The Next.js app is a *static export*; FastAPI serves it. One process, one port,
  no Node runtime in production, ~90 MB RSS idle.
* **Tool-calling agent.** The LLM plans and phrases; it never invents data. When it is unavailable,
  the orchestrator takes the same path with rules and templates — the SSE contract is identical.
* **Simulated sellers.** Contact is simulated (clearly badged in the UI). Each shop gets a stable
  persona: responsiveness, reliability, stock, language. Real channel adapters (`tel:`, `wa.me`,
  Bale deep links) sit behind the same interface.
* **Time compression.** `DEMO_TIME_SCALE=20` maps one simulated minute to 3 real seconds so a
  reply, a follow-up and a timeout are visible inside a 5-minute demo.

### Agent tools

| Tool | Purpose |
|---|---|
| `search_products` | text + category + brand + budget search (FTS5 bm25, Persian folding, synonyms) |
| `recommend_models` | 3–5 models with `reasons[]` and a score breakdown |
| `compare_products` | specs table across models, only where the dataset knows a value |
| `find_stores` | shops carrying a product, with distance, price age, open state, installment |
| `compare_stores` | price / distance / hours / warranty / installment side by side |
| `check_open` | open at the ETA (walking time), not "open now" |
| `locate_in_mall` | floor / unit / landmark + confidence |
| `contact_store` | ask price & stock (simulated; the only place a "confirmed" fact can appear) |
| `contact_status` | poll a thread |
| `suggest_alternatives` | other shops / models when `no_reply`, `out_of_stock`, `closed` |
| `plan_visit` | ordered stops, warnings, route link |

### SSE contract

```text
text_delta   {text}                       streaming answer text
tool_status  {name, status, label_fa}     visible agent trace
card         {kind, payload}              product_list | store_list | compare | contact | plan | ...
state_update {need}                       what the agent understood
done         {latency_ms, degraded}       end of turn
error        {message}                    never a stack trace
```

---

## 4. API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` · `/api/healthz` | liveness + db readiness |
| GET | `/api/ready` · `/api/readyz` | counts, means the ETL artefacts are usable |
| GET | `/api/meta` | dataset mode, snapshot date, demo flags, LLM provider |
| POST | `/api/search` | products + price stats + key specs |
| POST | `/api/stores` | shops for a product with all transparency fields |
| GET | `/api/shops/{id}` · `/api/products/{id}` | detail |
| POST | `/api/compare/stores` · `/api/compare/products` | comparison |
| POST | `/api/contact` · GET `/api/contact/{id}` · GET `/api/contacts` | seller simulation |
| POST | `/api/alternatives` · `/api/plan` | recovery path and trip plan |
| POST | `/api/agent` · `/api/agent/stream` | agent (JSON / SSE) |
| GET | `/api/malls` · `/api/malls/{key}` · `/api/categories` · `/api/neighbourhoods` | reference data |
| GET | `/api/docs` | OpenAPI UI |

---

## 5. Screens (mobile, RTL)

خانه · نتایج · کارت محصول · مقایسهٔ محصولات · فروشگاه‌های نزدیک (لیست/نقشه) ·
جزئیات فروشگاه · مقایسهٔ فروشگاه‌ها · مرکز تماس · برنامهٔ سفر · ذخیره‌شده‌ها · گفت‌وگو با دستیار

Every screen is reachable without the chat: cards, buttons, filters and sheets. The chat is an
*accelerator*, never the only path (master prompt §10).

### Documentation

| Doc | What |
|---|---|
| [`docs/01-challenge-analysis.md`](docs/01-challenge-analysis.md) | problem framing, personas, the "is it worth going?" loop (Persian) |
| [`docs/02-architecture.md`](docs/02-architecture.md) | stack, data flow, screen map, risk register |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | phase-0 decisions, folder layout, deviations |
| [`docs/DATA.md`](docs/DATA.md) | dataset pathologies, ETL rules, every derived label |
| [`docs/AGENT.md`](docs/AGENT.md) | agent design, tools, guardrails, evaluation |
| [`docs/DEPLOY.md`](docs/DEPLOY.md) | Liara / Docker runbook, env reference, troubleshooting |
| [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) | **5-minute demo video script** with timings and backup paths |
| [`docs/JUDGING.md`](docs/JUDGING.md) | rubric cheat sheet: where to click, what proves it |

---

## 6. Tests

```bash
make test      # 80 tests: unit (hours, address, pricing, normalize, simulator)
               #            API contract (all endpoints, SSE)
               #            agent evals (constraints, tool calls, guardrails)
```

The agent evals are the interesting ones: each scenario asserts the extracted constraints, the
tools that must run, the cards that must appear, and that the answer contains no number that was
not returned by a tool. CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) builds a small
dataset, validates the ETL invariants, runs the tests, builds the PWA, builds the image and runs a
container smoke test.

---

## 7. Repository layout

```
backend/app/
  api/        REST + SSE
  agent/      understand · llm · tools · guardrails · compose · orchestrator
  services/   normalize · hours · address · pricing · geo · search · stores
  simulator/  persona · parser · engine (threads, replies, timeouts)
  etl/        readers · taxonomy · synthetic · build · validate
frontend/
  app/        App Router entry + RTL shell
  components/ 20+ screens & UI primitives
  lib/        api client (incl. SSE), state store, format helpers
docs/         architecture, data, agent, deploy, demo script, judging cheat sheet
data/         CSV drop-in folder (synthetic placeholder included)
```

---

## 8. Limits & honesty

* The bundled dataset is **synthetic** (`/api/meta` → `dataset_mode: "synthetic"`). Shop names,
  phones and addresses in it are generated; real shop names are used only as *place labels*.
* Seller contact is **simulated**. The UI carries a badge and a Persian notice on every contact
  screen; real channels open the dialer / WhatsApp / Bale instead of pretending.
* Travel time falls back to haversine × walking factor when no routing service is configured —
  the UI then says «تقریبی».
* No LLM key is required to run the demo; the degraded path is a first-class citizen.

---

## خلاصهٔ فارسی

**ترب‌گرد** یک دستیار خرید **حضوری** است: از «نمی‌دانم چه مدلی» تا «جلوی در مغازه، با قیمت و
موجودی تأییدشده». نزدیک‌ترین فروشگاه‌ها را با فاصله، قیمت، تاریخ قیمت و ساعت کاری نشان می‌دهد،
فروشگاه‌ها را مقایسه می‌کند، با فروشنده تماس می‌گیرد (شبیه‌سازی‌شده و با برچسب شفاف)، و اگر جواب
نگرفت یا موجود نبود جایگزین پیشنهاد می‌دهد و برنامهٔ سفر می‌سازد. هر عدد از داده می‌آید و هر
دادهٔ نامعلوم «نامشخص» نمایش داده می‌شود.

اجرا: `make setup && make synthetic && make data && make build && make serve`

---

MIT © 2026 — see [LICENSE](LICENSE).
