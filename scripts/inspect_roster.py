import sys
sys.path.insert(0, ".")
from src.db.session import SessionLocal
from src.db.models import RosterEntryModel, PlayerModel
from sqlalchemy import select

db = SessionLocal()
entries = db.execute(
    select(RosterEntryModel, PlayerModel)
    .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
    .where(RosterEntryModel.league_id == 1841917737, RosterEntryModel.team_id == 6)
).all()

print(f"Total roster players on Team 6: {len(entries)}")
for re, p in entries[:3]:
    stats = p.projected_stats or {}
    print(f"\n--- {p.full_name} ({p.position} - {p.pro_team}) ---")
    print(f"Projected Points: {p.projected_points}")
    print(f"Itemized Stats: {stats}")
