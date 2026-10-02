import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from gateway.load_service import load_service_router
from shared.admin_seed import ensure_admin_account
from shared.config import APP_VERSION, settings
from shared.database import engine, init_db
from shared.score_sync import score_refresh_loop

auth = load_service_router("0-auth-service")
ingestion = load_service_router("1-data-ingestion-service")
poisson = load_service_router("2-poisson-analytics-engine")
odds = load_service_router("3-market-odds-monitor")
slips = load_service_router("4-slip-generator-service")
tracker = load_service_router("5-realtime-tracker-service")
purger = load_service_router("6-database-purger")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    await ensure_admin_account()
    refresher = asyncio.create_task(score_refresh_loop())
    yield
    refresher.cancel()


app = FastAPI(
    title="Casuya SuperWeb API",
    description="Football analytics, treble generation, and BetPawa-ready slips.",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(auth.router)
app.include_router(auth.admin_router)
app.include_router(ingestion.router)
app.include_router(poisson.router)
app.include_router(odds.router)
app.include_router(slips.router)
app.include_router(tracker.router)
app.include_router(purger.router)


@app.get("/health")
async def health() -> dict:
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "version": APP_VERSION,
        "database": "up" if db_ok else "down",
        "odds_api": "configured" if settings.odds_api_configured else "not_configured",
        "betpawa": settings.betpawa_brand,
    }
