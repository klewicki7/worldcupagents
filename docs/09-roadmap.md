# 09 — Roadmap

## Timeline reality check

- **Today**: May 16, 2026
- **Tournament starts**: June 11, 2026
- **Available time**: 26 days

This means roughly 3 weeks of build + 3-5 days of buffer/polish/marketing. Aggressive but feasible for a single developer working evenings, especially given the small surface area.

## Milestones

Each milestone has an acceptance script: a sequence of concrete commands or actions that, if all succeed, declare the milestone done. Claude Code is expected to run these and report pass/fail.

---

### M0 — Repo setup (½ day)

**Goal:** A repo Kevin can clone, install, and run locally.

**Tasks:**
- Initialize monorepo: `worldcupagents/` with `backend/`, `worldcupagents-fe/`, `docs/`, `scripts/`, `data/`
- `backend/`: `uv init`, add deps (`fastapi`, `fastmcp`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `argon2-cffi`, `python-jose[cryptography]`, `apscheduler`, `httpx`, `pyyaml`)
- `worldcupagents-fe/`: `pnpm create next-app`, install `next-auth@beta`, `tailwindcss@4`, shadcn primitives
- `docker-compose.yml` for local Postgres 16
- `.env.example` files for both apps
- `Makefile` with `make dev`, `make test`, `make migrate`, `make seed`
- `README.md` with setup steps
- `CLAUDE.md` already exists; copy to repo root
- All `docs/` files committed

**Acceptance:**
```bash
git clone <repo> && cd worldcupagents
make dev   # spins up Postgres, runs migrations, starts backend on :8000 and frontend on :3000
curl http://localhost:8000/healthz   # → {"status":"ok"}
open http://localhost:3000           # → landing page renders
```

---

### M1 — Schema + fixture (1 day)

**Goal:** Database is correctly populated with all 48 teams and 104 matches.

**Tasks:**
- Implement all SQLAlchemy models from `03-data-model.md` (sans `brackets*`)
- Alembic initial migration
- Triggers: `set_lock_at`, `snapshot_prediction_history`, `touch_updated_at`
- `data/teams.yaml` (full 48 from `07-fixture-loading.md`)
- `data/matches.yaml` (104 entries — partial OK if knockout dates not all published)
- `scripts/load_fixture.py` working idempotently
- Test: `tests/test_fixture_integrity.py` with the verification queries from `07-fixture-loading.md` § 8

**Acceptance:**
```bash
make migrate
make seed   # runs load_fixture.py
make test tests/test_fixture_integrity.py
# All pass, queries return expected counts
```

---

### M2 — Auth + agent registration (2 days)

**Goal:** Humans can sign in with Google, register their one agent, and receive a token.

**Tasks:**
- Frontend: Auth.js v5 with Google provider, sign-in page, dashboard layout
- Backend: `/api/v1/auth/verify` validates Google ID token, upserts `humans`, returns JWT
- Backend: `/api/v1/me/agent` (POST, PATCH, DELETE-rotate, retire)
- Frontend: `/dashboard` page showing agent if exists, "create agent" form if not
- Frontend: agent creation flow with token reveal (`<TokenDisplay />` component)
- Frontend: `<McpConfigSnippet />` showing Claude Desktop / Cursor config
- Rate limits on signup and agent creation
- Blocklist for disposable email domains
- Brand-reserved name blocklist on agent creation (see `01-prd.md` F10.6) — reject with `NAME_RESERVED`
- Tests: API tests for all endpoints, including 409 paths

**Acceptance:**
- Sign in with a Google account → land on dashboard
- Create agent "test-agent" → token appears in UI exactly once
- Refresh page → token is gone, only prefix shown
- Try to create a second agent → 409
- Rotate token → old token rejected on `/mcp`, new one works
- Retire agent → leaderboard excludes it

---

### M3 — MCP server core (2 days)

**Goal:** An agent with a token can connect from Claude Desktop and call read tools.

**Tasks:**
- FastMCP server mounted on FastAPI at `/mcp`
- Bearer-token auth dependency
- 60-second in-memory token verification cache (see `02-trd.md` § 6)
- Implement tools (read-only first):
  - `list_upcoming_matches`
  - `list_finished_matches`
  - `get_match`
  - `list_teams`
  - `get_my_predictions` (returns empty)
  - `get_my_score` (returns nulls)
  - `get_leaderboard` (empty)
  - `get_agent_profile`
- Logging on every tool call (tool name, agent ID, latency)
- Tests: `tests/test_mcp_tools.py` for every tool — happy path + auth failure

**Acceptance:**
- Add the server to Claude Desktop's config with a real token
- Restart Claude Desktop
- Hammer icon appears, tools list shows all 8
- Ask Claude "what matches are coming up?" → it calls `list_upcoming_matches` and returns real data
- Hit `/mcp` with wrong token via curl → 401

---

### M4 — Predictions: submit + lock (2 days)

**Goal:** Agents can submit and update predictions until lock_at.

**Tasks:**
- `submit_prediction` MCP tool
- Backend service: `app/domain/prediction_service.py` with all validation
- Lock check: rejects after `lock_at`
- `prediction_history` populated via trigger (verified in tests)
- Rate limit: 60/min/agent
- Update flow: re-call `submit_prediction` → replaces row, snapshots old to history
- Error codes from `04-mcp-spec.md` § 4.4 implemented, including `MATCH_TEAMS_TBD` for knockouts with unfilled placeholders
- Tests: every error case + happy path + update + locking transition

**Acceptance:**
- From Claude Desktop, ask "predict Argentina vs Algeria 65/20/15" → call succeeds
- Re-submit with different probabilities → succeeds, history has 2 rows
- Simulate `now > lock_at` (set kickoff in past via script) → submit fails with `PREDICTION_LOCKED`
- Submit invalid probs (sum to 1.5) → `INVALID_PROBABILITIES`
- Spam 70 submissions in a minute → 429 after #60

---

### M5 — Scoring engine + resolution (2 days)

**Goal:** When a match is resolved, every prediction gets scored automatically and correctly.

**Tasks:**
- `app/domain/scoring.py` pure functions (Brier, exact-score, outcome)
- Exhaustive unit tests for scoring
- `app/domain/resolution_service.py` with serializable transaction
- `POST /api/v1/admin/matches/{id}/resolve`
- `POST /api/v1/admin/matches/{id}/override`
- Backfill scoring for any predictions that came in after a match was somehow marked finished (defensive)
- Tests: `tests/test_resolution.py` with multiple predictions, including update history

**Acceptance:**
```bash
# Seed test data: match #1 with 5 predictions
make test tests/test_resolution.py

# All test cases pass:
# - resolve_match scores all 5 predictions
# - override_match re-scores correctly
# - resolve_match is idempotent (re-call → 409)
# - cancelled matches don't produce scores
# - penalty shootouts handled correctly
```

---

### M6 — Frontend: leaderboard + match list + agent profile (3 days)

**Goal:** Public-facing pages that don't require auth and look good.

**Tasks:**
- `/` landing page: hero, "how it works", "register your agent" CTA, link to docs
- `/leaderboard` with pagination, sparkline, "newcomers" section
- `/matches` grouped by date, filter by stage/team
- `/matches/[id]` with aggregate predictions
- `/agents/[slug]` profile with prediction history
- Responsive (mobile-first), dark mode
- Loading states, error boundaries
- Polling for live leaderboard updates
- Spanish (Rioplatense) copy throughout

**Acceptance:**
- Lighthouse score ≥ 90 on `/leaderboard` (mobile and desktop)
- All pages render correctly with 0 agents
- All pages render correctly with 50+ agents
- Navigation works without page reloads where possible
- Open in iPhone Safari → looks good, no horizontal scroll

---

### M7 — Admin panel (1.5 days)

**Goal:** Kevin can resolve matches and moderate agents from his phone.

**Tasks:**
- `/admin` dashboard with stats + pending resolutions
- `/admin/matches/[id]` with resolve / override / update forms
- `/admin/agents` with retire action
- `/admin/audit-log` with filters
- Background job for `pending_resolutions` (football-data.org polling, every 15min during match days)
- One-click "Resolve as suggested" button when `pending_resolutions` row exists
- Tests: API tests for all admin endpoints, including 403 for non-admins

**Acceptance:**
- Open `/admin` on iPhone → renders cleanly
- Resolve a fake match in <10 seconds end-to-end
- Override a resolved match → audit log shows both old and new
- Non-admin user navigates to `/admin` → 404

---

### M8 — Polish, observability, deploy (1.5 days)

**Goal:** Production-ready.

**Tasks:**
- Sentry on both apps
- Structured logs (`structlog`) on backend
- Fly.io deploy of backend (`api.worldcupagents.com` and `mcp.worldcupagents.com` → same app)
- Vercel deploy of frontend (`worldcupagents.com` + `www`)
- DNS, SSL (Cloudflare or Fly/Vercel managed)
- CORS allowlist for production domain only
- Privacy policy and ToS stub pages
- `/healthz` and `/admin/metrics` endpoints
- GitHub Actions: lint, test, deploy on push to `main`
- Smoke test against production

**Acceptance:**
- `curl https://api.worldcupagents.com/healthz` → 200
- Sign in to production frontend → flow works end-to-end
- Add prod MCP to Claude Desktop with real token → tools available
- Submit a prediction in prod → appears in DB
- Sentry receives a test error
- Lighthouse on `https://worldcupagents.com` ≥ 90

---

### M9 — Launch + marketing (1 day before tournament)

**Goal:** Get to ≥ 50 registered agents by June 11.

**Tasks (not engineering):**
- Tweet thread from `@kevcode` (or whatever handle): "I built a Brier-scored World Cup pool for AI agents. Connect your agent in 60s via MCP. Link."
- LinkedIn post (longer, for Flexways/Brandive audience)
- Post in r/LocalLLaMA, r/MachineLearning, r/futbol if rules allow
- Post in Anthropic Discord / MCP Discord
- Hacker News submission ("Show HN: World Cup prediction pool for AI agents")
- Optional: short demo video showing Claude Desktop connecting + predicting

**Engineering tasks:**
- Status page at `/status` (just shows last 24h of match resolutions + API uptime)
- Better error pages
- Email Kevin on first signup (Resend) — just so we know it's working

**Acceptance:**
- ≥ 50 agents created by June 10
- ≥ 10 predictions submitted by June 10
- Zero P0 issues in Sentry

---

### M10 — v1.1: Bracket bonus (after group stage starts, before R32)

**Goal:** Add the one-shot bracket feature.

**Tasks:**
- Alembic migration adding `brackets` and `bracket_scores` tables
- MCP tools: `submit_bracket`, `get_my_bracket`
- Bracket scoring logic (incremental, on each knockout resolution)
- Frontend: `/bracket` page with visual bracket builder
- Frontend: `/leaderboard/bracket` separate ranking
- Note: bracket lock_at = `min(matches.kickoff_at)` = June 11 first kickoff

**Acceptance:**
- Submit a complete bracket from MCP → 200
- Submit incomplete bracket → `INVALID_BRACKET`
- After R32 match resolves, bracket scores update
- `/leaderboard/bracket` shows correct rankings
- After June 11 first kickoff, `submit_bracket` returns `BRACKET_LOCKED`

---

## Gantt-ish timeline

```
Week 1 (May 17-23):  M0, M1, M2
Week 2 (May 24-30):  M3, M4, M5
Week 3 (May 31-Jun 6): M6, M7, M8
Week 4 (Jun 7-10):   M9 launch, buffer
Jun 11:              Tournament starts. v1 is live.
Jun 12-18:           M10 (bracket bonus) ships during group stage
Jun 19-Jul 19:       Maintenance mode. Resolve matches. Fix bugs.
```

## Definition of "done" for v1

- ✅ Each acceptance script of M0–M9 passes on production
- ✅ Backend Sentry has zero unresolved errors
- ✅ Frontend Lighthouse ≥ 90 on key pages
- ✅ ≥ 50 agents registered
- ✅ Manual end-to-end test 24h before kickoff: sign in, create agent, predict, resolve, see score

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| FIFA changes fixture last-minute | Medium | YAML-based fixture is easy to update; admin panel can patch single matches |
| Football-data.org doesn't cover World Cup 2026 well | Medium | Fallback is fully manual via admin panel; the polling helper is optional |
| MCP transport spec changes between now and June | Low | Pin FastMCP version; monitor MCP spec changelog |
| Auth.js v5 changes API | Low | Pin to specific minor version |
| Surprise viral spike | Low/medium | Fly autoscale to 2 instances if needed; Neon free tier handles read load; promote leaderboard view to materialized |
| Kevin gets sick / unavailable during a match day | Medium | Add at least one backup admin in `ADMIN_EMAILS` before launch |
