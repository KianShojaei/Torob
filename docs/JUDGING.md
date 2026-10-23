# Judging cheat sheet

One page. Left: what the rubric asks. Right: where to click, and which file proves it.

| # | Criterion (points) | Where to look | Proof in the repo |
|---|---|---|---|
| 1 | **Product thinking (75)** — does it solve the real problem end-to-end? | Home → results → shops → store → contact → alternatives → plan. Nothing requires the chat. | `docs/01-challenge-analysis.md`, `frontend/components/*.tsx` |
| 1a | Discovery → decision | «هدفون بلوتوثی زیر ۳ میلیون» → 3 models with `reasons[]` | `agent/tools.py::recommend_models` |
| 1b | Store choice with price/distance/hours | Shops screen; sort chips; score breakdown bars | `services/stores.py`, `StoreDetail.tsx` |
| 1c | Contact for live price/stock | Contact center stepper; parsed answer grid | `simulator/engine.py`, `ContactCenter.tsx` |
| 1d | Alternatives when no reply/closed | Timeout card → 3 alternatives; closed-at-arrival warning | `agent/tools.py::suggest_alternatives` |
| 1e | In-mall guidance | Store detail → «راهنمای داخل پاساژ» + confidence + say-this sentence | `services/address.py` |
| 1f | Installment-only filter | Filter sheet, hard-excludes unconfirmed shops | `services/stores.py::StoreFilters` |
| 2 | **UX (75)** — Persian, RTL, mobile-first, transparent | Every screen; `dir="rtl"`, Vazirmatn, 44px targets, bottom nav, PWA installable | `app/layout.tsx`, `app/globals.css`, `public/manifest.webmanifest` |
| 2a | Honest unknown states | Search for «نامشخص» across screens; «موجودی نامشخص», «ساعت نامشخص», «اطمینان آدرس» | `ui.tsx::AvailabilityBadge/OpenBadge` |
| 2b | No dead ends | Empty state offers «شعاع را بیشتر کنم یا فیلتر اقساط را بردارم؟» | `Stores.tsx` |
| 3 | **Intelligence (50)** — agentic behaviour, not a chatbot | Agent FAB: tool trace, cards, navigation; follow-up turns | `agent/orchestrator.py`, `ChatPanel.tsx` |
| 3a | Tool calling | 11 typed tools, schemas exposed to the LLM | `agent/tools.py::TOOLS` |
| 3b | No hallucinated data | Guardrail strips sentences with untraceable numbers | `agent/guardrails.py` |
| 3c | Degrades gracefully | `LLM_PROVIDER=none` → same screens, `degraded: true` badge | `agent/orchestrator.py` |
| 3d | Persian NLU | «قسطی»، «تا ۲۰ میلیون»، «بین ۲ تا ۴»، ZWNJ-safe keywords | `agent/understand.py`, `test_agent.py` |
| 4 | **Deployment (40)** | `/api/docs`, `/api/health`, `smoke.sh`, Dockerfile, Liara runbook | `Dockerfile`, `docs/DEPLOY.md`, `.github/workflows/ci.yml` |
| 4a | Public instance | Liara app URL in README/demo | `docs/DEPLOY.md#1-liara-public-instance` |
| 4b | One lean container | static PWA served by FastAPI, ~90 MB RSS, no Node at runtime | `app/main.py` |
| 5 | **Technical quality (40)** | 80 tests, typed boundaries, ETL validation in CI | `backend/app/tests/*`, `etl/validate.py` |
| 5b | Deterministic demo | seeded personas, time compression, prebuilt DB | `simulator/persona.py`, `config.py` |
| 6 | **Dataset mastery (20)** | Every pathology has a rule and a label | `docs/DATA.md` |

---

## Five questions a judge will ask

**«قیمت را از کجا می‌آورید؟»**
From `offers`, and we always show the date of that price and whether it is valid. We never show a
price without them. `services/pricing.py`.

**«نمی‌دانید موجود است یا نه — چطور می‌فهمید؟»**
We don't guess. `availability` is `listed` until the seller confirms. The contact flow is the only
place a fact becomes `confirmed_*`. Category names and `last_price_changed_at` are explicitly *not*
treated as stock proof.

**«اگر فروشنده جواب ندهد؟»**
After the timeout the thread becomes `no_reply`, the UI offers three alternatives (other shops
first, then other models) and can rebuild the plan. `suggest_alternatives`.

**«LLM چه کاری می‌کند؟ اگر قطع شود؟»**
It plans tool calls and writes Persian copy. If it is unavailable, the same `Need` drives a
rule-based plan, the same cards, the same SSE stream — with a visible «بدون مدل زبانی» badge.

**«تماس واقعی است؟»**
No, and the UI says so on every contact screen. Real channels (`tel:`, `wa.me`, Bale deep links)
are behind the same interface; the dataset's phone numbers are demo data, so we do not pretend.

---

## 60-second verification (for a judge with a phone)

1. Open the URL → tap «هدفون بلوتوثی زیر ۳ میلیون».
2. Read one card aloud: price, age, availability. All three must be present.
3. Tap the cheapest model → «فروشگاه‌ها» → look for a **بسته** badge.
4. Tap that shop → the in-mall line and «اطمینان آدرس» must be visible.
5. Tap «تماس با فروشنده» → watch the stepper → when it times out, alternatives appear.
6. Tap «سفر» → a numbered plan with warnings.
7. Tap the center FAB → type «گوشی سامسونگ تا ۲۰ میلیون قسطی» → tool trace → cards.
