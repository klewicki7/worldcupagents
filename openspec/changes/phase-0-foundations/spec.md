# Spec — phase-0-foundations

**Change**: phase-0-foundations
**Scope**: M0 (repo skeleton) + M1 (schema + fixture)
**Delivery strategy**: single-pr (size:exception)
**Spec date**: 2026-05-16
**Status**: APPROVED

---

## Overview

This spec describes what MUST be true after phase-0-foundations is merged. It covers M0 (repo skeleton: monorepo scaffold, local dev stack, `/healthz`, docs updates) and M1 (SQLAlchemy models, Alembic migration, DB triggers, fixture data, loader script, integrity tests). It does NOT describe HOW to achieve these outcomes — that is the design phase.

The authoritative schema source is `docs/03-data-model.md`. The authoritative fixture source is `docs/07-fixture-loading.md`. This spec references both by section rather than restating schema DDL verbatim.

---

## 1. Functional Requirements

### REQ-PHASE0-01 — `make dev` boots the full local stack

**Statement**: Running `make dev` from the repo root starts Postgres 16, the FastAPI backend on port 8000, and the Next.js frontend on port 3000, and all three services are ready to accept connections within the cold-boot time limit.

**Scenarios:**

```gherkin
Given a developer has cloned the repo and has Docker, uv, and pnpm installed
When they run `make dev` from the repo root for the first time
Then Postgres 16 is running on port 5432 within the configured healthcheck timeout
  And the FastAPI server is responding on http://localhost:8000
  And the Next.js server is responding on http://localhost:3000

Given `make dev` has been run at least once (images pulled, deps installed)
When a developer runs `make dev` again
Then the stack is fully up within 60 seconds (see NFR-01)

Given the DB container is not yet ready when the backend starts
When the backend process attempts to connect
Then the Makefile or compose file waits for DB readiness before declaring the stack up
  And no "connection refused" errors appear in normal startup output
```

---

### REQ-PHASE0-02 — `/healthz` endpoint returns 200

**Statement**: The FastAPI backend exposes a `GET /healthz` endpoint that returns HTTP 200 with JSON body `{"status":"ok"}` and requires no authentication.

**Scenarios:**

```gherkin
Given the backend is running
When an unauthenticated client sends GET http://localhost:8000/healthz
Then the response status is 200
  And the response body is exactly {"status":"ok"}
  And the Content-Type header is application/json

Given the backend is running but the database is temporarily unreachable
When a client sends GET /healthz
Then the response status is still 200
  And the endpoint does NOT perform a DB ping (it is intentionally shallow)
```

---

### REQ-PHASE0-03 — `.env.example` exists for backend and frontend with all required keys

**Statement**: Two `.env.example` files exist — one at `backend/.env.example` and one at `worldcupagents-fe/.env.example` — each listing every environment variable the respective app requires, with placeholder values and inline comments explaining each variable.

**Backend keys** (minimum set, must all be present):
- `DATABASE_URL` — asyncpg-style Postgres connection string
- `JWT_SECRET` — signing secret for JWTs
- `JWT_ALGORITHM` — algorithm identifier (example value: `HS256`)
- `ENVIRONMENT` — example value: `development`
- `LOG_LEVEL` — example value: `info`

**Frontend keys** (minimum set, must all be present):
- `NEXTAUTH_URL` — base URL for Auth.js callbacks
- `NEXTAUTH_SECRET` — Auth.js signing secret
- `NEXT_PUBLIC_API_BASE_URL` — URL of the backend REST API

**Scenarios:**

```gherkin
Given a developer clones the repo
When they inspect backend/.env.example
Then it contains DATABASE_URL, JWT_SECRET, JWT_ALGORITHM, ENVIRONMENT, and LOG_LEVEL
  And each line has an inline comment describing the variable

Given a developer clones the repo
When they inspect worldcupagents-fe/.env.example
Then it contains NEXTAUTH_URL, NEXTAUTH_SECRET, and NEXT_PUBLIC_API_BASE_URL
  And each line has an inline comment describing the variable

Given either .env.example file
When a developer copies it to .env.local and fills in real values
Then the respective application starts and connects successfully
```

---

### REQ-PHASE0-04 — Alembic migration applies cleanly to an empty database

**Statement**: Running `make migrate` against an empty Postgres 16 database applies the initial migration (`202605160001_initial.py`) without errors, creating all tables, indexes, constraints, triggers, and the `v_agent_leaderboard` view in a single transaction.

**Scenarios:**

```gherkin
Given a freshly initialized Postgres 16 instance with an empty target database
When `alembic upgrade head` is executed
Then it completes with exit code 0
  And the alembic_version table records revision 202605160001
  And all tables defined in docs/03-data-model.md §2 (excluding brackets and bracket_scores) exist
  And all named constraints exist (e.g. predictions_probs_sum_to_one, agents_name_length)
  And all indexes exist (e.g. idx_matches_kickoff, idx_agents_slug)
  And the three triggers exist: trg_matches_lock_at, trg_predictions_history, touch_updated_at
  And the view v_agent_leaderboard exists

Given the migration has been applied once
When `alembic upgrade head` is executed again
Then it completes with exit code 0 and reports "Already at head"
  And no tables or schema objects are duplicated or altered
```

---

### REQ-PHASE0-05 — DB triggers fire correctly on insert and update

**Statement**: The three database triggers defined in `docs/03-data-model.md` § 4 fire correctly and produce the specified side effects: `set_lock_at` computes `kickoff_at - INTERVAL '1 hour'`; `snapshot_prediction_history` writes one row to `prediction_history` on every insert or update of `predictions`; `touch_updated_at` updates the `updated_at` column on UPDATE of `humans`, `agents`, `matches`, and `predictions`.

**Scenarios:**

```gherkin
# set_lock_at
Given a match row does not yet exist
When a new match is inserted with kickoff_at = '2026-06-11T19:00:00Z'
Then the match row has lock_at = '2026-06-11T18:00:00Z'

Given a match row has kickoff_at = '2026-06-11T19:00:00Z'
When its kickoff_at is updated to '2026-06-11T20:00:00Z'
Then the match row has lock_at = '2026-06-11T19:00:00Z'

# snapshot_prediction_history
Given an agent and a match row exist
When a prediction is inserted for that (agent, match) pair
Then exactly one row exists in prediction_history for that prediction_id
  And the row's p_home, p_draw, p_away match the inserted prediction

Given a prediction row exists with a snapshot in prediction_history
When the prediction's p_home is updated
Then a second row is added to prediction_history for the same prediction_id
  And the new row captures the updated probability values

# touch_updated_at
Given a human row exists with updated_at = T0
When any column on that human row is updated
Then the human row's updated_at is greater than T0
```

---

### REQ-PHASE0-06 — `v_agent_leaderboard` view exists and is queryable

**Statement**: The `v_agent_leaderboard` view defined in `docs/03-data-model.md` § 3 exists in the database after migration and returns well-formed rows when queried, including the correct NULL-handling for agents with no scored matches.

**Scenarios:**

```gherkin
Given the migration has been applied
When `SELECT * FROM v_agent_leaderboard LIMIT 0` is executed
Then the query succeeds with exit code 0
  And the result set has columns: agent_id, slug, name, model_hint, avatar_url,
      matches_predicted, avg_brier, total_exact_pts, last_scored_at

Given two non-retired agents exist, one with scored matches and one without
When `SELECT * FROM v_agent_leaderboard` is executed
Then the agent with no scored matches appears with avg_brier = NULL (not 0)
  And total_exact_pts = 0 for that agent

Given the view is queried with the canonical leaderboard ordering
When `SELECT * FROM v_agent_leaderboard WHERE matches_predicted >= 3 ORDER BY avg_brier ASC NULLS LAST`
Then agents with NULL avg_brier appear last, not first
```

---

### REQ-PHASE0-07 — `data/teams.yaml` matches the 48-team source

**Statement**: The committed `data/teams.yaml` file contains exactly 48 entries, verbatim-matching the canonical list in `docs/07-fixture-loading.md` § 4, including stable IDs 1–48, `fifa_code`, `name_en`, `name_es`, `flag_emoji`, `group_letter` (A–L), and `confederation`.

**Scenarios:**

```gherkin
Given data/teams.yaml is loaded
When its entries are counted
Then exactly 48 entries exist

Given data/teams.yaml is loaded
When entries are grouped by group_letter
Then exactly 12 distinct groups (A through L) exist
  And each group has exactly 4 teams

Given data/teams.yaml is loaded
When team IDs are inspected
Then IDs are contiguous integers 1 through 48
  And no ID is repeated

Given data/teams.yaml is compared against docs/07-fixture-loading.md § 4 line by line
When any discrepancy is present (wrong fifa_code, name, flag, group, or confederation)
Then it is considered a spec violation
  And MEX is id=1, group=A; ARG is id=37, group=J (example anchor checks)
```

---

### REQ-PHASE0-08 — `data/matches.yaml` has 72 group-stage entries with non-null team IDs + 32 knockout placeholders

**Statement**: The committed `data/matches.yaml` contains exactly 104 entries: matches 1–72 have `stage: group`, a valid `group_letter`, and non-null `home_team_id` / `away_team_id` referencing valid team IDs; matches 73–104 have `stage` set to the appropriate knockout round (`r32`, `r16`, `qf`, `sf`, `third`, or `final`), `home_team_id: null`, `away_team_id: null`, and non-empty `home_placeholder` / `away_placeholder` strings. All 104 entries have a non-null `kickoff_at`.

**Scenarios:**

```gherkin
Given data/matches.yaml is loaded
When its entries are counted
Then exactly 104 entries exist

Given data/matches.yaml is loaded
When group-stage entries (id 1–72) are inspected
Then all 72 have stage = 'group'
  And all 72 have a non-null home_team_id
  And all 72 have a non-null away_team_id
  And all team IDs resolve to entries in data/teams.yaml

Given data/matches.yaml is loaded
When knockout entries (id 73–104) are inspected
Then home_team_id is null for all 32
  And away_team_id is null for all 32
  And home_placeholder and away_placeholder are non-empty strings for all 32

Given data/matches.yaml is loaded
When kickoff_at values are inspected
Then all 104 entries have a non-null kickoff_at
  And no kickoff_at predates 2026-06-11
```

---

### REQ-PHASE0-09 — `scripts/load_fixture.py` is idempotent

**Statement**: Running `scripts/load_fixture.py --all` a second time against a database that already contains the fixture data produces zero row changes — no inserts, updates, or deletes — and exits with code 0.

**Scenarios:**

```gherkin
Given the migration has been applied and the DB is empty
When load_fixture.py --all is run for the first time
Then 48 team rows and 104 match rows are inserted
  And the script exits with code 0

Given the DB already contains the 48 teams and 104 matches from a previous run
When load_fixture.py --all is run again with identical YAML files
Then zero additional rows are inserted
  And zero rows are updated
  And zero rows are deleted
  And the script exits with code 0

Given the script supports a --dry-run flag
When load_fixture.py --dry-run --all is executed against an empty DB
Then no rows are written to the database
  And the script reports what would be inserted
  And the script exits with code 0
```

---

### REQ-PHASE0-10 — `tests/test_fixture_integrity.py` encodes the 6 verification queries

**Statement**: The file `tests/test_fixture_integrity.py` contains pytest test cases that execute all 6 verification queries from `docs/07-fixture-loading.md` § 8 against a live Postgres instance seeded with the fixture, and all assertions match the expected values.

**The 6 required assertions (each must be a distinct test case or named assertion):**

1. `SELECT COUNT(*) FROM teams` = 48
2. `SELECT group_letter, COUNT(*) FROM teams GROUP BY group_letter` → 12 groups, each count = 4
3. `SELECT COUNT(*) FROM matches` = 104
4. `SELECT stage, COUNT(*) FROM matches GROUP BY stage` → 72 group / 16 r32 / 8 r16 / 4 qf / 2 sf / 1 third / 1 final
5. `SELECT COUNT(*) FROM matches WHERE stage = 'group' AND (home_team_id IS NULL OR away_team_id IS NULL)` = 0
6. `SELECT COUNT(*) FROM matches WHERE lock_at != kickoff_at - INTERVAL '1 hour'` = 0

**Scenarios:**

```gherkin
Given the migration has been applied and load_fixture.py --all has been run
When `pytest tests/test_fixture_integrity.py` is executed
Then all test cases pass with exit code 0
  And the output shows at least one named test per verification query

Given the DB has not been seeded (empty tables after migration)
When `pytest tests/test_fixture_integrity.py` is executed
Then at least one test fails (validates tests are non-trivial)

Given the DB has 47 teams (one missing)
When the teams-count test is executed
Then it fails with a clear assertion message stating expected 48, got 47
```

---

### REQ-PHASE0-11 — `agents.human_id` carries a UNIQUE constraint

**Statement**: The `agents` table has a `UNIQUE` constraint on the `human_id` column, enforcing the one-agent-per-human invariant at the database level. This constraint must be named or derivable from `docs/03-data-model.md` and must be present in the initial Alembic migration.

**Scenarios:**

```gherkin
Given the migration has been applied
When two separate agent rows are inserted with the same human_id
Then the database raises a unique constraint violation
  And no second agent row is committed for that human_id

Given a human row exists with one agent row
When the agent row is deleted and a new agent row is inserted for the same human_id
Then the insert succeeds (constraint only prevents duplicates, not reuse after deletion)

Given the Alembic migration file 202605160001_initial.py
When it is inspected
Then it contains a UNIQUE constraint definition on agents.human_id
```

---

### REQ-PHASE0-12 — `docs/02-trd.md` updated to Next.js 16 with compat note

**Statement**: The Technical Requirements Document (`docs/02-trd.md`) reflects Next.js 16 (not 15) as the frontend framework version in use, and includes an explicit note in the Auth.js / shadcn section flagging that the M2 implementer must verify Auth.js v5 + shadcn CLI + Tailwind v4 compatibility on Next.js 16 before beginning M2.

**Scenarios:**

```gherkin
Given the updated docs/02-trd.md
When the "Frontend" stack section is read
Then it references Next.js 16.x (not 15.x)

Given the updated docs/02-trd.md
When the Auth.js / shadcn / Tailwind section is read
Then it contains a note explicitly flagging compatibility verification required before M2
  And the note mentions: Auth.js v5 (next-auth@beta), shadcn CLI, Tailwind v4, Next.js 16 + React 19
```

---

### REQ-PHASE0-13 — `docs/KICKOFF.md` "Decisions locked" table gains 2 rows

**Statement**: The `docs/KICKOFF.md` file's "Decisions locked" table is updated to include two new rows: one for the Next.js version decision (Next.js 16.2.6, updated from 15) and one for the frontend directory name decision (`worldcupagents-fe/`, not renamed to `frontend/`).

**Scenarios:**

```gherkin
Given the updated docs/KICKOFF.md
When the "Decisions locked" table is read
Then a row exists for "Frontend framework" with value "Next.js 16.2.6" and source "phase-0-foundations proposal"
  And a row exists for "Frontend dir name" with value "worldcupagents-fe/" and source "phase-0-foundations proposal"
```

---

### REQ-PHASE0-14 — `docs/CLAUDE.md` "Repo layout (target)" shows `worldcupagents-fe/`

**Statement**: The `docs/CLAUDE.md` file's "Repo layout (target)" directory tree is updated to show `worldcupagents-fe/` in place of `frontend/`, reflecting the confirmed directory name.

**Scenarios:**

```gherkin
Given the updated docs/CLAUDE.md
When the "Repo layout (target)" section is read
Then the directory tree contains worldcupagents-fe/ (not frontend/)

Given the root CLAUDE.md (copy of docs/CLAUDE.md applied during M0)
When it is inspected
Then it also shows worldcupagents-fe/ in the repo layout tree
  And it does not reference frontend/ anywhere in the layout section
```

---

### REQ-PHASE0-15 — Root `CLAUDE.md` and `README.md` exist

**Statement**: A `CLAUDE.md` file exists at the repo root (a copy of `docs/CLAUDE.md`, updated with the `worldcupagents-fe/` path) and a `README.md` exists at the repo root containing at minimum: prerequisites (uv, pnpm, Docker), clone instructions, and the M0 acceptance script.

**Scenarios:**

```gherkin
Given the repo has been set up per M0
When the root CLAUDE.md is read
Then it is content-equivalent to docs/CLAUDE.md (after the CLAUDE.md doc update)

Given the root README.md
When it is read
Then it lists prerequisite tools: uv, pnpm, Docker
  And it includes the command sequence: git clone → make dev → curl /healthz → open :3000
```

---

### REQ-PHASE0-16 — `backend/` Python package is initialised with full dependency set

**Statement**: The `backend/` directory is a valid `uv`-managed Python project (`pyproject.toml` present) with all runtime and dev dependencies from `docs/KICKOFF.md` Day-1 script declared and locked. Running `uv sync` inside `backend/` installs all deps without errors.

**Runtime deps** (minimum, must all be declared):
`fastapi`, `fastmcp`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `argon2-cffi`, `python-jose[cryptography]`, `apscheduler`, `httpx`, `pyyaml`

**Dev deps** (minimum, must all be declared):
`pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`

**Scenarios:**

```gherkin
Given the backend/ directory
When `uv sync` is run inside it
Then it completes with exit code 0 and no dependency conflicts

Given the backend pyproject.toml
When it is inspected
Then all runtime and dev dependencies listed above are present
  And Python version is pinned to >=3.12
```

---

### REQ-PHASE0-17 — `worldcupagents-fe/` has `next-auth@beta` installed

**Statement**: The `worldcupagents-fe/` directory's `package.json` includes `next-auth` at a beta version. No shadcn setup has been performed. No Auth.js configuration files are created. The existing Tailwind v4 configuration left by `create-next-app` is not modified.

**Scenarios:**

```gherkin
Given worldcupagents-fe/package.json
When it is inspected
Then next-auth is listed as a dependency with a beta version tag

Given worldcupagents-fe/
When its file tree is inspected
Then no shadcn configuration files exist (e.g. no components.json from shadcn)
  And no auth.config.ts or auth.ts file exists
  And the Tailwind configuration file is the default from create-next-app
```

---

### REQ-PHASE0-18 — Makefile exposes `dev`, `test`, `migrate`, and `seed` targets

**Statement**: The root `Makefile` exposes exactly (at minimum) four named targets: `dev`, `test`, `migrate`, and `seed`. Each target performs the documented action. The `migrate` target runs `alembic upgrade head`. The `seed` target runs `scripts/load_fixture.py --all`. The `test` target runs `pytest` inside `backend/`.

**Scenarios:**

```gherkin
Given the root Makefile
When `make migrate` is executed with Postgres running and migrations not yet applied
Then alembic upgrade head runs and exits with code 0

Given the root Makefile
When `make seed` is executed with the DB schema applied
Then scripts/load_fixture.py --all runs and exits with code 0

Given the root Makefile
When `make test` is executed
Then pytest runs inside backend/ and reports results
```

---

## 2. Non-Functional Requirements

### NFR-01 — `make dev` cold-boot time

`make dev` must bring the full stack (Postgres, backend, frontend) to a ready state in under 60 seconds on a developer laptop with images already pulled and dependencies already installed. "Ready" means all three healthchecks pass.

### NFR-02 — Migration + seed + test run time

`make migrate && make seed && make test tests/test_fixture_integrity.py` must complete in under 30 seconds end-to-end against a local Postgres instance that is already running.

### NFR-03 — Fixture loader is purely additive

`scripts/load_fixture.py` MUST NEVER issue a `DELETE` statement against the `teams` or `matches` tables, even in error-recovery paths. It is an append/upsert-only tool. Any destructive operation requires a separate admin script and human approval.

### NFR-04 — Code quality gates

All code introduced in this change must pass the following checks before merge:
- **Backend**: `ruff check backend/` passes with zero errors; `mypy --strict backend/app/` passes with zero errors
- **Frontend**: `pnpm tsc --noEmit` inside `worldcupagents-fe/` passes with zero type errors
- **SQL in migrations**: all trigger DDL and view DDL matches `docs/03-data-model.md` § 3–4 verbatim (reviewer responsibility)

---

## 3. Data Contracts

The authoritative schema for this change is `docs/03-data-model.md` § 1–4. The following tables and objects are IN SCOPE for phase-0-foundations:

**Tables (created by 202605160001_initial.py):**
- `humans` — UUID PK, UNIQUE constraints on `google_sub` and `email`
- `agents` — UUID PK, UNIQUE on `human_id` (one-agent-per-human), UNIQUE on `slug`, `name`, `token_hash`; CHECK constraints on name length and description length
- `teams` — SMALLINT PK (1–48), UNIQUE on `fifa_code`
- `matches` — INT PK (1–104), stage CHECK enum, nullable `home_team_id` / `away_team_id` with FK to `teams`; CHECK constraints on score consistency
- `predictions` — BIGSERIAL PK, UNIQUE(agent_id, match_id), CHECK on probability sum (abs < 0.001), CHECK on exact score pair consistency
- `prediction_history` — BIGSERIAL PK, FK to `predictions`
- `scores` — Composite PK (agent_id, match_id)
- `audit_log` — BIGSERIAL PK, actor_type CHECK enum
- `pending_resolutions` — INT PK (FK to matches)

**NOT in scope (deferred to v1.1 migration):**
- `brackets`
- `bracket_scores`

**View:**
- `v_agent_leaderboard` — defined in `docs/03-data-model.md` § 3; leaderboard ranking MUST use `NULLS LAST` on `avg_brier`

**Triggers:**
- `trg_matches_lock_at` — BEFORE INSERT OR UPDATE OF kickoff_at ON matches; sets `lock_at = kickoff_at - INTERVAL '1 hour'`
- `trg_predictions_history` — AFTER INSERT OR UPDATE ON predictions; inserts into prediction_history
- `touch_updated_at` — generic, applied to humans, agents, matches, predictions; fires BEFORE UPDATE

**Key constraint to highlight (see REQ-PHASE0-11):**
- `agents.human_id UNIQUE` — single most load-bearing constraint in the product. One-agent-per-human is enforced HERE, not only in application code.

**Fixture data contracts:**
- `data/teams.yaml` — 48 rows, IDs 1–48, stable forever, sourced verbatim from `docs/07-fixture-loading.md` § 4
- `data/matches.yaml` — 104 rows; IDs 1–72 group stage with non-null team FKs; IDs 73–104 knockout placeholders with null team IDs; all rows have non-null `kickoff_at`

---

## 4. Out of Scope

The following are explicitly NOT part of phase-0-foundations:

- MCP tools or MCP server mount at `/mcp`
- Auth configuration — no Google OAuth, no Auth.js routes, no JWT middleware; `next-auth@beta` is installed only
- REST endpoints beyond `GET /healthz`
- Frontend pages beyond the default Next.js scaffold
- shadcn install or any Tailwind configuration changes beyond create-next-app defaults
- Deployment to Fly.io, Vercel, Neon, or any cloud infrastructure
- Sentry, structlog, or any observability configuration
- GitHub Actions or any CI pipeline
- `brackets` and `bracket_scores` tables (v1.1 migration)
- `scripts/seed_dev.py` (a separate developer seeding script; only `load_fixture.py` is in scope)
- The `scripts/build_matches_yaml.py` Wikipedia scraper (the YAML is hand-authored; the scraper is deferred)
- Full 104-match calendar with real knockout teams (knockouts remain as placeholders until group stage ends in real life)
- `pending_resolutions` population (table created by migration; rows inserted only by the background job in M7)
- Rate limiting on any endpoint

---

## 5. Verification Checklist (for `sdd-verify`)

The following can be checked programmatically or by file inspection:

| Check | Method |
|---|---|
| `make dev` exits cleanly | Run command, assert exit code 0, curl :8000/healthz and :3000 |
| `GET /healthz` → 200 + `{"status":"ok"}` | curl assertion |
| `backend/.env.example` has all 5 required keys | File inspection / grep |
| `worldcupagents-fe/.env.example` has all 3 required keys | File inspection / grep |
| `alembic upgrade head` succeeds on empty DB | Run in CI-like environment |
| All 9 in-scope tables exist after migration | `\dt` or SQLAlchemy inspection |
| All 3 triggers exist after migration | `\df` or pg_trigger query |
| `v_agent_leaderboard` view exists | `\dv` or information_schema query |
| `agents.human_id` UNIQUE enforced | Insert two agents with same human_id, expect constraint violation |
| `set_lock_at` trigger fires | Insert match, check lock_at = kickoff_at - 1h |
| `snapshot_prediction_history` fires | Insert prediction, check prediction_history has 1 row |
| `touch_updated_at` fires | Update human row, check updated_at increased |
| `data/teams.yaml` has exactly 48 entries | `wc -l` or YAML parse + count |
| `data/matches.yaml` has 104 entries | YAML parse + count |
| Group-stage matches (1–72) have non-null team IDs | YAML inspection |
| Knockout matches (73–104) have null team IDs | YAML inspection |
| `load_fixture.py --all` is idempotent | Run twice, compare row counts |
| `pytest tests/test_fixture_integrity.py` passes | Run command, assert exit code 0 |
| `docs/02-trd.md` references Next.js 16 | grep / text search |
| `docs/KICKOFF.md` has 2 new decision rows | Text search for "Next.js 16" and "worldcupagents-fe/" |
| `docs/CLAUDE.md` layout shows `worldcupagents-fe/` | grep / text search — must NOT find `frontend/` in layout tree |
| Root `CLAUDE.md` consistent with docs/CLAUDE.md | diff or text comparison |
| `ruff check backend/` clean | Run command |
| `mypy --strict backend/app/` clean | Run command |
| `pnpm tsc --noEmit` clean in frontend | Run command |
| `next-auth` beta in worldcupagents-fe/package.json | File inspection |
| No shadcn config files in worldcupagents-fe/ | File tree check — absence of components.json |

---

## 6. Spec Assumptions and Flags

The following assumptions were made where the proposal was silent. These are flagged for Kevin's awareness and should be overridden if incorrect:

1. **ASSUMPTION**: `kickoff_at` for knockout matches (73–104) is non-null, set to best-known published FIFA calendar dates. The proposal says "best-known kickoff times" and "optional kickoff if not published, patch later." This spec conservatively requires ALL 104 entries to have non-null `kickoff_at` — if some knockout dates are genuinely unknown, this can be relaxed to "non-null for group stage only" before the design phase begins.

2. **ASSUMPTION**: The verification query `SELECT MIN/MAX(kickoff_at)` from `docs/07-fixture-loading.md` § 8 is covered implicitly by the non-null kickoff_at assertion in REQ-PHASE0-08 rather than as a standalone fixture-integrity test case. If Kevin wants min/max bounds asserted in `test_fixture_integrity.py`, that should be called out as a 7th test case.

3. **ASSUMPTION**: `scripts/` and `data/` directories are created during M0 (scaffolded empty), and populated with content during M1. REQ-PHASE0-16 and REQ-PHASE0-18 treat M0 as meeting the structural requirement; content (YAML files, loader script) is M1.

4. **ASSUMPTION**: `touch_updated_at` is implemented as a single shared trigger function applied separately to `humans`, `agents`, `matches`, and `predictions` (4 trigger instances, one function). The doc says "generic" which implies this pattern.

5. **DESIGN NOTE**: The proposal open question about knockout kickoff times defaults to "set best-known times" (Recommendation accepted). No Kevin decision required unless he prefers nullable kickoffs for unknowns.
