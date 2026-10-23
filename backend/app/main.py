"""FastAPI application: API + built PWA in one container (master prompt §2, §7)."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import ROOT, settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
log = logging.getLogger("app")

app = FastAPI(
    title="Torbgard — In-store shopping assistant",
    version="1.0.0",
    description="Agentic assistant for in-person shopping in Tehran (Torob hackathon).",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.include_router(router, prefix="/api")

STATIC_DIR = Path(ROOT) / "backend" / "static"


@app.exception_handler(Exception)
async def unhandled(_request, exc):  # never leak a stack trace to the browser
    log.error("unhandled: %s", exc)
    return JSONResponse(status_code=500, content={"error": "internal_error"})


@app.on_event("startup")
def startup() -> None:
    log.info("snapshot=%s llm=%s", settings.snapshot_date,
             settings.llm_provider if settings.llm_enabled else "none")


# ---- static PWA (built by `make build`) ---------------------------------- #
if STATIC_DIR.exists():
    assets = STATIC_DIR / "_next"
    if assets.exists():
        app.mount("/_next", StaticFiles(directory=assets), name="next-assets")

    @app.get("/manifest.webmanifest")
    def manifest():
        return FileResponse(STATIC_DIR / "manifest.webmanifest")

    @app.get("/sw.js")
    def service_worker():
        return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"error": "not_found"})
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse(status_code=404, content={"error": "static_not_built"})
else:
    @app.get("/")
    def placeholder():
        return {
            "app": "torbgard-api",
            "status": "frontend_not_built",
            "hint": "run `make build` (needs Node) or use `make dev`",
            "docs": "/api/docs",
        }
