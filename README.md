# Casuya Win — SuperWeb

Modular football analytics: Poisson Over 1.5, ≥3.00 treble generation, slip tracking, and a BetPawa desk (manual placement).

## Stack

| Layer | Tech |
|-------|------|
| API | Python 3.12–3.14, FastAPI, SQLAlchemy, asyncpg |
| DB | PostgreSQL (`casuyawin`) |
| UI | Next.js Treble Desk (mobile-first, PWA) |
| Match feed | BetPawa Tanzania sportsbook listings (default) |
| Live odds (optional) | [The Odds API](https://the-odds-api.com/) |

## Project layout

```text
core-prediction-engine/
  shared/              # Models, Poisson, treble logic, Odds API client
  gateway/             # FastAPI entry
  0-auth-service/
  1-data-ingestion-service/
  2-poisson-analytics-engine/
  3-market-odds-monitor/
  4-slip-generator-service/
  5-realtime-tracker-service/
  6-database-purger/
apps/dashboard/
scripts/               # dev-api.ps1, dev-dashboard.ps1, test-api.ps1
```

## Quick start (Windows)

1. Create DB (once): `.\scripts\create-casuyawin-db.ps1`
2. Copy env: `copy .env.example .env` — set `DATABASE_URL`, `JWT_SECRET`, Postgres password
3. **Terminal 1 — API:**

```powershell
cd C:\Users\Admin\Desktop\casuya-win
.\scripts\dev-api.ps1 -Restart
```

4. **Terminal 2 — Dashboard:**

```powershell
cd C:\Users\Admin\Desktop\casuya-win
.\scripts\dev-dashboard.ps1
```

Open http://localhost:3000 → register / log in.

### Real matches (recommended)

1. Open the desk — it pulls upcoming football + Over 1.5 from betpawa.co.tz once per visit
2. **Generate best treble** → **Copy for BetPawa** → place manually on BetPawa → **Mark placed**
3. **More → Import BetPawa** anytime you want to refresh the list again

Optional: set `ODDS_API_KEY` and use **Import odds** for a third-party feed instead.

### Practice only (not real fixtures)

Desk → **More → Practice data** — labeled demo teams/dates for testing trebles without an API key.

## Tests

```powershell
.\scripts\test-api.ps1
```

## Key API routes

| Route | Purpose |
|-------|---------|
| `GET /health` | API + DB status |
| `POST /auth/register`, `POST /auth/login` | JWT auth |
| `POST /ingestion/fixtures/seed-demo` | Practice fixtures (not real schedule) |
| `POST /ingestion/import/betpawa` | Real BetPawa upcoming football + Over 1.5 odds |
| `POST /odds/import/the-odds-api` | Optional Odds API fixtures + Over 1.5 |
| `GET /slips`, `GET /slips/retention` | Slip history (default last 90 days) |
| `POST /slips/generate` | Best treble(s); prefers real fixtures when ≥3 exist |
| `POST /slips/sync-status` | Recompute PENDING/LIVE/WON/LOST from fixture scores |

Docs: http://localhost:8000/docs

## BetPawa workflow

1. **Import BetPawa** (or practice data for testing).
2. Generate treble → copy checklist → build acca on BetPawa manually.
3. **Mark placed on BetPawa**.
4. When scores are in the DB (`PATCH /tracker/fixtures/{id}/live`) → **Sync scores**.

## Mobile / PWA

Add to home screen from Samsung Internet or Chrome (HTTPS in production). Layout uses device safe-area margins only.

## Dashboard troubleshooting

| Issue | Fix |
|-------|-----|
| Webpack `897.js` / missing `.next` | Stop dev server → `.\scripts\dev-dashboard.ps1 -Clean` |
| CORS / 401 | Restart API; log in again |
| Stale demo team names | **More → Practice data** to refresh demo rows |

## Railway

Two services from this repo, plus Railway Postgres.

| Service | Root directory | Public route |
|---------|----------------|--------------|
| API | `core-prediction-engine` | `/health` |
| Web | `apps/dashboard` | `/` |

Set `DATABASE_URL` on the API to the Postgres variable (`postgresql://` is accepted). Set `JWT_SECRET`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` before the first start. Set `NEXT_PUBLIC_API_URL` on the web service to the API’s public URL before its build, then set `CORS_ORIGINS` and `APP_PUBLIC_URL` on the API to the web URL.

## Docker (optional)

```powershell
docker compose up --build
```

Local Postgres + `dev-api.ps1` works without Docker.

## 90-day retention

Slips older than `PURGE_DAYS` (default 90) are removed by `POST /maintenance/purge-slips` or the scheduled purger job.
