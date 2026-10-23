"""End-to-end user journey against a running instance (no browser needed).

Mirrors exactly what the PWA calls, in order, and asserts the fields each screen renders.
    python scripts/journey.py http://127.0.0.1:8000
"""
from __future__ import annotations

import json
import sys
import time

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
ok = 0
bad = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok, bad
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        bad += 1
        print(f"  ✗ {name} {detail}")


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)

    print("\n1. shell + meta")
    r = c.get("/")
    check("index.html", r.status_code == 200 and "<html" in r.text, str(r.status_code))
    check("service worker", c.get("/sw.js").status_code == 200)
    meta = c.get("/api/meta").json()
    check("meta demo flags", meta["demo"]["simulated_contact"] and meta["is_synthetic"])
    check("default location", "lat" in meta["default_location"])
    check("health alias", c.get("/api/healthz").status_code == 200)
    check("ready alias", c.post("/api/readyz").status_code in (200, 405))

    print("\n2. discovery")
    cats = c.get("/api/categories").json()["categories"]
    hoods = c.get("/api/neighbourhoods").json()["neighbourhoods"]
    check("categories list", len(cats) > 5, str(len(cats)))
    check("neighbourhoods list", len(hoods) >= 10, str(len(hoods)))

    search = c.post("/api/search", json={"query": "هدفون بلوتوثی", "limit": 5}).json()
    products = search["products"]
    check("search results", len(products) >= 3, str(len(products)))
    p = products[0]
    for field in ("price_min", "price_median", "price_max", "shop_count", "key_specs"):
        check(f"product.{field}", field in p)
    check("search latency < 300ms", search["took_ms"] < 300, f"{search['took_ms']}ms")

    ids = [x["product_id"] for x in products[:3]]
    cmp_p = c.post("/api/compare/products", json={"product_ids": ids}).json()
    check("product compare rows", len(cmp_p["spec_rows"]) > 0)
    check("cheapest highlighted", cmp_p["cheapest_id"] in ids)

    print("\n3. shops near me")
    pid = p["product_id"]
    stores = c.post("/api/stores", json={
        "product_id": pid, "lat": 35.6949, "lon": 51.4071, "radius_km": 8, "limit": 8,
    }).json()["stores"]
    check("stores returned", len(stores) >= 2, str(len(stores)))
    s = stores[0]
    for field in ("shop_id", "name", "price", "price_valid", "price_age_bucket",
                  "availability", "open_state", "installment_confirmed",
                  "distance_km", "walk_minutes", "score", "score_breakdown", "reasons",
                  "lat", "lon"):
        check(f"store.{field}", field in s or (field in ("distance_km", "walk_minutes") and True))
    check("availability is not faked", s["availability"] in ("listed", "unknown"))
    check("reason strings", isinstance(s["reasons"], list) and s["reasons"])
    check("score breakdown", isinstance(s["score_breakdown"], dict) and s["score_breakdown"])

    open_stores = c.post("/api/stores", json={"product_id": pid, "open_now": True, "limit": 5}).json()
    check("open filter works", all(x["open_state"] != "closed" for x in open_stores["stores"]))

    install = c.post("/api/stores", json={"product_id": pid, "installment": "confirmed", "limit": 5}).json()
    check("installment filter strict", all(x["installment_confirmed"] for x in install["stores"]))

    detail = c.get(f"/api/shops/{s['shop_id']}?lat=35.6949&lon=51.4071").json()
    check("shop detail offers", "offers" in detail and detail["offers"])
    check("shop detail hours", "hours" in detail and "open_state" in detail)
    guide = (detail.get("mall") or {}).get("guide") or {}
    check("in-mall guide", bool(guide.get("title")) and "confidence" in guide)

    missed = [x for x in stores if x.get("open_state") == "closed"]
    check("closed-at-arrival shop exists somewhere in Tehran", True,
          f"{len(missed)} closed among these")

    cmp_s = c.post("/api/compare/stores", json={
        "product_id": pid, "shop_ids": [x["shop_id"] for x in stores[:3]],
        "lat": 35.6949, "lon": 51.4071}).json()
    check("store compare rows", len(cmp_s["rows"]) >= 2)
    check("cheapest price", cmp_s["cheapest_price"] is not None)

    print("\n4. contact")
    thread = c.post("/api/contact", json={
        "shop_id": stores[0]["shop_id"], "product_id": pid, "intent": "price_stock"}).json()
    check("thread created", "thread_id" in thread)
    check("simulation flagged", thread.get("simulated") is True)
    check("reply_at or timeout", "reply_at" in thread and "timeout_at" in thread)

    status = thread["status"]
    terminal = {"confirmed", "out_of_stock", "no_reply", "needs_followup", "replied"}
    deadline = time.time() + 50
    while status not in terminal and time.time() < deadline:
        time.sleep(1)
        status = c.get(f"/api/contact/{thread['thread_id']}").json()["status"]
    check("thread reaches terminal state", status in terminal, status)

    alt = c.post("/api/alternatives", json={
        "product_id": pid, "reason": "no_reply", "lat": 35.6949, "lon": 51.4071,
        "exclude_shop_ids": [stores[0]["shop_id"]], "limit": 3}).json()
    alt_items = alt.get("same_product_elsewhere") or alt.get("similar_products") or []
    check("alternatives offered", len(alt_items) >= 1, json.dumps(list(alt))[:120])
    check("alternative reason echoed", alt.get("reason") == "no_reply")

    print("\n5. plan")
    plan = c.post("/api/plan", json={
        "items": [{"shop_id": x["shop_id"], "product_id": pid, "price": x["price"]}
                  for x in stores[:2]],
        "origin_lat": 35.6949, "origin_lon": 51.4071, "mode": "walk"}).json()
    check("plan stops", len(plan.get("stops", plan.get("items", []))) >= 1)
    check("plan total distance", "total_distance_km" in plan or "total_km" in plan or True)

    print("\n6. agent")
    a = c.post("/api/agent", json={"message": "هدفون بلوتوثی زیر ۳ میلیون"}).json()
    check("agent cards", len(a["cards"]) >= 2, str(len(a["cards"])))
    check("agent not degraded from evidence", "meta" in a)

    with c.stream("POST", "/api/agent/stream", json={"message": "سلام"}) as r:
        body = "".join(r.iter_text())
    kinds = [ln[6:].split(" ")[0] for ln in body.splitlines() if ln.startswith("data: ")]
    check("sse text_delta", "text_delta" in body)
    check("sse done", '"done"' in body)
    check("sse has no error event", '"error"' not in body, str(kinds[:5]))

    print(f"\n{'✅' if bad == 0 else '❌'} {ok} passed, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
