"""
SiteSense AI — FastAPI Application Entrypoint

Multi-tenant RAG chatbot platform.
Stage 2: authentication enabled, CORS tightened, Supabase + ChromaDB.
"""

import asyncio
import sys

# ── WINDOWS ASYNCIO FIX ──────────────────────────────────
# MUST be set at the absolute top before any loop starts.
import asyncio
import os

# MANDATORY: Windows Proactor Loop for Playwright/Subprocesses
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import database
from config import settings
from services.llm_provider import get_available_models

# Import routers
from routers.tenants import router as tenants_router
from routers.sources import router as sources_router
from routers.chat import router as chat_router
from routers.widget import router as widget_router
from routers.analytics import router as analytics_router
from routers.settings import router as settings_router
from routers.graph import router as graph_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("sitesense")

# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown tasks."""

    # ── STARTUP ──────────────────────────────────────────────
    # 1. Diagnostic Summary (Pre-check)
    logger.info(f"Config State: Supabase URL: {'Set' if settings.SUPABASE_URL else 'Missing'}, "
                f"Anthropic API: {'Set' if settings.ANTHROPIC_API_KEY else 'Missing'}, "
                f"Gemini API: {'Set' if settings.GEMINI_API_KEY else 'Missing'}, "
                f"Voyage API: {'Set' if settings.VOYAGE_API_KEY else 'Missing'}")

    # 2. Ensure directories exist
    os.makedirs("./data", exist_ok=True)
    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)

    # 3. Initialise Database connection (Supabase)
    await database.init_db()
    logger.info("Supabase database connection verified")

    # 3. Verify embedding provider/keys are configured
    if not settings.VOYAGE_API_KEY and not settings.OPENAI_API_KEY:
        logger.warning("WARNING: No embedding provider configured! Set VOYAGE_API_KEY or OPENAI_API_KEY in .env")
    else:
        provider = "Voyage AI" if settings.VOYAGE_API_KEY else "OpenAI"
        logger.info(f"Global Embedding provider: {provider}")

    # 4. Verify/Validate LLM provider
    has_llm = any([settings.ANTHROPIC_API_KEY, settings.GEMINI_API_KEY, settings.OPENROUTER_API_KEY])
    if not has_llm:
        logger.warning("WARNING: No global LLM provider configured! Set ANTHROPIC_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY in .env")
    else:
        from services.llm_provider import validate_provider, LLMProvider
        try:
            # Validate the default provider on startup
            default_prov = LLMProvider.GEMINI if settings.GEMINI_API_KEY else LLMProvider.CLAUDE
            await validate_provider(default_prov, "system")
            logger.info(f"Default LLM Provider ({default_prov}) verified.")
        except Exception as e:
            logger.error(f"CRITICAL: Default LLM validation failed: {str(e)}")
            # We don't exit(1) to allow the dashboard to stay accessible for config
            logger.info("SiteSense AI started with warnings (LLM issues)")
            yield
            return

    logger.info("SiteSense AI started successfully ✔")

    yield

    # ── SHUTDOWN ─────────────────────────────────────────────
    logger.info("SiteSense AI shutting down …")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SiteSense AI",
    version="1.1.0",
    description="Multi-tenant RAG chatbot platform (Supabase + Cloud AI APIs)",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS & Middlewares
# ---------------------------------------------------------------------------
# Note: Middlewares are executed in REVERSE order of addition.
# The LAST middleware added is the FIRST to handle the request (outermost).

# 1. Debug Logger (Middle Layer)
@app.middleware("http")
async def debug_log_middleware(request: Request, call_next):
    if settings.ENVIRONMENT == "development":
        import time
        start_time = time.time()
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            logger.info(f"REQ: {request.method} {request.url.path} - RESP: {response.status_code} ({process_time:.2f}ms)")
            return response
        except Exception as e:
            logger.error(f"Middleware Error: {str(e)}")
            raise
    return await call_next(request)

# 2. CORS (Outermost Layer)
# For the widget and local development, we need to be permissive.
# Since we use Bearer tokens (headers), we don't need allow_credentials=True.
cors_origins = ["*"]
if settings.ENVIRONMENT != "development":
    if settings.FRONTEND_URL:
        cors_origins = [settings.FRONTEND_URL.rstrip("/")]
    else:
        logger.warning("FRONTEND_URL not set in production! CORS is open (wildcard).")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "X-Bot-Id"],
)

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
app.include_router(tenants_router)
app.include_router(sources_router)
app.include_router(chat_router)
app.include_router(widget_router)
app.include_router(analytics_router)
app.include_router(settings_router)
app.include_router(graph_router)


# ---------------------------------------------------------------------------
# System Endpoints
# ---------------------------------------------------------------------------
@app.get("/", tags=["system"])
async def root():
    """Root redirect / welcome message to prevent 404 logs."""
    return {"status": "ok", "message": "SiteSense AI Backend API is running"}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Prevent 404 logs for browser favicon requests."""
    return {}

@app.get("/health", tags=["system"])
async def health_check():
    """Lightweight liveness probe."""
    return {"status": "ok", "version": "1.1.0", "db": "supabase"}

@app.get("/api/models", tags=["system"])
@app.get("/api/settings/models", tags=["system"])
async def get_models():
    """Returns available LLM provider models (unauthenticated alias for dev convenience)."""
    return get_available_models()
