"""Typed tools — the only path from the agent to the database (§5.3, §7).

Every tool is a pure Python function with a Pydantic input model and a JSON-schema
declaration for the LLM. The LLM chooses *which* tool to call; the numbers always
come from here.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Callable

from pydantic import BaseModel, Field

from app.config import settings
from app.etl.normalize import fold
from app.services import stores as stores_svc
from app.services import search as search_svc
from app.services.geo import haversine_km, travel_minutes
from app.services.hours import TEHRAN, open_status, parse_week
from app.services.stores import StoreFilters
from app.simulator import engine as simulator


# --------------------------------------------------------------------------- #
# input models
# --------------------------------------------------------------------------- #
class SearchIn(BaseModel):
    query: str = ""
    category: str | None = None
    brand: str | None = None
    max_price: float | None = None
    min_price: float | None = None
    limit: int = 8


class RecommendIn(BaseModel):
    category: str | None = None
    budget_max: float | None = None
    budget_min: float | None = None
    usage: str | None = None
    limit: int = 5


class CompareProductsIn(BaseModel):
    product_ids: list[str] = Field(default_factory=list)


class FindStoresIn(BaseModel):
    product_id: str
    lat: float | None = None
    lon: float | None = None
    radius_km: float = 6.0
    max_price: float | None = None
    installment: str = "off"
    open_now: bool = False
    sort: str = "balanced"
    limit: int = 20


class CompareStoresIn(BaseModel):
    product_id: str
    shop_ids: list[str] = Field(default_factory=list)
    lat: float | None = None
    lon: float | None = None


class OpenAtIn(BaseModel):
    shop_id: str
    travel_minutes: int = 0


class LocateIn(BaseModel):
    shop_id: str


class ContactIn(BaseModel):
    shop_id: str
    product_id: str | None = None
    intent: str = "price_stock"
    message: str | None = None
    channel: str = "simulated"


class ContactStatusIn(BaseModel):
    thread_id: str


class AlternativesIn(BaseModel):
    product_id: str
    reason: str = "no_reply"
    lat: float | None = None
    lon: float | None = None
    exclude_shop_ids: list[str] = Field(default_factory=list)
    limit: int = 3


class PlanVisitIn(BaseModel):
    items: list[dict] = Field(default_factory=list)   # [{shop_id, product_id, price}]
    origin_lat: float | None = None
    origin_lon: float | None = None
    depart_at: str | None = None
    mode: str = "car"


# --------------------------------------------------------------------------- #
# implementations
# --------------------------------------------------------------------------- #
def search_products(query: str, category: str | None = None, brand: str | None = None,
                    max_price: float | None = None, min_price: float | None = None,
                    limit: int = 8) -> dict:
    filters = search_svc.ProductFilters(
        category=category, brand=brand, max_price=max_price,
        min_price=min_price, limit=limit)
    hits = search_svc.search_products(query, filters)
    return {
        "products": [
            {
                "product_id": h.id, "title": h.title, "brand": h.brand,
                "category": h.category, "image": h.image,
                "price_min": h.price_min, "price_median": h.price_median,
                "price_max": h.price_max, "shop_count": h.shop_count,
                "key_specs": h.key_specs, "score": h.score, "reasons": h.matched,
            }
            for h in hits
        ],
        "count": len(hits),
        "query": query,
    }


def recommend_models(category: str | None, budget_max: float | None = None,
                     budget_min: float | None = None, usage: str | None = None,
                     limit: int = 5) -> dict:
    """Top models per category with a "best value" and "most available" pick."""
    hits = search_svc.search_products(
        usage or "", search_svc.ProductFilters(
            category=category, max_price=budget_max, min_price=budget_min,
            limit=max(limit * 3, 12)))
    if not hits:
        return {"models": [], "count": 0}

    def value(h):
        m = h.price_median or 0
        return (h.shop_count or 0) / max(1.0, m / 1_000_000)

    cheapest = min(hits, key=lambda h: h.price_median or 1e18)
    best_value = max(hits, key=value)
    most_available = max(hits, key=lambda h: h.shop_count or 0)

    chosen: list = []
    for tag, hit in (("بهترین نسبت قیمت به امکانات", best_value),
                     ("ارزان‌ترین", cheapest),
                     ("بیشترین فروشنده", most_available)):
        if hit not in chosen:
            chosen.append(hit)
    for h in hits:
        if len(chosen) >= limit:
            break
        if h not in chosen:
            chosen.append(h)

    out = []
    for h in chosen[:limit]:
        badges = []
        if h is cheapest:
            badges.append("ارزان‌ترین گزینه")
        if h is best_value:
            badges.append("بهترین ارزش خرید")
        if h is most_available:
            badges.append("بیشترین تعداد فروشنده")
        out.append({
            "product_id": h.id, "title": h.title, "brand": h.brand,
            "image": h.image, "price_median": h.price_median,
            "price_min": h.price_min, "price_max": h.price_max,
            "shop_count": h.shop_count, "key_specs": h.key_specs,
            "badges": badges, "reasons": h.matched,
        })
    return {"models": out, "count": len(out), "category": category}


def compare_products(product_ids: list[str]) -> dict:
    hits = search_svc.get_products(product_ids)
    if len(hits) < 2:
        return {"error": "need_at_least_two_products", "products": []}
    spec_keys: list[str] = []
    for h in hits:
        for k in h.key_specs:
            if k not in spec_keys:
                spec_keys.append(k)
    rows = []
    for k in spec_keys:
        row = {"spec": k, "values": {}}
        for h in hits:
            row["values"][h.id] = h.key_specs.get(k, "—")
        rows.append(row)

    # highlight the cheapest and the best-specified column
    prices = {h.id: h.price_median for h in hits if h.price_median}
    cheapest_id = min(prices, key=prices.get) if prices else None
    return {
        "products": [
            {"product_id": h.id, "title": h.title, "brand": h.brand, "image": h.image,
             "price_min": h.price_min, "price_median": h.price_median,
             "price_max": h.price_max, "shop_count": h.shop_count,
             "is_cheapest": h.id == cheapest_id}
            for h in hits
        ],
        "spec_rows": rows,
        "cheapest_id": cheapest_id,
    }


def find_stores(product_id: str, lat: float | None = None, lon: float | None = None,
                radius_km: float = 6.0, max_price: float | None = None,
                installment: str = "off", open_now: bool = False,
                sort: str = "balanced", limit: int = 20) -> dict:
    filters = StoreFilters(
        lat=lat, lon=lon, radius_km=radius_km, max_price=max_price,
        installment=installment, open_now=open_now, sort=sort, limit=limit)
    offers = stores_svc.find_stores(product_id, filters)
    product = search_svc.get_product(product_id)
    return {
        "product": {
            "product_id": product.id, "title": product.title,
            "price_median": product.price_median, "shop_count": product.shop_count,
        } if product else None,
        "stores": [_offer_dict(o) for o in offers],
        "count": len(offers),
        "filters": {"radius_km": radius_km, "installment": installment,
                    "open_now": open_now, "sort": sort, "max_price": max_price},
    }


def _offer_dict(o) -> dict:
    from app.db.engine import one as _one
    _loc = _one("SELECT lat, lon FROM shops WHERE id=?", (o.shop_id,))
    return {
        "shop_id": o.shop_id, "name": o.name, "name_is_real": o.name_is_real,
        "lat": _loc[0] if _loc else None, "lon": _loc[1] if _loc else None,
        "category": o.category, "location_label": o.location_label,
        "distance_km": o.distance_km, "distance_note": o.distance_note,
        "travel_minutes": o.travel_minutes, "mode": o.mode,
        "price": o.price, "price_valid": o.price_valid,
        "price_age_days": o.price_age_days, "price_age_label": o.price_age_label,
        "price_age_bucket": o.price_age_bucket,
        "availability": o.availability, "availability_source": o.availability_source,
        "availability_at": o.availability_at,
        "market_position": o.market_position,
        "open_state": o.open_state, "opens_at": o.opens_at, "closes_at": o.closes_at,
        "minutes_until_close": o.minutes_until_close,
        "open_on_arrival": o.open_on_arrival,
        "hours_known": o.weekly_hours_known,
        "installment_confirmed": o.installment_confirmed,
        "installment_declared": o.installment_declared,
        "installment_providers": o.installment_providers,
        "fast_delivery": o.fast_delivery, "mall": o.mall,
        "score": o.score, "score_breakdown": o.score_breakdown,
        "reasons": o.reasons, "flags": o.flags,
        "hours": o.hours,
    }


def compare_stores(product_id: str, shop_ids: list[str],
                   lat: float | None = None, lon: float | None = None) -> dict:
    filters = StoreFilters(lat=lat, lon=lon, radius_km=60, limit=500)
    offers = {o.shop_id: o for o in stores_svc.find_stores(product_id, filters)}
    rows = []
    for sid in shop_ids:
        o = offers.get(sid)
        if not o:
            continue
        rows.append(_offer_dict(o))
    if not rows:
        return {"error": "no_stores", "rows": []}

    cheapest = min((r["price"] for r in rows if r["price_valid"]), default=None)
    nearest = min((r["shop_id"] for r in rows if r["distance_km"] >= 0),
                  key=lambda s: next(r["distance_km"] for r in rows if r["shop_id"] == s),
                  default=None)
    for r in rows:
        r["is_cheapest"] = r["price"] == cheapest
        r["is_nearest"] = r["shop_id"] == nearest
    return {"rows": rows, "cheapest_price": cheapest,
            "criteria": ["قیمت", "فاصله", "ساعت کاری", "اقساط", "تازگی قیمت"]}


def check_open(shop_id: str, travel_minutes: int = 0) -> dict:
    from datetime import timedelta as _td

    from app.services.hours import open_at_arrival, parse_week

    week = parse_week(_week_of(shop_id))
    now = settings.now_tehran
    current = open_status(week, now)
    arrival = now + _td(minutes=max(0, travel_minutes))
    at_arrival = open_at_arrival(week, now, max(0, travel_minutes))
    return {
        "shop_id": shop_id,
        "open_state": current.state,
        "opens_at": current.opens_at,
        "closes_at": current.closes_at,
        "hours_known": any(d.status in ("declared", "closed") for d in week.values()),
        "arrival_in_minutes": travel_minutes,
        "arrival_time": arrival.strftime("%H:%M"),
        "open_on_arrival": at_arrival.state,
        "closes_at_arrival": at_arrival.closes_at,
        "note": "ساعت کاری نامشخص است" if current.state == "unknown" else None,
    }


def locate_in_mall(shop_id: str) -> dict:
    detail = stores_svc.store_detail(shop_id)
    if not detail:
        return {"error": "shop_not_found"}
    return {
        "shop_id": shop_id,
        "shop_name": detail["name"],
        "mall": detail["mall"],
        "address": detail["address"],
        "lat": detail["lat"], "lon": detail["lon"],
    }


def contact_store(shop_id: str, product_id: str | None = None,
                  intent: str = "price_stock", message: str | None = None,
                  channel: str = "simulated") -> dict:
    return simulator.ask(shop_id, product_id, intent, message, channel)


def contact_status(thread_id: str) -> dict:
    return simulator.status(thread_id) or {"error": "thread_not_found"}


def suggest_alternatives(product_id: str, reason: str = "no_reply",
                         lat: float | None = None, lon: float | None = None,
                         exclude_shop_ids: list[str] | None = None,
                         limit: int = 3) -> dict:
    product = search_svc.get_product(product_id)
    exclude = set(exclude_shop_ids or [])
    stores: list[dict] = []
    if reason in ("no_reply", "closed", "out_of_stock"):
        offers = stores_svc.find_stores(
            product_id, StoreFilters(lat=lat, lon=lon, radius_km=12, limit=40))
        for o in offers:
            if o.shop_id in exclude:
                continue
            if o.open_state == "closed" and reason == "closed":
                continue
            stores.append(_offer_dict(o))
            if len(stores) >= limit:
                break

    similar: list[dict] = []
    if reason == "out_of_stock" or len(stores) < limit:
        for h in search_svc.similar_products(product_id, limit=4):
            if h.id == product_id:
                continue
            similar.append({
                "product_id": h.id, "title": h.title, "brand": h.brand,
                "image": h.image, "price_median": h.price_median,
                "shop_count": h.shop_count, "key_specs": h.key_specs,
                "relation": "مدل مشابه — نه همان محصول",
            })
            if len(similar) >= max(2, limit):
                break
    return {
        "reason": reason,
        "same_product_elsewhere": stores,
        "similar_products": similar,
        "product": {"product_id": product.id, "title": product.title} if product else None,
    }


def plan_visit(items: list[dict], origin_lat: float | None = None,
               origin_lon: float | None = None, depart_at: str | None = None,
               mode: str = "car") -> dict:
    """Nearest-first ordering, open-at-arrival checks and closing warnings (§5.3 #12)."""
    if not items:
        return {"stops": [], "error": "empty_plan"}

    start = datetime.fromisoformat(depart_at) if depart_at else settings.now_tehran
    if start.tzinfo is None:
        start = start.replace(tzinfo=TEHRAN)

    enriched: list[dict] = []
    for item in items[:6]:
        shop_id = item.get("shop_id")
        detail = stores_svc.store_detail(shop_id)
        if not detail:
            continue
        dist = (haversine_km(origin_lat, origin_lon, detail["lat"], detail["lon"])
                if origin_lat is not None and detail["lat"] is not None else 0)
        enriched.append({
            "shop_id": shop_id,
            "shop_name": detail["name"],
            "product_id": item.get("product_id"),
            "price": item.get("price"),
            "lat": detail["lat"], "lon": detail["lon"],
            "distance_km": round(dist, 2),
            "travel_minutes": travel_minutes(dist, mode),
            "mall": detail["mall"],
        })

    # nearest-first (a lightweight TSP for ≤4 stops)
    if origin_lat is not None:
        enriched.sort(key=lambda s: s["distance_km"])
    else:
        enriched.sort(key=lambda s: s["travel_minutes"])

    stops = []
    clock = start
    warnings: list[str] = []
    for idx, stop in enumerate(enriched, start=1):
        clock = clock + timedelta(minutes=stop["travel_minutes"] + (20 if idx > 1 else 0))
        week = parse_week(_week_of(stop["shop_id"]))
        status = open_status(week, clock)
        entry = {
            **stop,
            "order": idx,
            "arrival_time": clock.strftime("%H:%M"),
            "open_state": status.state,
            "closes_at": status.closes_at,
            "opens_at": status.opens_at,
        }
        if status.state == "closed":
            warnings.append(f"{stop['shop_name']} ساعت {entry['arrival_time']} بسته است.")
            entry["warning"] = "با رسیدن شما بسته است"
        elif status.state == "open" and (status.minutes_until_close or 999) < 30:
            warnings.append(
                f"{stop['shop_name']} ساعت {entry['arrival_time']} فقط "
                f"{status.minutes_until_close} دقیقه باز است.")
            entry["warning"] = "نزدیک ساعت بسته شدن"
        stops.append(entry)

    return {
        "stops": stops,
        "warnings": warnings,
        "start_at": start.isoformat(),
        "total_travel_minutes": sum(s["travel_minutes"] for s in enriched),
        "mode": mode,
    }


def _week_of(shop_id: str) -> dict:
    from app.db.engine import one

    row = one("SELECT weekly_hours FROM shops WHERE id=?", (shop_id,))
    if not row or not row[0]:
        return {}
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return {}


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #
class _ChatterModel(BaseModel):
    category: str | None = None
    usage: str | None = None


TOOLS: dict[str, tuple[Callable[..., dict], type[BaseModel], str]] = {
    "search_products": (search_products, SearchIn, "جست‌وجوی محصول با متن، دسته، برند و بودجه"),
    "recommend_models": (recommend_models, RecommendIn, "پیشنهاد ۳ تا ۵ مدل با دلیل"),
    "compare_products": (compare_products, CompareProductsIn, "مقایسه‌ی مشخصات چند محصول"),
    "find_stores": (find_stores, FindStoresIn, "فروشگاه‌های دارای یک محصول با فاصله و ساعت"),
    "compare_stores": (compare_stores, CompareStoresIn, "مقایسه‌ی فروشگاه‌ها"),
    "check_open": (check_open, OpenAtIn, "بررسی باز بودن فروشگاه در زمان رسیدن"),
    "locate_in_mall": (locate_in_mall, LocateIn, "آدرس دقیق داخل پاساژ"),
    "contact_store": (contact_store, ContactIn, "پرسش قیمت/موجودی از فروشنده (شبیه‌سازی)"),
    "contact_status": (contact_status, ContactStatusIn, "وضعیت گفت‌وگو با فروشنده"),
    "suggest_alternatives": (suggest_alternatives, AlternativesIn, "جایگزین در صورت نبود پاسخ/موجودی"),
    "plan_visit": (plan_visit, PlanVisitIn, "برنامه‌ی سفر خرید"),
}


def call(name: str, payload: dict) -> dict:
    entry = TOOLS.get(name)
    if not entry:
        return {"error": "unknown_tool", "tool": name}
    fn, model, _desc = entry
    try:
        args = model(**payload)
    except Exception as exc:  # validation
        return {"error": "bad_arguments", "detail": str(exc)[:200]}
    try:
        return fn(**args.model_dump())
    except Exception as exc:  # never leak a stack trace to the LLM
        return {"error": "tool_failed", "detail": str(exc)[:200]}


def schemas() -> list[dict]:
    out = []
    for name, (_fn, model, desc) in TOOLS.items():
        out.append({
            "name": name,
            "description": desc,
            "input_schema": model.model_json_schema(),
        })
    return out
