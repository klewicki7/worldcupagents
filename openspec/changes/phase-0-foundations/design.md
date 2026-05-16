# Design — phase-0-foundations

**Change**: phase-0-foundations
**Phase**: SDD design (architecture)
**Scope covered**: M0 (repo skeleton) + M1 (schema + fixture)
**Date**: 2026-05-16
**Delivery**: single PR with `size:exception`

This document is the WHAT-it-looks-like for Phase 0. It locks file paths, dependency versions, the migration shape, the YAML schema for matches, and the loader/test contracts. It deliberately does NOT introduce new architectural patterns — the macro architecture is already locked by `docs/02-trd.md` and `docs/03-data-model.md`. Anything here that contradicts those docs is a bug in this document.

---

## 1. Architectural approach

Bootstrap-only. We are scaffolding a monorepo skeleton plus the data layer; no domain logic, no API surface beyond `/healthz`, no MCP server. The architectural pattern is dictated by the TRD:

- **Layering** (backend): `app/main.py` (FastAPI app) → `app/config.py` (settings) → `app/db/` (engine, session, models). Phase 0 stops at `db/`. `domain/`, `api/`, `mcp/`, `jobs/`, `lib/` directories are NOT created yet — `sdd-apply` MUST resist the urge to scaffold empty packages "for symmetry". We add them when the milestone that needs them lands.
- **Boundaries**: `scripts/load_fixture.py` imports from `backend/app/` (config, session, models). It is NOT a sibling package — it is a thin CLI on top of the backend. This avoids two engines, two settings instances, two sources of truth for `DATABASE_URL`.
- **Frontend**: untouched except for `.env.example`. The existing Next.js 16.2.6 scaffold stays as-is. We do NOT install shadcn, do NOT wire Auth.js, do NOT touch Tailwind config in this phase.
- **DB**: Postgres 16 via docker-compose locally. One Alembic migration creates everything. No data-only migrations (seeding lives in the loader, per `docs/03-data-model.md` § 5).

This is intentionally boring. Phase 0's job is to make every subsequent phase deterministic, not to make architecture decisions.

---

## 2. Final repo layout

```
worldcupagents/
├── CLAUDE.md                              # copy of docs/CLAUDE.md (root-level for Claude Code auto-load)
├── README.md                              # clone-and-run instructions
├── Makefile                               # dev, db-up, db-down, migrate, seed, test, lint
├── docker-compose.yml                     # Postgres 16
├── .env.example                           # backend-side keys (top-level convenience copy)
├── .gitignore                             # python, node, env, .venv, __pycache__, .DS_Store
├── docs/                                  # already exists, edited in this change
│   ├── 02-trd.md                          # § 2 Frontend: Next 15 → 16
│   ├── KICKOFF.md                         # Decisions locked: add two rows
│   └── CLAUDE.md                          # Repo layout: frontend/ → worldcupagents-fe/
│
├── backend/
│   ├── pyproject.toml                     # uv-managed, deps pinned by major version
│   ├── uv.lock                            # committed
│   ├── .env.example                       # backend keys
│   ├── .python-version                    # 3.12
│   ├── Dockerfile                         # scaffolded for M8; NOT used in Phase 0
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                         # async-aware
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 202605160001_initial.py    # all tables + triggers + view
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                        # FastAPI() + /healthz
│   │   ├── config.py                      # pydantic-settings
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── base.py                    # DeclarativeBase, metadata, naming convention
│   │       ├── session.py                 # async engine, async_sessionmaker, get_session()
│   │       └── models/
│   │           ├── __init__.py            # re-exports all models so alembic sees them
│   │           ├── human.py
│   │           ├── agent.py
│   │           ├── team.py
│   │           ├── match.py
│   │           ├── prediction.py
│   │           ├── prediction_history.py
│   │           ├── score.py
│   │           ├── audit_log.py
│   │           └── pending_resolution.py
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                    # DB fixture: alembic upgrade + load_fixture
│       └── test_fixture_integrity.py
│
├── worldcupagents-fe/                     # EXISTING — name preserved
│   ├── .env.example                       # NEXTAUTH_URL, NEXTAUTH_SECRET, NEXT_PUBLIC_API_BASE_URL
│   └── (rest unchanged)
│
├── scripts/
│   ├── __init__.py                        # empty; makes scripts a package so we can `python -m scripts.load_fixture`
│   └── load_fixture.py                    # imports backend.app — runs as `uv run python -m scripts.load_fixture`
│
└── data/
    ├── teams.yaml                         # 48 entries, verbatim from docs/07 § 4
    └── matches.yaml                       # 72 group + 32 knockout-placeholder entries
```

**Note on `scripts/` import path**: To let `scripts/load_fixture.py` do `from app.db.session import async_session_factory`, we add `backend/` to `sys.path` at the top of the script (or use `uv run` from the backend dir). Chosen approach: **invoke from `backend/`** (`cd backend && uv run python ../scripts/load_fixture.py --all`). The Makefile encapsulates this so callers never see it.

---

## 3. Backend bootstrap

### 3.1 Python and `pyproject.toml`

- **Python**: 3.12 (locked in TRD § 2)
- **Package manager**: uv
- **Deps** (runtime):
  ```
  fastapi>=0.115
  fastmcp>=0.2
  sqlalchemy[asyncio]>=2.0
  asyncpg>=0.30
  alembic>=1.13
  pydantic-settings>=2.5
  argon2-cffi>=23.1
  python-jose[cryptography]>=3.3
  apscheduler>=3.10
  httpx>=0.27
  pyyaml>=6.0
  uvicorn[standard]>=0.30
  ```
- **Deps** (dev):
  ```
  pytest>=8
  pytest-asyncio>=0.24
  ruff>=0.7
  mypy>=1.13
  ```

Pin only major. `uv.lock` captures exact resolutions and is committed. We do NOT install Phase 0-irrelevant transitives explicitly — uv resolves what's needed.

### 3.2 `app/config.py` — pydantic-settings

Single `Settings` class reading from env. Phase 0 fields:

| Field | Type | Default | Notes |
|---|---|---|---|
| `database_url` | str | — | required, async DSN (`postgresql+asyncpg://...`) |
| `jwt_secret` | str | `"dev-secret-not-for-prod"` | dev default to let `make dev` work without setup |
| `jwt_algorithm` | str | `"HS256"` | |
| `environment` | str | `"development"` | |
| `log_level` | str | `"info"` | |

`model_config = SettingsConfigDict(env_file=".env", extra="ignore")`. The `extra="ignore"` matters — later phases will add fields (Google OAuth, Sentry DSN); we don't want Phase 0 to break when those env vars land in `.env` ahead of code.

Exported as a module-level `settings = Settings()` singleton.

### 3.3 `app/main.py`

```python
from fastapi import FastAPI
from sqlalchemy import text
from app.db.session import async_session_factory

app = FastAPI(title="worldcupagents", version="0.1.0")

@app.get("/healthz")
async def healthz():
    db_ok = False
    try:
        async with async_session_factory() as s:
            await s.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "db": db_ok}
```

DB ping is cheap and forestalls a 5-minute debugging session at M8 when someone forgets to start Postgres. If DB is down, endpoint still returns 200 with `{"db": false}` — this is INTENTIONAL: the readiness signal is the JSON content, not the HTTP code, because Fly's health-check semantics in later phases benefit from "service up, dependency unhealthy" being distinct from "service down".

### 3.4 `app/db/base.py`

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

Naming convention is non-negotiable for Alembic to generate stable, diff-able constraint names. Without it, autogenerate produces random names and migrations become unreviewable.

### 3.5 `app/db/session.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=15, future=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
```

Pool config (5/15) matches TRD § 7. `expire_on_commit=False` is required so we can read attributes off an instance after a commit without forcing another roundtrip.

### 3.6 SQLAlchemy models

One file per table under `app/db/models/`. All `Mapped[...]` typed columns (SQLAlchemy 2.0 style). Models map verbatim to `docs/03-data-model.md` § 2. Specifically:

- `human.py` → `humans`
- `agent.py` → `agents` (including `human_id UNIQUE` for one-agent-per-human)
- `team.py` → `teams` (id SMALLINT PK, 1..48)
- `match.py` → `matches` (id INT PK, status/stage CHECKs)
- `prediction.py` → `predictions` (UNIQUE (agent_id, match_id), probability sum CHECK)
- `prediction_history.py` → `prediction_history`
- `score.py` → `scores` (composite PK)
- `audit_log.py` → `audit_log`
- `pending_resolution.py` → `pending_resolutions`

`brackets` and `bracket_scores` are explicitly OUT of scope (v1.1, per `docs/03-data-model.md` § 5).

`app/db/models/__init__.py` re-exports every model:
```python
from .human import Human
from .agent import Agent
# ... etc
__all__ = ["Human", "Agent", "Team", "Match", "Prediction",
           "PredictionHistory", "Score", "AuditLog", "PendingResolution"]
```

Alembic's `env.py` imports this module so `target_metadata = Base.metadata` sees every table.

---

## 4. Alembic strategy

### 4.1 `alembic/env.py` — async-aware

Standard SQLAlchemy 2.x async pattern:

```python
from logging.config import fileConfig
import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from app.config import settings
from app.db.base import Base
from app.db.models import *  # noqa: F401,F403  — register all tables

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    raise RuntimeError("Offline migrations not supported (async setup).")
else:
    asyncio.run(run_migrations_online())
```

Offline mode is explicitly disabled to avoid foot-guns. We never have a reason to generate SQL without a connection in this project.

### 4.2 The initial migration: `202605160001_initial.py`

**Generation workflow** (executed by `sdd-apply`, NOT hand-written from scratch):

1. Ensure DB is empty: `docker compose down -v && docker compose up -d --wait db`
2. Run `cd backend && uv run alembic revision --autogenerate -m "initial"`
3. Inspect the generated file. Autogenerate produces:
   - all `op.create_table(...)` for every model
   - all `op.create_index(...)`
   - all FK and CHECK constraints embedded in `create_table`
4. **Hand-add** (autogenerate cannot produce these):
   - The three trigger functions + triggers (`set_lock_at`, `snapshot_prediction_history`, `touch_updated_at`) as `op.execute("""CREATE OR REPLACE FUNCTION ...""")` calls. **Source the SQL verbatim from `docs/03-data-model.md` § 4** — copy-paste, do not retype.
   - The `v_agent_leaderboard` view as `op.execute("""CREATE VIEW ...""")`. **Source from `docs/03-data-model.md` § 3 verbatim.**
   - `op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")` at the top of `upgrade()` — `gen_random_uuid()` requires it on older Postgres builds. Postgres 16 ships it but `CREATE EXTENSION IF NOT EXISTS` is a safe no-op.
5. **`touch_updated_at` application**: apply to `humans`, `agents`, `matches`, `predictions` (per `docs/03-data-model.md` § 4). Phase 0 covers all four. Add the function once, then four `CREATE TRIGGER` statements.
6. **Downgrade**: `sdd-apply` SHOULD write a real downgrade (drop view, drop triggers, drop trigger functions, then let autogenerated `op.drop_table` calls run). If time-boxed, a `pass` downgrade is acceptable but MUST be flagged in the PR description as a known gap. **Recommendation**: implement the downgrade — it's 20 lines and unblocks `make db-reset` for the rest of the project.

**Critical reviewer checklist** (for the human PR review, not for `sdd-apply`):
- [ ] Trigger SQL byte-for-byte matches `docs/03-data-model.md` § 4
- [ ] View SQL byte-for-byte matches `docs/03-data-model.md` § 3
- [ ] `touch_updated_at` applied to all four mutable tables
- [ ] Column types match the doc (especially `NUMERIC(5,4)` for probabilities, `NUMERIC(7,6)` for Brier, SMALLINT vs INT distinctions)
- [ ] `predictions.UNIQUE (agent_id, match_id)` present
- [ ] `agents.human_id UNIQUE` present (one-agent-per-human enforcement)

---

## 5. `data/matches.yaml` schema

### 5.1 Top-level shape

```yaml
matches:
  - id: 1
    stage: group              # one of: group, r32, r16, qf, sf, third, final
    group_letter: A           # CHAR(1), null for knockout
    home_team_id: 1           # SMALLINT FK → teams.id, null for unresolved knockout
    away_team_id: 2
    home_placeholder: null    # TEXT, used when team unknown
    away_placeholder: null
    kickoff_at: "2026-06-11T19:00:00Z"   # ISO 8601 UTC
    venue_city: "Mexico City"
    venue_country: "MX"        # 2-letter ISO
```

**Field rules** (loader enforces, tests assert):

| Field | Type | Required | Null OK |
|---|---|---|---|
| `id` | int 1..104 | yes | no |
| `stage` | enum | yes | no |
| `group_letter` | char(1) A..L | yes for group, no for knockout | yes for knockout |
| `home_team_id` | int 1..48 | no | yes (knockout TBD) |
| `away_team_id` | int 1..48 | no | yes (knockout TBD) |
| `home_placeholder` | str | no | yes |
| `away_placeholder` | str | no | yes |
| `kickoff_at` | RFC3339 UTC | yes | no |
| `venue_city` | str | yes | no for group; nullable knockout if unknown |
| `venue_country` | str (2 letters) | yes | same as above |

**Invariants** (validated by loader before insert):
- For `stage == 'group'`: both `home_team_id` and `away_team_id` MUST be non-null, both `*_placeholder` MUST be null.
- For knockout stages: at least one of (`home_team_id`, `home_placeholder`) is non-null, same for away.
- `id` distribution: 72 group (1–72), 16 r32 (73–88), 8 r16 (89–96), 4 qf (97–100), 2 sf (101–102), 1 third (103), 1 final (104).

### 5.2 Content scope

- **1–72 (group stage)**: hand-authored from the published FIFA calendar. Both team IDs always set. Venue and kickoff always set.
- **73–104 (knockout)**: structural placeholders. `home_team_id = null`, `away_team_id = null`, `home_placeholder` / `away_placeholder` set ("Winner Group A", "Best 3rd C/D/E/F", etc.). `kickoff_at` set to best-known FIFA-published time; if unknown for a slot, use `2026-07-19T19:00:00Z` (final-day placeholder) and add a comment line above.

Setting `kickoff_at` for knockouts (even approximate) is required because the column is `NOT NULL` and the `set_lock_at` trigger depends on it. The admin panel will refine kickoffs later (per `docs/07 § 9`).

---

## 6. `scripts/load_fixture.py`

### 6.1 CLI surface

```
uv run python -m scripts.load_fixture --all
uv run python -m scripts.load_fixture --teams-only
uv run python -m scripts.load_fixture --matches-only
uv run python -m scripts.load_fixture --dry-run
```

`--all` is the default if no flag is given. `--dry-run` parses YAML, validates invariants (see § 5.1), prints summary, exits without DB writes.

### 6.2 Strategy

- **Async** SQLAlchemy session (matches `app/db/session.py`). Justification: keeps a single engine/pool/settings instance. Sync would mean instantiating a second engine.
- **Upsert** via `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(index_elements=["id"], set_={...})`.
- **Idempotency**: a clean re-run produces zero changes. The `ON CONFLICT DO UPDATE` always fires, but if values are identical Postgres still bumps `updated_at`. To avoid that:
  - Add a `WHERE` clause to the `ON CONFLICT DO UPDATE`: `where=(Team.fifa_code != stmt.excluded.fifa_code) | (Team.name_en != stmt.excluded.name_en) | ...`. This causes Postgres to NOT execute the UPDATE when all relevant columns match.
  - Acceptable alternative: skip the WHERE and just accept that `updated_at` churns on re-runs. The integrity test then compares row COUNT and CONTENT before/after — not `updated_at`.
  - **Decision**: implement the WHERE clause. It's 6 lines per upsert and makes idempotency real (not just observed).

### 6.3 Loader internal structure

```python
# scripts/load_fixture.py
import sys, asyncio, argparse
from pathlib import Path
import yaml
from sqlalchemy.dialects.postgresql import insert

# Add backend/ to sys.path so app.* imports resolve
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import async_session_factory  # noqa: E402
from app.db.models import Team, Match              # noqa: E402

DATA_DIR = ROOT / "data"

async def load_teams() -> dict:
    raw = yaml.safe_load((DATA_DIR / "teams.yaml").read_text())
    # raw is either a list (current doc shape) or a dict {"teams": [...]}
    teams = raw if isinstance(raw, list) else raw["teams"]
    async with async_session_factory() as s:
        stmt = insert(Team).values(teams)
        update_cols = {c: stmt.excluded[c] for c in
                       ("fifa_code","name_en","name_es","flag_emoji","group_letter","confederation")}
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_=update_cols,
            where=...,  # IS DISTINCT FROM check across the 6 columns
        )
        result = await s.execute(stmt)
        await s.commit()
        return {"inserted_or_updated": result.rowcount, "total_in_yaml": len(teams)}

async def load_matches() -> dict:
    # same pattern; validate invariants per § 5.1 before insert
    ...

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--teams-only", action="store_true")
    parser.add_argument("--matches-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not (args.teams_only or args.matches_only):
        args.all = True
    asyncio.run(_run(args))
```

### 6.4 Loader contract (test-visible)

- Exit code 0 on success, non-zero on validation failure or DB error.
- Prints summary line per stage: `Loaded teams: 48 (0 changed)` / `Loaded matches: 104 (0 changed)`.
- Honors `--dry-run` strictly: zero writes, zero side effects beyond stdout.

---

## 7. `tests/test_fixture_integrity.py` and `conftest.py`

### 7.1 `conftest.py` strategy

Session-scoped async fixture:

```python
import asyncio, pytest, pytest_asyncio
from alembic.config import Config
from alembic import command
from app.db.session import async_session_factory, engine

@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepared_db():
    # Run alembic upgrade head
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    # Run loader
    from scripts.load_fixture import load_teams, load_matches
    await load_teams()
    await load_matches()
    yield
    # No teardown — local-dev DB only; CI uses an ephemeral container
```

**`pytest-asyncio` mode**: `mode = "auto"` set in `pyproject.toml` so `async def test_...` works without per-test decorators. Justification: every test in this file is async; explicit decorators are noise. Trade-off accepted: sync tests need explicit opt-out, but Phase 0 has none.

**Test DB**: Phase 0 runs tests against the local docker-compose Postgres. There is NO separate test database in Phase 0 — `make test` assumes `make db-up && make migrate` has run, and OPERATES ON the dev DB. This is fine because: (a) the loader is idempotent, (b) Phase 0 tests are read-only after the initial seed, (c) creating a separate test schema is M-something-later work. **`sdd-apply` MUST add a comment in `conftest.py` flagging this so future phases know to introduce testcontainers/transactional rollback when integration tests grow.**

### 7.2 Test cases

Six cases mapping 1:1 to `docs/07-fixture-loading.md` § 8, plus one idempotency case:

1. `test_teams_count` → `SELECT COUNT(*) FROM teams` == 48
2. `test_teams_per_group` → for each of A..L, count == 4
3. `test_matches_count` → `SELECT COUNT(*) FROM matches` == 104
4. `test_stage_distribution` → {group:72, r32:16, r16:8, qf:4, sf:2, third:1, final:1}
5. `test_group_matches_have_teams` → 0 group matches with NULL `home_team_id` or `away_team_id`
6. `test_lock_at_invariant` → 0 matches where `lock_at != kickoff_at - INTERVAL '1 hour'` (proves trigger ran)
7. `test_loader_idempotent` → call `load_teams()` and `load_matches()` a second time; assert returned `(changed_rows)` is 0 AND `SELECT max(updated_at) FROM teams` before == after.

---

## 8. Local DB — `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16
    container_name: worldcupagents-db
    environment:
      POSTGRES_DB: worldcupagents
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d worldcupagents"]
      interval: 2s
      timeout: 5s
      retries: 10
volumes:
  pgdata: {}
```

The healthcheck + `--wait` flag in the Makefile (`docker compose up -d --wait db`) prevents the backend from racing Postgres on cold boot.

**`DATABASE_URL` for local dev**: `postgresql+asyncpg://postgres:postgres@localhost:5432/worldcupagents` — written into `backend/.env.example` and `.env.example` at root.

---

## 9. Makefile

```makefile
.PHONY: dev db-up db-down migrate seed test lint fmt

db-up:
	docker compose up -d --wait db

db-down:
	docker compose down

migrate: db-up
	cd backend && uv run alembic upgrade head

seed: migrate
	cd backend && uv run python -m scripts.load_fixture --all

dev: db-up
	@echo "Starting backend on :8000 and frontend on :3000"
	@(cd backend && uv run uvicorn app.main:app --reload --port 8000 &) ; \
	 (cd worldcupagents-fe && pnpm dev)

test: seed
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run mypy app

fmt:
	cd backend && uv run ruff format .
```

Notes:
- `dev` backgrounds backend; foreground frontend so Ctrl-C kills the visible process. The backgrounded backend is not auto-killed — accepted Phase 0 trade-off (M8 introduces a proper `tmuxinator` / `mprocs` config or honcho).
- `seed` depends on `migrate` which depends on `db-up`. So `make test` from a clean state does the right thing.
- The `python -m scripts.load_fixture` invocation requires `scripts/__init__.py` to exist (yes, see § 2).

---

## 10. Doc updates (in scope)

Three files edited by `sdd-apply`:

### 10.1 `docs/02-trd.md`
Section 2, Frontend table, `Framework` row:
- Before: `Next.js 15 (app router)`
- After: `Next.js 16 (app router)`

Add a callout under § 2 Frontend:
> **M2 compatibility check (Phase-0 carry-forward)**: Before M2, verify Next 16 + Auth.js v5 (`next-auth@beta`) + shadcn CLI + Tailwind v4 work together. Phase 0 only installs the Next 16 scaffold; it does NOT install shadcn or wire Auth.js.

### 10.2 `docs/KICKOFF.md`
Add two rows to the "Decisions locked" table:
| Frontend framework | Next.js 16.2.6 (was 15) | phase-0-foundations proposal |
| Frontend dir name | `worldcupagents-fe/` (was `frontend/`) | phase-0-foundations proposal |

### 10.3 `docs/CLAUDE.md`
"Repo layout (target)" tree: replace `frontend/` with `worldcupagents-fe/`. No other layout changes (backend, scripts, data, etc. all match § 2 of this design).

---

## 11. ADR-style decisions and rejected alternatives

### ADR-1: Keep `worldcupagents-fe/`, do NOT rename to `frontend/`
- **Status**: Accepted (locked decision #267)
- **Rationale**: Preserves existing scaffold + `pnpm` lockfile; rename has no functional benefit; docs are the cheap thing to update.
- **Rejected**: `git mv worldcupagents-fe frontend` + update Makefile. Cost: lockfile churn, IDE re-index, no benefit.

### ADR-2: Stay on Next.js 16.2.6 (not downgrade to 15)
- **Status**: Accepted (locked decision #265)
- **Rationale**: Existing scaffold already on 16; downgrade burns time + introduces a known regression path; the TRD locked 15 before this scaffold existed.
- **Rejected**: `pnpm create next-app@15 frontend` fresh install. Carries the risk that 15 is end-of-life soon and we re-upgrade in M2 anyway.
- **Risk carried forward**: Auth.js v5 + shadcn + Tailwind v4 compatibility on Next 16 — addressed by the M2 compatibility callout (§ 10.1).

### ADR-3: Hand-author `matches.yaml`, no scraper
- **Status**: Accepted (locked in proposal)
- **Rationale**: Scraper (`build_matches_yaml.py`) is "fragile, bootstrapping only" per `docs/07 § 7`. 72 group entries take ~30 min to author from FIFA calendar; knockout slots get structural placeholders. We never need to RUN the scraper.
- **Rejected**: Build the scraper now. Cost: extra code, Wikipedia HTML fragility, no production use case. Deferred indefinitely — may be written ad-hoc later if a refresh is needed.

### ADR-4: Single Alembic migration for the entire initial schema
- **Status**: Accepted
- **Rationale**: Phase 0 is a bootstrap. Splitting into "tables", "triggers", "views" produces three migrations that always run together. One file is reviewable, easily reverted, and matches `docs/03 § 5` which names the file `202605160001_initial.py`.
- **Rejected**: Per-table migrations. Standard practice for incremental schema evolution, useless for an initial drop.

### ADR-5: Loader uses async SQLAlchemy (not sync)
- **Status**: Accepted
- **Rationale**: Reuses `app/db/session.py`. Single engine, single settings instance, single source of truth for `DATABASE_URL`. Cost: `asyncio.run(...)` boilerplate at the CLI boundary — trivial.
- **Rejected**: Sync session for the loader. Would require a parallel sync engine, parallel pool, parallel settings read. Two ways to be wrong instead of one.

### ADR-6: `/healthz` includes a DB ping
- **Status**: Accepted
- **Rationale**: Almost free; surfaces "service up, DB unreachable" as a distinct signal; helps every later phase debug `make dev` issues. Returns 200 in both cases — content (`db: true/false`) carries the signal.
- **Rejected**: Plain `{"status": "ok"}`. Roadmap allows this, but the moment a DB issue appears in M2+ we'd add the ping. Adding it now costs three lines.

### ADR-7: `mode = "auto"` for pytest-asyncio
- **Status**: Accepted
- **Rationale**: All Phase 0 tests are async; per-test decorators are noise.
- **Rejected**: Strict mode with `@pytest.mark.asyncio` on every test. Reasonable in projects with mixed sync/async; not Phase 0.

### ADR-8: Skip empty package scaffolding for `domain/`, `api/`, `mcp/`, `jobs/`, `lib/`
- **Status**: Accepted
- **Rationale**: YAGNI. Empty `__init__.py` files for packages we'll touch in M2+ add visual noise and tempt `sdd-apply` to "fill them in for symmetry". Each later milestone creates its own package as part of its own scope.
- **Rejected**: Pre-create the full TRD § 3 directory tree.

### ADR-9: Phase 0 tests share the dev DB (no separate test schema)
- **Status**: Accepted for Phase 0, flagged for later revisit
- **Rationale**: Phase 0 tests are read-only after seed and use the idempotent loader. Spinning up testcontainers or a separate schema is M-something work.
- **Rejected**: Testcontainers / transactional rollback / parallel test DB. Right answer eventually, wrong answer for ½-day phase.
- **Carry-forward**: `conftest.py` MUST carry a comment flagging this so the next phase that introduces write-mutating tests knows it has to upgrade the harness.

---

## 12. Risks and unresolved items

| Risk | Severity | Mitigation |
|---|---|---|
| Trigger / view SQL drifts from `docs/03-data-model.md` § 3-4 | High | PR reviewer checklist (§ 4.2). Suggest `sdd-apply` paste SQL verbatim and add a comment `-- source: docs/03-data-model.md § 4 verbatim`. |
| Autogenerate produces unexpected diffs against the doc | Medium | `sdd-apply` MUST inspect the autogenerated migration before adding triggers. If a column type or nullability differs from `docs/03 § 2`, fix the SQLAlchemy model, NOT the migration. |
| `docker compose up -d` races the backend on cold `make dev` | Low | Already mitigated by `--wait` flag + healthcheck. |
| Hand-authored `matches.yaml` typos (wrong team IDs, wrong group letters) | Medium | FK constraint catches wrong team IDs at insert. Test 5 (group matches have teams) + test 4 (stage distribution) catch structural errors. Visual review against FIFA calendar required pre-merge — flagged in PR. |
| Knockout `venue_city` / `venue_country` not announced for all 32 slots | Low | Allow NULL for those columns in the YAML; doc § 5.1 already permits it. Loader treats NULL as NULL. No test enforces non-null for knockouts. |
| Next.js 16 incompat with Auth.js v5 / shadcn / Tailwind v4 surfaces in M2 | Medium | Out of Phase 0 scope; carried forward in TRD callout. If it blocks M2, fall back to `next-auth@latest` non-beta or a Next downgrade. |
| Single-PR exceeds 400 LOC | High (≈90% confidence) | Accepted: `size:exception` label at merge. Commits split per work-unit: `feat: bootstrap monorepo (M0)` / `feat: schema + fixture (M1)` / `docs: update TRD/KICKOFF/CLAUDE for Next 16 + dir name`. |
| `scripts/__init__.py` + sys.path manipulation breaks if user invokes from unexpected cwd | Low | Makefile encapsulates invocation. README documents `make seed` as the only supported entrypoint. |

**Unresolved (defer to `sdd-tasks` / `sdd-apply`)**:
- Exact knockout kickoff times for entries 73–104. The loader and trigger need a non-null `kickoff_at`; the human authoring the YAML uses best-known FIFA-published times. Where unknown, use a placeholder date within the FIFA-announced window. Not a blocker.
- Whether the Makefile's `dev` target should kill the backgrounded backend on Ctrl-C. Phase 0 accepts the leak; M8 introduces a proper process manager.

---

## 13. What `sdd-tasks` should produce

A deterministic ordered task list, grouped by work-unit, that will become commits in the single PR. Suggested grouping for `sdd-tasks`:

1. **chore: monorepo bootstrap** (M0 part 1) — root files: `.gitignore`, `README.md`, `CLAUDE.md`, `Makefile`, `docker-compose.yml`, root `.env.example`, `worldcupagents-fe/.env.example`.
2. **feat(backend): scaffold FastAPI + uv + config** (M0 part 2) — `backend/pyproject.toml`, `app/main.py`, `app/config.py`, `app/db/base.py`, `app/db/session.py`, `backend/.env.example`, `.python-version`, stub `Dockerfile`.
3. **feat(backend): SQLAlchemy models** (M1 part 1) — all nine model files under `app/db/models/`, `__init__.py` re-exports.
4. **feat(backend): Alembic async setup + initial migration** (M1 part 2) — `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/202605160001_initial.py`.
5. **feat(data): teams.yaml + matches.yaml** (M1 part 3) — both YAML files. teams verbatim; matches hand-authored.
6. **feat(scripts): load_fixture loader** (M1 part 4) — `scripts/__init__.py`, `scripts/load_fixture.py`.
7. **test(backend): fixture integrity tests** (M1 part 5) — `tests/__init__.py`, `tests/conftest.py`, `tests/test_fixture_integrity.py`.
8. **docs: update TRD/KICKOFF/CLAUDE for Next 16 + dir name** — three doc edits per § 10.

This is suggested grouping, not authoritative. `sdd-tasks` may resequence as long as it preserves dependency order (models before migration, migration before loader, loader before tests).

---

## 14. Out-of-scope reminders (echoes from proposal)

For `sdd-apply` discipline. None of these belong in Phase 0:

- No MCP server, no `app/mcp/` directory, no FastMCP mount call.
- No REST endpoints beyond `/healthz`.
- No auth, no `humans` row created via OAuth, no `agents` row created via API. Tables exist; no code writes to them yet.
- No `domain/`, `api/`, `jobs/`, `lib/` packages.
- No shadcn install, no Tailwind config change, no Auth.js wiring.
- No `seed_dev.py`, no `build_matches_yaml.py`.
- No CI workflow files (`.github/workflows/`).
- No Fly.toml, no Vercel config, no deployment.
- No Sentry, no `structlog`.
- No `brackets`, no `bracket_scores`.

If `sdd-apply` finds itself writing anything from this list, it has lost the plot. Re-read the proposal.
