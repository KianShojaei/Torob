"""Agent evaluation scenarios (master prompt §7 "a small set of agent evaluation
scenarios with assertions on tool calls & no hallucinated data").

Each scenario states the Persian utterance, the constraints that must be
extracted, and the tools that must run. Run against the live DB.
"""
import asyncio

import pytest

from app.agent.orchestrator import run
from app.agent.understand import understand
from app.db import engine

pytestmark = pytest.mark.skipif(not engine.is_ready(), reason="database not built")

SCENARIOS = [
    {
        "utterance": "هدفون بلوتوثی زیر ۳ میلیون",
        "expect": {"category": "هدفون، هندزفری و اسپیکر", "budget_max": 3_000_000},
        "tools": {"search_products", "find_stores"},
        "cards": {"product_list", "store_list"},
    },
    {
        "utterance": "گوشی سامسونگ تا ۲۰ میلیون قسطی",
        "expect": {"brand": "سامسونگ", "installment_only": True},
        "tools": {"search_products"},
        "cards": {"product_list"},
    },
    {
        "utterance": "یخچال ساید بای ساید نزدیک سعادت‌آباد",
        "expect": {"category": "یخچال و فریزر", "neighborhood": "سعادت‌آباد"},
        "tools": {"search_products", "find_stores"},
        "cards": {"store_list"},
    },
    {
        "utterance": "لپ تاپ برای برنامه نویسی تا ۵۰ میلیون",
        "expect": {"category": "لپ‌تاپ و کامپیوتر", "budget_max": 50_000_000},
        "tools": {"search_products", "find_stores"},
        "cards": {"product_list"},
    },
]


def collect(gen):
    async def _go():
        return [e async for e in gen]

    return asyncio.run(_go())


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["utterance"] for s in SCENARIOS])
def test_scenario_extracts_constraints(scenario):
    need = understand(scenario["utterance"], neighborhoods=["سعادت‌آباد", "ونک"])
    for key, value in scenario["expect"].items():
        assert getattr(need, key) == value, f"{key}: {getattr(need, key)!r} != {value!r}"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["utterance"] for s in SCENARIOS])
def test_scenario_calls_expected_tools_and_cards(scenario):
    events = collect(run(scenario["utterance"]))
    tools_called = {e["name"] for e in events if e["type"] == "tool_status"}
    assert scenario["tools"] <= tools_called
    card_kinds = {e["card"]["kind"] for e in events if e["type"] == "card"}
    assert scenario["cards"] <= card_kinds


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["utterance"] for s in SCENARIOS])
def test_scenario_finishes_quickly_and_offline(scenario):
    events = collect(run(scenario["utterance"]))
    done = next(e for e in events if e["type"] == "done")
    assert done["degraded"] is True
    assert done["latency_ms"] < 3000


def test_installment_request_filters_stores():
    events = collect(run("گوشی قسطی تا ۲۰ میلیون"))
    store_cards = [e["card"]["payload"] for e in events
                   if e["type"] == "card" and e["card"]["kind"] == "store_list"]
    if store_cards:
        for store in store_cards[0]["stores"]:
            assert store["installment_confirmed"] is True
