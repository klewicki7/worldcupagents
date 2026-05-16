# Proposal — phase-0-foundations

**Change**: phase-0-foundations
**Scope**: M0 (repo skeleton) + M1 (schema + fixture) from `docs/09-roadmap.md`
**Delivery strategy**: single-pr (size:exception expected)
**Date**: 2026-05-16

---

## Intent

Phase 0 turns a near-greenfield repo into a clone-and-run development environment with a fully seeded database. Without it, no downstream milestone (auth, MCP, predictions, scoring) has anywhere to land. The deliverable is a repo where `make dev` boots Postgres + backend + frontend on localhost, and where `make seed && make test` proves that all 48 teams and the group-stage portion of the 104-match calendar are correctly loaded with triggers, constraints, and lock-time semantics enforced. After Phase 0, every later phase has concrete, queryable data to build against instead of theoretical schema.

## Scope — In

**M0 — Repo skeleton (½ day)**
- Keep existing `worldcupagents-fe/` directory (NO rename). Update `docs/CLAUDE.md` "Repo layout (target)" to reference `worldcupagents-fe/` instead of `frontend/`.
- `backend/` via `uv init`; install full dep list from `docs/KICKOFF.md` Day-1 script
- `docker-compose.yml` — Postgres 16 local
- `Makefile` — targets `dev`, `test`, `migrate`, `seed`
- `.env.example` for backend and frontend
- Root `CLAUDE.md` (copy of `docs/CLAUDE.md`)
- `README.md` — clone-and-run setup
- `scripts/` and `data/` directories scaffolded
- Update `docs/02-trd.md`: Next.js 15 → 16; amend `docs/KICKOFF.md` "Decisions locked" table
- Backend `/healthz` endpoint returning `{"status":"ok"}`
- Frontend default landing page renders on `:3000`

**M1 — Schema + fixture (1 day)**
- All SQLAlchemy models from `docs/03-data-model.md` (sans `brackets`/`bracket_scores`): humans, agents, teams, matches, predictions, prediction_history, scores, audit_log, pending_resolutions
- Alembic initial migration `202605160001_initial.py` (autogenerate + manual review)
- Triggers: `set_lock_at`, `snapshot_prediction_history`, `touch_updated_at`
- `data/teams.yaml` — 48 teams, hand-copied verbatim from `docs/07-fixture-loading.md` § 4
- `data/matches.yaml` — 72 group-stage entries with full team IDs + kickoff/venue; 32 knockout entries as structural placeholders (`home_placeholder` / `away_placeholder`, kickoff dates per published FIFA calendar where available, otherwise nullable kickoff to be patched in later phases)
- `scripts/load_fixture.py` — idempotent upsert for both teams and matches
- `tests/test_fixture_integrity.py` — encodes the verification queries from `docs/07-fixture-loading.md` § 8

## Scope — Out (explicit non-goals)

- No MCP tools, no MCP server mount
- No auth, no Google OAuth setup, no Auth.js wiring beyond `next-auth@beta` install (not even configured)
- No REST endpoints beyond `/healthz`
- No frontend pages beyond the default Next scaffold
- No shadcn install, no Tailwind configuration changes beyond what `create-next-app` did
- No deployment (Fly, Vercel, Neon, DNS, domains)
- No Sentry, no `structlog`, no observability
- No GitHub Actions / CI
- No `brackets` / `bracket_scores` tables (v1.1)
- No `scripts/seed_dev.py` (only `load_fixture.py` for now)
- Full 104-match calendar with real teams in knockouts (cannot exist until group stage ends in real life)

## Approach

### M0 order (strict — each step unblocks the next)

1. **Frontend dir confirmed**: `worldcupagents-fe/` keeps its name. Verify `pnpm install && pnpm dev` boots on `:3000`. Update `docs/CLAUDE.md` "Repo layout (target)" to show `worldcupagents-fe/` in place of `frontend/`.
2. **Backend bootstrap**: `cd backend && uv init`; add deps (`fastapi fastmcp sqlalchemy[asyncio] asyncpg alembic pydantic-settings argon2-cffi python-jose[cryptography] apscheduler httpx pyyaml`) and dev deps (`pytest pytest-asyncio httpx ruff mypy`). Stub `app/main.py` with FastAPI + `/healthz`.
3. **Local DB**: `docker-compose.yml` with Postgres 16, named volume, port 5432, `POSTGRES_DB=worldcupagents`. Verify `docker compose up -d` + `psql` connect.
4. **Glue**: `Makefile` (`dev` runs `docker compose up -d db && (cd backend && uv run uvicorn app.main:app --reload --port 8000) & (cd frontend && pnpm dev)`); `.env.example` for backend (`DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM=HS256`, `ENVIRONMENT=development`, `LOG_LEVEL=info`) and frontend (`NEXTAUTH_URL`, `NEXTAUTH_SECRET`, `NEXT_PUBLIC_API_BASE_URL`).
5. **Docs**: root `CLAUDE.md` (copy of `docs/CLAUDE.md`, with `worldcupagents-fe/` path), `README.md` with prereqs (uv, pnpm, Docker) and the M0 acceptance script.
6. **TRD/KICKOFF/CLAUDE amendments**: edit `docs/02-trd.md` § 2 "Frontend" → Next.js 16; add a note flagging the need to verify Auth.js v5 + shadcn + Tailwind v4 compatibility before M2. Add two rows to `docs/KICKOFF.md` "Decisions locked" table: `Frontend framework | Next.js 16.2.6 (was 15) | this proposal` and `Frontend dir name | worldcupagents-fe/ (was frontend/) | this proposal`. Update `docs/CLAUDE.md` "Repo layout (target)" tree: replace `frontend/` with `worldcupagents-fe/`.

### M1 order (strict)

1. **SQLAlchemy models** — one file per table under `backend/app/db/models/`. Declarative base in `backend/app/db/base.py`, async engine + session factory in `backend/app/db/session.py`. All FKs, indexes, CHECK constraints, and column types match `docs/03-data-model.md` exactly.
2. **Alembic init** — `alembic init alembic`, point `env.py` at the declarative metadata, configure async-aware migrations.
3. **Initial migration** — run autogenerate, then **hand-edit** to add the three triggers (`set_lock_at`, `snapshot_prediction_history`, `touch_updated_at`) and the `v_agent_leaderboard` view as raw SQL operations. Autogenerate will not produce these.
4. **`data/teams.yaml`** — copy verbatim from `docs/07-fixture-loading.md` § 4. 48 entries.
5. **`data/matches.yaml`** — see strategy below.
6. **`scripts/load_fixture.py`** — implement as in `docs/07-fixture-loading.md` § 6. Use `INSERT ... ON CONFLICT DO UPDATE` so re-runs are no-ops when YAML is unchanged.
7. **`tests/test_fixture_integrity.py`** — encode all queries from `docs/07-fixture-loading.md` § 8 as pytest cases (count = 48 teams, count = 104 matches, 4 teams per group × 12, 72 group matches with both team IDs non-null, all `lock_at = kickoff_at - 1h`, stage distribution 72/16/8/4/2/1/1). Test fixture spins up the test DB, runs migration, runs `load_fixture`, asserts.

### `data/matches.yaml` strategy — hand-author group stage

**Decision**: hand-author the 72 group-stage entries; write knockout entries (73–104) as structural placeholders.

**Justification**: the Wikipedia scraper (`scripts/build_matches_yaml.py` per `docs/07-fixture-loading.md` § 7) is explicitly described as "fragile" and "bootstrapping only" — it depends on stable HTML structure of `es.wikipedia.org/wiki/Copa_Mundial_de_Fútbol_de_2026`. The roadmap says "partial OK if knockout dates not all published," so we don't need the scraper to deliver M1. Hand-writing 72 entries from the published FIFA calendar (kickoff, venue city, both team IDs by group order) takes ~30 minutes and is verifiable line-by-line. The scraper is deferred — we may write it later as a refresh tool, but it is NOT on the M1 critical path. Knockout entries (73–104) get `home_team_id: null`, `away_team_id: null`, structural placeholders ("Winner Group A", "Best 3rd C/D/E/F"), and best-known kickoff times.

### TRD compatibility check (carry-forward, NOT executed in Phase 0)

Phase 0 only **installs** `next-auth@beta` and leaves the default Next 16 scaffold's Tailwind v4 config untouched. It does NOT add shadcn, does NOT wire Auth.js. But the proposal explicitly flags — in the updated `docs/02-trd.md` — that before M2 begins, the implementer must verify on Next 16:
- Auth.js v5 (`next-auth@beta`) works with App Router middleware and JWT strategy
- shadcn CLI (`pnpm dlx shadcn@latest init`) succeeds on a Next 16 / React 19 / Tailwind v4 baseline
- No known peer-dep conflicts

This is a Phase 0 doc-update deliverable, not a Phase 0 code task.

## Acceptance criteria

**M0** (from `docs/09-roadmap.md`):
```bash
git clone <repo> && cd worldcupagents
make dev                                  # Postgres + backend :8000 + frontend :3000 all up
curl http://localhost:8000/healthz        # → {"status":"ok"}
open http://localhost:3000                # landing page renders
```

**M1** (from `docs/09-roadmap.md`):
```bash
make migrate                              # alembic upgrade head succeeds
make seed                                 # scripts/load_fixture.py --all runs idempotently
make test tests/test_fixture_integrity.py # all queries pass
```

Concretely, `test_fixture_integrity.py` asserts:
- `SELECT COUNT(*) FROM teams` = 48
- 4 teams per `group_letter`, all 12 groups present
- `SELECT COUNT(*) FROM matches` = 104
- Stage distribution: 72 group / 16 r32 / 8 r16 / 4 qf / 2 sf / 1 third / 1 final
- 0 group matches with NULL `home_team_id` or `away_team_id`
- 0 matches where `lock_at != kickoff_at - INTERVAL '1 hour'`
- Re-running `load_fixture.py` produces no row changes (idempotency)

## Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Hand-authored `matches.yaml` has typos (wrong team IDs, wrong dates) | Medium | `test_fixture_integrity.py` catches structural errors; team-ID typos caught by FK constraint on insert; human review against FIFA-published calendar |
| Next.js 16 + Auth.js v5 + shadcn + Tailwind v4 incompatibility surfaces later | Medium | Phase 0 only **flags** the check in TRD; M2 is the first phase that exercises this — earlier discovery would be better but requires installing those libs, which is out of scope |
| Doc references to `frontend/` get missed during the `worldcupagents-fe/` rename of the target layout | Low | Grep all docs for `frontend/` after edits; only `docs/CLAUDE.md` should change. The actual dir is not being renamed, so no tooling/CI impact. |
| Single-PR size > 400 LOC (likely) — review burden | High | Delivery strategy is `single-pr`, accepted upfront. PR will require a `size:exception` label at merge. Split commits cleanly per work-unit (`feat: bootstrap monorepo (M0)`, `feat: schema + fixture (M1)`, plus `docs:` for TRD/KICKOFF updates) to keep review tractable. |
| Async Alembic + triggers — autogenerate won't produce triggers/views | High | Initial migration is hand-edited; reviewer must verify trigger DDL matches `docs/03-data-model.md` § 4 verbatim |
| `docker compose` networking flakes on first `make dev` (DB not ready before backend connects) | Medium | Add a `wait-for-db` loop in `Makefile` or use `depends_on: condition: service_healthy` in compose |

## Open questions

1. **Knockout kickoff times**: do we set best-known UTC times for matches 73–104 now, or leave `kickoff_at` nullable and patch via admin panel later? Recommendation: set best-known times so `lock_at` trigger fires and queries work; admin can override.
2. **Frontend dep installs in M0**: install `next-auth@beta` only (per KICKOFF.md), or also install shadcn now to surface compat issues early? Recommendation: install `next-auth@beta` only. shadcn/Tailwind v4 wiring is M2.

(Both are minor; either answer is acceptable. Default to the recommendations unless Kevin pushes back.)

## Estimated effort

Per `docs/KICKOFF.md`: M0 = ½ day, M1 = 1 day. **Confirmed.** Hand-authoring 72 match rows from the FIFA calendar adds ~30 min within M1; not material. Total Phase 0 ≈ 1.5 dev-days.
