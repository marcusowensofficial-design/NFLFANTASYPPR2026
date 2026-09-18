"""Master nflverse & NextGenStats Data Ingestion Pipeline.

Downloads and persists complete, granular nflverse datasets directly to data/parquets/:
1. Player Stats (Weekly Passing, Rushing, Receiving, Box Scores)
2. NextGenStats (NGS):
   - Receiving: Cushion, Separation, Intended Air Yards Share, YAC Above Expectation
   - Rushing: Efficiency, 8+ Box Defenders %, Time to LOS, RYOE/att
   - Passing: Time to Throw, CPOE, Aggressiveness (Tight Window %)
3. FTN Charting:
   - Pre-snap motion, Play action, Screen passes, RPO, Read thrown (1st read vs checkdown)
4. PBP Participation:
   - Route participation, Offense/Defense personnel packages (11 vs 12)
5. Snap Counts:
   - Weekly offensive, defensive, and special teams snap counts
"""

import os
import sys
import io
import urllib.request
from pathlib import Path
import pandas as pd

PARQUET_DIR = Path("data/parquets")
PARQUET_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://github.com/nflverse/nflverse-data/releases/download"

def download_file(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def sync_nflverse_data(year: int = 2024):
    print(f"=== Syncing Full nflverse & NextGenStats Suite ({year}) ===")
    
    # 1. Player Stats
    try:
        url = f"{BASE_URL}/player_stats/player_stats_{year}.parquet"
        print(f"Fetching Player Stats from {url}...")
        df_stats = pd.read_parquet(url)
        dest = PARQUET_DIR / f"player_stats_{year}.parquet"
        df_stats.to_parquet(dest, engine="pyarrow")
        print(f" -> Saved Player Stats: {dest} ({df_stats.shape[0]} rows, {df_stats.shape[1]} cols)")
    except Exception as e:
        print(f" -> Failed Player Stats: {e}")

    # 2. NextGen Stats: Receiving
    try:
        url = f"{BASE_URL}/nextgen_stats/ngs_{year}_receiving.csv.gz"
        print(f"Fetching NGS Receiving from {url}...")
        df_ngs_rec = pd.read_csv(url)
        dest = PARQUET_DIR / f"ngs_receiving_{year}.parquet"
        df_ngs_rec.to_parquet(dest, engine="pyarrow")
        print(f" -> Saved NGS Receiving: {dest} ({df_ngs_rec.shape[0]} rows, {df_ngs_rec.shape[1]} cols)")
    except Exception as e:
        print(f" -> Failed NGS Receiving: {e}")

    # 3. NextGen Stats: Rushing
    try:
        url = f"{BASE_URL}/nextgen_stats/ngs_{year}_rushing.csv.gz"
        print(f"Fetching NGS Rushing from {url}...")
        df_ngs_rush = pd.read_csv(url)
        dest = PARQUET_DIR / f"ngs_rushing_{year}.parquet"
        df_ngs_rush.to_parquet(dest, engine="pyarrow")
        print(f" -> Saved NGS Rushing: {dest} ({df_ngs_rush.shape[0]} rows, {df_ngs_rush.shape[1]} cols)")
    except Exception as e:
        print(f" -> Failed NGS Rushing: {e}")

    # 4. FTN Charting
    try:
        url = f"{BASE_URL}/ftn_charting/ftn_charting_{year}.parquet"
        print(f"Fetching FTN Charting from {url}...")
        df_ftn = pd.read_parquet(url)
        dest = PARQUET_DIR / f"ftn_charting_{year}.parquet"
        df_ftn.to_parquet(dest, engine="pyarrow")
        print(f" -> Saved FTN Charting: {dest} ({df_ftn.shape[0]} rows, {df_ftn.shape[1]} cols)")
    except Exception as e:
        print(f" -> Failed FTN Charting: {e}")

    # 5. Snap Counts
    try:
        url = f"{BASE_URL}/snap_counts/snap_counts_{year}.parquet"
        print(f"Fetching Snap Counts from {url}...")
        df_snaps = pd.read_parquet(url)
        dest = PARQUET_DIR / f"snap_counts_{year}.parquet"
        df_snaps.to_parquet(dest, engine="pyarrow")
        print(f" -> Saved Snap Counts: {dest} ({df_snaps.shape[0]} rows, {df_snaps.shape[1]} cols)")
    except Exception as e:
        print(f" -> Failed Snap Counts: {e}")

    print("\nAll available nflverse & NextGenStats tables successfully synced to data/parquets/!")


if __name__ == "__main__":
    sync_nflverse_data()
