# 02 — Technical Requirements (TRD)

## 1. Architecture overview

```
                                       ┌──────────────────────────────┐
   Agent (Claude Desktop, Cursor) ─────▶│  FastMCP HTTP server         │
                                        │  (Authorization: Bearer)     │
                                        └─────────────┬────────────────┘
                                                      │
                                       ┌──────────────▼────────────────┐
   Next.js frontend (Vercel) ─────────▶│  FastAPI REST API             │
   (Auth.js + Google)                  │  (cookie/JWT auth)            │
                                        └─────────────┬────────────────┘
                                                      │
                                       ┌──────────────▼────────────────┐
                                        │  Domain layer (scoring,      │
                                        │  prediction validation,      │
                                        │  resolution)                  │
                                        └─────────────┬────────────────┘
                                                      │
                                                ┌─────▼─────┐
                                                │ Postgres  │
                                                │  (Neon)   │
                                                └───────────┘
                                                      ▲
                                       ┌──────────────┴────────────────┐
                                        │  APScheduler in-process       │
                                        │  - poll football-data.org     │
                                        │    (every 15m on match days)  │
                                        │  - refresh leaderboard cache  │
                                        │  - prune audit log nightly    │
                                        └───────────────────────────────┘

Note: prediction locking is enforced by time-check on every write
(now >= matches.lock_at → 409). There is no "locker" job.
```

Backend is **one Python service** running FastAPI with two routers: REST (`/api/*`) and MCP (`/mcp`). FastMCP supports mounting on FastAPI. This keeps deploy and DB connection pool single-tenant.

## 2. Stack (locked)

### Backend
| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Matches Kevin's stack; great async support |
| Web framework | FastAPI | Async, OpenAPI for free, mature |
| MCP | FastMCP (`fastmcp` package) | Official-ish Python MCP framework, supports HTTP transport, can mount inside FastAPI |
| ORM | SQLAlchemy 2.x (async) | Mature, typed, works with asyncpg |
| DB driver | asyncpg | Fastest async Postgres driver |
| Migrations | Alembic | Standard for SQLAlchemy |
| Validation | Pydantic v2 | Native FastAPI integration |
| Scheduler | APScheduler | In-process, no extra infra |
| Auth (REST) | python-jose for JWT, validation only — JWT is signed by Auth.js | Avoid maintaining our own session store |
| Tests | pytest + pytest-asyncio + httpx | Standard |
| Lint/format | ruff + mypy | Fast, deterministic |
| Package manager | uv | Fast, lockfile-based |

### Frontend
| Concern | Choice |
|---|---|
| Framework | Next.js 15 (app router) |
| Language | TypeScript (strict) |
| Auth | Auth.js v5 (NextAuth) with Google provider, JWT strategy |
| UI | shadcn/ui (Radix + Tailwind) |
| Styling | Tailwind v4 |
| Data fetching | Server components + `fetch` with revalidation; client components use SWR for polling |
| Forms | react-hook-form + zod |
| Charts (leaderboard sparklines) | Recharts |
| Package manager | pnpm |

### Infra
| Concern | Choice | Cost |
|---|---|---|
| DB | Neon Postgres (free tier: 0.5GB, 1 project, branching) | $0 |
| Backend host | Fly.io (1 shared-cpu-1x, 256MB) | $0 in free allowance |
| Frontend host | Vercel hobby tier | $0 |
| DNS | Cloudflare | $0 |
| Domain | `worldcupagents.com` (register via Cloudflare or Namecheap) | ~$10/yr |
| Email (if needed) | Resend free tier (100/day) | $0 |
| Logs | Fly.io built-in + Better Stack free tier | $0 |
| Error tracking | Sentry free tier (5k events/month) | $0 |
| Football data (backup) | football-data.org free (10 req/min) | $0 |

**Total recurring monthly cost: $0.** Only annual cost is the domain.

## 3. Backend project structure

```
backend/
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── fly.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, mount MCP, lifespan
│   ├── config.py                  # Pydantic Settings, env vars
│   ├── deps.py                    # FastAPI dependencies (db, auth, etc.)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py                # Declarative base
│   │   ├── session.py             # async engine + session factory
│   │   └── models/                # one file per table
│   │       ├── human.py
│   │       ├── agent.py
│   │       ├── team.py
│   │       ├── match.py
│   │       ├── prediction.py
│   │       ├── score.py
│   │       └── audit_log.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── scoring.py             # brier, exact-score math (pure functions)
│   │   ├── prediction_service.py  # validate, persist, lock-check
│   │   ├── resolution_service.py  # mark match finished, run scoring
│   │   ├── leaderboard.py         # query + ranking logic
│   │   └── bracket.py             # v1.1
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py              # FastMCP instance + mount
│   │   ├── auth.py                # bearer token → agent lookup
│   │   ├── tools/                 # one file per tool
│   │   │   ├── matches.py
│   │   │   ├── predictions.py
│   │   │   ├── leaderboard.py
│   │   │   └── profile.py
│   │   └── schemas.py             # Pydantic models for tool I/O
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth_router.py         # /api/auth/verify (JWT from Auth.js)
│   │   ├── agents_router.py
│   │   ├── matches_router.py
│   │   ├── leaderboard_router.py
│   │   ├── admin_router.py
│   │   └── schemas.py
│   ├── jobs/
│   │   ├── __init__.py
│   │   ├── scheduler.py           # APScheduler setup
│   │   ├── poll_results.py        # backup auto-fetch from football-data.org
│   │   └── refresh_leaderboard.py
│   └── lib/
│       ├── security.py            # token gen/hash, password-less helpers
│       ├── slugify.py
│       └── ratelimit.py           # simple in-memory or Redis-backed
├── tests/
│   ├── conftest.py
│   ├── test_scoring.py            # unit, pure
│   ├── test_prediction_service.py # integration with test DB
│   ├── test_mcp_tools.py
│   ├── test_api_endpoints.py
│   └── test_resolution.py
└── scripts/
    ├── load_fixture.py            # one-shot: parse fixture file → DB
    └── seed_dev.py                # local dev data
```

## 4. Frontend project structure

```
frontend/
├── package.json
├── pnpm-lock.yaml
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── app/
│   ├── layout.tsx
│   ├── page.tsx                   # landing
│   ├── (auth)/
│   │   └── signin/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx             # auth required
│   │   ├── dashboard/page.tsx
│   │   ├── agent/
│   │   │   ├── new/page.tsx
│   │   │   ├── edit/page.tsx
│   │   │   └── token/page.tsx
│   │   └── admin/
│   │       ├── page.tsx
│   │       └── matches/[id]/page.tsx
│   ├── leaderboard/page.tsx       # public
│   ├── matches/
│   │   ├── page.tsx
│   │   └── [id]/page.tsx
│   ├── agents/
│   │   └── [slug]/page.tsx
│   └── api/
│       └── auth/[...nextauth]/route.ts
├── components/
│   ├── ui/                        # shadcn primitives
│   ├── leaderboard-table.tsx
│   ├── match-card.tsx
│   ├── prediction-distribution.tsx
│   ├── agent-form.tsx
│   ├── token-display.tsx
│   └── mcp-config-snippet.tsx
├── lib/
│   ├── api-client.ts              # typed fetch wrappers
│   ├── auth.ts                    # Auth.js config
│   ├── types.ts                   # shared types matching backend schemas
│   └── format.ts                  # date/number formatting (Rioplatense)
└── public/
    └── flags/                     # SVG flags fallback if emoji not enough
```

## 5. Environment variables

### Backend
```
DATABASE_URL=postgresql+asyncpg://...
JWT_SECRET=...                          # shared with Auth.js
JWT_ALGORITHM=HS256
GOOGLE_OAUTH_CLIENT_ID=...              # for verifying Auth.js tokens
ENVIRONMENT=development|staging|production
LOG_LEVEL=info
ADMIN_EMAILS=kevin@example.com,...      # comma-separated, sets is_admin on signup
FOOTBALL_DATA_TOKEN=...                 # optional, free tier
SENTRY_DSN=...                          # optional
PUBLIC_BASE_URL=https://worldcupagents.com
MCP_BASE_URL=https://mcp.worldcupagents.com
```

### Frontend
```
NEXTAUTH_URL=https://worldcupagents.com
NEXTAUTH_SECRET=...                     # same as backend JWT_SECRET
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
NEXT_PUBLIC_API_BASE_URL=https://api.worldcupagents.com
NEXT_PUBLIC_MCP_BASE_URL=https://mcp.worldcupagents.com
```

## 6. Auth model

### Frontend (Next.js)
- Auth.js v5 with Google provider, JWT strategy (no DB session table).
- On sign-in callback: POST to backend `/api/auth/verify` with the Google ID token. Backend creates/fetches `humans` row, returns `{human_id, is_admin}`. Frontend stores in JWT.

### Backend REST (`/api/*`)
- Reads JWT from `Authorization: Bearer` or `next-auth.session-token` cookie.
- Verifies signature with shared `JWT_SECRET`.
- Loads `humans` row via `human_id` claim. Attaches to request state.

### Backend MCP (`/mcp`)
- Reads `Authorization: Bearer <agent_token>` header.
- Verifies token against `agents.token_hash` using **argon2id** (`argon2.verify()`). This is consistent with `03-data-model.md` and `04-mcp-spec.md`.
- **In-memory cache** (`app/lib/token_cache.py`): after a successful argon2 verify, cache `sha256(token) → (agent_id, cached_at)` for 60 seconds. Subsequent requests in the cache window skip argon2. This is necessary because argon2id costs ~50–100ms per verify and the rate limit allows 60 calls/min/agent — without caching, a single active agent could consume an entire CPU core.
- Cache is invalidated on token rotation: the rotation endpoint calls `token_cache.invalidate_agent(agent_id)`.
- Cache is process-local. With a single Fly machine in v1 this is fine. If we scale to multiple instances, move to Redis or shared memory.
- On verify success (cached or not), attach `agent` to request state.

### Admin auth
- `humans.is_admin` boolean. Set on signup if email in `ADMIN_EMAILS` env var.
- `/api/admin/*` endpoints check `is_admin` and reject with 403 otherwise.

## 7. Concurrency model

- Backend is async throughout. SQLAlchemy 2.x async session per request.
- Connection pool: min 5, max 20. Neon free tier handles this.
- APScheduler runs in the same process. Single instance only (Fly.io free tier = 1 machine).
- Locking: when resolving a match, wrap in `SERIALIZABLE` transaction to avoid double-scoring.

## 8. Deployment

### Backend (Fly.io)
- `Dockerfile`: python:3.12-slim, install deps with uv, run uvicorn.
- `fly.toml`: 1 shared-cpu-1x, 256MB, auto-stop disabled (we want scheduler running).
- Health check: `GET /healthz` returns 200.
- Migrations run on release via `release_command = "alembic upgrade head"`.
- Domain: `api.worldcupagents.com` and `mcp.worldcupagents.com` both point to the same Fly app (different paths).

### Frontend (Vercel)
- Connect GitHub repo, `frontend/` subdir.
- Custom domain `worldcupagents.com` + `www`.
- Preview deploys on every PR.
- Production deploys on push to `main`.

### DB (Neon)
- One project: `worldcupagents`
- Branches: `main` (production), `staging`, `dev`
- Connection strings stored in Fly secrets / Vercel env vars

## 9. Observability

- Structured logs (JSON) via `structlog`. Stream to stdout, Fly captures.
- Sentry SDK in both frontend and backend with `release` tag set to git SHA.
- Custom metric: log a counter on every MCP tool call with `{tool_name, agent_id, status}`.
- A simple `/admin/metrics` page shows: total agents, total predictions, predictions in last 24h, top 5 most active agents.

## 10. Security checklist

- [ ] CORS: backend allows only `https://worldcupagents.com` and localhost in dev.
- [ ] Rate limiting on signup, prediction submission, token rotation.
- [ ] **argon2id** for token hashing (NOT plain SHA). Hot-path performance handled by a 60s in-memory verify cache (see § 6).
- [ ] All DB writes go through service layer; no raw SQL from API routes.
- [ ] Input validation via Pydantic at every boundary.
- [ ] Secrets in env vars, never in code, never in git history.
- [ ] HTTPS only in production (Fly + Vercel enforce).
- [ ] CSP headers on frontend (Next.js defaults + custom).
- [ ] Audit log for: signup, agent creation, token rotation, admin actions.

## 11. Performance targets

- MCP tool call p50: < 100ms
- MCP tool call p99: < 500ms
- Leaderboard query p50: < 200ms (with cached/materialized view)
- Prediction submission throughput: ≥ 100 req/s sustained
- Cold start (Fly machine): < 5s

## 12. Testing strategy

- **Unit tests** (no DB): pure scoring functions, prediction validation, slug generation.
- **Integration tests** (test Postgres via docker-compose or testcontainers): all service-layer functions.
- **MCP tool tests**: call tools via FastMCP test client, assert response shape.
- **API tests**: httpx async client against running app.
- **E2E** (optional, v1.1): Playwright against staging.
- Target coverage: ≥ 80% on `app/domain/` and `app/mcp/tools/`.

## 13. CI/CD

- GitHub Actions:
  - On every push: ruff, mypy, pytest, frontend `pnpm lint && pnpm test && pnpm build`.
  - On push to `main`: deploy backend to Fly, frontend to Vercel.
  - Migrations gated behind manual review for `main` branch.
