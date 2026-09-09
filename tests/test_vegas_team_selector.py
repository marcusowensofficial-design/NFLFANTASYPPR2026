import pytest
from src.db.session import get_db
from src.api.analysis_routes import get_vegas_environments
from src.db.models import RosterEntryModel, LeagueModel
from sqlalchemy import select


@pytest.mark.anyio
async def test_vegas_environments_respects_team_id():
    """Verify that get_vegas_environments returns only players belonging to the requested team."""
    db = next(get_db())

    league = db.execute(select(LeagueModel)).scalars().first()
    if not league:
        pytest.skip("No league found in DB")

    user_team_id = league.user_team_id or 6

    # 1. Fetch for user_team_id (e.g. 6)
    res_user = await get_vegas_environments(team_id=user_team_id, week=1, season=2026, db=db)
    user_roster_entries = db.execute(
        select(RosterEntryModel).where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.team_id == user_team_id,
        )
    ).scalars().all()
    user_pids = {e.player_id for e in user_roster_entries}

    for g in res_user.games:
        for p in g.user_roster_exposure:
            assert p.player_id in user_pids, f"Player {p.full_name} ({p.player_id}) should be on team {user_team_id}"

    # 2. Fetch for team_id = 1
    res_team1 = await get_vegas_environments(team_id=1, week=1, season=2026, db=db)
    team1_entries = db.execute(
        select(RosterEntryModel).where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.team_id == 1,
        )
    ).scalars().all()
    team1_pids = {e.player_id for e in team1_entries}

    for g in res_team1.games:
        for p in g.user_roster_exposure:
            assert p.player_id in team1_pids, f"Player {p.full_name} ({p.player_id}) should be on team 1"

    # 3. Fetch with team_id=None -> defaults to user_team_id
    res_default = await get_vegas_environments(team_id=None, week=1, season=2026, db=db)
    default_pids = {
        p.player_id
        for g in res_default.games
        for p in g.user_roster_exposure
    }
    user_found_pids = {
        p.player_id
        for g in res_user.games
        for p in g.user_roster_exposure
    }
    assert default_pids == user_found_pids, "Omitted team_id should cleanly default to user team"


@pytest.mark.anyio
async def test_vegas_slate_props_endpoint():
    """Verify that get_vegas_slate_props returns synthesized sportsbook player props for active players."""
    from src.api.analysis_routes import get_vegas_slate_props
    db = next(get_db())

    props = await get_vegas_slate_props(week=1, season=2026, limit=10, db=db)
    assert isinstance(props, list)
    if props:
        first = props[0]
        assert first.player_name
        assert first.position in ["QB", "RB", "WR", "TE"]
        assert first.implied_ppr_points >= 0.0
        assert first.anytime_td_prob >= 0.0
        assert first.vegas_grade in ["VERY_ELITE", "ELITE", "GOOD", "AVERAGE", "FADE", "VERY_BAD"]
