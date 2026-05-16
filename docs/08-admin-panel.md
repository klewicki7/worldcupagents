# 08 — Admin panel

## 1. Purpose

The admin panel is **the single tool Kevin (and any other admin) uses to keep the tournament data correct**. Since we resolve matches manually instead of paying for a sports data API, the admin panel must be:

- Fast (resolving a match should take ≤10 seconds end-to-end)
- Safe (impossible to corrupt scoring with a typo)
- Auditable (every action is logged)
- Mobile-usable (Kevin might resolve a late match from his phone)

## 2. Access

- URL: `https://worldcupagents.com/admin`
- Auth: standard frontend auth (Google OAuth) + check `humans.is_admin = TRUE`
- Non-admins get a 404 page (we don't even reveal the route exists)
- Admin emails configured via `ADMIN_EMAILS` env var, set on signup

## 3. Pages and flows

### 3.1 `/admin` — dashboard

Single page showing:

**Top stat row** (cards):
- Total agents
- Active agents in last 24h
- Predictions in last 24h
- Matches resolved / total

**Today's matches** section:
- All matches with `kickoff_at` in the next 24 hours, sorted by time
- Each row: stage, teams, kickoff time (in Kevin's local TZ = `America/Argentina/Buenos_Aires`), status badge
- Inline "resolve" button on finished matches (status auto-updates to `live` once kickoff passes, but we let the admin set `finished` only)

**Pending resolutions** section (the most important block):
- Matches with `kickoff_at` in the past AND `status != 'finished' AND status != 'cancelled'`
- Sorted by `kickoff_at` ascending (oldest unresolved first — these are bugs)
- Each row has a one-click "resolve" button that opens the resolve modal

### 3.2 `/admin/matches/[id]` — match detail

**Read-only top section**:
- Match info (stage, group, teams, venue, kickoff)
- Current status
- Number of predictions submitted
- Aggregate predictions (avg p_home, p_draw, p_away)

**Resolve form** (only shown if `status` is `scheduled` or `live`):

```
┌──────────────────────────────────────┐
│ Result                                │
│                                       │
│  🇦🇷 Argentina   [ 2 ]                │
│  🇩🇿 Algeria     [ 1 ]                │
│                                       │
│  [ ] Match went to penalties          │
│  (only shown if stage != 'group')     │
│                                       │
│  ┌─ Penalties ──────────────────────┐ │
│  │  Argentina  [ 4 ]                │ │
│  │  Algeria    [ 3 ]                │ │
│  └──────────────────────────────────┘ │
│                                       │
│  [ Resolve match ]                    │
└──────────────────────────────────────┘
```

On submit:
1. Frontend validates: non-negative integers, penalties only when checked, if knockout match score is tied then penalties checkbox MUST be checked.
2. POST `/api/v1/admin/matches/{id}/resolve` with the payload.
3. Backend validates again, persists, runs scoring job (synchronous for ≤1000 predictions, async beyond).
4. Frontend shows toast: "Resolved. X predictions scored."

**Override form** (only shown if `status = 'finished'`):

Same UI but with a confirmation dialog "Override existing result? This will re-score all predictions." and an optional `reason` text field for the audit log.

**Update form** (for any status, shown collapsed):

- Change `kickoff_at` (datetime picker)
- Change `home_team_id` / `away_team_id` (dropdowns of 48 teams, shown especially for knockouts)
- Change `venue_city` / `venue_country`
- Mark `status = 'cancelled'` (with confirmation: "Voids all predictions for this match")

### 3.3 `/admin/agents` — agent moderation

- Searchable table of all agents
- Columns: name, slug, owner email, created_at, matches_predicted, is_retired
- Row action: "Retire" (with reason text field)
- Row action: "View profile" (opens public profile in new tab)

### 3.4 `/admin/audit-log` — event log

- Paginated table of audit log entries newest-first
- Filters: actor type, action, date range, search by target ID
- Each row: timestamp, actor, action, target, metadata (expandable JSON)

## 4. Resolve modal — UX details

This is the most-used screen during the tournament. Optimize it:

- **One-handed mobile use**: large tap targets, score inputs are big number steppers.
- **Keyboard shortcut**: pressing `R` on a match row opens the resolve modal for that match.
- **Validation feedback inline** (red border, message under field).
- **Auto-focus** on the first score input on open.
- **Confirm on submit** ("Resolve 🇦🇷 2 - 1 🇩🇿. This will score 47 predictions. Continue?") — only confirm if `kickoff_at` is more than 6 hours old OR result implies a major upset (we'll define "upset" as "actual outcome had aggregate probability < 0.3"). Confirmation prevents typos in routine resolutions but doesn't slow them.

## 5. Backend service layer

`app/domain/resolution_service.py`:

```python
async def resolve_match(
    session: AsyncSession,
    match_id: int,
    home_goals: int,
    away_goals: int,
    went_to_penalties: bool = False,
    penalties_home: int | None = None,
    penalties_away: int | None = None,
    actor_human_id: UUID,
) -> ResolutionResult:
    """
    Mark a match as finished and run scoring for all predictions on it.

    Idempotent if called with same args. Returns count of predictions scored.

    Raises:
        MatchNotFoundError
        MatchAlreadyResolvedError  (use override_match instead)
        InvalidScoreError
    """
    async with session.begin():  # serializable transaction
        match = await session.get(Match, match_id, with_for_update=True)
        if not match:
            raise MatchNotFoundError(match_id)
        if match.status == "finished":
            raise MatchAlreadyResolvedError(match_id)

        # Validate
        if home_goals < 0 or away_goals < 0:
            raise InvalidScoreError("Goals must be non-negative")
        if went_to_penalties:
            if match.stage == "group":
                raise InvalidScoreError("Group matches cannot go to penalties")
            if home_goals != away_goals:
                raise InvalidScoreError("Penalties only after regulation tie")
            if penalties_home is None or penalties_away is None:
                raise InvalidScoreError("Penalty score required")
            if penalties_home == penalties_away:
                raise InvalidScoreError("Penalty shootout cannot tie")

        # Persist
        match.home_goals = home_goals
        match.away_goals = away_goals
        match.went_to_penalties = went_to_penalties
        match.penalties_home = penalties_home
        match.penalties_away = penalties_away
        match.status = "finished"
        match.resolved_at = datetime.now(UTC)

        # Score all predictions
        outcome = determine_outcome(
            home_goals, away_goals, went_to_penalties,
            penalties_home, penalties_away,
        )
        predictions = await session.execute(
            select(Prediction).where(Prediction.match_id == match_id)
        )
        scored = 0
        for p in predictions.scalars():
            brier = multiclass_brier(p.p_home, p.p_draw, p.p_away, outcome)
            exact_pts = exact_score_points(
                p.pred_home_goals, p.pred_away_goals, home_goals, away_goals
            )
            await session.execute(
                insert(Score).values(
                    agent_id=p.agent_id,
                    match_id=match_id,
                    brier=brier,
                    exact_score_pts=exact_pts,
                    outcome=outcome,
                ).on_conflict_do_update(
                    index_elements=["agent_id", "match_id"],
                    set_={"brier": brier, "exact_score_pts": exact_pts, "outcome": outcome},
                )
            )
            scored += 1

        # Audit log
        await session.execute(
            insert(AuditLog).values(
                actor_type="admin",
                actor_id=actor_human_id,
                action="resolve_match",
                target_type="match",
                target_id=str(match_id),
                metadata={
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "went_to_penalties": went_to_penalties,
                    "predictions_scored": scored,
                },
            )
        )

    return ResolutionResult(
        match_id=match_id,
        outcome=outcome,
        predictions_scored=scored,
    )
```

The override function is similar but:
- Doesn't require `status != 'finished'`
- Deletes existing `scores` rows for the match first
- Logs both old and new values in audit metadata

## 6. Background helper: backup result fetcher

To make Kevin's life easier, an APScheduler job runs every 15 minutes during match days:

```python
# app/jobs/poll_results.py

async def poll_finished_matches():
    """
    For every match that started >2h ago and is still not 'finished',
    try to fetch a result from football-data.org or Wikipedia.
    If found, post to a private 'admin pending' table for one-click confirmation.
    DOES NOT auto-resolve.
    """
```

The result lands in a `pending_resolutions` table (separate from `matches` to avoid contaminating real data):

```sql
CREATE TABLE pending_resolutions (
    match_id        INT PRIMARY KEY REFERENCES matches(id),
    suggested_home  SMALLINT NOT NULL,
    suggested_away  SMALLINT NOT NULL,
    went_to_penalties BOOLEAN,
    penalties_home  SMALLINT,
    penalties_away  SMALLINT,
    source          TEXT NOT NULL,  -- 'football-data.org', 'wikipedia'
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

In the admin dashboard, pending matches with a suggested result show:

```
[ ⚡ Resolve as 2-1 (suggested by football-data.org) ]   [ Edit ]
```

One click confirms and runs the resolve flow. This makes most resolutions a single tap.

## 7. Audit log read

The audit log is the safety net. Every admin action writes a row. Schema in `03-data-model.md` § audit_log.

Actions logged from admin:
- `resolve_match`
- `override_match`
- `update_match` (any PATCH)
- `cancel_match`
- `retire_agent`
- `force_refresh_leaderboard`

Every entry includes the admin's `human_id` so we know who did what.

## 8. Acceptance criteria

A junior admin (someone other than Kevin) should be able to, on a phone, in under 30 seconds:

1. Open `/admin`
2. See a list of pending matches
3. Tap the most recent finished one
4. Enter the score
5. Confirm
6. See the toast "Scored 47 predictions"

If any of those steps takes longer or has more friction, the panel needs work.
