import asyncio
from contextlib import asynccontextmanager

from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.load_service import load_service_router
from shared.admin_seed import ensure_admin_account
from shared.config import APP_VERSION, settings
from shared.database import engine, get_db, init_db
from shared.models import PageVisit
from shared.score_sync import score_refresh_loop
from shared.visits import count_window_start, nairobi_today, visit_totals

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


class VisitIn(BaseModel):
    visitor_id: str


@app.post("/visits")
async def record_visit(body: VisitIn, db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    try:
        key = str(UUID(body.visitor_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="visitor_id must be a UUID") from exc

    today = nairobi_today()
    existing = await db.execute(
        select(PageVisit.id).where(PageVisit.visitor_key == key, PageVisit.visit_day == today)
    )
    if existing.scalar_one_or_none() is None:
        db.add(PageVisit(visitor_key=key, visit_day=today))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()

    window = count_window_start(today)
    rows = await db.execute(
        select(PageVisit.visitor_key, PageVisit.visit_day).where(PageVisit.visit_day >= window)
    )
    return visit_totals(list(rows.all()), today)


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
