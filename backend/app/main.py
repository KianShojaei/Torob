from backend.app.db.bootstrap import ensure_db_ready
ensure_db_ready()
import json
from pathlib import Path
from typing import Any
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.db.repo import (
    get_neighborhoods,
    get_supported_cities,
    get_popular_categories,
    search_products,
    recommend_models,
    compare_products_by_ids,
)
from backend.app.services.ranking import (
    find_stores_for_product,
    compare_stores_by_offer_ids,
    get_in_mall_guide,
    build_visit_plan,
)
from backend.app.simulator.seller_sim import start_seller_contacts, poll_conversations
from backend.app.agent.orchestrator import process_agent_chat

app = FastAPI(
    title="Torob In-Store Shopping Assistant API (Tehran)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_HTML = Path("frontend/index.html")

class CompareProductsRequest(BaseModel):
    product_ids: list[str]

class CompareStoresRequest(BaseModel):
    offer_ids: list[str]
    user_lat: float | None = None
    user_lon: float | None = None
    travel_mode: str = "car"

class ContactStoresRequest(BaseModel):
    shop_ids: list[str]
    product_id: str
    intent: str = "all"
    custom_message: str | None = None
    proposed_price_toman: int | None = None

class PollConversationsRequest(BaseModel):
    conversation_ids: list[str]
    user_lat: float | None = None
    user_lon: float | None = None

class VisitPlanRequest(BaseModel):
    offer_ids: list[str]
    user_lat: float | None = None
    user_lon: float | None = None
    travel_mode: str = "car"
    depart_time_iso: str | None = None

class AgentChatRequest(BaseModel):
    message: str
    context: dict[str, Any] = {}

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    if FRONTEND_HTML.exists():
        return FileResponse(str(FRONTEND_HTML))
    return HTMLResponse("<h1>Torob Assistant Backend is running.</h1>")

@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "db_exists": settings.SQLITE_DB_PATH.exists(),
        "llm_base_url": settings.LLM_BASE_URL,
        "llm_model": settings.LLM_MODEL,
    }

@app.get("/api/init")
def api_init():
    return {
        "cities": get_supported_cities(),
        "neighborhoods": get_neighborhoods(),
        "popular_categories": get_popular_categories(),
        "default_location": {
            "city": "تهران",
            "lat": settings.DEFAULT_LAT,
            "lon": settings.DEFAULT_LON,
            "label": "همه مناطق تهران",
        },
        "snapshot_date": settings.SNAPSHOT_DATE,
    }

@app.get("/api/products/search")
def api_search_products(
    q: str = Query("", description="Search query"),
    category: str | None = None,
    brand: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    installment_only: bool = False,
    limit: int = 12,
):
    return search_products(
        query=q,
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        installment_only=installment_only,
        limit=limit,
    )

@app.get("/api/products/recommend")
def api_recommend_models(
    q: str = Query("هدفون بی سیم"),
    usage: str | None = None,
    max_price: int | None = None,
    brand: str | None = None,
    installment_only: bool = False,
    limit: int = 5,
):
    return recommend_models(
        category_or_query=q,
        usage_hint=usage,
        max_price=max_price,
        brand=brand,
        installment_only=installment_only,
        limit=limit,
    )

@app.post("/api/products/compare")
def api_compare_products(req: CompareProductsRequest):
    return compare_products_by_ids(req.product_ids)

@app.get("/api/stores/find")
def api_find_stores(
    product_id: str,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 15.0,
    neighborhood: str | None = None,
    max_budget: int | None = None,
    installment_mode: str = "any",
    open_filter: str = "any",
    travel_mode: str = "car",
    depart_time_iso: str | None = None,
    sort_by: str = "best",
    limit: int = 25,
):
    return find_stores_for_product(
        product_id_or_group=product_id,
        user_lat=lat,
        user_lon=lon,
        radius_km=radius_km,
        neighborhood_filter=neighborhood,
        max_budget_toman=max_budget,
        installment_mode=installment_mode,
        open_filter=open_filter,
        travel_mode=travel_mode,
        depart_time_iso=depart_time_iso,
        sort_by=sort_by,
        limit=limit,
    )

@app.post("/api/stores/compare")
def api_compare_stores(req: CompareStoresRequest):
    return compare_stores_by_offer_ids(
        offer_ids=req.offer_ids,
        user_lat=req.user_lat,
        user_lon=req.user_lon,
        travel_mode=req.travel_mode,
    )

@app.get("/api/stores/{shop_id}/mall-guide")
def api_mall_guide(shop_id: str):
    return get_in_mall_guide(shop_id)

@app.post("/api/contact/start")
def api_contact_start(req: ContactStoresRequest):
    convs = start_seller_contacts(
        shop_ids=req.shop_ids,
        product_id=req.product_id,
        intent=req.intent,
        custom_message=req.custom_message,
        proposed_price_toman=req.proposed_price_toman,
    )
    return {"conversations": convs}

@app.post("/api/contact/poll")
def api_contact_poll(req: PollConversationsRequest):
    return poll_conversations(
        conversation_ids=req.conversation_ids,
        user_lat=req.user_lat,
        user_lon=req.user_lon,
    )

@app.post("/api/plan/visit")
def api_visit_plan(req: VisitPlanRequest):
    return build_visit_plan(
        offer_ids=req.offer_ids,
        user_lat=req.user_lat,
        user_lon=req.user_lon,
        travel_mode=req.travel_mode,
        depart_time_iso=req.depart_time_iso,
    )

@app.post("/api/agent/chat")
def api_agent_chat(req: AgentChatRequest):
    return process_agent_chat(req.message, req.context)

@app.post("/api/agent/stream")
def api_agent_stream(req: AgentChatRequest):
    def event_gen():
        res = process_agent_chat(req.message, req.context)
        yield f"data: {json.dumps({'type': 'text_delta', 'content': res['reply_fa']}, ensure_ascii=False)}\n\n"
        for card in res.get("cards", []):
            yield f"data: {json.dumps({'type': 'card', 'card_type': card['type'], 'data': card['data']}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'detected_filters': res.get('detected_filters', {})}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
