import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import asyncio
from src.adapters.weather.client import weather_client
from src.services.matchup.wrcb_matrix import wrcb_analyzer
from src.adapters.nfl.injuries_client import nfl_injuries_client

async def run_audit():
    print("="*75)
    print("1. WEATHER AUDIT FOR LINEUP VENUES:")
    print("="*75)
    teams_to_check = [("CIN", "Paycor Stadium (TB@CIN)"), ("PHI", "Lincoln Financial Field (WAS@PHI)"), ("TEN", "Nissan Stadium (NYJ@TEN)"), ("LAC", "SoFi Stadium (ARI@LAC)"), ("LV", "Allegiant Stadium (MIA@LV)")]
    for t, venue in teams_to_check:
        try:
            w = await weather_client.get_stadium_weather(t)
            print(f"  {venue:<35} | Dome: {w.is_dome} | Temp: {w.temperature_f:.1f}°F | Wind: {w.wind_speed_mph:.1f} mph (Gusts: {w.wind_gusts_mph:.1f}) | Precip: {w.precipitation_in:.2f} in | Score: {w.weather_score} | Concern: {w.weather_concern}")
        except Exception as e:
            print(f"  {venue:<35} | Weather check error: {e}")

    print("\n" + "="*75)
    print("2. WR-CB SHADOW COVERAGE & MATCHUP ADVANTAGE AUDIT:")
    print("="*75)
    wr_checks = [
        (85701, "Ja'Marr Chase", "CIN", "TB", 21.0),
        (138800, "Ladd McConkey", "LAC", "ARI", 15.0),
        (89000, "Michael Pittman Jr.", "PIT", "ATL", 13.5),
    ]
    for pid, name, team, opp, proj in wr_checks:
        try:
            analysis = wrcb_analyzer.analyze_matchup(
                player_id=pid,
                full_name=name,
                pro_team=team,
                opponent=opp,
                projected_points=proj
            )
            print(f"  {name:<20} ({team} vs {opp}) | Primary CB: {analysis.primary_cb.name} (Grade: {analysis.primary_cb.coverage_grade}) | Shadow: {analysis.is_shadow_projected} | Advantage: {analysis.advantage_score:+.1f}% ({analysis.advantage_rating}) | Takeaway: {analysis.tactical_takeaway}")
        except Exception as e:
            print(f"  {name} WR-CB check error: {e}")

    print("\n" + "="*75)
    print("3. INJURY FORENSIC AUDIT:")
    print("="*75)
    try:
        report = await nfl_injuries_client.fetch_injuries()
        print(f"  Total live injury records tracked: {len(report)}")
        targets = ["Ja'Marr Chase", "Ashton Jeanty", "Zay Flowers", "Tee Higgins", "Saquon Barkley", "Omarion Hampton", "Cade Otton", "Ladd McConkey", "Joe Burrow"]
        for t in targets:
            found = [r for r in report.values() if t.lower() in r.name.lower()]
            if found:
                for r in found:
                    print(f"  [INJURY] {r.name} ({r.team} - {r.position}) | Status: {r.status} | Practice: {r.practice_status} | Headline: {r.headline} | Notes: {r.notes}")
            else:
                print(f"  [CLEAN] {t}: No active injury report / expected full go.")
    except Exception as e:
        print(f"  Injury client error: {e}")

if __name__ == '__main__':
    asyncio.run(run_audit())
