"""
app/main.py
────────────
FastAPI application factory.

Run in development:
    uvicorn app.main:app --reload --port 8000

Run in production (with gunicorn managing uvicorn workers):
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import create_all_tables
from app.routers import auth, progress, users

settings = get_settings()


# ── Lifespan: startup / shutdown hooks ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup (before yield) and shutdown (after yield)."""
    # Create DB tables if they don't exist
    # In production, remove this and rely solely on Alembic migrations
    await create_all_tables()
    print(f"✅ NIZAM-RUS API started | DB: {settings.database_url}")
    yield
    print("🛑 NIZAM-RUS API shutting down")


# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="NIZAM-RUS API",
    description="Backend for the 180-Day Russian Language Learning Platform",
    version="1.0.0",
    lifespan=lifespan,
    # In production, disable docs to avoid leaking endpoint structure
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
# Controls which origins (domains) can make requests to this API.
# In production, replace the wildcard with your exact frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,   # e.g. "https://nizam-rus.com"
        "http://localhost:5500",    # VS Code Live Server
        "http://127.0.0.1:5500",
        "http://localhost:3000",    # React dev server (if you migrate later)
    ],
    allow_credentials=True,         # Required for Authorization header
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(progress.router)
app.include_router(users.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Meta"])
async def health_check():
    """Kubernetes / load-balancer liveness probe. Should always return 200."""
    return {"status": "ok", "app": settings.app_name}
