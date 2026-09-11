"""Test Sunday Week 1 Main Slate data loading and optimization."""

import asyncio
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dfs.loader import dfs_loader
from src.dfs.optimizer import dfs_optimizer
from src.dfs.analyzer import dfs_analyzer


async def main():
    csv_path = "data/FanDuel-NFL-2026 MDT-09 MDT-13 MDT-133104-players-list.csv"
    print(f"Loading Sunday Main Slate from {csv_path}...")

    df_slate = await dfs_loader.load_slate(csv_path=csv_path, projection_source="MODEL")
    print(f"Successfully loaded and enriched {len(df_slate)} players!")
    print(f"Columns available: {list(df_slate.columns)[:15]}")

    print("\n--- TOP GAME STACKS ---")
    stacks = dfs_analyzer.get_top_game_stacks(df_slate, top_n=5)
    for s in stacks:
        print(f"Game: {s.get('game')} (O/U: {s.get('total')}) | QB: {s.get('qb')} | Stack Score: {s.get('stack_score')}")

    print("\n--- TOP VALUE PLAYS BY POSITION ---")
    for pos in ["QB", "RB", "WR", "TE", "D"]:
        top_pos = dfs_analyzer.get_top_by_position(df_slate, position=pos, top_n=3)
        print(f"\nTop {pos}s:")
        for _, row in top_pos.iterrows():
            print(f"  - {row['name']} ({row['team']}) - ${row['salary']:,} | Proj: {row['proj']:.1f} | Value: {row.get('value', 0):.2f}")

    print("\n--- RUNNING CLASSIC 9-SLOT GPP OPTIMIZER ---")
    sol = dfs_optimizer.optimize(
        df_slate,
        mode="SINGLE_ENTRY_GPP",
        max_salary=59800,  # leaves buffer
        min_salary=59000,
    )

    if sol:
        print(f"\nOptimal 9-Slot Roster (Total Salary: ${sol['total_salary']:,} | Proj: {sol['total_projected_points']:.1f} pts | Ceiling: {sol['total_ceiling_points']:.1f} pts):")
        for p in sol["roster"]:
            print(f"  [{p['slot']:<10}] {p['name']:<22} | {p['team']:<4} | ${p['salary']:,} | Proj: {p['proj']:.1f} | Ceiling: {p['ceiling']:.1f}")
    else:
        print("Optimizer returned None.")


if __name__ == "__main__":
    asyncio.run(main())
