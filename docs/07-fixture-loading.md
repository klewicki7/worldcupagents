# 07 — Fixture loading

## 1. Why this is a separate doc

The 48 teams and 104 matches are static data that we need correctly loaded into the DB before anything else works. This doc is the single source of truth for that data and the script that loads it. If FIFA changes a venue or kickoff time, we update the YAML and re-run the loader. We do NOT use Alembic for this — fixture data is not schema.

## 2. Data sources

- **Groups** (sorteo 5 December 2025): confirmed, hardcoded below.
- **Group-stage match calendar**: published on `fifa.com/worldcup/canadamexicousa2026` and mirrored on Wikipedia. We parse the Wikipedia table because it's stable HTML.
- **Knockout matchups**: structurally known (e.g. "winner Group A plays third-placed B/C/D/E" in R32 match #N), but the actual teams are TBD until group stage ends. We store placeholders.
- **Knockout dates and venues**: published with the fixture.

## 3. The 12 groups (confirmed from sorteo)

| Group | Teams |
|---|---|
| A | México, Sudáfrica, Corea del Sur, República Checa |
| B | Canadá, Suiza, Catar, Bosnia y Herzegovina |
| C | Brasil, Marruecos, Haití, Escocia |
| D | Estados Unidos, Paraguay, Australia, Turquía |
| E | Alemania, Ecuador, Costa de Marfil, Curazao |
| F | Países Bajos, Japón, Túnez, Suecia |
| G | Bélgica, Egipto, Irán, Nueva Zelanda |
| H | España, Uruguay, Arabia Saudita, Cabo Verde |
| I | Francia, Senegal, Noruega, Irak |
| J | Argentina, Argelia, Austria, Jordania |
| K | Portugal, Colombia, Uzbekistán, R.D. del Congo |
| L | Inglaterra, Croacia, Panamá, Ghana |

## 4. `data/teams.yaml`

```yaml
# 48 teams, IDs are stable forever. DO NOT REORDER.
- id: 1
  fifa_code: MEX
  name_en: Mexico
  name_es: México
  flag_emoji: "🇲🇽"
  group_letter: A
  confederation: CONCACAF
- id: 2
  fifa_code: RSA
  name_en: South Africa
  name_es: Sudáfrica
  flag_emoji: "🇿🇦"
  group_letter: A
  confederation: CAF
- id: 3
  fifa_code: KOR
  name_en: South Korea
  name_es: Corea del Sur
  flag_emoji: "🇰🇷"
  group_letter: A
  confederation: AFC
- id: 4
  fifa_code: CZE
  name_en: Czech Republic
  name_es: República Checa
  flag_emoji: "🇨🇿"
  group_letter: A
  confederation: UEFA

- id: 5
  fifa_code: CAN
  name_en: Canada
  name_es: Canadá
  flag_emoji: "🇨🇦"
  group_letter: B
  confederation: CONCACAF
- id: 6
  fifa_code: SUI
  name_en: Switzerland
  name_es: Suiza
  flag_emoji: "🇨🇭"
  group_letter: B
  confederation: UEFA
- id: 7
  fifa_code: QAT
  name_en: Qatar
  name_es: Catar
  flag_emoji: "🇶🇦"
  group_letter: B
  confederation: AFC
- id: 8
  fifa_code: BIH
  name_en: Bosnia and Herzegovina
  name_es: Bosnia y Herzegovina
  flag_emoji: "🇧🇦"
  group_letter: B
  confederation: UEFA

- id: 9
  fifa_code: BRA
  name_en: Brazil
  name_es: Brasil
  flag_emoji: "🇧🇷"
  group_letter: C
  confederation: CONMEBOL
- id: 10
  fifa_code: MAR
  name_en: Morocco
  name_es: Marruecos
  flag_emoji: "🇲🇦"
  group_letter: C
  confederation: CAF
- id: 11
  fifa_code: HAI
  name_en: Haiti
  name_es: Haití
  flag_emoji: "🇭🇹"
  group_letter: C
  confederation: CONCACAF
- id: 12
  fifa_code: SCO
  name_en: Scotland
  name_es: Escocia
  flag_emoji: "🏴󠁧󠁢󠁳󠁣󠁴󠁿"
  group_letter: C
  confederation: UEFA

- id: 13
  fifa_code: USA
  name_en: United States
  name_es: Estados Unidos
  flag_emoji: "🇺🇸"
  group_letter: D
  confederation: CONCACAF
- id: 14
  fifa_code: PAR
  name_en: Paraguay
  name_es: Paraguay
  flag_emoji: "🇵🇾"
  group_letter: D
  confederation: CONMEBOL
- id: 15
  fifa_code: AUS
  name_en: Australia
  name_es: Australia
  flag_emoji: "🇦🇺"
  group_letter: D
  confederation: AFC
- id: 16
  fifa_code: TUR
  name_en: Turkey
  name_es: Turquía
  flag_emoji: "🇹🇷"
  group_letter: D
  confederation: UEFA

- id: 17
  fifa_code: GER
  name_en: Germany
  name_es: Alemania
  flag_emoji: "🇩🇪"
  group_letter: E
  confederation: UEFA
- id: 18
  fifa_code: ECU
  name_en: Ecuador
  name_es: Ecuador
  flag_emoji: "🇪🇨"
  group_letter: E
  confederation: CONMEBOL
- id: 19
  fifa_code: CIV
  name_en: Ivory Coast
  name_es: Costa de Marfil
  flag_emoji: "🇨🇮"
  group_letter: E
  confederation: CAF
- id: 20
  fifa_code: CUW
  name_en: Curaçao
  name_es: Curazao
  flag_emoji: "🇨🇼"
  group_letter: E
  confederation: CONCACAF

- id: 21
  fifa_code: NED
  name_en: Netherlands
  name_es: Países Bajos
  flag_emoji: "🇳🇱"
  group_letter: F
  confederation: UEFA
- id: 22
  fifa_code: JPN
  name_en: Japan
  name_es: Japón
  flag_emoji: "🇯🇵"
  group_letter: F
  confederation: AFC
- id: 23
  fifa_code: TUN
  name_en: Tunisia
  name_es: Túnez
  flag_emoji: "🇹🇳"
  group_letter: F
  confederation: CAF
- id: 24
  fifa_code: SWE
  name_en: Sweden
  name_es: Suecia
  flag_emoji: "🇸🇪"
  group_letter: F
  confederation: UEFA

- id: 25
  fifa_code: BEL
  name_en: Belgium
  name_es: Bélgica
  flag_emoji: "🇧🇪"
  group_letter: G
  confederation: UEFA
- id: 26
  fifa_code: EGY
  name_en: Egypt
  name_es: Egipto
  flag_emoji: "🇪🇬"
  group_letter: G
  confederation: CAF
- id: 27
  fifa_code: IRN
  name_en: Iran
  name_es: Irán
  flag_emoji: "🇮🇷"
  group_letter: G
  confederation: AFC
- id: 28
  fifa_code: NZL
  name_en: New Zealand
  name_es: Nueva Zelanda
  flag_emoji: "🇳🇿"
  group_letter: G
  confederation: OFC

- id: 29
  fifa_code: ESP
  name_en: Spain
  name_es: España
  flag_emoji: "🇪🇸"
  group_letter: H
  confederation: UEFA
- id: 30
  fifa_code: URU
  name_en: Uruguay
  name_es: Uruguay
  flag_emoji: "🇺🇾"
  group_letter: H
  confederation: CONMEBOL
- id: 31
  fifa_code: KSA
  name_en: Saudi Arabia
  name_es: Arabia Saudita
  flag_emoji: "🇸🇦"
  group_letter: H
  confederation: AFC
- id: 32
  fifa_code: CPV
  name_en: Cape Verde
  name_es: Cabo Verde
  flag_emoji: "🇨🇻"
  group_letter: H
  confederation: CAF

- id: 33
  fifa_code: FRA
  name_en: France
  name_es: Francia
  flag_emoji: "🇫🇷"
  group_letter: I
  confederation: UEFA
- id: 34
  fifa_code: SEN
  name_en: Senegal
  name_es: Senegal
  flag_emoji: "🇸🇳"
  group_letter: I
  confederation: CAF
- id: 35
  fifa_code: NOR
  name_en: Norway
  name_es: Noruega
  flag_emoji: "🇳🇴"
  group_letter: I
  confederation: UEFA
- id: 36
  fifa_code: IRQ
  name_en: Iraq
  name_es: Irak
  flag_emoji: "🇮🇶"
  group_letter: I
  confederation: AFC

- id: 37
  fifa_code: ARG
  name_en: Argentina
  name_es: Argentina
  flag_emoji: "🇦🇷"
  group_letter: J
  confederation: CONMEBOL
- id: 38
  fifa_code: ALG
  name_en: Algeria
  name_es: Argelia
  flag_emoji: "🇩🇿"
  group_letter: J
  confederation: CAF
- id: 39
  fifa_code: AUT
  name_en: Austria
  name_es: Austria
  flag_emoji: "🇦🇹"
  group_letter: J
  confederation: UEFA
- id: 40
  fifa_code: JOR
  name_en: Jordan
  name_es: Jordania
  flag_emoji: "🇯🇴"
  group_letter: J
  confederation: AFC

- id: 41
  fifa_code: POR
  name_en: Portugal
  name_es: Portugal
  flag_emoji: "🇵🇹"
  group_letter: K
  confederation: UEFA
- id: 42
  fifa_code: COL
  name_en: Colombia
  name_es: Colombia
  flag_emoji: "🇨🇴"
  group_letter: K
  confederation: CONMEBOL
- id: 43
  fifa_code: UZB
  name_en: Uzbekistan
  name_es: Uzbekistán
  flag_emoji: "🇺🇿"
  group_letter: K
  confederation: AFC
- id: 44
  fifa_code: COD
  name_en: DR Congo
  name_es: R.D. del Congo
  flag_emoji: "🇨🇩"
  group_letter: K
  confederation: CAF

- id: 45
  fifa_code: ENG
  name_en: England
  name_es: Inglaterra
  flag_emoji: "🏴󠁧󠁢󠁥󠁮󠁧󠁿"
  group_letter: L
  confederation: UEFA
- id: 46
  fifa_code: CRO
  name_en: Croatia
  name_es: Croacia
  flag_emoji: "🇭🇷"
  group_letter: L
  confederation: UEFA
- id: 47
  fifa_code: PAN
  name_en: Panama
  name_es: Panamá
  flag_emoji: "🇵🇦"
  group_letter: L
  confederation: CONCACAF
- id: 48
  fifa_code: GHA
  name_en: Ghana
  name_es: Ghana
  flag_emoji: "🇬🇭"
  group_letter: L
  confederation: CAF
```

## 5. `data/matches.yaml`

We use the FIFA official match numbers (1–104). Group stage is 1–72, R32 is 73–88, R16 is 89–96, QF is 97–100, SF is 101–102, third-place is 103, final is 104.

Structure of an entry:

```yaml
- id: 1
  stage: group
  group_letter: A
  home_team_id: 1            # México
  away_team_id: 2            # Sudáfrica
  kickoff_at: "2026-06-11T19:00:00Z"
  venue_city: Mexico City
  venue_country: MX
```

For knockouts where teams aren't yet known:

```yaml
- id: 73
  stage: r32
  home_team_id: null
  away_team_id: null
  home_placeholder: "Winner Group A"
  away_placeholder: "Best 3rd C/D/E/F"
  kickoff_at: "2026-06-28T19:00:00Z"
  venue_city: Toronto
  venue_country: CA
```

**Note on the file**: at the time of writing this doc, the full 104-match calendar with venues and kickoff times has been announced. The complete YAML is generated by `scripts/build_matches_yaml.py` (see § 7), which Kevin runs once during initial setup. The script source pulls from Wikipedia's "Copa Mundial de Fútbol de 2026" article, which is kept up to date by the community.

## 6. `scripts/load_fixture.py`

```python
"""
Loads teams and matches from data/*.yaml into the database.

Usage:
    uv run python scripts/load_fixture.py --teams --matches
    uv run python scripts/load_fixture.py --matches-only
    uv run python scripts/load_fixture.py --dry-run

Idempotent: re-running with the same YAML produces no changes. Updates
that conflict (e.g. team's group changed) require --force.
"""

import asyncio
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db.session import async_session_factory
from app.db.models.team import Team
from app.db.models.match import Match


DATA_DIR = Path(__file__).parent.parent / "data"


async def load_teams(force: bool = False) -> None:
    raw = yaml.safe_load((DATA_DIR / "teams.yaml").read_text())
    async with async_session_factory() as session:
        stmt = insert(Team).values(raw)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "fifa_code": stmt.excluded.fifa_code,
                "name_en": stmt.excluded.name_en,
                "name_es": stmt.excluded.name_es,
                "flag_emoji": stmt.excluded.flag_emoji,
                "group_letter": stmt.excluded.group_letter,
                "confederation": stmt.excluded.confederation,
            } if force else {},
        )
        await session.execute(stmt)
        await session.commit()
        print(f"Loaded {len(raw)} teams.")


async def load_matches(force: bool = False) -> None:
    raw = yaml.safe_load((DATA_DIR / "matches.yaml").read_text())
    async with async_session_factory() as session:
        # ... similar upsert pattern, plus lock_at = kickoff_at - 1h
        # (also handled by DB trigger — explicit set here as safety)
        ...


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", action="store_true")
    parser.add_argument("--matches", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.all or args.teams:
        asyncio.run(load_teams(force=args.force))
    if args.all or args.matches:
        asyncio.run(load_matches(force=args.force))


if __name__ == "__main__":
    main()
```

## 7. `scripts/build_matches_yaml.py` (optional helper)

A one-shot scraper that pulls the match list from Wikipedia's article on the World Cup and emits `data/matches.yaml`. We don't run this in CI — it's a developer tool to bootstrap the YAML once. After that the file is hand-maintained.

The script:
1. Fetches `https://es.wikipedia.org/wiki/Copa_Mundial_de_Fútbol_de_2026`.
2. Parses the per-day tables (`wikitable` class) for each stage.
3. Resolves team names to `team_id` via `data/teams.yaml`.
4. For knockouts, fills `home_placeholder` / `away_placeholder` from the structural description ("Ganador Grupo A").
5. Writes `data/matches.yaml`.

**Important**: this script is fragile (it depends on Wikipedia HTML structure) and is NOT a fallback during the tournament. It's bootstrapping only.

## 8. Verification queries

After loading, run:

```sql
-- Should be 48
SELECT COUNT(*) FROM teams;

-- Should be 4 per group, all 12 groups
SELECT group_letter, COUNT(*) FROM teams GROUP BY group_letter ORDER BY group_letter;

-- Should be 104
SELECT COUNT(*) FROM matches;

-- 72 group, 16 r32, 8 r16, 4 qf, 2 sf, 1 third, 1 final
SELECT stage, COUNT(*) FROM matches GROUP BY stage;

-- Every group match has both team IDs set
SELECT COUNT(*) FROM matches WHERE stage = 'group' AND (home_team_id IS NULL OR away_team_id IS NULL);
-- Expected: 0

-- Earliest kickoff
SELECT MIN(kickoff_at) FROM matches;  -- 2026-06-11 around 19:00 UTC

-- Latest kickoff
SELECT MAX(kickoff_at) FROM matches;  -- 2026-07-19 around 19:00 UTC

-- All lock_at = kickoff_at - 1h
SELECT COUNT(*) FROM matches WHERE lock_at != kickoff_at - INTERVAL '1 hour';
-- Expected: 0
```

These are encoded as a pytest test in `tests/test_fixture_integrity.py` that runs against a freshly seeded DB.

## 9. When FIFA changes something

Scenarios and what to do:

| Change | Action |
|---|---|
| Kickoff time moved | Edit `data/matches.yaml`, rerun `load_fixture.py --matches --force`. Predictions stay; `lock_at` auto-updates. |
| Venue changed | Same — just edit and re-run. |
| Match cancelled | Use admin panel: `PATCH /api/v1/admin/matches/{id}` with `status: cancelled`. Don't delete the row. |
| Knockout team known | Use admin panel: `PATCH /api/v1/admin/matches/{id}` with `home_team_id`/`away_team_id`. |
| Team withdrew (extreme case) | Mark all their matches `cancelled`, communicate to users via banner. Predictions void. |

## 10. Backup / source of truth

`data/teams.yaml` and `data/matches.yaml` are checked into the repo. The DB rows can always be regenerated from these files. Conversely, if someone edits the DB directly (only admins can), they must mirror the change back to YAML — checked by a Sunday cron that dumps DB state, diffs against YAML, and posts to a private Slack channel if there's drift.
