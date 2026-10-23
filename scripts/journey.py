#!/usr/bin/env python3
"""End-to-end user journey against a running server (no browser needed).

Mirrors exactly what the PWA does, in order, and fails loudly if any promise breaks:

    search → shortlist → stores → compare → shop detail → contact → alternatives
           → visit plan → agent (JSON and SSE)

    python scripts/journey.py http://127.0.0.1:8000
"""
from __future__ import annotations

import json
import sys
import time

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
OK, BAD = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global OK, BAD
    if cond:
        OK += 1
        print(f"  \033[32m✓\033[0m {name}")
    else:
        BAD += 1
        print(f"  \033[31m✗\033[0m {name} — {detail}")


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)

    print("\n1. shell")
    r = c.get("/")
    check("index.html", r.status_code == 200 and "<html" in r.text, str(r.status_code))
    check("service worker", c.get("/sw.js").status_code == 200)
    check("manifest", c.get("/manifest.webmanifest").status_code == 200)
    check("health", c.get("/api/health").json()["db_ready"] is True)
    meta = c.get("/api/meta").json()
    check("meta says demo honestly", meta["demo"]["simulated_contact"] is True)
    check("default location", "lat" in meta["default_location"])
    check("health alias", c.get("/api/healthz").status_code == 200)

    print("\n2. discovery")
    check("categories", len(c.get("/api/categories").json()["categories"]) > 3)
    check("neighbourhoods", len(c.get("/api/neighbourhoods").json()["neighbourhoods"]) > 3)
    search = c.post("/api/search", json={"query": "هدفون بلوتوثی", "limit": 6}).json()
    products = search["products"]
    check("search returns products", len(products) >= 2, str(len(products)))
    p = products[0]
    check("product has price stats", p.get("price_median") is not None)
    check("product has key specs", isinstance(p.get("key_specs"), (list, dict)))
    ids = [x["product_id"] for x in products[:3]]
    cmp_p = c.post("/api/compare/products", json={"product_ids": ids}).json()
    check("compare products", len(cmp_p.get("products", [])) == len(ids))

    print("\n3. stores")
    pid = p["product_id"]
    body = {"product_id": pid, "lat": 35.6949, "lon": 51.4071, "radius_km": 10, "limit": 8}
    stores = c.post("/api/stores", json=body).json()["stores"]
    check("stores found", len(stores) >= 1, str(len(stores)))
    s = stores[0]
    for field in ("price", "price_valid", "price_age_bucket", "availability",
                  "open_state", "open_on_arrival", "installment_confirmed",
                  "distance_km", "score", "score_breakdown", "reasons"):
        check(f"store.{field}", field in s)
    check("availability is never faked", s["availability"] in ("listed", "unknown"))
    check("score breakdown is visible", isinstance(s["score_breakdown"], dict))
    check("reasons are Persian", any(any("\u0600" <= ch <= "\u06ff" for ch in r_) for r_ in s["reasons"]))
    closed = c.post("/api/stores", json={**body, "open_now": True}).json()["stores"]
    check("open-now filter never returns closed shops",
          all(x["open_state"] != "closed" for x in closed))
    inst = c.post("/api/stores", json={**body, "installment": "confirmed"}).json()["stores"]
    check("installment filter is strict", all(x["installment_confirmed"] for x in inst))

    detail = c.get(f"/api/shops/{s['shop_id']}?lat=35.6949&lon=51.4071").json()
    check("shop detail has offers", len(detail.get("offers", [])) >= 1)
    check("shop detail has hours structure", "hours" in detail)
    guide = (detail.get("mall") or {}).get("guide") or {}
    check("in-mall guide has confidence", "confidence" in guide)

    cmp_s = c.post("/api/compare/stores", json={
        "product_id": pid, "shop_ids": [x["shop_id"] for x in stores[:3]],
        "lat": 35.6949, "lon": 51.4071}).json()
    check("compare stores", len(cmp_s.get("rows", [])) >= 1)

    print("\n4. contact")
    thread = c.post("/api/contact", json={
        "shop_id": s["shop_id"], "product_id": pid, "intent": "price_stock"}).json()
    check("thread created", bool(thread.get("thread_id")))
    check("thread is flagged simulated", thread.get("simulated") is True)
    status = thread["status"]
    terminal = {"confirmed", "out_of_stock", "no_reply", "needs_followup", "replied"}
    deadline = time.time() + 55
    while status not in terminal and time.time() < deadline:
        time.sleep(1.5)
        status = c.get(f"/api/contact/{thread['thread_id']}").json()["status"]
    check("thread reaches a terminal state", status in terminal, status)

    alt = c.post("/api/alternatives", json={
        "product_id": pid, "reason": "no_reply",
        "exclude_shop_ids": [s["shop_id"]], "lat": 35.6949, "lon": 51.4071}).json()
    check("alternatives exist", bool(alt.get("same_product_elsewhere")
                                     or alt.get("similar_products")))

    print("\n5. plan")
    plan = c.post("/api/plan", json={
        "items": [{"shop_id": x["shop_id"], "product_id": pid} for x in stores[:2]],
        "origin_lat": 35.6949, "origin_lon": 51.4071}).json()
    check("plan has stops", len(plan.get("stops", [])) >= 1)
    check("plan has warnings list", isinstance(plan.get("warnings"), list))

    print("\n6. agent")
    a = c.post("/api/agent", json={"message": "هدفون بلوتوثی زیر ۳ میلیون"}).json()
    check("agent returns cards", len(a.get("cards", [])) >= 1)
    check("agent reports tool calls", len(a.get("tool_calls", [])) >= 1)
    check("agent meta", "degraded" in a.get("meta", {}))

    with c.stream("POST", "/api/agent/stream", json={"message": "سلام"}) as resp:
        events = [ln for ln in resp.iter_lines() if ln.startswith("data: ")]
    kinds = {json.loads(e[6:]).get("type") for e in events}
    check("SSE text_delta", "text_delta" in kinds, str(kinds))
    check("SSE done", "done" in kinds)
    check("SSE no error", "error" not in kinds)

    print(f"\n{'✅' if BAD == 0 else '❌'} {OK} passed, {BAD} failed")
    return 1 if BAD else 0


if __name__ == "__main__":
    raise SystemExit(main())
