#!/usr/bin/env python3
"""Pick a good demo product and print the exact facts the recording will show.

    python scripts/seed_demo.py [base_url]

It contacts every shop that carries the chosen product (the simulator is deterministic),
so it also tells you which shop answers, which one stays silent, and how long that takes.
"""
from __future__ import annotations

import sys
import time

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
QUERIES = ["هدفون بلوتوثی", "تلویزیون", "گوشی سامسونگ", "لپ تاپ", "ماگمای میکروویو"]


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)
    print(f"▶ demo seed against {BASE}\n")

    best = None
    for q in QUERIES:
        try:
            products = c.post("/api/search", json={"query": q, "limit": 12}).json()["products"]
        except Exception as exc:  # noqa: BLE001
            print(f"  ! search failed for {q}: {exc}")
            continue
        for p in products:
            stores = c.post("/api/stores", json={
                "product_id": p["product_id"], "lat": 35.6949, "lon": 51.4071,
                "radius_km": 15, "limit": 12}).json()["stores"]
            malls = [s for s in stores if (s.get("mall") or {}).get("name")]
            inst = [s for s in stores if s.get("installment_confirmed")]
            closed = [s for s in stores if s.get("open_on_arrival") == "closed"]
            score = len(stores) * 2 + len(malls) + len(inst) * 2 + len(closed)
            if best is None or score > best[0]:
                best = (score, q, p, stores)

    if not best:
        print("no product found — is the database built?")
        return 1

    _, query, product, stores = best
    print(f"query      : {query}")
    print(f"product    : {product['title']}")
    print(f"id         : {product['product_id']}")
    fmt = lambda v: f"{v:,.0f}" if v is not None else "نامشخص"
    print(f"price      : {fmt(product.get('price_min'))} … {fmt(product.get('price_max'))} "
          f"(median {fmt(product.get('price_median'))})")
    print(f"shops      : {len(stores)}\n")

    print("shops the demo will show:")
    for s in stores:
        mall = (s.get("mall") or {})
        where = ", ".join(x for x in [mall.get("name"), mall.get("floor") and f"طبقه {mall['floor']}",
                                      mall.get("unit") and f"واحد {mall['unit']}"] if x) or "—"
        print(f"  • {s['name']}")
        price = f"{s['price']:,.0f}" if s.get("price") is not None else "نامشخص"
        print(f"      price {price} | {s['price_age_bucket']} | "
              f"open at arrival: {s['open_on_arrival']} | installment: {s['installment_confirmed']}")
        print(f"      {where} | {s['distance_km']} km ({s['travel_minutes']} min)")
        print(f"      id {s['shop_id']}")

    print("\ncontact behaviour (real time):")
    threads = []
    for s in stores:
        t = c.post("/api/contact", json={
            "shop_id": s["shop_id"], "product_id": product["product_id"],
            "intent": "price_stock"}).json()
        threads.append((s, t))
        print(f"  • {s['name']:<35} → {t['status']:<10} "
              f"reply_at={t.get('reply_at') or '—'} timeout={t['timeout_at']}")

    fastest = min(threads, key=lambda pair: pair[1].get("reply_at") or "9999")
    silent = max(threads, key=lambda pair: pair[1].get("reply_at") or "9999")
    print(f"\n  use for the answering beat : {fastest[0]['name']}")
    print(f"  use for the no-reply beat  : {silent[0]['name']}")

    print("\nwaiting for the fastest thread to finish (demo realism check)…")
    deadline = time.time() + 60
    while time.time() < deadline:
        st = c.get(f"/api/contact/{fastest[1]['thread_id']}").json()
        if st["status"] not in ("sent", "seen", "queued"):
            print(f"  final status: {st['status']}  parsed={st.get('parsed')}")
            break
        time.sleep(2)

    print("\nPaste into the search box for the same result:")
    print(f"  {query}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
