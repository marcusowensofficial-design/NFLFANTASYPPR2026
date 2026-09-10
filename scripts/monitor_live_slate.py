import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.adapters.nfl.live_game_client import LiveGameTracker, KICKOFF_EVENT_ID, DEFAULT_SHOWDOWN_ROSTER



import os
import time

async def run_live_tracker(poll_once: bool = True):
    tracker = LiveGameTracker()
    
    while True:
        # Clear screen on each refresh in watch mode
        if not poll_once:
            os.system("cls" if os.name == "nt" else "clear")

        print(f"\n=======================================================")
        print(f"[*] LIVE FANDUEL SHOWDOWN TRACKER - 2026 SEASON OPENER")
        print(f"    Auto-refreshing every 25s | Press Ctrl+C to exit")
        print(f"=======================================================\n")

        status = await tracker.fetch_live_game(event_id=KICKOFF_EVENT_ID, roster=DEFAULT_SHOWDOWN_ROSTER)
        
        print(f"Matchup: {status.game_name} ({status.detail})")
        print(f"Score:   {status.away_team} {status.away_score} - {status.home_team} {status.home_score}")
        if status.down_distance_text:
            print(f"Drive:   {status.possession_team} possession | {status.down_distance_text}")
        print(f"Status:  Game State: {status.state.upper()}\n")

        print(f"{'SLOT':<6} | {'PLAYER':<22} | {'TEAM':<4} | {'STATLINE':<28} | {'FPTS (1.5x)':<10}")
        print("-" * 76)
        
        for p in status.roster_scores:
            stat_parts = []
            if p.pass_yards > 0 or p.pass_tds > 0 or p.interceptions > 0:
                stat_parts.append(f"{int(p.pass_yards)} pass yds, {p.pass_tds} TD, {p.interceptions} INT")
            if p.carries > 0 or p.rush_yards > 0 or p.rush_tds > 0:
                stat_parts.append(f"{p.carries} car, {int(p.rush_yards)} rush yds, {p.rush_tds} TD")
            if p.receptions > 0 or p.rec_yards > 0 or p.rec_tds > 0:
                stat_parts.append(f"{p.receptions} rec, {int(p.rec_yards)} yds, {p.rec_tds} TD")
            if p.fg_made > 0 or p.pat_made > 0:
                stat_parts.append(f"{p.fg_made} FG, {p.pat_made} XP")
            
            stat_str = ", ".join(stat_parts) if stat_parts else "0 stats (pregame)"
            mvp_str = f"[{p.slot}]" if not p.is_mvp else f"*[{p.slot}]"
            print(f"{mvp_str:<6} | {p.name:<22} | {p.team:<4} | {stat_str:<28} | {p.multiplier_fpts:>6.2f} pts")

        print("-" * 76)
        print(f"TOTAL LINEUP SCORE: {status.total_lineup_fpts:.2f} PTS\n")

        if poll_once:
            break

        print("[*] Next update in 25 seconds...")
        await asyncio.sleep(25)


if __name__ == "__main__":
    is_watch = "--watch" in sys.argv
    try:
        asyncio.run(run_live_tracker(poll_once=not is_watch))
    except KeyboardInterrupt:
        print("\n[*] Live tracker stopped.")

