# worldcupagents — Claude Code instructions

You are working on **worldcupagents**, an MCP-based prediction platform where each human registers exactly one AI agent that predicts FIFA World Cup 2026 matches. Agents submit probabilistic predictions through MCP tools and are scored on calibration (Brier score) plus an optional one-shot bracket bonus (added in v1.1).

## Read these docs in order before writing code

1. `docs/00-overview.md` — what we're building and why
2. `docs/01-prd.md` — product requirements (features, scope, non-goals)
3. `docs/02-trd.md` — technical requirements (stack, architecture, deploy)
4. `docs/03-data-model.md` — database schema, migrations, constraints
5. `docs/04-mcp-spec.md` — MCP server tools, auth, contracts
6. `docs/05-scoring.md` — Brier scoring, exact-score bonus, leaderboard math
7. `docs/06-api-spec.md` — REST endpoints for the Next.js frontend and admin
8. `docs/07-fixture-loading.md` — how to load the 104 matches into the DB
9. `docs/08-admin-panel.md` — manual match resolution flow
10. `docs/09-roadmap.md` — milestones with acceptance criteria
11. `docs/10-conventions.md` — code style, project structure, testing rules

## Critical constraints (do not violate)

- **One agent per human.** Enforced by a `UNIQUE` constraint on `agents.human_id` AND by gating signup behind Google OAuth. Never bypass.
- **Predictions lock 1 hour before kickoff.** Server-side check in every write path.
- **Probabilities must sum to 1.0** (with ε=0.001 tolerance). Reject otherwise.
- **No paid services in v1.** Everything must run on free tiers. If a feature requires paid infra, flag it and propose an alternative.
- **Match resolution is admin-only.** Agents and users never write to `matches.home_goals` / `away_goals`.
- **Spanish (Rioplatense) for user-facing copy in the frontend. Code, identifiers, commit messages, and internal docs are in English.**

## Stack (locked)

- Backend: Python 3.12, FastAPI, FastMCP (HTTP transport), SQLAlchemy 2.x, Alembic, Pydantic v2
- DB: PostgreSQL 16 (Neon free tier in prod, docker-compose locally)
- Frontend: Next.js 15 (app router), TypeScript, shadcn/ui, Tailwind v4, Auth.js (NextAuth v5) with Google provider
- Hosting: Fly.io (backend), Vercel (frontend)
- Scheduler: APScheduler in-process
- Package managers: `uv` for Python, `pnpm` for Node

## Working agreements with the human (Kevin)

- Kevin is technical, 6+ years dev experience. **Ask before making decisions that change architecture, schema, or contracts.** Don't silently swap libraries.
- When you finish a task, summarize what changed and why in 3–5 bullets. No long postambles.
- If a doc is ambiguous, ask. Don't guess.
- Commit messages: conventional commits (`feat:`, `fix:`, `chore:`, `docs:`). One concern per commit.

## Repo layout (target)

```
worldcupagents/
├── CLAUDE.md                  # this file
├── docs/                      # all design docs
├── backend/                   # FastAPI + FastMCP server
│   ├── app/
│   │   ├── main.py
│   │   ├── mcp/               # MCP tool definitions
│   │   ├── api/               # REST endpoints
│   │   ├── domain/            # business logic, scoring
│   │   ├── db/                # models, session, migrations
│   │   ├── jobs/              # APScheduler tasks
│   │   └── config.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                  # Next.js app
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── package.json
├── scripts/                   # fixture loader, one-off utils
├── docker-compose.yml         # local Postgres
└── README.md
```

Build in this order: backend skeleton → DB + migrations → MCP server with `list_upcoming_matches` → auth + agent registration → prediction submission → scoring engine → admin panel → frontend leaderboard → bracket bonus (v1.1).
