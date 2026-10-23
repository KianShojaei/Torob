# The agent

Two modes, one contract.

```
understand(message) ──▶ Need ──▶ orchestrator ──▶ tools ──▶ compose ──▶ SSE
                        │            ▲                              
                        │            └── LLM tool-calling (optional)
                        └── rules: category, brand, budget, neighborhood,
                            installment, usage, intent, follow-up target
```

* **With an LLM** (`LLM_PROVIDER=anthropic|openai`): the model plans which tools to call and writes
  the Persian answer, but it only sees tool output. Any sentence containing a number that did not
  come from a tool result is removed before it reaches the browser (`guardrails.py`).
* **Without an LLM** (`none`): the same `Need` drives a deterministic plan, the cards are identical,
  and the copy is templated. `done.degraded = true` and the UI shows «حالت بدون مدل زبانی».

This is deliberate: an unreliable LLM must not be able to break the product demo, and the judge can
run everything with no key.

---

## 1. Understanding (`agent/understand.py`)

Persian (and Latin) normalization: Arabic ي/ك → ی/ک, ZWNJ handling, Persian digits, diacritics,
synonyms («کتونی» → «کفش ورزشی»), budget parsing («تا ۲۰ میلیون», «بین ۲ تا ۴ میلیون»,
«زیر سه تومن»), neighborhoods from the dataset, installment words («قسطی», «اقساط», «چک»),
usage phrases («برای برنامه‌نویسی», «برای پیاده‌روی»).

Word-boundary matching uses `[\u0600-\u06ff\w]` lookarounds — Python's `\b` is unreliable with
ZWNJ and produced a real bug: «می‌خوام» matched the installment keyword «وام». There is a test for it.

Produces:

```python
Need(category, brand, budget_min, budget_max, neighborhood, installment_only,
     usage, intent, product_id, shop_id, location, limit, ...)
```

`intent ∈ {discover, recommend, compare_products, find_stores, compare_stores, contact,
follow_up, alternatives, plan, locate, smalltalk}`.

## 2. Tools (`agent/tools.py`) — 11, typed

Every tool has a Pydantic input model, returns a JSON-serializable dict, and is also exposed as a
JSON schema for the LLM. Errors are caught and returned as `{"error": ...}` — a tool can never throw
into the chat.

| Do | Tool |
|---|---|
| discovery | `search_products`, `recommend_models`, `compare_products` |
| decide | `find_stores`, `compare_stores`, `check_open` |
| act | `contact_store`, `contact_status`, `suggest_alternatives` |
| execute | `locate_in_mall`, `plan_visit` |

`find_stores` returns, per shop: `price`, `price_valid`, `price_age_days`, `price_age_bucket`,
`availability`, `open_state` **at the arrival ETA**, `installment_confirmed`, `distance_km`,
`walk_minutes`, `mall`, `floor`, `unit`, `addr_confidence`, `score`, `score_breakdown`, `reasons[]`.

## 3. Guardrails (`agent/guardrails.py`)

1. Collect every number from every tool result of the turn (recursively).
2. Extract numbers from the generated text (Persian + ASCII digits, separators).
3. Remove sentences with numbers that cannot be traced to a tool result.
4. Never let the agent say "موجود است" for an offer that was only *listed*.

Covered by tests: `test_guardrail_flags_invented_number`,
`test_guardrail_allows_numbers_from_tools`, `test_sanitize_drops_only_bad_sentence`.

## 4. Composition (`agent/compose.py`)

Persian copy that separates the three facts the master prompt demands:

> «۲٬۴۵۰٬۰۰۰ تومان — قیمت ثبت‌شده ۱۲ روز پیش — موجودی نامشخص»

and asks the next question instead of dumping everything («رسیدن شما حدود ۱۴ دقیقه است؛ ساعت ۲۰:۳۰
باز است. می‌خواهید موجودی را تأیید کنم؟»).

## 5. Evaluation (`backend/app/tests/test_eval.py`)

Each scenario asserts: extracted constraints → tools called → cards emitted → latency → no
hallucinated numbers. They run in CI in degraded mode, which is also the demo-safe mode.

```bash
cd backend && python -m pytest app/tests/test_eval.py -v
```

## 6. Adding a provider

`agent/llm.py` has three clients behind one interface: `AnthropicClient`, `OpenAICompatClient`
(works with OpenAI, OpenRouter, and Iranian OpenAI-compatible gateways via `LLM_BASE_URL`), and
`NoLLM`. To add another, implement `complete(messages, tools) -> {text, tool_calls}` and register it
in `get_client()`.
