import time
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health_and_init():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["db_exists"] is True

    init_r = client.get("/api/init")
    assert init_r.status_code == 200
    data = init_r.json()
    assert len(data["neighborhoods"]) > 0
    assert data["neighborhoods"][0]["location_label"] == "فردوسی"

def test_search_and_recommend_headphones():
    r = client.get("/api/products/recommend", params={"q": "هدفون بی سیم"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["recommended_models"]) > 0
    first = data["recommended_models"][0]
    assert "persian_title" in first
    assert "why_suggested" in first

def test_find_stores_and_strict_3part_price():
    rec = client.get("/api/products/recommend", params={"q": "گوشی موبایل"}).json()
    prod_id = rec["recommended_models"][0]["product_id"]

    st_res = client.get("/api/stores/find", params={"product_id": prod_id}).json()
    assert st_res["total_stores_found"] > 0
    st = st_res["stores"][0]
    # Verify strict 3-part price transparency
    assert "price_part_1_recorded_fa" in st
    assert "price_part_2_age_fa" in st
    assert "price_part_3_availability_fa" in st
    assert "score_breakdown" in st

def test_installment_filter_strict():
    rec = client.get("/api/products/recommend", params={"q": "گوشی موبایل", "installment_only": True}).json()
    assert len(rec["recommended_models"]) > 0
    prod_id = rec["recommended_models"][0]["product_id"]

    st_res = client.get(
        "/api/stores/find",
        params={"product_id": prod_id, "installment_mode": "all_installment"},
    ).json()
    for s in st_res["stores"]:
        assert s["has_installment"] is True
        assert s["installment_level"] in ("in_person", "declared")

def test_seller_simulator_and_failover():
    rec = client.get("/api/products/recommend", params={"q": "هدفون بی سیم"}).json()
    prod_id = rec["recommended_models"][0]["product_id"]
    st_res = client.get("/api/stores/find", params={"product_id": prod_id}).json()
    shop_ids = [s["shop_id"] for s in st_res["stores"][:2]]

    start_r = client.post("/api/contact/start", json={"shop_ids": shop_ids, "product_id": prod_id})
    assert start_r.status_code == 200
    convs = start_r.json()["conversations"]
    assert len(convs) == len(shop_ids)

    poll_r = client.post(
        "/api/contact/poll",
        json={"conversation_ids": [c["conversation_id"] for c in convs]},
    )
    assert poll_r.status_code == 200
    assert "conversations" in poll_r.json()

def test_agent_chat_endpoint():
    r = client.post(
        "/api/agent/chat",
        json={"message": "سلام، یه هدفون بی‌سیم خوب تا ۵ میلیون می‌خوام که قسطی هم بشه خرید"},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["reply_fa"]) > 10
    assert len(data["cards"]) > 0
    assert data["detected_filters"]["installment_only"] is True
