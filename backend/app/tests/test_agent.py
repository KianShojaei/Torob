import asyncio

import pytest

from app.agent.guardrails import check_text, collect_numbers, sanitize
from app.agent.orchestrator import run
from app.agent.understand import understand


def collect(async_gen):
    async def _go():
        return [e async for e in async_gen]

    return asyncio.run(_go())


# ------------------------------------------------------------------ NLU
def test_understands_persian_budget_and_category():
    n = understand("گوشی سامسونگ تا ۲۰ میلیون قسطی")
    assert n.category == "گوشی موبایل"
    assert n.brand == "سامسونگ"
    assert n.budget_max == 20_000_000
    assert n.installment_only is True


def test_installment_word_not_matched_inside_mikhaham():
    # "میخوام" contains "وام" — must not flip the installment filter
    n = understand("هدفون خوب میخوام")
    assert n.installment_only is False


def test_budget_range_parsing():
    n = understand("بین ۲ تا ۴ میلیون اسپیکر")
    assert n.budget_min == 2_000_000
    assert n.budget_max == 4_000_000


def test_usage_and_neighborhood():
    n = understand("کتونی برای پیاده‌روی نزدیک ونک", neighborhoods=["ونک", "شیخ هادی"])
    assert n.neighborhood == "ونک"
    assert n.usage in ("پیاده روی", "پیاده‌روی")


def test_greeting_asks_a_question():
    events = collect(run("سلام"))
    text = next(e["text"] for e in events if e["type"] == "text_delta")
    assert "؟" in text


# ------------------------------------------------------------------ agent
@pytest.mark.skipif(not __import__("app.db.engine", fromlist=["x"]).is_ready(),
                    reason="database not built")
def test_agent_returns_cards_for_product_query():
    events = collect(run("هدفون بلوتوثی زیر ۳ میلیون"))
    kinds = [e["card"]["kind"] for e in events if e["type"] == "card"]
    assert "product_list" in kinds
    assert "store_list" in kinds
    done = next(e for e in events if e["type"] == "done")
    assert done["degraded"] is True  # CI runs with LLM_PROVIDER=none


@pytest.mark.skipif(not __import__("app.db.engine", fromlist=["x"]).is_ready(),
                    reason="database not built")
def test_agent_text_has_no_invented_prices():
    events = collect(run("لپ تاپ تا ۵۰ میلیون"))
    text = next(e["text"] for e in events if e["type"] == "text_delta")
    results = [e["card"]["payload"] for e in events if e["type"] == "card"]
    ok, violations = check_text(text, results)
    assert ok, violations


# ------------------------------------------------------------------ guardrail
def test_guardrail_flags_invented_number():
    ok, bad = check_text("قیمت این فروشگاه ۸٬۷۶۵٬۰۰۰ تومان است.", [{"price": 2_000_000}])
    assert not ok and bad


def test_guardrail_allows_numbers_from_tools():
    ok, bad = check_text("قیمت ۲٬۰۰۰٬۰۰۰ تومان است.", [{"price": 2_000_000}])
    assert ok and not bad


def test_sanitize_drops_only_bad_sentence():
    text = "سلام. قیمت ۹٬۹۹۹٬۹۹۹ تومان است. فروشگاه باز است."
    out = sanitize(text, [{"price": 1_000_000}])
    assert "۹٬۹۹۹٬۹۹۹" not in out
    assert "سلام" in out


def test_collect_numbers_from_nested_payload():
    nums = collect_numbers({"a": [{"price": 1_250_000}], "b": "۱۲۳۴"}, set())
    assert "1250000" in nums
