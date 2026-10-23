"""API contract tests. Skipped when the serving DB has not been built."""
import time
from time import sleep

import pytest
from fastapi.testclient import TestClient

from app.db import engine
from app.main import app

pytestmark = pytest.mark.skipif(not engine.is_ready(), reason="database not built")

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["db_ready"] is True


def test_ready_reports_counts():
    r = client.get("/api/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["shops"] > 0 and body["products"] > 0


def test_meta_flags_simulation():
    body = client.get("/api/meta").json()
    assert body["demo"]["simulated_contact"] is True
    assert "notice_fa" in body["demo"]
    assert body["default_location"]["lat"] > 35


def test_search_returns_products_with_price_stats():
    r = client.post("/api/search", json={"query": "هدفون بلوتوثی", "limit": 5})
    assert r.status_code == 200
    items = r.json()["products"]
    assert items
    first = items[0]
    assert first["product_id"].startswith("product_")
    assert "price_median" in first
    assert r.json()["took_ms"] >= 0


def test_search_empty_query_does_not_500():
    r = client.post("/api/search", json={"query": "", "limit": 3})
    assert r.status_code == 200


def test_stores_payload_has_transparency_fields():
    pid = client.post("/api/search", json={"query": "هدفون", "limit": 1}).json()["products"][0]["product_id"]
    r = client.post("/api/stores", json={"product_id": pid, "lat": 35.69, "lon": 51.40, "limit": 5})
    assert r.status_code == 200
    stores = r.json()["stores"]
    assert stores
    s = stores[0]
    for key in ("price_valid", "price_age_bucket", "availability", "open_state",
                "installment_confirmed", "reasons", "score_breakdown"):
        assert key in s
    # never conflate: availability must not be "confirmed_*" for a listed offer
    assert s["availability"] == "listed"


def test_installment_filter_is_strict():
    pid = client.post("/api/search", json={"query": "هدفون", "limit": 1}).json()["products"][0]["product_id"]
    body = client.post("/api/stores", json={"product_id": pid, "installment": "confirmed"}).json()
    assert all(s["installment_confirmed"] for s in body["stores"])


def test_contact_flow_reaches_a_terminal_state():
    pid = client.post("/api/search", json={"query": "هدفون", "limit": 1}).json()["products"][0]["product_id"]
    stores = client.post("/api/stores", json={"product_id": pid, "limit": 6}).json()["stores"]
    assert stores
    # pick the shop that will answer soonest so the suite stays fast
    threads = [
        client.post("/api/contact", json={"shop_id": s["shop_id"], "product_id": pid,
                                          "intent": "price_stock"}).json()
        for s in stores[:4]
    ]
    thread = min(threads, key=lambda t: t.get("reply_at") or t["timeout_at"])
    assert thread["simulated"] is True
    terminal = {"confirmed", "out_of_stock", "no_reply", "needs_followup", "replied"}
    status = thread["status"]
    deadline = thread["timeout_at"]
    for _ in range(120):
        if status in terminal:
            break
        sleep(0.5)
        status = client.get(f"/api/contact/{thread['thread_id']}").json()["status"]
    assert status in terminal, f"stuck at {status} (deadline {deadline})"


def test_agent_endpoint_returns_cards():
    r = client.post("/api/agent", json={"message": "هدفون زیر ۳ میلیون"})
    assert r.status_code == 200
    body = r.json()
    assert body["cards"]
    assert body["meta"]["degraded"] is True


def test_agent_stream_is_sse():
    with client.stream("POST", "/api/agent/stream", json={"message": "سلام"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        chunk = next(r.iter_text())
        assert chunk.startswith("data: ")


def test_unknown_product_404():
    assert client.get("/api/products/nope").status_code == 404


def test_malformed_body_is_422_not_500():
    assert client.post("/api/stores", json={"wrong": 1}).status_code == 422
