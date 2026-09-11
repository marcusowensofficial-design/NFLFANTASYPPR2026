# NFL Fantasy & DFS Workspace Rules

## Core Operational Directives

1. **Persistent Analytical Memory:**
   * Treat all research, mathematical modeling, and strategic game theory developed in this workspace as persistent institutional knowledge.
   * Whenever addressing DFS or season-long fantasy questions, automatically apply the established frameworks without requiring re-explanation.

2. **FanDuel Single Game (Showdown) Strategy Standards:**
   * **Format Engine:** Always operate on the updated **6-slot roster** (1 MVP + 5 AnyFLEX) with a **$60,000 salary cap**.
   * **1.5x MVP Pricing Rule & Strategic Regimes:** Factor in that placing a player in the MVP slot costs **1.5x their base salary**, requiring true mathematical trade-off analysis between **"Multiplier Equity"** and **"FLEX Cap Relief"**:
     * *Alpha Outlier Slate:* When a player has an elite separated ceiling (e.g. JSN 30% target share), pay up at MVP and use injury vacancies to subsidize the roster.
     * *Compressed Slate:* In low-total, committee games, pay down at MVP ($9k–$11k) to upgrade to an all-starter FLEX and eliminate low-floor punts.
   * **Official Scoring Nuance:** FanDuel awards **4.0 pts per passing TD (6.0 at MVP)**, **0.5 PPR (0.75 at MVP)**, **-1.0 per INT thrown (-1.5 at MVP)**, **+2.0 per INT made by D/ST (+3.0 at MVP)**, **6.0 per rush/rec TD (9.0 at MVP)**, and **+3.0 milestone bonuses for 100+ rush/rec yards and 300+ passing yards (+4.5 at MVP)**. Recognize that in competitive, mid-total games (O/U 40–46), **"Zero-QB" builds that monopolize both teams' WR1s and RB1s** offer a massive structural edge over casual QB-heavy lineups.
   * **Correlation Integrity (ETR & FantasyLabs):**
     * Never pair a D/ST with the opposing starting Running Back (RB1).
     * Never roster a D/ST against 3+ opposing offensive players.
     * If rostering a Quarterback, always pair with at least one primary pass-catcher (no naked QBs).
     * **Negative Correlation Leakage & The QB Rule of 3:**
       * **NEVER roster 3 or more pass-catchers (WR/TE) from the same team without their Quarterback.** If 3+ receivers from Team A have ceiling games, their QB aggregates all their yards and TDs and will mathematically outscore the 3rd and 4th receiver, knocking them out of the optimal lineup.
       * If a team's QB is NOT in the lineup (e.g. Zero-QB builds), **strictly cap that team to at most 2 pass-catchers**.
       * If rostering 3 or more pass-catchers from Team A, **Team A's QB MUST be rostered** (either at MVP or in the FLEX).
     * **Pro-Calibrated Zero-QB Touchdown Monopoly Structure:**
       * True Zero-QB winners do not overload one receiving room; they capture the **True Touchdown Monopoly**: Team A RB1 + Team B RB1 + Team A WR1 + Team B WR1 + Favored Kicker + Value Starter/FB.
       * Rushing TDs (6.0 pts) and Field Goals (3.0–5.0 pts) bypass the QB entirely. When 2-3 passing TDs are divided strictly between WR1 and WR2, the QBs are completely starved of ceiling points.
     * **1.5x MVP Dynamic Salary Leverage:**
       * When running a QB stack, the sharpest GPP construction places the **alpha pass-catcher (WR1/WR2) at MVP** to leverage the 1.5x multiplier on 6.0-pt receiving TDs (9.0 pts), while placing the **QB in the FLEX** to capture the volume floor.
   * **Single-Entry Discipline:**
     * Do not gamble on speculative backups (e.g. backup vultures); prioritize verified, high-volume starting assets.
     * Leave **$200 to $900 unspent** to prevent chopped/split prizes.
   * **Specialized Skill Link:** Reference and follow [.agents/skills/fanduel-single-game/SKILL.md](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/.agents/skills/fanduel-single-game/SKILL.md) for full algorithmic guidelines.

3. **NFL DFS Contest Slate Taxonomy & Multi-Game Formats (MST Reference):**
   * **Sunday Main Slate:**
     * Encompasses the **11:00 AM MST early window**, the **2:00/2:15/2:25 PM MST afternoon window**, and the **6:20 PM MST Sunday Night game**.
     * **Format:** Full 9-slot Classic roster (1 QB, 2 RB, 3 WR, 1 TE, 1 FLEX, 1 D/ST) with $60,000 cap (flat pricing).
     * **Strategy Engine:** Game stacking (QB + WR1/TE1 + Opposing Bring-Back in games with O/U > 48), bellcow running back volume, and positional VORP across 10–13 games.
   * **Sunday Early Only Slate:**
     * Specifically covers the **11:00 AM / 11:15 AM MST** kickoffs.
     * Focuses on concentrated target volume, morning weather impacts, and backfield workloads before late games start.
   * **Sunday Afternoon Only Slate:**
     * Specifically covers the **2:00 PM / 2:15 PM / 2:25 PM MST** late afternoon window.
     * Compact 3-to-5 game slate requiring high-leverage game stacks and contrarian pivots.
   * **Single Game (Showdown) Slates:**
     * Dedicated island games on **Thursday Night (TNF)**, **Sunday Night (SNF)**, **Monday Night (MNF)**, and **Special Kickoff Openers** (like tonight's Wednesday game).
     * Always governed by the **6-slot (1 MVP + 5 FLEX) dynamic 1.5x salary & scoring rules** detailed in Section 2.

4. **World-Class Forensic Micro-Metrics & Pre-Lock Protocol:**
   * **Advanced Micro-Metrics Integration:**
     * **PFF CB/WR Alignment & Shadow Tracking:** Differentiate boundary (X/Z) vs. slot (Y) routes and isolate individual coverage grades rather than evaluating secondaries as a monolith.
     * **Defensive Shell Alignment:** Distinguish Middle-Field Closed (MOFC - Cover 1/3, single-high boundary 1-on-1s) from Middle-Field Open (MOFO - Cover 2/4/6, intermediate crossers and RB checkdowns).
     * **High-Value Touches (HVTs):** Weight carries inside the 5-yard line and targets inside the 10-yard line over empty between-the-20s touches.
     * **Usage Efficiency:** Prioritize TPRR ($\ge 26\%$) and YPRR ($\ge 2.20$) over raw box-score flukes.
   * **Mandatory 6-Step Pre-Lock Checklist:**
     1. Vegas Blueprint (Spreads, game totals, 5-1 / 4-2 / 3-3 script classification).
     2. 1.5x MVP Math (Multiplier Equity vs. Cap Relief, avoiding the Salary Relief Fallacy).
     3. Correlation & Anti-Cannibalization (QB Rule of 3, D/ST vs. RB1 ban).
     4. Sub-$3,500 Punt Route Viability Filter ($\ge 25\%$ route participation, zero blocking-only assets).
     5. Salary Buffer Verification ($200–$900 unspent to eliminate prize chops).
     6. Official 90-Minute Inactive Verification.

5. **Anti-Bias, Multi-Script Stress-Testing & Knapsack Optimization Directives:**
   * **The "Zero Yes-Man" Anti-Cheerleading Mandate:**
     * NEVER cheerlead, validate, or double down on a lineup simply because the user has already entered it.
     * When the user expresses doubt (e.g. "should I hop off?"), the assistant MUST STOP and provide a steel-manned counter-script detailing the exact failure mode and downside risks of the lineup before confirming.
     * Always run and present the **Multi-Script Solver** (`python scripts/run_showdown_optimizer.py`) to show the user the optimal construction across all 4 scripts:
       1. Team A Dominant (Onslaught)
       2. Team B Dominant (Onslaught)
       3. Balanced Game Script (3-3 / 4-2)
       4. Zero-QB Touchdown Monopoly
   * **The Knapsack MVP Cap Relief Rule:**
     * In FanDuel Showdown, evaluate MVP selection through the lens of the **Knapsack Problem**: A cheaper ceiling MVP (e.g., Purdy at $15,900) that unlocks five $5,400+ full-time starters mathematically dominates an expensive MVP ($17,100–$19,500) that forces a sub-$3,500 zero-point punt.
   * **The Strict Single-Entry Punt Floor ($\ge \$3,500$):**
     * In Single-Entry contests, taking a 0.0 point score is mathematically fatal.
     * Strictly **ban all sub-$3,500 rotational/depth punts** (e.g. 3rd-string tight ends or backup vultures) unless an official 90-minute inactive directly vaults them into a verified starting role ($\ge 60\%$ projected snap share).
     * The lowest-priced player in a single-entry lineup must be a verified offensive contributor (e.g., Demarcus Robinson at $5,400).
   * **Pro Exposure Signal Integration:**
     * When top pro models (like Mike McClure / SportsLine or ETR) publish exposure distributions with $\ge 25\%$ MVP or $\ge 50\%$ total exposure on a player, treat this as a high-priority mathematical signal.
     * NEVER dismiss consensus pro exposure as "chalk to fade" without running an integer programming simulation to understand why the optimizer favored them.
