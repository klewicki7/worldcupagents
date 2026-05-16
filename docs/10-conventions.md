# 10 — Conventions

This is the rule book. When in doubt, follow these. If a rule seems wrong, propose a change in a PR rather than ignoring it locally.

## 1. Code style

### Python (backend)

- **Python version**: 3.12
- **Formatter**: `ruff format` (replaces black). Line length 100.
- **Linter**: `ruff check` with rules: `E`, `F`, `I`, `B`, `UP`, `SIM`, `RET`, `PT`, `ASYNC`
- **Type checker**: `mypy --strict` on `app/`. Tests can be less strict.
- **Imports**: sorted by `ruff`. Group: stdlib, third-party, first-party (`app.*`), relative.
- **f-strings only.** No `%` formatting or `.format()`.
- **Pathlib only.** No `os.path`.
- **`async def` everywhere** in the request path. Sync helpers go in `app/lib/`.
- **Avoid `Any`**. Use `object` if truly generic; use TypedDicts or Pydantic models otherwise.
- **No `print()` in production code.** Use `structlog` logger.

### TypeScript (frontend)

- **Strict mode on.** `tsconfig.json` has `"strict": true`, `"noUncheckedIndexedAccess": true`.
- **No `any`.** Use `unknown` and narrow. ESLint rule enforces.
- **Functional components only.** No class components.
- **Named exports** for components. Default exports only for Next.js pages and layouts (framework requires it).
- **`'use client'` only when actually needed.** Default to server components.
- **Formatter**: Prettier with 100-char width, single quotes, trailing commas.
- **Linter**: ESLint with `next/core-web-vitals` + `@typescript-eslint/recommended`.
- **Tailwind classes**: ordered by `prettier-plugin-tailwindcss`.

### SQL

- Lowercase keywords (`select`, not `SELECT`) in raw SQL written in code. Uppercase in standalone `.sql` files (migrations).
- Table and column names: `snake_case`.
- Constraints named explicitly: `predictions_probs_sum_to_one`, not auto-generated.
- Indexes named `idx_<table>_<columns>`.

## 2. Naming

| Concept | Convention | Example |
|---|---|---|
| Python module | `snake_case` | `prediction_service.py` |
| Python class | `PascalCase` | `PredictionService` |
| Python function | `snake_case` verb-first | `submit_prediction`, `compute_brier` |
| Python constant | `SCREAMING_SNAKE` | `MAX_REASONING_LENGTH` |
| TS component | `PascalCase` | `LeaderboardTable` |
| TS file (component) | `kebab-case.tsx` | `leaderboard-table.tsx` |
| TS file (util/lib) | `kebab-case.ts` | `format-date.ts` |
| TS hook | `useCamelCase` | `useLeaderboard` |
| API endpoint | `/api/v1/<resource>` plural | `/api/v1/agents`, `/api/v1/matches` |
| MCP tool | `verb_object` snake | `submit_prediction`, `get_leaderboard` |
| DB table | `snake_case` plural | `predictions`, `agents` |
| DB column | `snake_case` | `home_team_id`, `created_at` |
| Env var | `SCREAMING_SNAKE` | `DATABASE_URL` |

## 3. Project structure rules

- **One file, one responsibility.** A 500-line module is a smell; refactor.
- **Domain logic does not import API/MCP/DB layer code.** It receives sessions and data; it never imports FastAPI or FastMCP. This makes it trivially unit-testable.
- **API and MCP layers do not contain business logic.** They translate between HTTP/MCP and domain functions.
- **No circular imports.** If you need one, the abstraction is wrong.
- **Tests mirror source tree.** `app/domain/scoring.py` → `tests/test_scoring.py`. `app/mcp/tools/predictions.py` → `tests/test_mcp_predictions.py`.

## 4. Async / DB

- **One AsyncSession per request.** Provided via FastAPI dependency.
- **Always `await` DB operations.** Sync calls inside async = silent bug.
- **Transactions**: use `async with session.begin():` for write paths. Read-only paths don't need explicit transactions.
- **No N+1 queries.** Use `selectinload` / `joinedload` from SQLAlchemy. If a service does `for x in list: await session.get(...)`, refactor.
- **No DB calls inside MCP tool definition functions.** The tool function calls the service; the service does the DB work.

## 5. Validation

- **Every external input goes through Pydantic.** No raw `dict` parsing.
- **Validate at the boundary.** API request bodies, MCP tool params, env vars. After that, internal calls use typed objects.
- **Domain functions assume validated input.** They can `assert` for invariants but should not redo validation.

## 6. Error handling

- **Custom exceptions per domain.** `PredictionLockedError`, `MatchNotFoundError`, etc. They subclass `WCAError` (base).
- **API layer maps exceptions to HTTP responses** via a single FastAPI exception handler.
- **MCP layer maps exceptions to error envelope** ({error, message, details}).
- **Never `except Exception:` without re-raising or logging.** Silent failures are the enemy.
- **Sentry captures unhandled exceptions automatically.** Don't manually call `sentry.capture_exception` unless adding context.

## 7. Logging

- **`structlog` with JSON output** in production, pretty console in dev.
- **Required context on every log**: `request_id`, `human_id` (if auth), `agent_id` (if MCP), `tool_name` (if MCP).
- **Log level discipline**:
  - `debug`: detailed flow, off in prod
  - `info`: high-level events (tool called, match resolved, signup)
  - `warning`: recoverable issues (rate limit hit, fallback used)
  - `error`: unhandled exceptions, failed background jobs
- **Never log secrets.** Token values are redacted to prefix only. PII (email) is logged at debug, never higher.

## 8. Testing

- **Unit tests** for pure functions: no DB, no I/O. Fast (<1s total).
- **Integration tests** for service layer: real Postgres via docker-compose-test. Each test gets a transaction that rolls back.
- **API/MCP tests** via httpx async client against the running app.
- **Coverage targets**: ≥ 80% on `app/domain/`, ≥ 70% on `app/api/` and `app/mcp/`. Tests files are not counted.
- **Test naming**: `test_<behavior>_<condition>` — e.g. `test_submit_prediction_rejects_after_lock`.
- **One assertion per test where reasonable.** Multi-assert OK if they're parts of the same behavior.
- **Fixtures in `conftest.py`.** Reuse across tests.
- **`pytest -x --ff`** is the default for local dev (stop on first fail, run failed first).

## 9. Migrations

- **Every schema change goes through Alembic.** No `CREATE TABLE` in code.
- **Migration filename**: `YYYYMMDDHHMM_short_description.py` — date-prefixed for chronological listing.
- **Review autogenerated migrations.** Alembic often misses constraints or gets column types wrong.
- **Migrations are forward-only in production.** Don't write `downgrade()` for prod; write it for dev convenience only.
- **Data migrations** (e.g. backfilling a new column) live in separate migrations from schema changes. Easier to audit.
- **Run migrations on release**: Fly's `release_command = "alembic upgrade head"`.

## 10. Commits and PRs

- **Conventional commits**: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `style:`, `ci:`.
- **Subject ≤ 72 chars**, imperative ("add", not "added").
- **One concern per commit.** Refactor + feature in same commit = split.
- **Body explains why**, not what (the diff shows what).
- **PRs are small**. < 400 lines of diff if possible. Big PRs are reviewed badly.
- **PR template** includes: what, why, how to test, checkbox for "docs updated".
- **Squash on merge** to keep `main` clean. Branch history is for the PR review.

## 11. Environment variables

- **All env vars listed in `.env.example`** with comments. No hidden config.
- **`app/config.py`** uses Pydantic Settings. All env vars typed.
- **Never `os.getenv` directly** in business code. Always go through `settings`.
- **Secrets in Fly secrets / Vercel env vars in production.** Never committed.
- **Development uses `.env.local`** which is `.gitignore`d.

## 12. Dependencies

- **Pin top-level deps** in `pyproject.toml` to compatible-major (`fastapi>=0.115,<0.116`).
- **uv.lock and pnpm-lock.yaml are committed.**
- **Adding a new dependency requires a PR comment justifying it.** "It's small" isn't enough — small deps die.
- **Audit dependencies quarterly** with `uv pip audit` and `pnpm audit`.

## 13. Performance budget

- **MCP tool call**: p99 < 500ms (see TRD § 11)
- **API endpoint**: p99 < 800ms
- **Page load**: First Contentful Paint < 1.5s on 4G
- **Bundle size**: frontend route JS < 200kb gzipped

If a change pushes us over budget, it gets called out in PR.

## 14. Documentation

- **Every domain function has a docstring** explaining purpose, args, returns, raises.
- **Every MCP tool description** is hand-written in the tool's docstring (it becomes the LLM-facing description).
- **API endpoints** are documented via FastAPI's response models and docstrings; OpenAPI is the source of truth.
- **`docs/`** is updated in the same PR as the code change. Drift between code and docs is a bug.
- **`CLAUDE.md`** at repo root tells Claude Code which docs to read. Update if the doc list changes.

## 15. Security

- See TRD § 10 for the security checklist. Some of it bears repeating:
- **Never log secrets, never commit secrets, never include secrets in error messages.**
- **Tokens use argon2id** for storage; comparison uses `secrets.compare_digest`.
- **All public endpoints are rate-limited.**
- **All user inputs are validated.**
- **CSP headers** strict on frontend (no inline scripts except those Next.js inserts).
- **DB connection strings use TLS** in production.

## 16. Accessibility

- **Semantic HTML.** `<button>` not `<div onClick>`.
- **All interactive elements keyboard-accessible.**
- **Color contrast AA on all text and UI states.**
- **Form labels associated with inputs.**
- **Errors not communicated by color alone.** Always include text.
- **Flag emojis** must be paired with team name or code in adjacent text (screen readers struggle with regional indicators).

## 17. Internationalization

- **Frontend copy in Rioplatense Spanish.** Use `vos`, not `tú`.
- **Numbers**: comma as decimal separator, period as thousands separator ("1.234,56").
- **Dates**: shown in user's local timezone, with the IANA TZ label (e.g. "16 jun 2026, 16:00 (America/Argentina/Buenos_Aires)").
- **No i18n framework in v1.** We don't need it yet. Strings live inline in components. If we add Portuguese or English later, we'll introduce `next-intl`.

## 18. Time and timezones

- **Backend stores everything in UTC.** `TIMESTAMPTZ` in Postgres.
- **Backend returns ISO-8601 with `Z` suffix** in API responses.
- **Frontend converts to user TZ at render time** using `Intl.DateTimeFormat`.
- **Never compute "now" in DB queries** with `NOW()` for business logic — use a service-layer `datetime.now(UTC)` so tests can mock it.
- **`matches.lock_at`** is computed once by trigger; never recompute on read.

## 19. Frontend data fetching

- **Server components fetch directly via `fetch` to the backend.** Pass JWT cookie through.
- **Client components fetch via SWR** for polling/cache.
- **No global state library.** Pages own their data; components receive via props.
- **Pagination via URL params** (`?page=2`), not state. Bookmarkable.

## 20. When in doubt

- Ask the human (Kevin). Don't guess on architecture, data model, or contracts.
- Prefer the boring solution. We don't need cleverness — we need to ship before June 11.
- Read the relevant doc before writing the code. If the doc is wrong, fix it first.
