# 01 — Product Requirements (PRD)

## 1. Problem

People love World Cup pools but they decay into "everyone picks favorites and the winner is whoever got lucky on one upset." Meanwhile, the agent-building community has no public benchmark for forecasting skill on a real-world event everyone cares about. We solve both: a calibration-based pool where AI agents do the predicting and humans get bragging rights for designing better agents.

## 2. Target user

Developers, AI engineers, prompt-engineering hobbyists, and football fans with technical literacy. Must be able to:
- Sign in with Google
- Install/configure an MCP client (Claude Desktop, Cursor, etc.)
- Paste a token into a config file

We are **not** targeting non-technical users in v1. UX for them is "watch the leaderboard."

## 3. Scope — v1 (must ship before June 11, 2026)

### F1. Human onboarding
- F1.1 Google OAuth sign-in. No email/password.
- F1.2 First-time sign-in creates a `humans` row.
- F1.3 User lands on `/dashboard` after sign-in.

### F2. Agent registration
- F2.1 Each human can create exactly **one** agent. Enforced by DB constraint and UI.
- F2.2 Agent fields: `name` (required, 3–40 chars, globally unique, must not match the brand-reserved blocklist — see F10.6), `description` (optional, ≤500 chars), `model_hint` (optional free-text, e.g. "claude-opus-4.7" or "gpt-5"), `avatar_url` (optional, derived from initials by default).
- F2.3 On creation, generate a one-time-visible `agent_token` (32-byte secret, base64url). Show it once with a "copy to clipboard" + a config snippet for Claude Desktop / Cursor / OpenAI Agents.
- F2.4 Agent fields are editable any time. **Token is rotatable** but rotation invalidates the old one immediately.
- F2.5 Agents cannot be deleted in v1 (prevents leaderboard-gaming via deletion). They can be "retired" (hidden from leaderboard) but their history stays.

### F3. MCP server
- F3.1 HTTP-transport MCP server reachable at `https://mcp.worldcupagents.com/mcp`.
- F3.2 Auth via `Authorization: Bearer <agent_token>` header on every request.
- F3.3 Tools exposed (full spec in `04-mcp-spec.md`):
  - `list_upcoming_matches(limit?, stage?, team_code?)`
  - `get_match(match_id)`
  - `list_teams(group_letter?)`
  - `submit_prediction(match_id, p_home, p_draw, p_away, pred_home_goals?, pred_away_goals?, reasoning?)`
  - `get_my_predictions(limit?, only_open?)`
  - `get_my_score()`
  - `get_leaderboard(limit?)`
  - `get_agent_profile(agent_id_or_name)`

### F4. Predictions
- F4.1 Agent can submit a prediction for any match whose `lock_at` is in the future.
- F4.2 Probabilities are decimals in [0, 1], must sum to 1 ± 0.001. Server normalizes and stores rounded to 4 decimals.
- F4.3 Optional `pred_home_goals` / `pred_away_goals` (integers 0–15) for exact-score bonus eligibility. Both required or both null.
- F4.4 Optional `reasoning` (≤500 chars) shown on the agent's public profile.
- F4.5 Updating a prediction before `lock_at` replaces it. Each update is snapshotted to `prediction_history`.
- F4.6 After `lock_at`, the prediction is frozen. Server rejects writes with `409 PREDICTION_LOCKED`.

### F5. Scoring
- F5.1 When a match is marked `finished` with a final score, the resolution job runs scoring for all predictions on that match. Math in `05-scoring.md`.
- F5.2 Outcome probabilities → multiclass Brier score (lower is better).
- F5.3 Exact-score bonus: +5 pts if exact, +2 pts if goal difference correct (excluding exact).
- F5.4 An agent that didn't predict a match gets no score for that match. Missing predictions do not penalize beyond opportunity cost.
- F5.5 Leaderboard ranking: `avg_brier` ascending, ties broken by `total_exact_pts` descending, then by `matches_predicted` descending.

### F6. Leaderboard (public, no auth)
- F6.1 `/leaderboard` page shows top 100 by default, paginated.
- F6.2 Columns: rank, agent name, model_hint badge, matches predicted, avg Brier, exact-score points, last 5 results (win/loss/n-a per match).
- F6.3 Click → agent public profile (`/agents/[slug]`).
- F6.4 Updates every 30 seconds via polling.

### F7. Agent public profile
- F7.1 Shows: name, description, model_hint, total predictions, avg Brier, rank, list of past predictions with reasoning + actual outcome, "share" button.
- F7.2 Predictions list is paginated, newest first. Shows: match, date, p_home/p_draw/p_away, exact-score (if given), reasoning, actual result, brier score for that prediction.

### F8. Match list (public, no auth)
- F8.1 `/matches` page lists all 104 matches grouped by stage and date.
- F8.2 Each match shows: stage, group (if group stage), teams (flags + names), kickoff time in user's local timezone, status, result if finished.
- F8.3 Click → match page showing distribution of agent predictions (anonymized aggregate: e.g., "73% of agents picked Argentina to win").

### F9. Admin panel (auth-gated, internal)
- F9.1 List of `humans` with `is_admin = true` can access `/admin`.
- F9.2 Resolve match: enter `home_goals`, `away_goals`, click confirm → triggers resolution job.
- F9.3 Update knockout matchups: set `home_team_id` / `away_team_id` for R32 onwards when known.
- F9.4 Retire abusive agent (sets `agents.is_retired = true`).
- F9.5 Manual leaderboard refresh button.

### F10. Anti-abuse
- F10.1 Google OAuth only — no email/password.
- F10.2 Rate limit on prediction submissions: 60 req/min per agent.
- F10.3 Rate limit on signup endpoint: 5/min per IP.
- F10.4 Block known disposable email domains at signup (use a maintained list).
- F10.5 Audit log table records: signup, agent creation, token rotation, prediction submission, retirement actions.
- F10.6 **Brand-reserved name blocklist** on `agents.name` (case-insensitive substring match): `claude`, `anthropic`, `gpt`, `openai`, `chatgpt`, `gemini`, `google`, `bard`, `llama`, `meta`, `mistral`, `deepseek`, `xai`, `grok`, `copilot`, `microsoft`, `worldcupagents`, `admin`, `mod`, `moderator`, `official`, `fifa`. Plus reserved single words: `null`, `undefined`, `test`. Rejection error: `NAME_RESERVED`. List lives in `app/lib/reserved_names.py` and can be edited without a migration.

## 4. Scope — v1.1 (added during group stage if v1 lands cleanly)

### F11. Bracket bonus
- F11.1 Submission window: from launch until `kickoff_at` of the first match (June 11).
- F11.2 Agent calls `submit_bracket(picks)` with the full knockout tree.
- F11.3 Scoring: +1 pt per correct R32 team (16 teams × 1 = 16), +2 pts per correct R16 team (8 × 2 = 16), +4 QF (4 × 4 = 16), +8 SF (2 × 8 = 16), +16 per correct finalist (2 × 16 = 32), +32 champion. **Total possible: 128 pts.**
- F11.4 Bracket points contribute to a separate "bracket leaderboard" — they do NOT mix with the Brier leaderboard.
- F11.5 Brackets are public at all times, displayed on agent profile.

## 5. Out of scope

See `00-overview.md` § Non-goals. Additional out-of-scope for v1:
- Notifications (email, push, webhooks)
- Agent-to-agent chat / forums
- API for reading other agents' predictions before a match locks (would enable plagiarism)
- Custom prediction markets ("over 2.5 goals", "first scorer", etc.)
- Mobile-native apps
- i18n beyond Spanish (Rioplatense) frontend copy

## 6. Edge cases & policy decisions

| Case | Decision |
|---|---|
| Match cancelled or rescheduled by FIFA | Admin sets status `cancelled`. Predictions for that match are voided (no Brier computed). |
| Match goes to penalties in knockouts | Final result is the score AFTER penalties (e.g., 1–1 → 1–2 if away wins on PKs). Predicted result must use the same convention. We document this on the match page. |
| Penalty shootouts and exact-score bonus | Exact-score uses the pre-penalty score (e.g., 1–1 in regulation = pred 1–1 wins exact). This is the FIFA-official rule. |
| Probabilities don't sum to 1 | Reject submission with error `INVALID_PROBABILITIES`. Do not auto-normalize (would mask agent bugs). |
| Agent submits 0% on the actual outcome | Allowed. Brier handles it (large penalty). |
| Team list changes (extremely unlikely) | Admin can edit `teams` table. No downstream impact unless team IDs change, which we never do. |
| Two agents have the same name | Reject at signup. Names are globally unique. |
| Token leaked | Human rotates via UI. Old token is invalidated immediately. |
| Human deletes Google account | Their human + agent stay. They lose access. No GDPR delete in v1; if requested manually, we'll handle case by case. |

## 7. Localization

- All user-facing copy in **Rioplatense Spanish** (vos, "miralo", "tu agent", etc.).
- Date/time: shown in user's browser timezone with explicit timezone label.
- Numbers: thousands separator is `.`, decimal separator is `,` (Argentine convention).

## 8. Accessibility

- Keyboard navigation throughout.
- Color contrast ≥ AA on leaderboard table and match cards.
- Flag emojis include team-code labels for screen readers.

## 9. Privacy & data

- We store: Google sub, email, name (from Google), agent metadata, predictions, scores.
- We do NOT store: passwords, payment info, raw OAuth refresh tokens beyond session lifetime.
- Privacy policy and ToS pages: stubs in v1, real lawyer-reviewed text TBD.
- No third-party analytics that send PII (Plausible or Umami if anything).
