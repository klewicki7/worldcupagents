# Tasks — phase-0-foundations

**Change**: phase-0-foundations
**Scope**: M0 (repo skeleton) + M1 (schema + fixture)
**Delivery**: single PR with `size:exception`
**Artifact store**: hybrid
**Tasks date**: 2026-05-16
**Status**: READY

---

## Dependency key

Tasks are strictly ordered within each section. Across sections:
- M1a (schema) requires M0 complete
- M1b (fixture data) requires M1a complete
- M1c (tests) requires M1a + M1b complete
- Docs (Commit 5) can run in parallel with M1a once M0 is committed, but SHOULD land last to stay coherent with the full diff

---

## Commit 1 — `feat: bootstrap monorepo (M0)`

### TASK-001 — Create root `.gitignore`

Write `/worldcupagents/.gitignore` covering Python (`__pycache__`, `.venv`, `*.pyc`, `*.pyo`, `.env`, `uv.lock` is NOT excluded — it IS committed), Node (`node_modules`, `.next`, `dist`), editors (`.DS_Store`, `.idea`, `*.swp`), and Docker ephemera.

**Files**: `.gitignore`
**REQ**: REQ-PHASE0-15
**Dependencies**: none
**Acceptance**: `git check-ignore .venv/bin/python` returns `.venv/bin/python`; `git check-ignore backend/uv.lock` returns nothing (not ignored).

---

### TASK-002 — Create root `README.md`

Write root `README.md` containing: prerequisite tools (uv, pnpm, Docker), one-liner clone instruction, and the full M0 acceptance command sequence (`make dev` → `curl /healthz` → `open :3000`). No prose beyond the minimum.

**Files**: `README.md`
**REQ**: REQ-PHASE0-15
**Dependencies**: TASK-001
**Acceptance**: File contains `uv`, `pnpm`, `Docker` as keywords and includes the exact `curl http://localhost:8000/healthz` command.

---

### TASK-003 — Copy `docs/CLAUDE.md` to root `CLAUDE.md` (pre-edit)

Copy the current `docs/CLAUDE.md` to `/CLAUDE.md`. This creates the root file that Claude Code auto-loads. The `worldcupagents-fe/` rename in the layout tree is handled in TASK-032 (Commit 5); this task only ensures the file exists.

> **NOTE for implementer**: At this point the root `CLAUDE.md` still says `frontend/` in the layout tree. TASK-032 fixes both `docs/CLAUDE.md` and this file. These two tasks MUST be treated as an atomic pair — do NOT commit a root `CLAUDE.md` that disagrees with `docs/CLAUDE.md`.

**Files**: `CLAUDE.md`
**REQ**: REQ-PHASE0-14, REQ-PHASE0-15
**Dependencies**: TASK-001
**Acceptance**: `diff CLAUDE.md docs/CLAUDE.md` exits 0.

---

### TASK-004 — `uv init` backend + declare full dependency set

Inside `backend/`, run `uv init --python 3.12`. Add runtime deps: `fastapi>=0.115`, `fastmcp>=0.2`, `sqlalchemy[asyncio]>=2.0`, `asyncpg>=0.30`, `alembic>=1.13`, `pydantic-settings>=2.5`, `argon2-cffi>=23.1`, `python-jose[cryptography]>=3.3`, `apscheduler>=3.10`, `httpx>=0.27`, `pyyaml>=6.0`, `uvicorn[standard]>=0.30`. Add dev deps: `pytest>=8`, `pytest-asyncio>=0.24`, `ruff>=0.7`, `mypy>=1.13`. Create `backend/.python-version` containing `3.12`. Run `uv sync` to produce `uv.lock`. Commit both `pyproject.toml` and `uv.lock`.

**Files**: `backend/pyproject.toml`, `backend/uv.lock`, `backend/.python-version`
**REQ**: REQ-PHASE0-16
**Dependencies**: TASK-001
**Acceptance**: `cd backend && uv sync` exits 0 with no conflicts. `python --version` via uv shows 3.12.x.

---

### TASK-005 — Backend app skeleton (`app/__init__.py`, `app/config.py`)

Create `backend/app/__init__.py` (empty). Create `backend/app/config.py` with a pydantic-settings `Settings` class per design § 3.2: fields `database_url`, `jwt_secret` (default `"dev-secret-not-for-prod"`), `jwt_algorithm` (default `"HS256"`), `environment` (default `"development"`), `log_level` (default `"info"`). `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`. Module-level singleton `settings = Settings()`.

**Files**: `backend/app/__init__.py`, `backend/app/config.py`
**REQ**: REQ-PHASE0-16
**Dependencies**: TASK-004
**Acceptance**: `cd backend && uv run python -c "from app.config import settings; print(settings.environment)"` prints `development`.

---

### TASK-006 — Backend `/healthz` endpoint (`app/main.py`)

Create `backend/app/main.py` per design § 3.3. FastAPI app with title `"worldcupagents"`, version `"0.1.0"`. `GET /healthz` returns `{"status": "ok", "db": <bool>}`. DB ping (`SELECT 1`) is attempted; if it fails, `db` is `false` but HTTP status is still 200. Import `async_session_factory` from `app.db.session` (this module will be created in TASK-013 — add a `try/except ImportError` guard OR create session.py stub now; preferred: create the stub in TASK-013 and keep TASK-006 aware that it depends on TASK-013).

> **SEQUENCING NOTE**: TASK-006 depends on TASK-013 for `app.db.session`. Either (a) implement a stub `session.py` in this task and replace in TASK-013, or (b) reorder so TASK-013 runs before TASK-006. The task list reflects option (b): TASK-006 is listed here for grouping clarity but MUST be implemented after TASK-013 in practice.

**Files**: `backend/app/main.py`
**REQ**: REQ-PHASE0-02
**Dependencies**: TASK-005, TASK-013
**Acceptance**: `cd backend && uv run uvicorn app.main:app --port 8000 &` then `curl -s http://localhost:8000/healthz` returns JSON with `"status":"ok"` and HTTP 200.

---

### TASK-007 — Backend `.env.example`

Write `backend/.env.example` with all 5 required keys, each with an inline comment:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/worldcupagents  # asyncpg-style DSN
JWT_SECRET=change-me-in-production  # signing secret for JWTs
JWT_ALGORITHM=HS256  # HMAC-SHA256
ENVIRONMENT=development  # development | production
LOG_LEVEL=info  # debug | info | warning | error
```

**Files**: `backend/.env.example`
**REQ**: REQ-PHASE0-03
**Dependencies**: TASK-004
**Acceptance**: File contains `DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `ENVIRONMENT`, `LOG_LEVEL`. Each line has an inline `#` comment.

---

### TASK-008 — Root `.env.example` (convenience copy for backend)

Write root `.env.example` as a convenience copy of the backend keys (same 5 vars). Add a header comment noting this is the backend config and `worldcupagents-fe/.env.example` is the frontend config.

**Files**: `.env.example`
**REQ**: REQ-PHASE0-03
**Dependencies**: TASK-007
**Acceptance**: Root `.env.example` contains all 5 backend keys. File has a comment identifying it as backend config.

---

### TASK-009 — Frontend `.env.example`

Write `worldcupagents-fe/.env.example` with 3 required keys + inline comments:
```
NEXTAUTH_URL=http://localhost:3000  # base URL for Auth.js callbacks
NEXTAUTH_SECRET=change-me-in-production  # Auth.js signing secret
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000  # URL of the backend REST API
```

**Files**: `worldcupagents-fe/.env.example`
**REQ**: REQ-PHASE0-03, REQ-PHASE0-17
**Dependencies**: TASK-001
**Acceptance**: File contains `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, `NEXT_PUBLIC_API_BASE_URL`. Each line has an inline comment.

---

### TASK-010 — `docker-compose.yml` with Postgres 16 + healthcheck

Write `docker-compose.yml` per design § 8: `postgres:16` image, `POSTGRES_DB=worldcupagents`, `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, port `5432:5432`, named volume `pgdata`, healthcheck (`pg_isready`, interval 2s, retries 10).

**Files**: `docker-compose.yml`
**REQ**: REQ-PHASE0-01
**Dependencies**: TASK-001
**Acceptance**: `docker compose up -d --wait db` exits 0 within 30 s. `docker compose ps` shows db as healthy.

---

### TASK-011 — `Makefile` with all required targets

Write root `Makefile` per design § 9: `.PHONY` for all targets, `db-up`, `db-down`, `migrate` (depends on `db-up`), `seed` (depends on `migrate`), `dev` (starts db + uvicorn backend on :8000 background + pnpm frontend foreground), `test` (depends on `seed`, runs `cd backend && uv run pytest`), `lint` (ruff + mypy), `fmt` (ruff format). The `python -m scripts.load_fixture` call is invoked as `cd backend && uv run python -m scripts.load_fixture --all` (per design § 2 import-path note).

> **NOTE**: `python -m scripts.load_fixture` requires `scripts/__init__.py` (TASK-017) and `sys.path` manipulation inside the script (TASK-023). The Makefile target is authored now; the referenced module is created in M1b.

**Files**: `Makefile`
**REQ**: REQ-PHASE0-01, REQ-PHASE0-18
**Dependencies**: TASK-010
**Acceptance**: `make db-up` starts Postgres. `make --dry-run migrate` shows the alembic command. `make --dry-run seed` shows the load_fixture command. `make --dry-run test` shows pytest command.

---

### TASK-012 — Scaffold `scripts/__init__.py` and `data/.gitkeep`

Create `scripts/__init__.py` (empty — makes `scripts` a package for `python -m scripts.load_fixture`). Create `data/.gitkeep` (empty — reserves the directory in git). These are M0 scaffolds; content arrives in M1b.

**Files**: `scripts/__init__.py`, `data/.gitkeep`
**REQ**: REQ-PHASE0-01 (structural pre-requisite)
**Dependencies**: TASK-001
**Acceptance**: Both files exist. `git status` tracks them.

---

### TASK-013 — Backend DB layer: `app/db/base.py` + `app/db/session.py`

Create `backend/app/db/__init__.py` (empty). Create `backend/app/db/base.py` per design § 3.4: `NAMING_CONVENTION` dict + `Base(DeclarativeBase)` with `metadata = MetaData(naming_convention=NAMING_CONVENTION)`. Create `backend/app/db/session.py` per design § 3.5: async engine (pool_size=5, max_overflow=15), `async_session_factory`, `get_session()` generator.

**Files**: `backend/app/db/__init__.py`, `backend/app/db/base.py`, `backend/app/db/session.py`
**REQ**: REQ-PHASE0-04, REQ-PHASE0-16
**Dependencies**: TASK-005
**Acceptance**: `cd backend && uv run python -c "from app.db.base import Base; print(Base.metadata.naming_convention)"` prints the naming convention dict without errors.

---

### M0 Acceptance gate (TASK-014)

### TASK-014 — M0 acceptance run

With DB running (`make db-up`), verify `make dev` (or manual uvicorn) boots the backend and `curl http://localhost:8000/healthz` returns `{"status":"ok","db":false}` (db false because no schema yet — that is correct). Verify `cd worldcupagents-fe && pnpm dev` serves on `:3000`. This is a MANUAL verification task, not a code task.

**Files**: none (verification only)
**REQ**: REQ-PHASE0-01, REQ-PHASE0-02
**Dependencies**: TASK-006 through TASK-013 complete
**Acceptance**: `curl -s localhost:8000/healthz | python -m json.tool` shows `"status": "ok"`. Browser shows Next.js default page on :3000.

> **Commit boundary**: after TASK-014 passes, create commit: `feat: bootstrap monorepo (M0)`

---

## Commit 2 — `feat: schema + fixture (M1a)`

### TASK-015 — SQLAlchemy model: `human.py`

Create `backend/app/db/models/__init__.py` (stub — will be populated in TASK-024). Create `backend/app/db/models/human.py`. Map the `humans` table per `docs/03-data-model.md` § 2: UUID PK (gen_random_uuid default), `google_sub TEXT NOT NULL UNIQUE`, `email TEXT NOT NULL UNIQUE`, `name TEXT`, `avatar_url TEXT`, `is_admin BOOLEAN NOT NULL DEFAULT FALSE`, `created_at` / `updated_at` TIMESTAMPTZ. All columns use SQLAlchemy 2.0 `Mapped[...]` typing.

**Files**: `backend/app/db/models/__init__.py`, `backend/app/db/models/human.py`
**REQ**: REQ-PHASE0-04, REQ-PHASE0-05 (touch_updated_at applies here)
**Dependencies**: TASK-013
**Acceptance**: `cd backend && uv run python -c "from app.db.models.human import Human; print(Human.__tablename__)"` prints `humans`.

---

### TASK-016 — SQLAlchemy model: `agent.py`

Create `backend/app/db/models/agent.py`. Map the `agents` table per `docs/03-data-model.md` § 2. Critical: `human_id UUID NOT NULL UNIQUE REFERENCES humans(id) ON DELETE CASCADE`. CHECK constraints: `agents_name_length` (char_length 3–40), `agents_description_length` (null OR <= 500). Indexes: `idx_agents_slug`, `idx_agents_is_retired` (partial WHERE is_retired=FALSE).

**Files**: `backend/app/db/models/agent.py`
**REQ**: REQ-PHASE0-04, REQ-PHASE0-11
**Dependencies**: TASK-015
**Acceptance**: `from app.db.models.agent import Agent` imports without error. `Agent.__table__.constraints` includes a UniqueConstraint on `human_id`.

---

### TASK-017 — SQLAlchemy model: `team.py`

Create `backend/app/db/models/team.py`. Map `teams` table: `id SMALLINT PK` (1–48, hand-assigned, no sequence), `fifa_code TEXT NOT NULL UNIQUE`, `name_en TEXT NOT NULL`, `name_es TEXT NOT NULL`, `flag_emoji TEXT NOT NULL`, `group_letter CHAR(1)`, `confederation TEXT`. No `created_at`/`updated_at` (static table).

**Files**: `backend/app/db/models/team.py`
**REQ**: REQ-PHASE0-04, REQ-PHASE0-07
**Dependencies**: TASK-013
**Acceptance**: `Team.__table__.c.id.type` is `SMALLINT`. `Team.__table__.c.fifa_code` has unique constraint.

---

### TASK-018 — SQLAlchemy model: `match.py`

Create `backend/app/db/models/match.py`. Map `matches` table per `docs/03-data-model.md` § 2: `id INT PK` (1–104), stage CHECK enum (`group`, `r32`, `r16`, `qf`, `sf`, `third`, `final`), status CHECK enum, nullable `home_team_id`/`away_team_id` SMALLINT FK → teams.id, `home_placeholder`/`away_placeholder` TEXT, `kickoff_at TIMESTAMPTZ NOT NULL`, `lock_at TIMESTAMPTZ` (set by trigger), `venue_city`, `venue_country`. Include score consistency CHECK constraints per the data model doc.

**Files**: `backend/app/db/models/match.py`
**REQ**: REQ-PHASE0-04, REQ-PHASE0-05, REQ-PHASE0-08
**Dependencies**: TASK-017
**Acceptance**: `Match.__table__.c.kickoff_at.nullable` is `False`. `Match.__table__.c.home_team_id.nullable` is `True`.

---

### TASK-019 — SQLAlchemy model: `prediction.py`

Create `backend/app/db/models/prediction.py`. Map `predictions` table: BIGSERIAL PK, `UNIQUE(agent_id, match_id)`, `p_home NUMERIC(5,4)`, `p_draw NUMERIC(5,4)`, `p_away NUMERIC(5,4)`, probability sum CHECK (abs(p_home+p_draw+p_away-1) < 0.001), exact score pair consistency CHECK per the data model doc.

**Files**: `backend/app/db/models/prediction.py`
**REQ**: REQ-PHASE0-04
**Dependencies**: TASK-016, TASK-018
**Acceptance**: `Prediction.__table__` has a UniqueConstraint on `(agent_id, match_id)`. CHECK constraint name matches `ck_predictions_probs_sum_to_one` (or auto-named via convention).

---

### TASK-020 — SQLAlchemy model: `prediction_history.py`

Create `backend/app/db/models/prediction_history.py`. Map `prediction_history` table: BIGSERIAL PK, FK to `predictions.id`, mirrors the probability columns + snapshot timestamp.

**Files**: `backend/app/db/models/prediction_history.py`
**REQ**: REQ-PHASE0-04, REQ-PHASE0-05
**Dependencies**: TASK-019
**Acceptance**: `PredictionHistory.__table__.c.prediction_id` has FK to `predictions.id`.

---

### TASK-021 — SQLAlchemy model: `score.py`

Create `backend/app/db/models/score.py`. Map `scores` table: composite PK `(agent_id, match_id)`, brier score `NUMERIC(7,6)`, exact-score boolean, etc. per `docs/03-data-model.md` § 2.

**Files**: `backend/app/db/models/score.py`
**REQ**: REQ-PHASE0-04
**Dependencies**: TASK-016, TASK-018
**Acceptance**: `Score.__table__.primary_key.columns.keys()` equals `['agent_id', 'match_id']`.

---

### TASK-022 — SQLAlchemy model: `audit_log.py`

Create `backend/app/db/models/audit_log.py`. Map `audit_log` table: BIGSERIAL PK, `actor_type` CHECK enum, actor_id, action, payload JSONB, `created_at`.

**Files**: `backend/app/db/models/audit_log.py`
**REQ**: REQ-PHASE0-04
**Dependencies**: TASK-013
**Acceptance**: `AuditLog.__table__.c.actor_type` has a CHECK constraint per the enum values in the data model doc.

---

### TASK-023 — SQLAlchemy model: `pending_resolution.py`

Create `backend/app/db/models/pending_resolution.py`. Map `pending_resolutions` table: `match_id INT PK` (FK to `matches.id`), `flagged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.

**Files**: `backend/app/db/models/pending_resolution.py`
**REQ**: REQ-PHASE0-04
**Dependencies**: TASK-018
**Acceptance**: `PendingResolution.__table__.c.match_id` is both PK and FK to `matches.id`.

---

### TASK-024 — Models `__init__.py` — re-export all models

Populate `backend/app/db/models/__init__.py` with re-exports of all 9 model classes so Alembic's `env.py` sees them via `from app.db.models import *`.

```python
from .human import Human
from .agent import Agent
from .team import Team
from .match import Match
from .prediction import Prediction
from .prediction_history import PredictionHistory
from .score import Score
from .audit_log import AuditLog
from .pending_resolution import PendingResolution

__all__ = ["Human", "Agent", "Team", "Match", "Prediction",
           "PredictionHistory", "Score", "AuditLog", "PendingResolution"]
```

**Files**: `backend/app/db/models/__init__.py`
**REQ**: REQ-PHASE0-04
**Dependencies**: TASK-015 through TASK-023
**Acceptance**: `cd backend && uv run python -c "from app.db.models import *; print('ok')"` prints `ok` with no errors.

---

### TASK-025 — Alembic init + async `env.py`

Run `cd backend && uv run alembic init alembic`. Replace the generated `alembic/env.py` with the async-aware version from design § 4.1 verbatim. Set `sqlalchemy.url` from `settings.database_url` at runtime (not from `alembic.ini`). Comment the URL line in `alembic.ini` to avoid confusion. Import `from app.db.models import *` in `env.py` so autogenerate detects all tables. Disable offline mode (raise `RuntimeError`).

**Files**: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`
**REQ**: REQ-PHASE0-04
**Dependencies**: TASK-024
**Acceptance**: `cd backend && uv run alembic current` exits 0 (may print "no migration applied" — that is correct; it should not error).

---

### TASK-026 — Generate initial migration via autogenerate

With an empty Postgres running (`make db-up`): `cd backend && uv run alembic revision --autogenerate -m "initial"`. Rename the output file to `alembic/versions/202605160001_initial.py`. Inspect the generated file — ALL 9 tables and their columns, indexes, and constraints must be present. If any column type, nullability, or constraint deviates from `docs/03-data-model.md` § 2, fix the SQLAlchemy model (NOT the migration) and regenerate.

**Files**: `backend/alembic/versions/202605160001_initial.py` (auto-generated + renamed)
**REQ**: REQ-PHASE0-04
**Dependencies**: TASK-025, TASK-010 (DB must be running)
**Acceptance**: The file exists with revision id visible. All 9 `op.create_table(...)` calls are present. No `brackets` or `bracket_scores` tables appear.

---

### TASK-027 — Hand-add triggers + view to migration

Edit `202605160001_initial.py` to add the following at the end of `upgrade()`, after all `op.create_table` calls:

1. `op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")` — at the very top of `upgrade()`, before any table creation.
2. `trg_matches_lock_at` function + trigger — sourced VERBATIM from `docs/03-data-model.md` § 4. Add comment `-- source: docs/03-data-model.md § 4 verbatim`.
3. `snapshot_prediction_history` function + trigger — same source, same comment.
4. `touch_updated_at` shared function — ONE function definition.
5. Four `CREATE TRIGGER` statements for `touch_updated_at`: one each for `humans`, `agents`, `matches`, `predictions`.
6. `v_agent_leaderboard` view — sourced VERBATIM from `docs/03-data-model.md` § 3. Comment: `-- source: docs/03-data-model.md § 3 verbatim`.

Also write `downgrade()`: drop view → drop triggers → drop trigger functions → `op.drop_table(...)` for all 9 tables in reverse FK order.

> **CRITICAL**: Do NOT retype the trigger/view SQL. Copy-paste from `docs/03-data-model.md`. Any deviation is a spec violation caught by the PR reviewer checklist.

**Files**: `backend/alembic/versions/202605160001_initial.py`
**REQ**: REQ-PHASE0-04, REQ-PHASE0-05, REQ-PHASE0-06
**Dependencies**: TASK-026
**Acceptance**: Migration file contains: `CREATE EXTENSION IF NOT EXISTS pgcrypto`, `CREATE OR REPLACE FUNCTION set_lock_at`, `CREATE OR REPLACE FUNCTION snapshot_prediction_history`, `CREATE OR REPLACE FUNCTION touch_updated_at`, 4 touch_updated_at `CREATE TRIGGER` statements, `CREATE VIEW v_agent_leaderboard`.

---

### TASK-028 — Verify `alembic upgrade head` on empty DB

Run `docker compose down -v && docker compose up -d --wait db` to get a truly empty DB, then `cd backend && uv run alembic upgrade head`. Verify:
- Exit code 0
- `alembic_version` table exists with one row (revision `202605160001`)
- All 9 tables visible via `\dt` or SQLAlchemy inspect
- `\df` (or `pg_proc`) shows `set_lock_at`, `snapshot_prediction_history`, `touch_updated_at` functions
- `\dv` shows `v_agent_leaderboard`
- Running `alembic upgrade head` again reports "Already at head" and exits 0

**Files**: none (verification only)
**REQ**: REQ-PHASE0-04, REQ-PHASE0-05, REQ-PHASE0-06, REQ-PHASE0-11
**Dependencies**: TASK-027
**Acceptance**: All checklist items above pass. `make migrate` from clean state also passes.

> **Commit boundary**: after TASK-028 passes, create commit: `feat: schema + fixture (M1a — schema + migration)`

---

## Commit 3 — `feat: load fixture data (M1b)`

### TASK-029 — Write `data/teams.yaml`

Hand-author `data/teams.yaml` with exactly 48 entries verbatim from `docs/07-fixture-loading.md` § 4. Each entry: `id` (1–48), `fifa_code`, `name_en`, `name_es`, `flag_emoji`, `group_letter` (A–L), `confederation`. Anchor checks: MEX is id=1 group=A; ARG is id=37 group=J.

> **WARNING**: Copy from `docs/07-fixture-loading.md` § 4 exactly. Any discrepancy in fifa_code, name, flag, group, or confederation is a spec violation (REQ-PHASE0-07). Remove `data/.gitkeep` only after this file is created.

**Files**: `data/teams.yaml`, `data/.gitkeep` (deleted)
**REQ**: REQ-PHASE0-07
**Dependencies**: TASK-012
**Acceptance**: `python -c "import yaml; d=yaml.safe_load(open('data/teams.yaml')); print(len(d['teams']))"` prints `48`. 12 distinct `group_letter` values, 4 each.

---

### TASK-030 — Write `data/matches.yaml` — group stage (IDs 1–72)

Hand-author entries 1–72 in `data/matches.yaml`. Each entry: `id`, `stage: group`, `group_letter` (A–L), `home_team_id` (non-null, valid 1–48), `away_team_id` (non-null, valid 1–48), `home_placeholder: null`, `away_placeholder: null`, `kickoff_at` (ISO 8601 UTC from FIFA calendar), `venue_city`, `venue_country` (2-letter ISO). Distribution: 6 matches per group × 12 groups = 72 matches.

> **WARNING**: Both team IDs must be non-null for ALL 72 group-stage entries. Each team appears exactly 3 times as home or away within its group. All team IDs must resolve to valid IDs in `data/teams.yaml`. Any FK violation will be caught at loader insert time.

**Files**: `data/matches.yaml` (group stage portion)
**REQ**: REQ-PHASE0-08
**Dependencies**: TASK-029
**Acceptance**: 72 entries with `stage: group`. All 72 have non-null `home_team_id` and `away_team_id`. All `kickoff_at` values are >= `2026-06-11`.

---

### TASK-031 — Write `data/matches.yaml` — knockout placeholders (IDs 73–104)

Append entries 73–104 to `data/matches.yaml`. Distribution: 73–88 (16 × r32), 89–96 (8 × r16), 97–100 (4 × qf), 101–102 (2 × sf), 103 (third-place), 104 (final). Each entry: `id`, `stage` (appropriate enum value), `group_letter: null`, `home_team_id: null`, `away_team_id: null`, `home_placeholder` (e.g., "Winner Group A"), `away_placeholder` (e.g., "Winner Group B"), `kickoff_at` (best-known FIFA-published UTC time; where unknown use `2026-07-19T19:00:00Z` final-day placeholder with a YAML comment `# placeholder — refine via admin panel`), `venue_city` / `venue_country` (null if not yet published).

> **Per orchestrator resolution #1**: All 32 knockout entries MUST have a non-null `kickoff_at`. Use best-known times. `home_team_id` and `away_team_id` are null for all 32 — this is correct per spec.

**Files**: `data/matches.yaml` (knockout portion appended)
**REQ**: REQ-PHASE0-08
**Dependencies**: TASK-030
**Acceptance**: Total entries = 104. Knockout stages: r32=16, r16=8, qf=4, sf=2, third=1, final=1. All 104 `kickoff_at` values are non-null.

---

### TASK-032 — `scripts/load_fixture.py` — teams loader

Create `scripts/load_fixture.py` with the `sys.path` manipulation per design § 6.3 (`ROOT / "backend"` prepended to `sys.path`). Implement `async def load_teams()`: parse `data/teams.yaml`, validate entries (count=48, contiguous IDs 1–48), upsert via `INSERT ... ON CONFLICT DO UPDATE WHERE <IS DISTINCT FROM check>`. Return `{"inserted_or_updated": N, "total_in_yaml": 48}`. Print `Loaded teams: 48 (N changed)`.

**Files**: `scripts/load_fixture.py`
**REQ**: REQ-PHASE0-09, NFR-03
**Dependencies**: TASK-029, TASK-024
**Acceptance**: `cd backend && uv run python -m scripts.load_fixture --teams-only` (against seeded DB after migrate) exits 0 and prints team summary. Re-run shows `0 changed`.

---

### TASK-033 — `scripts/load_fixture.py` — matches loader

Add `async def load_matches()` to `scripts/load_fixture.py`: parse `data/matches.yaml`, validate invariants per design § 5.1 (group: non-null team IDs; knockout: null team IDs + non-empty placeholders + non-null kickoff_at), upsert with `ON CONFLICT DO UPDATE WHERE IS DISTINCT FROM`. Validate all 104 entries have non-null `kickoff_at`. Print `Loaded matches: 104 (N changed)`.

> **Per NFR-03**: NEVER issue a DELETE statement. This is an upsert-only loader. Any error path must abort cleanly, not delete.

**Files**: `scripts/load_fixture.py` (extended)
**REQ**: REQ-PHASE0-09, NFR-03
**Dependencies**: TASK-031, TASK-032
**Acceptance**: `cd backend && uv run python -m scripts.load_fixture --matches-only` exits 0 and prints match summary. Re-run shows `0 changed`.

---

### TASK-034 — `scripts/load_fixture.py` — CLI flags + `--dry-run`

Add `argparse` main function with `--all` (default if no flag), `--teams-only`, `--matches-only`, `--dry-run` flags. `--dry-run` parses YAML, validates invariants, prints summary, exits 0 with ZERO DB writes. Wire `asyncio.run(_run(args))`.

**Files**: `scripts/load_fixture.py` (CLI section)
**REQ**: REQ-PHASE0-09
**Dependencies**: TASK-033
**Acceptance**: `cd backend && uv run python -m scripts.load_fixture --dry-run --all` exits 0 and prints what WOULD be inserted without touching the DB (verify with `SELECT COUNT(*) FROM teams` = 0 on a fresh DB).

---

### TASK-035 — Verify `make seed` clean + idempotent

Run `make seed` (which depends on `make migrate`). Verify exit code 0 and summary output. Run `make seed` again immediately. Verify exit code 0 and `0 changed` for both teams and matches.

**Files**: none (verification only)
**REQ**: REQ-PHASE0-09
**Dependencies**: TASK-034, TASK-028
**Acceptance**: First run: `Loaded teams: 48 (48 changed)`, `Loaded matches: 104 (104 changed)`. Second run: `Loaded teams: 48 (0 changed)`, `Loaded matches: 104 (0 changed)`.

> **Commit boundary**: after TASK-035 passes, create commit: `feat: load fixture data (M1b)`

---

## Commit 4 — `test: fixture integrity (M1c)`

### TASK-036 — `tests/conftest.py` — session fixture

Create `backend/tests/__init__.py` (empty). Create `backend/tests/conftest.py` with session-scoped async fixture `prepared_db` per design § 7.1: runs `alembic upgrade head`, then calls `load_teams()` and `load_matches()` from `scripts.load_fixture`. Set `asyncio_mode = "auto"` in `pyproject.toml` under `[tool.pytest.ini_options]`. Add a comment per design § 7.1 (ADR-9 carry-forward): `# TODO: Phase 0 tests share the local dev DB — no testcontainers, no rollback. Introduce transactional fixtures when write-mutating tests are added in later milestones.`

**Files**: `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/pyproject.toml` (asyncio_mode)
**REQ**: REQ-PHASE0-10
**Dependencies**: TASK-034, TASK-028
**Acceptance**: `cd backend && uv run pytest --collect-only` collects without errors (even if no tests found yet).

---

### TASK-037 — `tests/test_fixture_integrity.py` — 6 verification queries

Create `backend/tests/test_fixture_integrity.py` with 6 test functions mapping 1:1 to `docs/07-fixture-loading.md` § 8:

1. `test_teams_count` — `SELECT COUNT(*) FROM teams` == 48
2. `test_teams_per_group` — for each of A..L: `SELECT COUNT(*) FROM teams WHERE group_letter = X` == 4 (12 assertions)
3. `test_matches_count` — `SELECT COUNT(*) FROM matches` == 104
4. `test_stage_distribution` — `GROUP BY stage`: {group:72, r32:16, r16:8, qf:4, sf:2, third:1, final:1}
5. `test_group_matches_have_teams` — `SELECT COUNT(*) FROM matches WHERE stage='group' AND (home_team_id IS NULL OR away_team_id IS NULL)` == 0
6. `test_lock_at_invariant` — `SELECT COUNT(*) FROM matches WHERE lock_at != kickoff_at - INTERVAL '1 hour'` == 0

> **Per orchestrator resolution #2**: No 7th MIN/MAX kickoff_at test case. The 6 queries above are sufficient.

All tests are `async def` and use `async_session_factory` from `app.db.session`. Each test must have a clear assertion message.

**Files**: `backend/tests/test_fixture_integrity.py`
**REQ**: REQ-PHASE0-10
**Dependencies**: TASK-036
**Acceptance**: `cd backend && uv run pytest tests/test_fixture_integrity.py -v` shows 6 named tests, all PASSED.

---

### TASK-038 — Add idempotency test

Add `test_loader_idempotent` to `test_fixture_integrity.py`: call `load_teams()` and `load_matches()` a second time, assert returned `changed_rows` is 0 for both, AND verify `SELECT max(updated_at) FROM teams` is identical before and after the second load call (proves the WHERE clause on the upsert prevents spurious updates).

**Files**: `backend/tests/test_fixture_integrity.py` (extended)
**REQ**: REQ-PHASE0-09
**Dependencies**: TASK-037, TASK-033
**Acceptance**: `test_loader_idempotent` passes. The test must fail if the upsert WHERE clause is removed (non-trivial).

---

### TASK-039 — Verify `make test` green

Run `make test` (which triggers `make seed` which triggers `make migrate` which triggers `make db-up`). All 7 test cases pass. `make lint` also passes (`ruff check backend/` + `mypy --strict backend/app/` zero errors). `pnpm tsc --noEmit` inside `worldcupagents-fe/` passes.

**Files**: none (verification only)
**REQ**: REQ-PHASE0-10, NFR-04
**Dependencies**: TASK-036, TASK-037, TASK-038
**Acceptance**: `make test` exits 0. `make lint` exits 0. `pnpm tsc --noEmit` exits 0.

> **Commit boundary**: after TASK-039 passes, create commit: `test: fixture integrity (M1c)`

---

## Commit 5 — `docs: update TRD, KICKOFF, CLAUDE.md for Phase 0 decisions`

> These three tasks CAN be worked on in parallel with M1a once M0 is committed, but they MUST be committed together as a single docs commit at the end to keep the diff coherent.

### TASK-040 — Update `docs/02-trd.md` — Next.js 16 + M2 compat note

Edit `docs/02-trd.md` § 2 Frontend:
- Change `Next.js 15 (app router)` → `Next.js 16 (app router)` in the stack table
- Add callout under § 2 Frontend per design § 10.1:
  > **M2 compatibility check (Phase-0 carry-forward)**: Before M2, verify Next 16 + Auth.js v5 (`next-auth@beta`) + shadcn CLI + Tailwind v4 work together. Phase 0 only installs the Next 16 scaffold; it does NOT install shadcn or wire Auth.js.

**Files**: `docs/02-trd.md`
**REQ**: REQ-PHASE0-12
**Dependencies**: TASK-003 (M0 complete)
**Acceptance**: `grep "Next.js 16" docs/02-trd.md` returns a hit. `grep "M2 compatibility" docs/02-trd.md` returns a hit. `grep "Next.js 15" docs/02-trd.md` returns no hits in the stack section.

---

### TASK-041 — Update `docs/KICKOFF.md` — add 2 rows to Decisions locked table

Add two rows to the "Decisions locked" table in `docs/KICKOFF.md`:

| Frontend framework | Next.js 16.2.6 (was 15) | phase-0-foundations proposal |
| Frontend dir name | `worldcupagents-fe/` (was `frontend/`) | phase-0-foundations proposal |

**Files**: `docs/KICKOFF.md`
**REQ**: REQ-PHASE0-13
**Dependencies**: TASK-003
**Acceptance**: `grep "Next.js 16.2.6" docs/KICKOFF.md` returns a hit. `grep "worldcupagents-fe" docs/KICKOFF.md` returns a hit.

---

### TASK-042 — Update `docs/CLAUDE.md` + root `CLAUDE.md` — `worldcupagents-fe/`

Edit `docs/CLAUDE.md` "Repo layout (target)" tree: replace `frontend/` with `worldcupagents-fe/`. Copy the updated `docs/CLAUDE.md` over the root `CLAUDE.md` so both files are identical. Verify no other reference to `frontend/` remains in the layout tree (grep both files).

> **CRITICAL**: Root `CLAUDE.md` and `docs/CLAUDE.md` MUST be byte-identical after this task. TASK-003 created the initial copy; this task updates both atomically.

**Files**: `docs/CLAUDE.md`, `CLAUDE.md`
**REQ**: REQ-PHASE0-14, REQ-PHASE0-15
**Dependencies**: TASK-040, TASK-041 (all docs tasks batched together)
**Acceptance**: `diff CLAUDE.md docs/CLAUDE.md` exits 0. `grep "frontend/" CLAUDE.md` returns no hits in the layout section. `grep "worldcupagents-fe/" CLAUDE.md` returns a hit.

> **Commit boundary**: after TASK-042, create commit: `docs: update TRD, KICKOFF, CLAUDE.md for Phase 0 decisions`

---

## Final verification (TASK-043)

### TASK-043 — Full end-to-end acceptance run

Execute the full acceptance sequence from a clean state:

```bash
docker compose down -v          # clean slate
make dev                        # Postgres + backend :8000 + frontend :3000
curl http://localhost:8000/healthz   # → {"status":"ok","db":true} (db:true now that schema is applied)
make migrate                    # alembic upgrade head (idempotent from make dev's db-up)
make seed                       # load_fixture --all (first run: 48+104 rows)
make seed                       # again — 0 changes
make test                       # all 7 pytest tests pass
make lint                       # ruff + mypy clean
cd worldcupagents-fe && pnpm tsc --noEmit  # TypeScript clean
```

Verify trigger behaviour manually:
- Insert a match with known kickoff_at → confirm `lock_at = kickoff_at - 1h`
- Check `SELECT * FROM v_agent_leaderboard LIMIT 0` succeeds with correct column names

**Files**: none (verification only)
**REQ**: ALL (REQ-PHASE0-01 through REQ-PHASE0-18)
**Dependencies**: TASK-039, TASK-042
**Acceptance**: Every command exits 0. `make test` shows 7 tests passed. No ruff/mypy/tsc errors.

---

### TASK-044 — Open PR with `size:exception` label

Open the PR with:
- Title: `feat: phase-0-foundations (M0 + M1)`
- Body: work-unit commit list, `size:exception` label explanation, reviewer checklist from design § 4.2 (trigger/view SQL byte-for-byte match against `docs/03-data-model.md` § 3–4)
- Label: `size:exception`
- Commits in order: Commit 1 (M0) → Commit 2 (schema) → Commit 3 (loader) → Commit 4 (tests) → Commit 5 (docs)

**Files**: none (PR creation)
**REQ**: REQ-PHASE0-01 through REQ-PHASE0-18
**Dependencies**: TASK-043
**Acceptance**: PR is open. `size:exception` label is applied. PR body contains the reviewer checklist.

---

## Review Workload Forecast

- Estimated changed LOC: ~1 100–1 400 (breakdown: 200 root/infra files, 300 models + session/base, 250 migration including trigger+view SQL, 350 YAML data files, 150 loader script, 100 tests + conftest, 50 doc edits)
- 400-line budget risk: High (M1 alone authors 104 YAML rows + 9 model files + migration + tests)
- Chained PRs recommended: No (overridden by delivery strategy `single-pr`)
- size:exception required: Yes
- Decision needed before apply: No (user accepted size:exception upfront in proposal phase)

---

## Sequencing summary (dependency graph)

```
TASK-001 (gitignore)
  ├── TASK-002 (README)
  ├── TASK-003 (root CLAUDE.md copy)
  ├── TASK-004 (uv init) → TASK-005 (config.py) → TASK-013 (db/base+session) → TASK-015..023 (models) → TASK-024 (__init__) → TASK-025 (alembic init) → TASK-026 (autogenerate) → TASK-027 (hand-edit triggers) → TASK-028 (verify migrate) [Commit 2]
  │     └── TASK-007 (.env.example backend) → TASK-008 (root .env.example)
  ├── TASK-009 (fe .env.example)
  ├── TASK-010 (docker-compose) → TASK-011 (Makefile)
  └── TASK-012 (scripts/__init__ + data/.gitkeep)

TASK-013 → TASK-006 (main.py + healthz)

[Commit 1 gate: TASK-014 — M0 acceptance]

TASK-028 → TASK-029 (teams.yaml) → TASK-030 (matches group) → TASK-031 (matches knockout) → TASK-032 (loader teams) → TASK-033 (loader matches) → TASK-034 (CLI) → TASK-035 (verify seed) [Commit 3]

TASK-035 → TASK-036 (conftest) → TASK-037 (6 tests) → TASK-038 (idempotency test) → TASK-039 (make test green) [Commit 4]

TASK-003 → TASK-040 (trd.md) + TASK-041 (kickoff.md) + TASK-042 (claude.md) [Commit 5, parallel with M1a+]

TASK-039 + TASK-042 → TASK-043 (full acceptance) → TASK-044 (PR)
```

**Total tasks**: 44
**Sequential chain**: 001 → 004 → 013 → 015–024 → 025 → 026 → 027 → 028 → 029 → 030 → 031 → 032 → 033 → 034 → 035 → 036 → 037 → 038 → 039 → 043 → 044
**Parallel opportunities**: TASK-040/041/042 (docs) can run after M0 commit, independently of M1a/M1b/M1c; TASK-017 (team.py) and TASK-022/023 (audit_log/pending_resolution) have no cross-model dependencies and can be written concurrently with other models in TASK-015–023.

---

## Flags for implementer

1. **TASK-006 ordering**: `app/main.py` depends on `app/db/session.py` (TASK-013). The commit grouping places both in Commit 1 — implement session.py before main.py within that commit.
2. **TASK-027 copy-paste discipline**: Trigger and view SQL MUST be copied verbatim from `docs/03-data-model.md`. Do not retype. The PR reviewer checklist explicitly checks byte-for-byte match.
3. **TASK-029 anchor check**: After writing `data/teams.yaml`, spot-check MEX=id1=groupA and ARG=id37=groupJ before moving to TASK-030.
4. **TASK-042 atomicity**: `docs/CLAUDE.md` and root `CLAUDE.md` must be identical after this task. Use `cp docs/CLAUDE.md CLAUDE.md` to guarantee it.
5. **No extra packages**: Design § 14 lists 15 out-of-scope items. If you find yourself creating `app/domain/`, `app/api/`, `app/mcp/`, or any GitHub Actions file, stop and re-read the proposal.
