# KICKOFF — Where to start, what to attack, in what order

> Companion to `09-roadmap.md`. The roadmap tells you **what** each milestone is.
> This doc tells you **why this order**, **what's on the critical path**, and **what NOT to do early**.

---

## Decisions locked before coding

| Decision | Resolution | Source |
|---|---|---|
| Auth provider | **Google OAuth** (Auth.js v5). Single provider for v1. | TRD § 6 |
| JWT signing | **HS256 symmetric**. `JWT_SECRET` = `NEXTAUTH_SECRET` (same string). Rotation = coordinated deploy. | TRD § 7 |
| Token hashing (agents) | **argon2id** + 60s in-memory verify cache. | TRD § 6 |
| Bracket idempotency | **Upsert until `BRACKET_LOCKED`** (first kickoff). `is_update` flag in response. | MCP spec § 4.12 |
| Build approach | **Backend-first vertical slice**, then frontend. Reason: MCP server is the product. The frontend is a dashboard around it. | this doc |
| Frontend framework | **Next.js 16.2.6** (was 15) | phase-0-foundations proposal |
| Frontend dir name | **`worldcupagents-fe/`** (was `frontend/`) | phase-0-foundations proposal |

If any of these change later, update this table first, then the relevant doc.

---

## The two principles

**1. Critical path drives order, not feature glamour.**
The product is: an agent connects via MCP, predicts, gets scored. Anything that doesn't move that vertical slice forward is deferred. Leaderboard UI is pretty but useless without scored predictions. Build the engine first.

**2. Every milestone ends with an acceptance script that runs.**
If you can't curl it / run a test / open a URL and see the thing work, the milestone isn't done. No "looks good in my head" milestones.

---

## Phase 0 — Foundations (before any feature code)

Goal: a repo you can clone-and-run in 60 seconds.

**Order is strict — each step unblocks the next:**

1. **M0 repo skeleton** (½ day) — monorepo layout, `docker-compose.yml`, `uv` + `pnpm` init, `Makefile`, `.env.example` for both apps, `make dev` boots Postgres + backend + frontend.
2. **M1 schema + fixture** (1 day) — all 48 teams + 104 matches loaded, triggers in place, `tests/test_fixture_integrity.py` green.

**Why these two first and ALONE:** they have zero external dependencies (no Google client ID, no Fly account, no Vercel, no domain). You can do them on a plane. After M1 you have a seeded DB that makes everything downstream concrete instead of theoretical.

**Do NOT do during Phase 0:**
- Don't deploy. Don't buy a domain. Don't configure Google OAuth in Cloud Console yet.
- Don't write frontend pages. The frontend in M0 is just `pnpm create next-app` boilerplate.
- Don't open Sentry, don't set up CI. That's M8.

---

## Phase 1 — Critical path to "an agent can predict" (the vertical slice)

This is the product. Everything else is decoration around it.

**Strict order:**

3. **M2 auth + agent registration** (2 days) — humans sign in with Google, register 1 agent, receive a token shown exactly once.
4. **M3 MCP server with read-only tools** (2 days) — agent connects from Claude Desktop, sees the 8 read tools, calls `list_upcoming_matches` against real data.
5. **M4 `submit_prediction`** (2 days) — the only write tool that matters for v1.
6. **M5 scoring + resolution** (2 days) — admin resolves a match → all predictions get a Brier score automatically.

**End of Phase 1 = the product works.** Without a single UI page beyond the agent-registration flow, you can demo: "Sign in → create agent → connect Claude Desktop → predict a match → I resolve it → you have a score." That's the whole game.

**Parallelizable inside this phase (if you ever have help):**
- M3 read-only tools and the dashboard polish from M2 can be done in parallel by two people. Solo: do M3 first, the dashboard can wait.
- M5 scoring **pure functions** (`app/domain/scoring.py`) can be written and unit-tested before M4 lands — they have zero dependencies on anything except input types. Good "warm-up while coffee brews" work.

---

## Phase 2 — Make it public and operable

7. **M6 frontend public pages** (3 days) — landing, leaderboard, matches, agent profiles. Now there's something to share.
8. **M7 admin panel** (1.5 days) — you (Kevin) need to resolve 104 matches from your phone over 30 days. This is non-negotiable infrastructure.
9. **M8 deploy + observability** (1.5 days) — Fly + Vercel + Sentry + Cloudflare DNS. Smoke test in prod.

**Why M6 before M7:** the public site is what drives signups. The admin panel is internal-only. If you launch a day late on admin, you patch via SQL the first day. If you launch a day late on the public site, you have no agents to score.

**Parallelizable:**
- M6 and M7 can interleave. The leaderboard page (M6) and the resolve-match flow (M7) hit different routes.

---

## Phase 3 — Launch and post-launch

10. **M9 marketing + soft launch** — see roadmap. Engineering side is small (status page, signup notification email).
11. **M10 bracket bonus** (v1.1) — ships AFTER tournament starts, BEFORE Round of 32. Don't try to fit it in v1.

---

## Day 1 concrete starting point

When you sit down tomorrow:

```bash
# 1. Create the repo skeleton at the right location
mkdir -p worldcupagents/{backend,frontend,scripts,data}
cd worldcupagents
git init
# move docs/ in, copy docs/CLAUDE.md to root CLAUDE.md

# 2. Backend init
cd backend && uv init
uv add fastapi fastmcp 'sqlalchemy[asyncio]' asyncpg alembic pydantic-settings \
       argon2-cffi 'python-jose[cryptography]' apscheduler httpx pyyaml
uv add --dev pytest pytest-asyncio httpx ruff mypy

# 3. Frontend init
cd ../frontend && pnpm create next-app@latest . --typescript --tailwind --app --eslint
pnpm add next-auth@beta

# 4. docker-compose.yml + Makefile + .env.example
# 5. Commit: "feat: bootstrap monorepo (M0)"
```

That's your **first commit**. Don't write a single line of business logic until `make dev` boots everything.

---

## What "robust AND fast" means here

- **Robust = the constraints in `docs/CLAUDE.md` are enforced in code, not just in your head.**
  Unique constraint on `agents.human_id`. Server-side lock check on every write. Probability sum validation on every submission. Argon2id on token verification. Idempotent resolution. These are not features — they are the spine.

- **Fast = ruthless deferral of anything not on the critical path.**
  No Sentry until M8. No CI until M8. No domain until M8. No bracket until M10. No "what if we add Discord login" until v2 — and probably never.

If you find yourself writing code that isn't unblocking the next acceptance script, stop.

---

## Risk checklist before coding M2

Before touching auth code, confirm these are done (15 min, not engineering):

- [ ] Google Cloud project created, OAuth consent screen configured (External, testing mode is fine).
- [ ] OAuth 2.0 Client ID created (Web Application type), authorized redirect URI = `http://localhost:3000/api/auth/callback/google` for dev.
- [ ] Client ID + client secret saved to a password manager.
- [ ] `JWT_SECRET` / `NEXTAUTH_SECRET` generated once (`openssl rand -base64 32`) and saved.
- [ ] `ADMIN_EMAILS` env var planned: your email + one backup (per `09-roadmap.md` risks table).

If any of these are blank when M2 starts, you'll lose half a day mid-flow.
