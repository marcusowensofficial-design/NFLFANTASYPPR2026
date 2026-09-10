"""10,000-Trial Monte Carlo GPP Tournament Simulator for FanDuel Single Game."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_player_pool():
    csv_path = Path("data/SINGLEGAMESLATE.csv")
    if not csv_path.exists():
        print(f"Error: {csv_path} not found.")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    # Filter viable player pool (ignore null or 0 FPPG depth chart ghosts)
    # Set default projections based on FPPG and Vegas totals
    viable = df[df["FPPG"].notnull() & (df["FPPG"] > 0)].copy()
    
    # Fill in Ferguson if FPPG is low due to small sample
    if "Terrance Ferguson" in viable["Nickname"].values:
        idx = viable[viable["Nickname"] == "Terrance Ferguson"].index[0]
        viable.loc[idx, "FPPG"] = max(viable.loc[idx, "FPPG"], 5.2)

    return viable


def run_monte_carlo_sim(n_sims: int = 10000):
    print("=" * 72)
    print(f"[*] RUNNING {n_sims:,} MONTE CARLO TOURNAMENT SIMULATIONS (SF @ LAR)")
    print("    Incorporating Positional Variance & Stacking Covariances...")
    print("=" * 72 + "\n")


    df = load_player_pool()
    n_players = len(df)
    names = df["Nickname"].values
    salaries = df["Salary"].values
    teams = df["Team"].values
    positions = df["Position"].values
    base_proj = df["FPPG"].values

    name_to_idx = {name: i for i, name in enumerate(names)}

    # Build Correlation Matrix
    # Base correlation identity
    corr = np.eye(n_players)

    def set_corr(p1, p2, val):
        if p1 in name_to_idx and p2 in name_to_idx:
            i, j = name_to_idx[p1], name_to_idx[p2]
            corr[i, j] = val
            corr[j, i] = val

    # Rams Air Stacking Correlations
    set_corr("Matthew Stafford", "Davante Adams", 0.45)
    set_corr("Matthew Stafford", "Puka Nacua", 0.45)
    set_corr("Matthew Stafford", "Terrance Ferguson", 0.28)
    set_corr("Matthew Stafford", "Harrison Mevis", 0.18)
    set_corr("Matthew Stafford", "Kyren Williams", -0.15)  # Rushing TD cannibalization
    set_corr("Davante Adams", "Puka Nacua", 0.10)

    # 49ers Passing Correlations
    set_corr("Brock Purdy", "Mike Evans", 0.40)
    set_corr("Brock Purdy", "Deebo Samuel Sr.", 0.38)
    set_corr("Brock Purdy", "George Kittle", 0.25)
    set_corr("Brock Purdy", "Christian McCaffrey", 0.32)
    set_corr("Brock Purdy", "Eddy Pineiro", 0.15)

    # Game Pace / Shootout Bring-Back Correlation
    set_corr("Matthew Stafford", "Brock Purdy", 0.22)
    set_corr("Matthew Stafford", "Christian McCaffrey", 0.18)
    set_corr("Brock Purdy", "Puka Nacua", 0.16)

    # Ensure covariance matrix is positive semi-definite
    # Positional Standard Deviations (% of mean projection)
    std_dev_pct = []
    for pos in positions:
        if pos == "QB":
            std_dev_pct.append(0.28)
        elif pos == "RB":
            std_dev_pct.append(0.38)
        elif pos == "WR":
            std_dev_pct.append(0.48)
        elif pos == "TE":
            std_dev_pct.append(0.52)
        elif pos == "K":
            std_dev_pct.append(0.35)
        else:
            std_dev_pct.append(0.40)

    stds = base_proj * np.array(std_dev_pct)
    cov = np.outer(stds, stds) * corr

    # Make cov PSD
    min_eig = np.min(np.real(np.linalg.eigvals(cov)))
    if min_eig < 0:
        cov -= 1.1 * min_eig * np.eye(n_players)

    # Generate multivariate normal draws
    np.random.seed(42)
    sim_scores = np.random.multivariate_normal(base_proj, cov, size=n_sims)
    sim_scores = np.clip(sim_scores, 0.0, None)  # Floor at 0.0

    # Track optimal MVPs and Winning Lineups
    mvp_counter = Counter()
    winning_lineups = Counter()
    
    # Specific tracking for Our Lineup:
    # Adams (MVP) + CMC + Nacua + Stafford + Mevis + Ferguson
    our_players = ["Davante Adams", "Christian McCaffrey", "Puka Nacua", "Matthew Stafford", "Harrison Mevis", "Terrance Ferguson"]
    our_indices = [name_to_idx[p] for p in our_players if p in name_to_idx]
    adams_idx = name_to_idx["Davante Adams"]

    our_lineup_scores = []
    top_winning_scores = []

    # Fast Greedy/Knapsack evaluation across simulations
    for t in range(n_sims):
        scores_t = sim_scores[t]
        
        # Calculate our lineup score in trial t:
        if len(our_indices) == 6:
            # Adams at MVP (1.5x) + 5 other at 1.0x
            our_score = scores_t[adams_idx] * 1.5 + sum(scores_t[i] for i in our_indices if i != adams_idx)
            our_lineup_scores.append(our_score)

        # Find the optimal 6-man lineup in this trial:
        # Candidate MVPs: Top 8 projected/salary players
        best_lineup_score = 0.0
        best_mvp = None
        best_lineup_tuple = None

        candidate_mvp_indices = [
            i for i in range(n_players) if salaries[i] >= 6000 or positions[i] in ["WR", "RB", "QB"]
        ]

        for mvp_i in candidate_mvp_indices:
            mvp_cost = int(salaries[mvp_i] * 1.5)
            rem_cap = 60000 - mvp_cost
            if rem_cap < 5000:
                continue

            # Eligible flex candidates (excluding mvp_i)
            flex_cands = [i for i in range(n_players) if i != mvp_i]
            # Sort flex candidates by points-per-dollar in this simulation
            flex_cands = sorted(flex_cands, key=lambda i: scores_t[i] / max(salaries[i], 1000), reverse=True)

            # Pick top 5 feasible flex within cap and single-game team rule
            current_flex = []
            cur_cap = rem_cap
            
            # Use top sorted candidates that fit
            for cand_i in flex_cands:
                if len(current_flex) == 5:
                    break
                if salaries[cand_i] <= cur_cap - (4 - len(current_flex)) * 1000:
                    current_flex.append(cand_i)
                    cur_cap -= salaries[cand_i]

            if len(current_flex) == 5:
                # Check team constraint (at least 1 from each team)
                all_teams = {teams[mvp_i]} | {teams[i] for i in current_flex}
                if len(all_teams) >= 2:
                    total_score = scores_t[mvp_i] * 1.5 + sum(scores_t[i] for i in current_flex)
                    if total_score > best_lineup_score:
                        best_lineup_score = total_score
                        best_mvp = names[mvp_i]
                        roster_names = tuple(sorted([names[mvp_i] + " [MVP]"] + [names[i] for i in current_flex]))
                        best_lineup_tuple = roster_names

        if best_mvp:
            mvp_counter[best_mvp] += 1
            winning_lineups[best_lineup_tuple] += 1
            top_winning_scores.append(best_lineup_score)

    our_lineup_scores = np.array(our_lineup_scores)
    top_winning_scores = np.array(top_winning_scores)

    # Print Results
    print("[*] 1. OPTIMAL MVP FREQUENCY (% OF SIMULATIONS WON AT MVP)")
    print("-" * 60)
    for name, count in mvp_counter.most_common(8):
        pct = (count / n_sims) * 100
        bar = "#" * int(pct / 2)
        print(f"{name:<22} | {pct:>5.1f}% | {bar}")

    print("\n[*] 2. TOP 3 MOST FREQUENT WINNING LINEUP CONSTRUCTIONS")
    print("-" * 60)
    for rank, (lineup, count) in enumerate(winning_lineups.most_common(3), 1):
        pct = (count / n_sims) * 100
        print(f"Rank #{rank} (Won {count:,} sims - {pct:.1f}%):")
        for p in lineup:
            print(f"   - {p}")
        print()

    print("[*] 3. OUR LOCKED LINEUP PERFORMANCE AUDIT")
    print("-" * 60)
    print("Lineup: Adams [MVP] + CMC + Nacua + Stafford + Mevis + Ferguson ($59,300)")
    print(f"   - Median Simulation Score:      {np.median(our_lineup_scores):.1f} pts")
    print(f"   - 90th Percentile Ceiling:     {np.percentile(our_lineup_scores, 90):.1f} pts")
    print(f"   - 95th Percentile Ceiling:     {np.percentile(our_lineup_scores, 95):.1f} pts")
    print(f"   - 99th Percentile Ceiling:     {np.percentile(our_lineup_scores, 99):.1f} pts")
    print(f"   - Max Simulated Ceiling:       {np.max(our_lineup_scores):.1f} pts")
    
    # Calculate GPP Win/Cash Probability
    top_1_pct_threshold = np.percentile(top_winning_scores, 90)
    cash_rate = (np.sum(our_lineup_scores >= top_1_pct_threshold) / n_sims) * 100
    print(f"   - High-Stakes GPP Ceiling Rate: {cash_rate:.1f}% (Chance of hitting 90th+ percentile winning score)")
    print("=" * 72 + "\n")



if __name__ == "__main__":
    run_monte_carlo_sim(n_sims=10000)
