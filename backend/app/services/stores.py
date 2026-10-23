"""Store finding + transparent ranking (master prompt §5.3 tools 5–6, §5.4).

Ranking weights are configurable and every card carries `reasons[]` explaining
the position. Prices, distances, hours and confirmation states are always kept as
three separate facts (§6.3).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from app.config import settings
from app.db.engine import connection
from app.services.address import find_it_text, parse_address
from app.services.geo import best_mode, describe_distance, haversine_km, travel_minutes
from app.services.hours import open_at_arrival, open_status, parse_week, week_display
from app.services.pricing import age_bucket, relative_to_market

DEFAULT_WEIGHTS = {
    "price": 0.30,
    "distance": 0.24,
    "open": 0.16,
    "freshness": 0.10,
    "confirmation": 0.10,
    "installment": 0.04,
    "warranty": 0.03,
    "confidence": 0.03,
}

SORT_PRESETS = {
    "balanced": ("بهترین ترکیب", DEFAULT_WEIGHTS),
    "cheapest": ("ارزان‌ترین", {"price": 0.62, "distance": 0.10, "open": 0.10,
                                "freshness": 0.06, "confirmation": 0.06,
                                "installment": 0.03, "warranty": 0.02, "confidence": 0.01}),
    "nearest": ("نزدیک‌ترین", {"distance": 0.62, "price": 0.10, "open": 0.10,
                               "freshness": 0.06, "confirmation": 0.06,
                               "installment": 0.03, "warranty": 0.02, "confidence": 0.01}),
    "trusted": ("مطمئن‌ترین", {"confirmation": 0.30, "freshness": 0.24, "open": 0.16,
                               "confidence": 0.12, "price": 0.08, "distance": 0.06,
                               "installment": 0.02, "warranty": 0.02}),
    "open_now": ("باز الان", {"open": 0.50, "distance": 0.18, "price": 0.12,
                              "freshness": 0.08, "confirmation": 0.06,
                              "installment": 0.02, "warranty": 0.02, "confidence": 0.02}),
}


@dataclass
class StoreFilters:
    lat: float | None = None
    lon: float | None = None
    radius_km: float = 6.0
    mode: str = "car"
    max_price: float | None = None
    min_price: float | None = None
    installment: str = "off"          # off | confirmed | any
    open_now: bool = False
    open_on_arrival: bool = False
    fresh_only: bool = False
    mall_only: bool = False
    neighborhood: str | None = None
    sort: str = "balanced"
    limit: int = 30
    arrival_at: datetime | None = None


@dataclass
class StoreOffer:
    shop_id: str
    name: str
    name_is_real: bool
    category: str | None
    location_label: str | None
    address: str | None
    distance_km: float
    distance_note: str
    travel_minutes: int
    mode: str
    price: float | None
    price_valid: bool
    price_age_days: int | None
    price_age_label: str
    price_age_bucket: str
    availability: str                  # listed | confirmed_in_stock | confirmed_out_of_stock | unknown
    availability_source: str | None
    availability_at: str | None
    market_position: dict | None
    open_state: str
    opens_at: str | None
    closes_at: str | None
    minutes_until_close: int | None
    open_on_arrival: str | None
    weekly_hours_known: bool
    installment_confirmed: bool
    installment_declared: bool
    installment_providers: list[str]
    fast_delivery: str
    mall: dict
    score: float
    score_breakdown: dict
    reasons: list[str]
    flags: list[str]
    hours: list[dict] = field(default_factory=list)


def _decode_json(raw, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _shop_row(shop_id: str):
    with connection() as conn:
        return conn.execute("SELECT * FROM shops WHERE id=?", (shop_id,)).fetchone()


def find_stores(product_id: str, filters: StoreFilters) -> list[StoreOffer]:
    sql = [
        """SELECT o.id offer_id, o.price, o.price_valid, o.age_days, o.age_bucket,
                  o.last_changed_at, o.warranty_months,
                  s.*
           FROM offers o JOIN shops s ON s.id = o.shop_id
           WHERE o.product_id = ?"""
    ]
    params: list = [product_id]

    if filters.max_price:
        sql.append("AND (o.price_valid = 0 OR o.price <= ?)")
        params.append(filters.max_price)
    if filters.min_price:
        sql.append("AND (o.price_valid = 0 OR o.price >= ?)")
        params.append(filters.min_price)
    if filters.installment == "confirmed":
        sql.append("AND s.has_in_person_installment = 1")
    elif filters.installment == "any":
        sql.append("AND s.has_any_installment = 1")
    if filters.fresh_only:
        sql.append("AND o.age_days IS NOT NULL AND o.age_days <= 7")
    if filters.mall_only:
        sql.append("AND s.mall_key IS NOT NULL")
    if filters.neighborhood:
        sql.append("AND s.location_label = ?")
        params.append(filters.neighborhood)

    with connection() as conn:
        rows = conn.execute(" ".join(sql), params).fetchall()

    if not rows:
        return []

    prices = [r["price"] for r in rows if r["price_valid"]]
    valid_prices = sorted(prices)
    n = len(valid_prices)

    def pct(q: float) -> float:
        if not n:
            return 0.0
        k = (n - 1) * q
        lo, hi = int(k), min(int(k) + 1, n - 1)
        return valid_prices[lo] + (valid_prices[hi] - valid_prices[lo]) * (k - lo)

    market = None
    if n:
        market = {"count": n, "min": valid_prices[0], "median": pct(0.5),
                  "p75": pct(0.75), "max": valid_prices[-1]}

    now = settings.now_tehran
    weights = SORT_PRESETS.get(filters.sort, SORT_PRESETS["balanced"])[1]
    cheapest = valid_prices[0] if valid_prices else None
    out: list[StoreOffer] = []

    for r in rows:
        shop = dict(r)
        lat, lon = shop.get("lat"), shop.get("lon")
        if filters.lat is not None and lat is not None:
            dist = haversine_km(filters.lat, filters.lon, lat, lon)
        else:
            dist = float("inf")
        mode = best_mode(dist) if filters.mode == "auto" else filters.mode
        minutes = travel_minutes(dist, mode) if dist != float("inf") else 0

        week = parse_week(_decode_json(shop.get("weekly_hours"), {}))
        now_status = open_status(week, now)
        arrival = open_at_arrival(week, now, minutes)

        price = shop.get("price")
        valid = bool(shop.get("price_valid"))
        days = shop.get("age_days")
        bucket, age_label = age_bucket(days)

        providers = _decode_json(shop.get("installment_providers"), [])
        addr = find_it_text(parse_address(shop.get("address")), shop.get("name"))

        # ---- score components, all in [0, 1] ----
        price_score = 0.0
        if valid and cheapest and price:
            # cheapest candidate = 1.0, twice the cheapest = 0.0
            price_score = max(0.0, min(1.0, 1 - (price - cheapest) / max(1.0, cheapest)))

        distance_score = 0.0
        if dist != float("inf"):
            distance_score = max(0.0, 1 - dist / max(1.0, filters.radius_km))

        open_score = {"open": 1.0, "closed": 0.0, "unknown": 0.45}.get(now_status.state, 0.45)
        arrival_score = {"open": 1.0, "closed": 0.0, "unknown": 0.45}.get(arrival.state, 0.45)

        freshness_score = {"fresh": 1.0, "recent": 0.65, "old": 0.3,
                           "stale": 0.1, "unknown": 0.2}.get(bucket, 0.2)
        confirmation_score = 0.25  # listed only
        installment_score = 1.0 if shop.get("has_in_person_installment") else (
            0.5 if shop.get("has_any_installment") else 0.0)
        warranty_score = 1.0 if (shop.get("warranty_months") or 0) >= 12 else (
            0.5 if shop.get("warranty_months") else 0.0)
        confidence_score = float(shop.get("addr_confidence") or 0)
        if shop.get("name_is_real"):
            confidence_score = min(1.0, confidence_score + 0.2)

        breakdown = {
            "price": round(price_score, 3),
            "distance": round(distance_score, 3),
            "open": round(open_score, 3),
            "arrival": round(arrival_score, 3),
            "freshness": round(freshness_score, 3),
            "confirmation": round(confirmation_score, 3),
            "installment": round(installment_score, 3),
            "warranty": round(warranty_score, 3),
            "confidence": round(confidence_score, 3),
        }

        score = (
            weights["price"] * price_score
            + weights["distance"] * distance_score
            + weights["open"] * (0.4 * open_score + 0.6 * arrival_score
                                 if filters.open_on_arrival else open_score)
            + weights["freshness"] * freshness_score
            + weights["confirmation"] * confirmation_score
            + weights["installment"] * installment_score
            + weights["warranty"] * warranty_score
            + weights["confidence"] * confidence_score
        )

        # hard filters: never show a shop we know is closed when the user asked
        if filters.open_now and now_status.state != "open":
            continue
        if filters.open_on_arrival and arrival.state == "closed":
            continue

        # ---- human reasons (max 3, straight from the numbers) ----
        reasons: list[str] = []
        flags: list[str] = []
        if valid and cheapest and price == cheapest:
            reasons.append("ارزان‌ترین قیمت این محصول")
        elif valid and market and price and market["median"]:
            rel = relative_to_market(price, market)
            if rel and rel["tone"] == "good":
                reasons.append(f"{abs(rel['delta_pct']):.0f}٪ زیر میانه‌ی بازار")
        if dist != float("inf") and dist < filters.radius_km * 0.35:
            reasons.append(describe_distance(dist, minutes, mode))
        if now_status.state == "open":
            reasons.append(f"الان باز است تا {now_status.closes_at}")
        elif arrival.state == "open" and minutes:
            reasons.append(f"با رسیدن شما باز است (تا {arrival.closes_at})")
        elif arrival.state == "closed":
            flags.append("با رسیدن شما بسته می‌شود")
        if shop.get("has_in_person_installment"):
            reasons.append("خرید اقساطی حضوری تأییدشده")
        elif shop.get("has_any_installment"):
            reasons.append("اقساط اعلام‌شده (تأییدنشده)")
        if bucket in ("stale", "unknown"):
            flags.append("قیمت قدیمی یا بدون تاریخ")
        if now_status.state == "unknown":
            flags.append("ساعت کاری نامشخص")
        if not valid:
            flags.append("قیمت نامعتبر یا نامشخص")

        out.append(StoreOffer(
            shop_id=shop["id"],
            name=shop["name"],
            name_is_real=bool(shop["name_is_real"]),
            category=(_decode_json(shop.get("category_names"), []) or [None])[0],
            location_label=shop.get("location_label"),
            address=shop.get("address"),
            distance_km=round(dist, 2) if dist != float("inf") else -1,
            distance_note=describe_distance(dist, minutes, mode) if dist != float("inf") else "فاصله نامشخص",
            travel_minutes=minutes,
            mode=mode,
            price=price,
            price_valid=valid,
            price_age_days=days,
            price_age_label=age_label,
            price_age_bucket=bucket,
            availability="listed",
            availability_source=None,
            availability_at=None,
            market_position=relative_to_market(price, market) if (valid and market) else None,
            open_state=now_status.state,
            opens_at=now_status.opens_at,
            closes_at=now_status.closes_at,
            minutes_until_close=now_status.minutes_until_close,
            open_on_arrival=arrival.state if minutes else None,
            weekly_hours_known=bool(shop.get("hours_known")),
            installment_confirmed=bool(shop.get("has_in_person_installment")),
            installment_declared=bool(shop.get("has_any_installment")),
            installment_providers=providers if isinstance(providers, list) else [],
            fast_delivery=shop.get("supports_fast_delivery") or "unknown",
            mall={"name": shop.get("mall_name"), "floor": shop.get("floor"),
                  "unit": shop.get("unit"), "guide": addr},
            score=round(score, 4),
            score_breakdown=breakdown,
            reasons=reasons[:3],
            flags=flags,
            hours=week_display(week) if shop.get("hours_known") else [],
        ))

    out.sort(key=lambda s: -s.score)
    return out[: filters.limit]


def store_detail(shop_id: str, lat: float | None = None, lon: float | None = None) -> dict | None:
    row = _shop_row(shop_id)
    if not row:
        return None
    shop = dict(row)
    week = parse_week(_decode_json(shop.get("weekly_hours"), {}))
    now = settings.now_tehran
    status = open_status(week, now)
    addr = parse_address(shop.get("address"))
    dist = haversine_km(lat, lon, shop["lat"], shop["lon"]) if (lat and shop["lat"]) else -1

    other_offers = []
    with connection() as conn:
        rows = conn.execute(
            """SELECT p.id, p.title, p.image_urls, p.category, o.price, o.price_valid,
                      o.age_days, o.age_bucket
               FROM offers o JOIN products p ON p.id = o.product_id
               WHERE o.shop_id = ? ORDER BY o.price_valid DESC, o.price ASC LIMIT 24""",
            (shop_id,)).fetchall()
    for r in rows:
        images = _decode_json(r["image_urls"], [])
        bucket, label = age_bucket(r["age_days"])
        other_offers.append({
            "product_id": r["id"], "title": r["title"], "category": r["category"],
            "image": images[0] if images else None,
            "price": r["price"], "price_valid": bool(r["price_valid"]),
            "price_age_label": label, "price_age_bucket": bucket,
        })

    return {
        "shop_id": shop["id"],
        "name": shop["name"],
        "name_is_real": bool(shop["name_is_real"]),
        "address": shop.get("address"),
        "location_label": shop.get("location_label"),
        "lat": shop.get("lat"), "lon": shop.get("lon"),
        "distance_km": round(dist, 2) if dist >= 0 else None,
        "categories": _decode_json(shop.get("category_names"), []),
        "contacts": _decode_json(shop.get("contacts"), []),
        "instagram": shop.get("instagram"),
        "website": shop.get("website_url"),
        "open_state": status.state,
        "opens_at": status.opens_at,
        "closes_at": status.closes_at,
        "minutes_until_close": status.minutes_until_close,
        "hours_known": bool(shop.get("hours_known")),
        "hours": week_display(week) if shop.get("hours_known") else [],
        "installment": {
            "confirmed": bool(shop.get("has_in_person_installment")),
            "declared": bool(shop.get("has_any_installment")),
            "providers": _decode_json(shop.get("installment_providers"), []),
        },
        "fast_delivery": shop.get("supports_fast_delivery"),
        "mall": {"name": shop.get("mall_name"), "floor": shop.get("floor"),
                 "unit": shop.get("unit"), "landmark": shop.get("landmark"),
                 "guide": find_it_text(addr, shop["name"])},
        "offer_count": shop.get("offer_count"),
        "offers": other_offers,
    }


def neighbourhoods() -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM neighbourhoods ORDER BY shop_count DESC").fetchall()
    return [dict(r) for r in rows]


def malls(limit: int = 40) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM malls WHERE shop_count > 1 ORDER BY shop_count DESC LIMIT ?",
            (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["categories"] = _decode_json(d.get("categories"), [])
        out.append(d)
    return out


def mall_detail(key: str) -> dict | None:
    with connection() as conn:
        row = conn.execute("SELECT * FROM malls WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        shops = conn.execute(
            """SELECT id, name, floor, unit, location_label, category_names, offer_count
               FROM shops WHERE mall_key=? ORDER BY offer_count DESC""", (key,)).fetchall()
    mall = dict(row)
    mall["categories"] = _decode_json(mall.get("categories"), [])
    mall["shops"] = [
        {**dict(s), "categories": _decode_json(s["category_names"], [])} for s in shops
    ]
    for s in mall["shops"]:
        s.pop("category_names", None)
    return mall
