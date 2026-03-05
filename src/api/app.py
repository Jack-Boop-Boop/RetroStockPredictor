"""FastAPI application: the single entry point for all API routes.

Run locally:  uvicorn src.api.app:app --reload --port 5000
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from ..utils.settings import settings

PROJECT_ROOT = Path(__file__).parent.parent.parent

app = FastAPI(
    title="Stock Predictor API",
    version="0.2.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---
from .routes.auth import router as auth_router
from .routes.portfolio import router as portfolio_router
from .routes.market import router as market_router
from .routes.analysis import router as analysis_router
from .routes.stocks import router as stocks_router
from .routes.agents import router as agents_router

app.include_router(auth_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(stocks_router, prefix="/api")
app.include_router(agents_router, prefix="/api")


# --- Global error handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # In production, don't leak internal errors
    if settings.is_production:
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# --- Health check ---
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.2.0"}


# --- Serve static frontend ---
static_dir = PROJECT_ROOT / "public" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index():
    return FileResponse(str(PROJECT_ROOT / "public" / "index.html"))
