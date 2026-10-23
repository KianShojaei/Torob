"""REST + SSE endpoints (master prompt §7)."""
from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent import tools
from app.agent.orchestrator import run as agent_run
from app.config import settings
from app.db import engine
from app.services import search as search_svc
from app.services import stores as stores_svc
from app.services.hours import TEHRAN
from app.simulator import engine as simulator

log = logging.getLogger("api")
router = APIRouter()


# --------------------------------------------------------------------------- #
# meta / health
# --------------------------------------------------------------------------- #
@router.get("/health")
@router.get("/healthz", include_in_schema=False)
def health():
    ready = engine.is_ready()
    return {
        "status": "ok" if ready else "degraded",
        "db_ready": ready,
        "llm": settings.llm_provider if settings.llm_enabled else "none",
        "time": datetime.now(TEHRAN).isoformat(),
    }


@router.get("/ready")
@router.get("/readyz", include_in_schema=False)
def ready():
    if not engine.is_ready():
        raise HTTPException(503, "database_not_built")
    c = engine.counts()
    if not c.get("shops") or not c.get("products"):
        raise HTTPException(503, "database_empty")
    return {"ready": True, **c}


@router.get("/meta")
def meta():
    build = engine.meta()
    seeded = build.get("mode", "unknown")
    return {
        "dataset_mode": seeded,
        "is_synthetic": seeded == "synthetic",
        "snapshot_date": settings.snapshot_date,
        "build": build,
        "counts": engine.counts(),
        "demo": {
            "simulated_contact": True,
            "time_scale": settings.demo_time_scale,
            "contact_timeout_seconds": settings.contact_timeout_seconds,
            "notice_fa": "تماس با فروشنده شبیه‌سازی شده است؛ شماره‌های دیتاست نمایشی‌اند.",
        },
        "llm": {"provider": settings.llm_provider if settings.llm_enabled else "none",
                "degraded": not settings.llm_enabled},
        "map": {"tile_url": settings.map_tile_url, "attribution": settings.map_attribution},
        "default_location": {"lat": settings.default_lat, "lon": settings.default_lon},
    }


# --------------------------------------------------------------------------- #
# catalogue
# --------------------------------------------------------------------------- #
@router.get("/categories")
def categories():
    return {"categories": search_svc.categories()}


@router.get("/neighbourhoods")
def neighbourhoods():
    return {"neighbourhoods": stores_svc.neighbourhoods()}


@router.get("/malls")
def malls(limit: int = 40):
    return {"malls": stores_svc.malls(limit)}


@router.get("/malls/{key}")
def mall(key: str):
    d = stores_svc.mall_detail(key)
    if not d:
        raise HTTPException(404, "mall_not_found")
    return d


class SearchBody(BaseModel):
    query: str = ""
    category: str | None = None
    brand: str | None = None
    max_price: float | None = None
    min_price: float | None = None
    limit: int = 12
    sort: str | None = None


@router.post("/search")
def search(body: SearchBody):
    t0 = datetime.now()
    hits = search_svc.search_products(
        body.query,
        search_svc.ProductFilters(category=body.category, brand=body.brand,
                                  max_price=body.max_price, min_price=body.min_price,
                                  limit=body.limit))
    return {
        "products": [
            {"product_id": h.id, "title": h.title, "brand": h.brand,
             "category": h.category, "image": h.image, "price_min": h.price_min,
             "price_median": h.price_median, "price_max": h.price_max,
             "shop_count": h.shop_count, "offer_count": h.offer_count,
             "key_specs": h.key_specs, "reasons": h.matched, "score": h.score}
            for h in hits
        ],
        "count": len(hits),
        "took_ms": int((datetime.now() - t0).total_seconds() * 1000),
    }


@router.get("/products/{product_id}")
def product(product_id: str):
    hit = search_svc.get_product(product_id)
    if not hit:
        raise HTTPException(404, "product_not_found")
    return {"product": {
        "product_id": hit.id, "title": hit.title, "brand": hit.brand,
        "category": hit.category, "image": hit.image, "key_specs": hit.key_specs,
        "price_min": hit.price_min, "price_median": hit.price_median,
        "price_max": hit.price_max, "shop_count": hit.shop_count,
        "offer_count": hit.offer_count,
    }}


class CompareProductsBody(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=4)


@router.post("/compare/products")
def compare_products(body: CompareProductsBody):
    return tools.compare_products(body.product_ids)


class StoresBody(BaseModel):
    product_id: str
    lat: float | None = None
    lon: float | None = None
    radius_km: float = 6.0
    max_price: float | None = None
    min_price: float | None = None
    installment: str = "off"
    open_now: bool = False
    fresh_only: bool = False
    mall_only: bool = False
    neighborhood: str | None = None
    sort: str = "balanced"
    limit: int = 30


@router.post("/stores")
def stores(body: StoresBody):
    payload = body.model_dump()
    product_id = payload.pop("product_id")
    filters = stores_svc.StoreFilters(**payload)
    offers = stores_svc.find_stores(product_id, filters)
    return {
        "stores": [tools._offer_dict(o) for o in offers],
        "count": len(offers),
        "filters": body.model_dump(),
    }


@router.get("/shops/{shop_id}")
def shop(shop_id: str, lat: float | None = Query(None), lon: float | None = Query(None)):
    d = stores_svc.store_detail(shop_id, lat, lon)
    if not d:
        raise HTTPException(404, "shop_not_found")
    return d


class CompareStoresBody(BaseModel):
    product_id: str
    shop_ids: list[str]
    lat: float | None = None
    lon: float | None = None


@router.post("/compare/stores")
def compare_stores(body: CompareStoresBody):
    return tools.compare_stores(body.product_id, body.shop_ids, body.lat, body.lon)


# --------------------------------------------------------------------------- #
# contact (simulated)
# --------------------------------------------------------------------------- #
class ContactBody(BaseModel):
    shop_id: str
    product_id: str | None = None
    intent: str = "price_stock"
    message: str | None = None
    channel: str = "simulated"


@router.post("/contact")
def contact(body: ContactBody):
    try:
        return simulator.ask(body.shop_id, body.product_id, body.intent,
                             body.message, body.channel)
    except ValueError:
        raise HTTPException(404, "shop_not_found")


@router.get("/contact/{thread_id}")
def contact_status(thread_id: str):
    st = simulator.status(thread_id)
    if not st:
        raise HTTPException(404, "thread_not_found")
    return st


@router.get("/contacts")
def contacts(limit: int = 20):
    return {"threads": simulator.list_threads(limit)}


class AlternativesBody(BaseModel):
    product_id: str
    reason: str = "no_reply"
    lat: float | None = None
    lon: float | None = None
    exclude_shop_ids: list[str] = Field(default_factory=list)
    limit: int = 3


@router.post("/alternatives")
def alternatives(body: AlternativesBody):
    return tools.suggest_alternatives(**body.model_dump())


class PlanBody(BaseModel):
    items: list[dict]
    origin_lat: float | None = None
    origin_lon: float | None = None
    depart_at: str | None = None
    mode: str = "car"


@router.post("/plan")
def plan(body: PlanBody):
    return tools.plan_visit(**body.model_dump())


# --------------------------------------------------------------------------- #
# agent (SSE)
# --------------------------------------------------------------------------- #
class AgentBody(BaseModel):
    message: str
    session_id: str | None = None
    category: str | None = None
    lat: float | None = None
    lon: float | None = None


@router.post("/agent/stream")
async def agent_stream(body: AgentBody, request: Request):
    context = {"category": body.category, "lat": body.lat, "lon": body.lon}

    async def gen():
        async for ev in agent_run(body.message, body.session_id, context):
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@router.post("/agent")
async def agent_once(body: AgentBody):
    """Non-streaming variant for tests and the judge's smoke script."""
    events = []
    async for ev in agent_run(body.message, body.session_id,
                              {"category": body.category, "lat": body.lat, "lon": body.lon}):
        events.append(ev)
    text = next((e["text"] for e in reversed(events) if e["type"] == "text_delta"), "")
    cards = [e["card"] for e in events if e["type"] == "card"]
    done = next((e for e in events if e["type"] == "done"), {})
    return {"text": text, "cards": cards, "meta": done,
            "tool_calls": [e for e in events if e["type"] == "tool_status"]}


class EventBody(BaseModel):
    session_id: str | None = None
    name: str
    payload: dict = Field(default_factory=dict)


@router.post("/events")
def log_event(body: EventBody):
    with engine.write_connection() as conn:
        conn.execute(
            "INSERT INTO events (session_id, name, payload, created_at) "
            "VALUES (?,?,?,datetime('now'))",
            (body.session_id, body.name, json.dumps(body.payload, ensure_ascii=False)))
    return {"ok": True}


@router.get("/stats")
def stats():
    with engine.write_connection() as conn:
        top_events = conn.execute(
            "SELECT name, COUNT(*) c FROM events GROUP BY name ORDER BY c DESC LIMIT 10"
        ).fetchall()
        runs = conn.execute(
            "SELECT COUNT(*) c, AVG(latency_ms) ms FROM agent_runs").fetchone()
        threads = conn.execute(
            "SELECT status, COUNT(*) c FROM contact_threads GROUP BY status").fetchall()
    return {
        "events": [dict(r) for r in top_events],
        "agent_runs": dict(runs) if runs else {},
        "threads": [dict(r) for r in threads],
    }
