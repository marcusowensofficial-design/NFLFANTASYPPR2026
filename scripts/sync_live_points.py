"""Script to calculate and persist live starter points into team Points For (PF) and Points Against (PA).

Can be executed manually or automatically scheduled to ensure all teams reflect live in-progress scoring.
"""

import sys
from collections import defaultdict
from sqlalchemy import select

# Ensure project root is in sys.path
sys.path.insert(0, ".")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.db.models import LeagueModel, MatchupModel, PlayerModel, RosterEntryModel, TeamModel
from src.db.session import SessionLocal


def sync_live_points_for_league():
    db = SessionLocal()
    try:
        league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
        if not league:
            print("❌ No active league found in database.")
            return

        print(f"🏈 Syncing Live Points for '{league.name}' (Season {league.season}, Week {league.current_week})...\n")

        # 1. Fetch all roster entries joined with player stats for the league
        roster_rows = db.execute(
            select(RosterEntryModel, PlayerModel)
            .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
            .where(RosterEntryModel.league_id == league.id)
        ).all()

        live_starters_actual: dict[int, float] = defaultdict(float)
        live_starters_effective: dict[int, float] = defaultdict(float)
        starters_count_by_team: dict[int, int] = defaultdict(int)

        for entry, player in roster_rows:
            if entry.is_starter:
                starters_count_by_team[entry.team_id] += 1
                act = float(player.actual_points or 0.0)
                proj = float(player.projected_points or 0.0)
                is_locked = bool(entry.lineup_locked)
                live_starters_actual[entry.team_id] += act
                eff = act if (act > 0 or is_locked) else proj
                live_starters_effective[entry.team_id] += eff

        # 2. Resolve current week matchups for Opponents (Points Against)
        current_matchups = db.execute(
            select(MatchupModel).where(
                MatchupModel.league_id == league.id,
                MatchupModel.week == league.current_week,
            )
        ).scalars().all()

        team_opponent_map: dict[int, int] = {}
        for m in current_matchups:
            team_opponent_map[m.home_team_id] = m.away_team_id
            team_opponent_map[m.away_team_id] = m.home_team_id

        # 3. Update all teams in the database
        teams = db.execute(
            select(TeamModel).where(TeamModel.league_id == league.id).order_by(TeamModel.id)
        ).scalars().all()

        updated_teams = []
        for t in teams:
            live_pf = round(live_starters_actual.get(t.id, 0.0), 2)
            opp_id = team_opponent_map.get(t.id)
            live_pa = round(live_starters_actual.get(opp_id, 0.0) if opp_id else 0.0, 2)
            live_proj = round(live_starters_effective.get(t.id, 0.0), 2)

            # Update DB columns
            t.points_for = live_pf
            t.points_against = live_pa

            updated_teams.append({
                "id": t.id,
                "name": t.name,
                "abbrev": t.abbrev,
                "record": t.record_str,
                "is_user": t.is_user_team,
                "pf": live_pf,
                "pa": live_pa,
                "proj": live_proj,
            })

        db.commit()

        # Sort standings: Win Pct (all 0-0 in week 1) then Points For (descending)
        updated_teams.sort(key=lambda x: x["pf"], reverse=True)

        print(f"{'Rank':<5} {'Team Name':<28} {'Record':<8} {'Points For (PF)':<16} {'Points Against (PA)':<20} {'Live Projected'}")
        print("-" * 95)
        for idx, tm in enumerate(updated_teams):
            rank = idx + 1
            user_tag = " ★ (My Team)" if tm["is_user"] else ""
            team_display = f"{tm['name']}{user_tag}"
            print(f"#{rank:<4} {team_display:<28} {tm['record']:<8} {tm['pf']:<5.1f} pts (LIVE)   {tm['pa']:<5.1f} pts (Opp)        {tm['proj']:.1f} pts")

        print("-" * 95)
        print("✅ Successfully updated all teams' Points For and Points Against in SQLite database!\n")

    except Exception as e:
        db.rollback()
        print(f"❌ Error syncing live points: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sync_live_points_for_league()
