import asyncio
from src.db.session import SessionLocal
from src.api.lineup_routes import get_optimal_lineup, push_lineup_to_espn, LineupPushRequest


async def main():
    db = SessionLocal()
    res = await get_optimal_lineup(team_id=6, db=db)
    print("Optimal Lineup for Team 6 (Marcus Owens):")
    print(f"  Total StartScore: {res.total_start_score}")
    print(f"  Differences count: {res.differences_count}")
    for s in res.starters:
        p = s.recommended_player
        rush = p.itemized_stats.get("rush_att", 0)
        tgts = p.itemized_stats.get("targets", 0)
        rec = p.itemized_stats.get("receptions", 0)
        pass_yd = p.itemized_stats.get("pass_yds", 0)
        pass_td = p.itemized_stats.get("pass_td", 0)
        sched = [(c["week"], c["opp"], "HOME" if c["is_home"] else "AWAY") for c in p.upcoming_schedule]
        stat_summary = f"carries={rush}, targets={tgts}, rec={rec}" if p.position in ("RB", "WR", "TE") else f"pass_yds={pass_yd}, pass_td={pass_td}"
        print(f"  [{s.slot_name}] {p.full_name} ({p.position} - {p.pro_team}) StartScore={p.start_score} | {stat_summary} | Sched={sched}")

    # Test pre-flight push preview
    req = LineupPushRequest(team_id=6, confirm=False)
    preview = await push_lineup_to_espn(req, db=db)
    print("\nPre-flight Lineup Push Preview:")
    print(f"  Moves count: {preview.moves_count}")
    print(f"  Can push to ESPN: {preview.can_push_to_espn}")
    print(f"  Status message: {preview.status_message}")
    for m in preview.moves:
        print(f"    Move {m.player_name}: {m.from_slot_name} -> {m.to_slot_name} (net delta: {m.net_gain:+.2f} pts)")

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
