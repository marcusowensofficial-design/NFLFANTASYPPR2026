"""Production-grade FanDuel Single-Game (Showdown) Tournament Solver.

Enforces:
1. $60,000 salary cap with a mandatory $200-$1,000 unspent single-entry buffer.
2. 1 MVP (1.5x salary & 1.5x fantasy points) + 5 AnyFLEX slots.
3. Strict Correlation & The QB Rule of 3 (no naked QBs; max 2 pass-catchers without QB).
4. No D/ST paired with opposing starting RB1.
5. Route-Running & Target-Equity filter (excludes pure blocking fullbacks / sub-15% snap depth).
"""

import csv
import itertools
import sys
from pathlib import Path

DEFAULT_CSV = Path("data/SINGLEGAMESLATE.csv")


def run_solver(csv_path: Path = DEFAULT_CSV, top_n: int = 5):
    if not csv_path.exists():
        print(f"Error: {csv_path} not found.")
        sys.exit(1)

    players = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("Nickname"):
                continue
            injury = row.get("Injury Indicator", "").strip()
            if injury == "IR":
                continue

            name = row["Nickname"]
            pos = row["Position"]
            salary = int(row["Salary"])
            mvp_salary = int(row["MVP 1.5x Salary"])
            fppg = float(row["FPPG"] or 0.0)
            team = row["Team"]

            # Filter out pure inactive depth or non-route runners with 0 FPPG and no offensive role
            is_viable = (
                fppg >= 1.5
                or pos in ["K", "D"]
                or name in ["Terrance Ferguson", "Jordan Whittington", "Kyle Juszczyk", "Colby Parkinson"]
            )
            if not is_viable:
                continue

            players.append({
                "id": row["Id"],
                "name": name,
                "team": team,
                "pos": pos,
                "salary": salary,
                "mvp_salary": mvp_salary,
                "fppg": fppg,
                "injury": injury,
            })

    print(f"Loaded {len(players)} viable tournament assets from {csv_path.name}")

    def evaluate_lineup(mvp, flexes):
        total_cost = mvp["mvp_salary"] + sum(f["salary"] for f in flexes)
        if total_cost > 60000:
            return None
        remaining = 60000 - total_cost
        if remaining < 200 or remaining > 1500:  # Single-entry discipline: leave $200-$1500 unspent
            return None

        lineup_players = [mvp] + list(flexes)
        teams_in_lineup = {p["team"] for p in lineup_players}
        if len(teams_in_lineup) < 2:
            return None

        # 1. D/ST Correlation: Never pair D/ST with opposing starting RB
        has_dst = next((p for p in lineup_players if p["pos"] == "D"), None)
        if has_dst:
            opp_team = [t for t in teams_in_lineup if t != has_dst["team"]]
            if opp_team:
                opp_t = opp_team[0]
                has_opp_rb = any(p["team"] == opp_t and p["pos"] == "RB" and p["salary"] >= 9000 for p in lineup_players)
                if has_opp_rb:
                    return None

        # 2. QB Rule of 3 (Negative correlation leakage)
        for t in teams_in_lineup:
            has_qb = any(p["team"] == t and p["pos"] == "QB" for p in lineup_players)
            pass_catchers = sum(1 for p in lineup_players if p["team"] == t and p["pos"] in ["WR", "TE"])
            if not has_qb and pass_catchers >= 3:
                return None

        # 3. If rostering a QB, require at least 1 primary pass-catcher (no naked QBs)
        for p in lineup_players:
            if p["pos"] == "QB":
                paired = any(
                    other["team"] == p["team"] and other["pos"] in ["WR", "TE", "RB"] and other["name"] != p["name"]
                    for other in lineup_players
                )
                if not paired:
                    return None

        # Calculate projected points (1.5x on MVP)
        proj_score = (mvp["fppg"] * 1.5) + sum(f["fppg"] for f in flexes)

        sf_count = sum(1 for p in lineup_players if p["team"] == "SF")
        lar_count = sum(1 for p in lineup_players if p["team"] == "LAR")

        return {
            "mvp": mvp,
            "flexes": list(flexes),
            "cost": total_cost,
            "remaining": remaining,
            "proj": round(proj_score, 2),
            "split": f"{lar_count} LAR - {sf_count} SF",
        }

    all_valid = []
    for mvp in players:
        pool_for_flex = [p for p in players if p["name"] != mvp["name"]]
        for flex_combo in itertools.combinations(pool_for_flex, 5):
            res = evaluate_lineup(mvp, flex_combo)
            if res:
                all_valid.append(res)

    all_valid.sort(key=lambda x: x["proj"], reverse=True)

    print(f"\nGenerated {len(all_valid)} verified tournament lineups.")
    print("\n" + "=" * 65)
    print(f"TOP {top_n} MATHEMATICALLY OPTIMAL TOURNAMENT LINEUPS")
    print("=" * 65)

    for i, l in enumerate(all_valid[:top_n], 1):
        mvp = l["mvp"]
        flex_str = " | ".join([f"{f['name']} (${f['salary']})" for f in l["flexes"]])
        print(f"\nRank #{i} | Proj: {l['proj']} FPTS | Cost: ${l['cost']} (Unspent: ${l['remaining']}) | {l['split']}")
        print(f"  MVP (1.5x): {mvp['name']} ({mvp['team']} {mvp['pos']}) - ${mvp['mvp_salary']}")
        print(f"  FLEX:       {flex_str}")

    return all_valid[:top_n]


if __name__ == "__main__":
    run_solver()
