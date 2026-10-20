#!/usr/bin/env python3
"""Generates 150 Unique, Bulletproofed FanDuel Single-Game (Showdown) Lineups for SEA @ DEN.

Tactical Value Rebalancing (Post-Expert Consensus & Injury Wire):
1. Tory Horton Demoted to True Dart Flyer:
   - Hard capped at max 18 of 150 lineups (12.0% exposure), acknowledging his 17% route share.
2. AJ Barner & Troy Franklin Elevated to Core Value:
   - AJ Barner ($4,800) elevated to ~40-50% exposure (exploiting Talanoa Hufanga OUT over the middle).
   - Troy Franklin ($3,800) elevated to ~25-35% exposure (consistent 45%+ route participation with Bo Nix).
3. Patrick Surtain II OUT Capitalized:
   - JSN remains the primary 80-84% alpha anchor with Surtain sidelined.
4. Zach Charbonnet OUT Capitalized:
   - Emanuel Wilson remains bellcow RB anchor (35-40% total, 18% MVP).
5. Courtland Sutton Red-Zone Protection:
   - Retained at 20-25% total exposure (8 MVPs).
6. Strict FanDuel Format Integrity:
   - Exactly 1 MVP (1.5x salary/points) + 5 AnyFLEX (1.0x salary/points).
   - Total salary <= $60,000.
   - At least 1 player from each team.
   - Exactly 150 non-duplicate lineups.
   - Zero garbage can players (filtered strictly to the verified 20-player rotation, min salary $3,400).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import json
import random
import numpy as np
import pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds


def build_150_pro_rebalanced_lineups():
    slate_file = PROJECT_ROOT / "data" / "seavsdensinglegameslate10-15-26.csv"
    if not slate_file.exists():
        print(f"Error: {slate_file} not found.")
        sys.exit(1)

    df_raw = pd.read_csv(slate_file)

    # 1. Strictly Filter to the Verified 20-Player Pool (Zero Garbage Can Players)
    verified_pool = [
        "Jaxon Smith-Njigba", "Bo Nix", "Sam Darnold", "Emanuel Wilson",
        "Jaylen Waddle", "J.K. Dobbins", "Courtland Sutton", "RJ Harvey",
        "Cooper Kupp", "Rashid Shaheed", "Denver Broncos", "Seattle Seahawks",
        "Jason Myers", "Wil Lutz", "Evan Engram", "George Holani",
        "AJ Barner", "Marvin Mims Jr.", "Troy Franklin", "Tory Horton"
    ]

    df = df_raw[df_raw["Nickname"].isin(verified_pool)].copy().reset_index(drop=True)
    n = len(df)
    print(f"Verified Player Pool: {n} players (All verified starters & primary contributors)")

    # Standardize columns
    df["player_id"] = df["Id"]
    df["name"] = df["Nickname"]
    df["team"] = df["Team"]
    df["pos"] = df["Position"]
    df["salary"] = df["Salary"].astype(int)
    df["mvp_salary"] = (df["salary"] * 1.5).astype(int)
    df["fppg"] = pd.to_numeric(df["FPPG"], errors="coerce").fillna(5.0)

    # Base baseline ceiling projections
    is_skill = df["pos"].isin(["WR", "RB", "TE", "QB"])
    df["base_ceiling"] = df["fppg"] * 1.35 + (is_skill.astype(float) * 3.5)
    df["base_median"] = df["fppg"]

    # Red-Team Calibrated MVP Plans across 5 Scripts (Total = 150)
    script_configs = [
        {
            "id": "SEA_FAVORED",
            "desc": "Seattle Favored Grind (4-2 SEA / Dual-QB)",
            "mvp_plan": [
                ("Jaxon Smith-Njigba", 16),
                ("Sam Darnold", 10),
                ("Emanuel Wilson", 6),
                ("Rashid Shaheed", 3),
            ]
        },
        {
            "id": "SEA_BLOWOUT",
            "desc": "Seattle Blowout Onslaught (5-1 / 4-2 Heavy SEA)",
            "mvp_plan": [
                ("Emanuel Wilson", 14),
                ("Jaxon Smith-Njigba", 9),
                ("Sam Darnold", 4),
                ("Seattle Seahawks", 5),
                ("Cooper Kupp", 3),
            ]
        },
        {
            "id": "DEN_UPSET",
            "desc": "Denver Dominant Upset (4-2 DEN / 5-1 DEN)",
            "mvp_plan": [
                ("Bo Nix", 16),
                ("J.K. Dobbins", 8),
                ("Courtland Sutton", 4),
                ("Jaylen Waddle", 4),
                ("Denver Broncos", 3),
            ]
        },
        {
            "id": "ZERO_QB",
            "desc": "Zero-QB Ground & Turnover Monopoly",
            "mvp_plan": [
                ("Emanuel Wilson", 7),
                ("Jaxon Smith-Njigba", 6),
                ("J.K. Dobbins", 5),
                ("Courtland Sutton", 2),
                ("Jason Myers", 3),
                ("Wil Lutz", 2),
            ]
        },
        {
            "id": "SHOOTOUT",
            "desc": "High-Total Aerial Shootout (Dual-QB)",
            "mvp_plan": [
                ("Jaxon Smith-Njigba", 6),
                ("Bo Nix", 5),
                ("Sam Darnold", 4),
                ("Jaylen Waddle", 3),
                ("Courtland Sutton", 2),
            ]
        },
    ]

    generated_lineups = []
    seen_rosters = set()
    existing_indices_sets = []
    lineup_counter = 1

    # Portfolio-wide exposure counters
    player_total_counts = {p: 0 for p in verified_pool}
    max_jsn_cap = 120       # Exactly 80.0% max
    max_horton_cap = 18    # Hard cap at 12.0% (demoting from 36.7% due to 17% route share)

    def solve_single(
        script_id: str,
        target_mvp: str | None,
        exclude_players: list[str] | None = None,
        force_players: list[str] | None = None,
        max_salary: int = 59800,
        min_salary: int = 56500
    ):
        proj = df["base_median"].copy().values
        ceil = df["base_ceiling"].copy().values

        # Gaussian perturbation for combinatoric diversity
        noise = np.random.normal(0.0, 1.25, size=n)
        pts = ceil * 0.70 + proj * 0.30 + noise

        # Boost Courtland Sutton
        sutton_idx = df.index[df["name"] == "Courtland Sutton"].tolist()[0]
        pts[sutton_idx] *= 1.25

        # Boost AJ Barner ($4,800) and Troy Franklin ($3,800) as preferred value plays
        barner_idx = df.index[df["name"] == "AJ Barner"].tolist()[0]
        franklin_idx = df.index[df["name"] == "Troy Franklin"].tolist()[0]
        pts[barner_idx] *= 1.30
        pts[franklin_idx] *= 1.22

        # Script-specific weighting
        if script_id in ["SEA_FAVORED", "SEA_BLOWOUT"]:
            sea_mask = df["team"] == "SEA"
            pts[sea_mask] *= np.random.uniform(1.10, 1.25)
            if script_id == "SEA_BLOWOUT":
                pts[df["name"] == "Seattle Seahawks"] *= 1.30

        elif script_id == "DEN_UPSET":
            den_mask = df["team"] == "DEN"
            pts[den_mask] *= np.random.uniform(1.15, 1.30)
            pts[df["name"] == "Denver Broncos"] *= 1.25
            pts[sutton_idx] *= 1.15

        elif script_id == "ZERO_QB":
            qb_mask = df["pos"] == "QB"
            pts[qb_mask] = -9999.0  # Ban QBs
            rb_k_mask = df["pos"].isin(["RB", "K", "D"])
            pts[rb_k_mask] *= np.random.uniform(1.10, 1.25)

        elif script_id == "SHOOTOUT":
            qb_pass_mask = df["pos"].isin(["QB", "WR", "TE"])
            pts[qb_pass_mask] *= np.random.uniform(1.15, 1.30)

        # Objective vector
        c = np.zeros(2 * n)
        c[0:n] = -1.5 * pts
        c[n:2*n] = -1.0 * pts

        integrality = np.ones(2 * n)
        bounds = Bounds(0, 1)

        A_rows = []
        b_l = []
        b_u = []

        # 1. Exactly 1 MVP slot
        row_mvp = np.zeros(2 * n)
        row_mvp[0:n] = 1.0
        A_rows.append(row_mvp)
        b_l.append(1.0)
        b_u.append(1.0)

        # Target MVP constraint if specified
        if target_mvp:
            mvp_target_indices = df.index[df["name"] == target_mvp].tolist()
            if mvp_target_indices:
                t_idx = mvp_target_indices[0]
                row_t_mvp = np.zeros(2 * n)
                row_t_mvp[t_idx] = 1.0
                A_rows.append(row_t_mvp)
                b_l.append(1.0)
                b_u.append(1.0)

        # 2. Exactly 5 AnyFLEX slots
        row_flex = np.zeros(2 * n)
        row_flex[n:2*n] = 1.0
        A_rows.append(row_flex)
        b_l.append(5.0)
        b_u.append(5.0)

        # 3. Each player selected at most once total (MVP + FLEX <= 1)
        for i in range(n):
            row_p = np.zeros(2 * n)
            row_p[i] = 1.0
            row_p[n + i] = 1.0
            A_rows.append(row_p)
            b_l.append(0.0)
            b_u.append(1.0)

        # Forced inclusions
        if force_players:
            for fp in force_players:
                fp_indices = df.index[df["name"] == fp].tolist()
                if fp_indices:
                    f_idx = fp_indices[0]
                    row_force = np.zeros(2 * n)
                    row_force[f_idx] = 1.0
                    row_force[n + f_idx] = 1.0
                    A_rows.append(row_force)
                    b_l.append(1.0)
                    b_u.append(1.0)

        # Exclusions (e.g. JSN cap or Horton cap)
        if exclude_players:
            for ep in exclude_players:
                ep_indices = df.index[df["name"] == ep].tolist()
                if ep_indices:
                    e_idx = ep_indices[0]
                    row_excl = np.zeros(2 * n)
                    row_excl[e_idx] = 1.0
                    row_excl[n + e_idx] = 1.0
                    A_rows.append(row_excl)
                    b_l.append(0.0)
                    b_u.append(0.0)

        # 4. Salary Cap constraint
        row_sal = np.zeros(2 * n)
        row_sal[0:n] = df["mvp_salary"].values
        row_sal[n:2*n] = df["salary"].values
        A_rows.append(row_sal)
        b_l.append(float(min_salary))
        b_u.append(float(max_salary))

        # 5. Team diversity: At least 1 player from SEA and at least 1 from DEN
        sea_indices = df.index[df["team"] == "SEA"].tolist()
        den_indices = df.index[df["team"] == "DEN"].tolist()

        row_sea = np.zeros(2 * n)
        for idx in sea_indices:
            row_sea[idx] = 1.0
            row_sea[n + idx] = 1.0
        A_rows.append(row_sea)
        b_l.append(1.0)
        b_u.append(5.0)

        row_den = np.zeros(2 * n)
        for idx in den_indices:
            row_den[idx] = 1.0
            row_den[n + idx] = 1.0
        A_rows.append(row_den)
        b_l.append(1.0)
        b_u.append(5.0)

        # 6. Script specific team count constraints
        if script_id == "SEA_BLOWOUT":
            row_sea_blow = np.zeros(2 * n)
            for idx in sea_indices:
                row_sea_blow[idx] = 1.0
                row_sea_blow[n + idx] = 1.0
            A_rows.append(row_sea_blow)
            b_l.append(4.0)
            b_u.append(5.0)

        elif script_id == "DEN_UPSET":
            row_den_upset = np.zeros(2 * n)
            for idx in den_indices:
                row_den_upset[idx] = 1.0
                row_den_upset[n + idx] = 1.0
            A_rows.append(row_den_upset)
            b_l.append(4.0)
            b_u.append(5.0)

        elif script_id == "SHOOTOUT":
            darnold_idx = df.index[df["name"] == "Sam Darnold"].tolist()[0]
            nix_idx = df.index[df["name"] == "Bo Nix"].tolist()[0]

            row_darnold = np.zeros(2 * n)
            row_darnold[darnold_idx] = 1.0
            row_darnold[n + darnold_idx] = 1.0
            A_rows.append(row_darnold)
            b_l.append(1.0)
            b_u.append(1.0)

            row_nix = np.zeros(2 * n)
            row_nix[nix_idx] = 1.0
            row_nix[n + nix_idx] = 1.0
            A_rows.append(row_nix)
            b_l.append(1.0)
            b_u.append(1.0)

        # 7. Correlation Integrity (D/ST Anti-Cannibalization)
        den_dst_idx = df.index[df["name"] == "Denver Broncos"].tolist()
        sea_rb1_idx = df.index[df["name"] == "Emanuel Wilson"].tolist()
        if den_dst_idx and sea_rb1_idx:
            d_idx = den_dst_idx[0]
            rb_idx = sea_rb1_idx[0]
            row_anti1 = np.zeros(2 * n)
            row_anti1[d_idx] = 1.0
            row_anti1[n + d_idx] = 1.0
            row_anti1[rb_idx] = 1.0
            row_anti1[n + rb_idx] = 1.0
            A_rows.append(row_anti1)
            b_l.append(0.0)
            b_u.append(1.0)

        sea_dst_idx = df.index[df["name"] == "Seattle Seahawks"].tolist()
        den_rb1_idx = df.index[df["name"] == "J.K. Dobbins"].tolist()
        if sea_dst_idx and den_rb1_idx:
            d_idx = sea_dst_idx[0]
            rb_idx = den_rb1_idx[0]
            row_anti2 = np.zeros(2 * n)
            row_anti2[d_idx] = 1.0
            row_anti2[n + d_idx] = 1.0
            row_anti2[rb_idx] = 1.0
            row_anti2[n + rb_idx] = 1.0
            A_rows.append(row_anti2)
            b_l.append(0.0)
            b_u.append(1.0)

        # 8. Prevent duplicate lineups
        for prev_roster_indices in existing_indices_sets:
            row_dup = np.zeros(2 * n)
            for p_idx in prev_roster_indices:
                row_dup[p_idx] = 1.0
                row_dup[n + p_idx] = 1.0
            A_rows.append(row_dup)
            b_l.append(0.0)
            b_u.append(5.0)

        A = np.vstack(A_rows)
        constraints = LinearConstraint(A, b_l, b_u)

        res = milp(c=c, integrality=integrality, bounds=bounds, constraints=constraints)
        if not res.success:
            return None

        sol_x = res.x
        mvp_idx = np.where(sol_x[0:n] > 0.5)[0][0]
        flex_indices = np.where(sol_x[n:2*n] > 0.5)[0].tolist()

        return mvp_idx, flex_indices

    print("\nExecuting Expert-Calibrated 150-Lineup Synthesis...")

    for sc in script_configs:
        script_id = sc["id"]
        script_desc = sc["desc"]
        print(f"\nProcessing [{script_desc}]...")

        for target_mvp, quota in sc["mvp_plan"]:
            success_count = 0
            attempts = 0

            while success_count < quota and attempts < 400:
                attempts += 1
                
                # Check portfolio-wide caps
                current_excludes = []
                if player_total_counts["Jaxon Smith-Njigba"] >= max_jsn_cap:
                    if target_mvp != "Jaxon Smith-Njigba":
                        current_excludes.append("Jaxon Smith-Njigba")

                if player_total_counts["Tory Horton"] >= max_horton_cap:
                    current_excludes.append("Tory Horton")

                # Force Courtland Sutton into a fraction of Denver Upset, Zero-QB, and Shootout lineups
                current_forces = []
                if script_id in ["DEN_UPSET", "SHOOTOUT", "ZERO_QB"] and player_total_counts["Courtland Sutton"] < 25:
                    if random.random() < 0.35 and target_mvp != "Courtland Sutton":
                        current_forces.append("Courtland Sutton")

                # Promote AJ Barner and Troy Franklin into a fraction of lineups
                if script_id in ["SEA_FAVORED", "SEA_BLOWOUT", "SHOOTOUT"] and player_total_counts["AJ Barner"] < 65:
                    if random.random() < 0.40 and target_mvp != "AJ Barner":
                        current_forces.append("AJ Barner")

                if script_id in ["DEN_UPSET", "SHOOTOUT"] and player_total_counts["Troy Franklin"] < 45:
                    if random.random() < 0.35 and target_mvp != "Troy Franklin":
                        current_forces.append("Troy Franklin")

                # Buffer variation ($200 to $3,500 unspent)
                if random.random() < 0.70:
                    max_sal = random.randint(57400, 58800)
                    min_sal = 56200
                else:
                    max_sal = random.randint(58800, 59800)
                    min_sal = 56800

                sol = solve_single(
                    script_id,
                    target_mvp=target_mvp,
                    exclude_players=current_excludes,
                    force_players=current_forces,
                    max_salary=max_sal,
                    min_salary=min_sal
                )
                if sol is None:
                    continue

                mvp_idx, flex_indices = sol
                roster_indices = tuple(sorted([mvp_idx] + flex_indices))

                if roster_indices in seen_rosters:
                    continue

                seen_rosters.add(roster_indices)
                existing_indices_sets.append(set(roster_indices))

                mvp_row = df.iloc[mvp_idx]
                flex_rows = [df.iloc[idx] for idx in flex_indices]

                # Update portfolio tracker
                player_total_counts[mvp_row["name"]] += 1
                for f in flex_rows:
                    player_total_counts[f["name"]] += 1

                total_salary = int(mvp_row["mvp_salary"] + sum(f["salary"] for f in flex_rows))
                unspent = 60000 - total_salary
                proj_pts = round(float(mvp_row["fppg"] * 1.5 + sum(f["fppg"] for f in flex_rows)), 2)
                ceil_pts = round(float(mvp_row["base_ceiling"] * 1.5 + sum(f["base_ceiling"] for f in flex_rows)), 2)

                team_counts = {}
                team_counts[mvp_row["team"]] = 1
                for f in flex_rows:
                    team_counts[f["team"]] = team_counts.get(f["team"], 0) + 1

                lineup_data = {
                    "lineup_num": lineup_counter,
                    "script_id": script_id,
                    "script_name": script_desc,
                    "total_salary": total_salary,
                    "unspent_buffer": unspent,
                    "projected_pts": proj_pts,
                    "ceiling_pts": ceil_pts,
                    "team_counts": f"{team_counts.get('SEA', 0)} SEA / {team_counts.get('DEN', 0)} DEN",
                    "mvp_name": mvp_row["name"],
                    "mvp_id": mvp_row["player_id"],
                    "mvp_cost": int(mvp_row["mvp_salary"]),
                    "mvp_pos": mvp_row["pos"],
                    "mvp_team": mvp_row["team"],
                    "flex_names": [f["name"] for f in flex_rows],
                    "flex_ids": [f["player_id"] for f in flex_rows],
                    "flex_teams": [f["team"] for f in flex_rows],
                    "flex_costs": [int(f["salary"]) for f in flex_rows],
                    "flex_positions": [f["pos"] for f in flex_rows],
                }

                generated_lineups.append(lineup_data)
                lineup_counter += 1
                success_count += 1

            print(f"  -> Generated {success_count}/{quota} lineups with MVP: {target_mvp}")

    assert len(generated_lineups) == 150, f"Expected 150 lineups, generated {len(generated_lineups)}"
    print(f"\nSUCCESS: Generated {len(generated_lineups)} unique, pro-calibrated lineups!")

    # 3. Export Output Files
    upload_rows = []
    ids_only_rows = []
    readable_rows = []

    for item in generated_lineups:
        mvp_str = f"{item['mvp_id']}:{item['mvp_name']}"
        flex_strs = [f"{fid}:{fname}" for fid, fname in zip(item["flex_ids"], item["flex_names"])]

        upload_rows.append({
            "MVP": mvp_str,
            "AnyFLEX": flex_strs[0],
            "AnyFLEX.1": flex_strs[1],
            "AnyFLEX.2": flex_strs[2],
            "AnyFLEX.3": flex_strs[3],
            "AnyFLEX.4": flex_strs[4],
        })

        ids_only_rows.append({
            "MVP": item["mvp_id"],
            "AnyFLEX": item["flex_ids"][0],
            "AnyFLEX.1": item["flex_ids"][1],
            "AnyFLEX.2": item["flex_ids"][2],
            "AnyFLEX.3": item["flex_ids"][3],
            "AnyFLEX.4": item["flex_ids"][4],
        })

        readable_rows.append({
            "Lineup": item["lineup_num"],
            "Script": item["script_name"],
            "Salary Spent": item["total_salary"],
            "Unspent Buffer": item["unspent_buffer"],
            "Projected FP": item["projected_pts"],
            "Ceiling FP": item["ceiling_pts"],
            "Build Ratio": item["team_counts"],
            "MVP": f"{item['mvp_name']} ({item['mvp_team']} {item['mvp_pos']}) - ${item['mvp_cost']:,}",
            "FLEX 1": f"{item['flex_names'][0]} ({item['flex_teams'][0]}) - ${item['flex_costs'][0]:,}",
            "FLEX 2": f"{item['flex_names'][1]} ({item['flex_teams'][1]}) - ${item['flex_costs'][1]:,}",
            "FLEX 3": f"{item['flex_names'][2]} ({item['flex_teams'][2]}) - ${item['flex_costs'][2]:,}",
            "FLEX 4": f"{item['flex_names'][3]} ({item['flex_teams'][3]}) - ${item['flex_costs'][3]:,}",
            "FLEX 5": f"{item['flex_names'][4]} ({item['flex_teams'][4]}) - ${item['flex_costs'][4]:,}",
        })

    out_upload_path = PROJECT_ROOT / "data" / "fanduel_sea_den_150_upload.csv"
    out_ids_path = PROJECT_ROOT / "data" / "fanduel_sea_den_150_ids.csv"
    out_readable_path = PROJECT_ROOT / "data" / "fanduel_sea_den_150_readable.csv"

    with open(out_upload_path, "w", encoding="utf-8") as f:
        f.write("MVP,AnyFLEX,AnyFLEX,AnyFLEX,AnyFLEX,AnyFLEX\n")
        for r in upload_rows:
            f.write(f'"{r["MVP"]}","{r["AnyFLEX"]}","{r["AnyFLEX.1"]}","{r["AnyFLEX.2"]}","{r["AnyFLEX.3"]}","{r["AnyFLEX.4"]}"\n')

    with open(out_ids_path, "w", encoding="utf-8") as f:
        f.write("MVP,AnyFLEX,AnyFLEX,AnyFLEX,AnyFLEX,AnyFLEX\n")
        for r in ids_only_rows:
            f.write(f'"{r["MVP"]}","{r["AnyFLEX"]}","{r["AnyFLEX.1"]}","{r["AnyFLEX.2"]}","{r["AnyFLEX.3"]}","{r["AnyFLEX.4"]}"\n')

    df_readable = pd.DataFrame(readable_rows)
    df_readable.to_csv(out_readable_path, index=False)

    # 4. Generate Final Exposure Distribution
    mvp_counts = {}
    flex_counts = {}
    for item in generated_lineups:
        m = item["mvp_name"]
        mvp_counts[m] = mvp_counts.get(m, 0) + 1
        for fx in item["flex_names"]:
            flex_counts[fx] = flex_counts.get(fx, 0) + 1

    exposure_data = []
    for p in verified_pool:
        m_c = mvp_counts.get(p, 0)
        f_c = flex_counts.get(p, 0)
        tot_c = m_c + f_c
        exposure_data.append({
            "Player": p,
            "MVP Count": m_c,
            "MVP %": f"{(m_c / 150) * 100:.1f}%",
            "FLEX Count": f_c,
            "FLEX %": f"{(f_c / 150) * 100:.1f}%",
            "Total Count": tot_c,
            "Total %": f"{(tot_c / 150) * 100:.1f}%",
        })

    df_exposures = pd.DataFrame(exposure_data).sort_values(by="Total Count", ascending=False).reset_index(drop=True)
    out_exp_path = PROJECT_ROOT / "data" / "fanduel_sea_den_150_exposures.csv"
    df_exposures.to_csv(out_exp_path, index=False)

    print(f"\nFiles Saved to /data:")
    print(f"1. [Upload Ready]:   {out_upload_path}")
    print(f"2. [IDs Only]:       {out_ids_path}")
    print(f"3. [Readable Audit]: {out_readable_path}")
    print(f"4. [Exposures]:      {out_exp_path}")

    print("\n" + "=" * 90)
    print("FINAL EXPERT-ALIGNED 150-LINEUP PORTFOLIO EXPOSURE DISTRIBUTION")
    print("=" * 90)
    print(df_exposures.to_string(index=False))
    print("=" * 90)

    salaries = [item["total_salary"] for item in generated_lineups]
    print("\nPORTFOLIO AUDIT:")
    print(f"- Total Lineups:         150 / 150")
    print(f"- 100% Unique Check:     {len(seen_rosters)} / 150 (Zero duplicate lineups)")
    print(f"- Min Salary Spent:      ${min(salaries):,} (Buffer: ${60000 - min(salaries):,})")
    print(f"- Max Salary Spent:      ${max(salaries):,} (Buffer: ${60000 - max(salaries):,})")
    print(f"- Mean Salary Spent:     ${int(np.mean(salaries)):,} (Average Buffer: ${int(60000 - np.mean(salaries)):,})")
    print(f"- AJ Barner Exposure:    {df_exposures[df_exposures['Player'] == 'AJ Barner']['Total %'].values[0]} (Elevated core value play)")
    print(f"- Troy Franklin Exp:     {df_exposures[df_exposures['Player'] == 'Troy Franklin']['Total %'].values[0]} (Elevated core value play)")
    print(f"- Tory Horton Exposure:  {df_exposures[df_exposures['Player'] == 'Tory Horton']['Total %'].values[0]} (Demoted to GPP flyer)")
    print(f"- Courtland Sutton:      {df_exposures[df_exposures['Player'] == 'Courtland Sutton']['Total %'].values[0]} (Red-zone protection)")
    print(f"- JSN Total Exposure:    {df_exposures[df_exposures['Player'] == 'Jaxon Smith-Njigba']['Total %'].values[0]} (Surtain-less ceiling)")
    print(f"- Garbage Can Filter:    PASSED (Zero players outside verified 20-man starter pool)")


if __name__ == "__main__":
    build_150_pro_rebalanced_lineups()
