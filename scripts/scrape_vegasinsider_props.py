#!/usr/bin/env python3
"""Dedicated VegasInsider NFL Player Props Scraper.

Scrapes live consensus lines and sportsbook odds from:
https://www.vegasinsider.com/nfl/odds/player-props/
Across:
- Table 1: Touchdown Odds
- Table 2: Receiving Yards Odds
- Table 3: Passing Yards Odds
- Table 4: Rushing Yards Odds
Outputs structured JSON to data/player_props_live.json and prints summary table.
"""

import sys
import re
import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

URL = "https://www.vegasinsider.com/nfl/odds/player-props/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

def clean_prop_cell(cell_str: str) -> dict:
    """Parses cells like 'o90.5-113+' or '-250+' or '+140'."""
    s = cell_str.strip().replace('+', '').replace('', '')
    if not s:
        return {}
    
    # Check for over/under lines: e.g. o76.5-115
    match_ou = re.match(r'([ou])([0-9.]+)([-+][0-9]+)?', s, re.I)
    if match_ou:
        direction = match_ou.group(1).upper()
        line = float(match_ou.group(2))
        odds = match_ou.group(3) or "-110"
        return {"type": "line", "direction": direction, "line": line, "odds": odds}
    
    # Check for moneyline/odds: e.g. -250 or +150
    match_ml = re.match(r'([-+][0-9]+)', s)
    if match_ml:
        return {"type": "odds", "odds": match_ml.group(1)}
        
    return {"raw": s}

def scrape_vegasinsider_props(save_json: bool = True):
    print(f"[*] Fetching live NFL player props from {URL}...")
    try:
        r = requests.get(URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"Error connecting to VegasInsider: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")
    print(f"[+] Found {len(tables)} prop tables on page.")

    category_names = ["Touchdowns", "Receiving Yards", "Passing Yards", "Rushing Yards"]
    prop_data = {
        "source": URL,
        "categories": {}
    }

    all_player_records = {}

    for idx, table in enumerate(tables):
        cat = category_names[idx] if idx < len(category_names) else f"Category_{idx+1}"
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        
        # Determine sportsbooks from headers
        books = [h for h in headers if h and h not in ["Time", "See All", ""]]
        
        rows = table.find_all("tr")
        records = []
        for tr in rows[1:]: # skip header row
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if not cells or len(cells) < 2:
                continue
            player_name = cells[0].strip()
            if not player_name or player_name in ["Time", "See All", ""]:
                continue
                
            book_odds = {}
            lines_list = []
            for b_idx, book in enumerate(books):
                c_idx = b_idx + 1
                if c_idx < len(cells):
                    raw_val = cells[c_idx].strip()
                    parsed = clean_prop_cell(raw_val)
                    if parsed:
                        book_odds[book] = parsed
                        if parsed.get("type") == "line":
                            lines_list.append(parsed["line"])

            consensus_line = round(float(np.median(lines_list)), 1) if lines_list else None
            record = {
                "player": player_name,
                "category": cat,
                "consensus_line": consensus_line,
                "books": book_odds
            }
            records.append(record)
            
            # Aggregate by player
            if player_name not in all_player_records:
                all_player_records[player_name] = {}
            all_player_records[player_name][cat] = {
                "consensus_line": consensus_line,
                "books": book_odds
            }

        prop_data["categories"][cat] = records
        print(f"    - {cat}: Extracted {len(records)} player lines")

    prop_data["players"] = all_player_records

    if save_json:
        out_path = Path("data/player_props_live.json")
        with open(out_path, "w") as f:
            json.dump(prop_data, f, indent=2)
        print(f"[+] Saved structured props to {out_path}")

    return prop_data

if __name__ == "__main__":
    import numpy as np
    data = scrape_vegasinsider_props()
    if data:
        print("\n" + "="*80)
        print("SAMPLE EXTRACTED PROPS SUMMARY")
        print("="*80)
        for cat, recs in data["categories"].items():
            print(f"\n--- {cat.upper()} (Top 5) ---")
            for r in recs[:5]:
                consensus = f"Consensus: {r['consensus_line']}" if r['consensus_line'] is not None else ""
                print(f"  {r['player']:<22} | {consensus}")
        print("="*80)
