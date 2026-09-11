---
name: fanduel-single-game
description: >-
  Master playbook and analytical framework for building winning FanDuel Single Game (Showdown) DFS lineups.
  Covers the 1.5x MVP salary & scoring rules, game script classification (LineStar / ETR), correlation rules,
  and single-entry tournament strategy. Activate whenever analyzing or building single-game or showdown NFL DFS lineups.
---

# FanDuel Single Game (Showdown) Championship Playbook

This skill encapsulates the professional methodology and mathematical principles (derived from Establish The Run, FantasyLabs, LineStar, and high-stakes tournament winners) for winning FanDuel NFL Single Game contests.

---

## 1. Format & Pricing Rules (Updated 2025/2026 Engine)

* **Roster Composition:** Exactly **6 roster spots**:
  * **1 MVP slot** (1.5x Fantasy Points)
  * **5 AnyFLEX slots** (Standard Fantasy Points)
* **The 1.5x MVP Salary Rule:**
  * Placing a player in the MVP slot costs **1.5x their base salary** (e.g., a $12,000 player costs $18,000 at MVP).
  * This creates real opportunity cost; you cannot mindlessly jam the most expensive stud at MVP without sacrificing FLEX quality.
* **Salary Cap:** Exactly **$60,000** (average of $10,000 per slot).
* **Team Constraint:** Must roster at least 1 player from each team (e.g., 3-3, 4-2, or 5-1 builds).

---

## 2. FanDuel Scoring Dynamics: The "Zero-QB" Edge

* **Official FanDuel Single Game Scoring Matrix (AnyFLEX vs. 1.5x MVP):**
  | Stat Category | AnyFLEX Standard | MVP (1.5x Multiplier) | Strategic Implication |
  | :--- | :--- | :--- | :--- |
  | **Passing Yards** | 0.04 / yd (1 pt / 25 yds) | 0.06 / yd | QB yardage accrues slowly compared to rushing/receiving |
  | **Passing TD** | 4.0 pts | 6.0 pts | Pass TDs discounted 33% relative to Rush/Rec TDs |
  | **Interception Thrown (Offense / QB)** | -1.0 pt | -1.5 pts | Penalty deducted from the passer |
  | **300+ Passing Yds Bonus** | +3.0 pts | +4.5 pts | High volume pocket passers need 300 yds to compete |
  | **Rushing Yards** | 0.10 / yd (1 pt / 10 yds) | 0.15 / yd | 2.5x more valuable than passing yards |
  | **Rushing TD** | 6.0 pts | 9.0 pts | Massive 9.0 pt reward at MVP |
  | **100+ Rushing Yds Bonus** | +3.0 pts | +4.5 pts | Huge boost for bellcow RBs crossing the century mark |
  | **Receptions** | 0.50 PPR | 0.75 PPR | High target share WRs gain separation |
  | **Receiving Yards** | 0.10 / yd (1 pt / 10 yds) | 0.15 / yd | 2.5x more valuable than passing yards |
  | **Receiving TD** | 6.0 pts | 9.0 pts | High-leverage ceiling event (9.0 pts at MVP) |
  | **100+ Receiving Yds Bonus** | +3.0 pts | +4.5 pts | Multiplier expands 100+ yd WRs (JSN ceiling) |
  | **Fumble Lost** | -2.0 pts | -3.0 pts | Severe penalty at MVP |
  | **2-Pt Conversion (Pass/Score)**| 2.0 pts | 3.0 pts | High leverage goal-line conversion |
  | **Field Goal: 0–39 Yards** | 3.0 pts | 4.5 pts | Standard baseline kick |
  | **Field Goal: 40–49 Yards** | 4.0 pts | 6.0 pts | Medium-range kick |
  | **Field Goal: 50+ Yards** | 5.0 pts | 7.5 pts | Elite kicker bonus (Jason Myers range) |
  | **Extra Point Made** | 1.0 pt | 1.5 pts | Baseline PAT |
  | **Sack (D/ST)** | 1.0 pt | 1.5 pts | Baseline pressure stat |
  | **Interception Made (D/ST)** | 2.0 pts | 3.0 pts | Defensive turnover reward |
  | **Fumble Recovery (D/ST)** | 2.0 pts | 3.0 pts | Defensive turnover reward |
  | **Safety (D/ST)** | 2.0 pts | 3.0 pts | Defensive 2-pt score |
  | **Blocked Punt / Kick (D/ST)**| 2.0 pts | 3.0 pts | Special teams turnover/block |
  | **Defensive / Return TD** | 6.0 pts | 9.0 pts | Nuclear defensive outlier (Pick-6, scoop & score, return TD) |
  | **Extra-Point Return (D/ST)** | 2.0 pts | 3.0 pts | Rare defensive conversion |
  | **Points Allowed: 0** | 10.0 pts | 15.0 pts | Shutout tier |
  | **Points Allowed: 1–6** | 7.0 pts | 10.5 pts | Dominant tier |
  | **Points Allowed: 7–13** | 4.0 pts | 6.0 pts | Strong tier |
  | **Points Allowed: 14–20** | 1.0 pt | 1.5 pts | Average tier |
  | **Points Allowed: 21–27** | 0.0 pts | 0.0 pts | Neutral tier |
  | **Points Allowed: 28–34** | -1.0 pt | -1.5 pts | Negative tier |
  | **Points Allowed: 35+** | -4.0 pts | -6.0 pts | Severe negative tier |

### The Math of Fading QBs:
In tight or moderate-scoring games (O/U 40–46), QBs often fail to crack the top 5 FLEX scores because their touchdowns are aggregated by their receivers.
* Example: A QB throws 220 yards, 2 TDs, 1 INT = **14.8 points** ($12,000+ salary).
* If those 2 TDs go to WR1 (8 rec, 105 yds, 2 TDs), WR1 scores **26.5 points** (or **39.8 at MVP**).
* If the team's RB punches in the other score (15 carries, 60 yds, 1 TD), RB scores **14.5 points** ($9,000).
* **Fading both QBs** allows you to roster the **#1 WR and #1 RB of BOTH teams**, capturing a 100% monopoly on the game's touchdowns while 80% of the casual public wastes salary on overpriced QBs.

---

## 3. Strict Correlation & Roster Construction Rules

### Rule A: The D/ST Cannibalization Rule
* **NEVER pair a D/ST with the opposing starting Running Back (RB1).**
  * If the RB1 has a ceiling game (75+ yards, 2 TDs), the opposing defense loses points for scoring and yards allowed.
  * If the D/ST has a ceiling game (5 sacks, low score), the running game is abandoned.
* **Avoid pairing a D/ST with 3+ opposing offensive players.**
  * If the opposing offense moves the ball well enough for 3 players to hit their ceiling, the D/ST cannot achieve a winning fantasy score.

### Rule B: The QB Stacking Rule
* If a Quarterback IS rostered (especially at MVP), he **MUST be paired with at least 1 (or 2) of his pass-catchers** (WR1, WR2, or TE).
* Never roster a "naked" non-scrambling pocket QB.

### Rule C: Game Script Identification (LineStar Framework)
* **Tight Spreads (<= 4.0 pts) & Mid Totals (41–46):**
  * **3–3 Balanced Build** or **4–2 Build** is optimal.
  * Fade both defenses.
  * Focus on the top 4 skill touchdown scorers + favored home kicker + primary slot value.
* **Blowout Spreads (>= 7.0 pts):**
  * **5–1 Onslaught Build** (5 players from favored team + 1 lone-wolf pass-catcher or trailing QB from underdog).

### Rule D: The QB Rule of 3 & Negative Correlation Leakage (Anti-Cannibalization)
* **NEVER roster 3 or more pass-catchers (WR/TE) from the same team without their Quarterback.**
  * *The Mathematical Trap:* If 3 or 4 receivers from Team A have ceiling games (e.g. 70+ yds or a TD each), their QB aggregates all their yards and passing TDs ($250+$ passing yds, 3+ pass TDs = 20+ FPTS). The QB mathematically outscores the 3rd and 4th receiver in raw fantasy points, eliminating them from the top 5 FLEX spots. A lineup holding 3+ receivers without their QB beats itself before kickoff.
* **The "Pass-Catcher Cap Without QB" Rule:**
  * If a team's quarterback is **NOT** in the lineup, strictly cap that team to **at most 2 pass-catchers** (WR/TE).
* **The "Air Supremacy Multi-Stack" Rule:**
  * If rostering 3 or more pass-catchers from Team A, **Team A's quarterback MUST be rostered** (either at MVP or in the FLEX).
  * *MVP Leverage:* In FanDuel single-game, place the primary alpha receiver at MVP (1.5x on 6.0-pt receiving TDs) and the QB in the FLEX to capture the high volume passing floor.

### Rule E: Pro-Calibrated Zero-QB Touchdown Monopoly Structure
* Winning Zero-QB builds do NOT overload one team's receiving room; they capture the **True Touchdown Monopoly**:
  1. **Team A Starting Running Back (RB1):** Bellcow goal-line and rushing TD monopoly (6.0 pts raw, 9.0 at MVP).
  2. **Team B Starting Running Back (RB1):** Bellcow rushing volume.
  3. **Team A Primary Receiver (WR1):** High-volume target hog (0.5 PPR separation).
  4. **Team B Primary Receiver (WR1):** Intermediate/red-zone target share.
  5. **Favored Home Kicker:** Stalled red-zone drives yield 3.0 to 12.0 kicking points uncredited to either passer.
  6. **Cap-Relief Starter or Fullback:** Legitimate snap-count piece (FB or slot WR) to subsidize the cap.
* *Why this wins:* When RBs score the rushing touchdowns and kickers hit field goals, the QBs are completely starved of ceiling scores, allowing all 6 non-QB skill players to finish ahead of both passers.

---

## 4. Single-Entry (1-Lineup) Championship Principles

1. **Do NOT Gamble on Speculative Backups:**
   * In 150-max MME, players can spray 3rd-string tight ends or backup goal-line vultures (like George Holani).
   * In **Single-Entry**, stick to **verified starters with guaranteed snap counts and touch floors**.
2. **Leave Salary on the Table:**
   * Spending all $60,000 creates massive duplicate lineups.
   * Leaving **$200 to $900 unspent** dramatically differentiates your lineup without sacrificing projected points.
3. **Touchdown Monopoly Strategy:**
   * Identify the 4 players most likely to cross the goal line (WR1 and RB1 of each team). Prioritize rostering all 4.

---

## 5. Dynamic MVP Optimization: Multiplier Equity vs. FLEX Cap Relief

Because FanDuel assigns a dynamic 1.5x salary penalty to the MVP slot, every showdown slate is a mathematical chess match between two distinct game environments:

### Regime 1: The "Alpha Outlier" Slate (Pay-Up at MVP)
* **Trigger:** An elite player has a statistically separated 95th-percentile ceiling (e.g. 30%+ target share alpha WR1 or true bellcow RB with 25+ touch upside).
* **The Math:** If an alpha player drops 28.0 raw points, the 1.5x MVP multiplier yields **+14.0 bonus points (42.0 total)**. No combination of mid-tier upgrades in FLEX can compensate for surrendering that 14-point multiplier gap if that ceiling occurs.
* **Execution Directive:** Anchor the Alpha at MVP ($18k–$20k) and utilize mispriced injury vacancies (e.g. backup RBs/WRs thrust into starting volume) to subsidize the roster without resorting to low-floor zero-point punts.

### Regime 2: The "Compressed Tier" Slate (Pay-Down at MVP)
* **Trigger:** A low-total game (O/U < 41), muddy backfields, 4-way receiver committees, or elite defensive matchups where the top scorer is projected for only 15–18 points and no individual ceiling stands out.
* **The Math:** The multiplier bonus between an $18k player (16 pts -> +8 bonus) and a $10k player (14 pts -> +7 bonus) is only ~1.0 point. Paying $15k–$18k at MVP forces two unplayable $2k punts.
* **Execution Directive:** Pay down at MVP ($9,000–$11,500) to capture $4,500+ in cap relief, allowing you to roster 5 high-floor starters ($9k–$11k) across the entire FLEX and completely eliminate sub-$4k liability assets.

---

## 6. Generalized Analytical Axioms & Anti-Overfitting Safeguards

To prevent curve-fitting to small sample sizes (N=1), always apply these universal, empirically proven showdown principles across all future single-game slates:

### Axiom 1: The Dual-Threat vs. Pocket Passer Asymmetry
* **Dual-Threat QBs (Rushing Equity):** QBs with 5+ designed carries or scrambling ability earn **0.10 pts/rush yd (2.5x passing rate)** and **6.0 pts/rush TD (50% more than pass TD)**. They can sustain viable fantasy floors even in defensive, low-scoring games.
* **Pure Pocket Passers:** Non-scrambling QBs in mid-to-low total games (O/U <= 45) carry extreme negative variance. Taking sacks and throwing an INT (-1.0 pt) drains their ceiling, while their passing touchdowns are heavily discounted (4.0 pts) relative to the receivers who catch them (6.0 pts + 0.5 PPR + 0.10/yd). Fading pocket passers in favor of their primary pass-catchers is mathematically positive-EV long term.

### Axiom 2: The "Isolated Ghost TD" Variance Trap
* When a QB throws a touchdown to an unowned backup tight end or fullback (sub-5% drafted), it creates an immediate artificial spike on the leaderboard for QB rosters.
* **Do NOT overreact to this variance:** A QB cannot sustain a tournament-winning ceiling on 2-yard flat routes to backup blockers. Over 60 minutes, the primary WR1s and RB1s outscore passing QBs on touchdowns by 50% to 150%. Trust the structural math over short-term goal-line variance.

### Axiom 3: The Punt Viability Filter (Target Floor vs. Blocking Trap)
* In **Single-Entry tournaments**, sub-$4,000 punts are ONLY viable if they meet the **"Target/Touch Floor Criteria"**:
  1. **Route Participation vs. Blocking Snaps:** Never judge a punt by snap count alone. A player playing 50% of snaps exclusively to run-block (e.g. a blocking fullback or in-line blocking TE) has a microscopic fantasy ceiling (0.5 to 2.0 pts). Conversely, an athletic "move" tight end or slot receiver playing 20% to 30% of snaps specifically flexed out to run routes downfield or in the red zone carries legitimate 8.0+ point ceiling.
  2. **Correlation Alignment:** Does the punt correlate with your roster stack? (e.g. a cheap move-TE stacked with your passing QB compounds passing touchdowns; an uncoordinated fullback does not).
  3. **The 8.0+ Point Ceiling Test:** Can this player realistically catch a 20-yard pass and a touchdown? If their 95th-percentile ceiling is 2 points, they are mathematically disqualified from GPP tournaments.

### Axiom 4: The Favored Home Kicker in Low-Spread, Mid-Total Environments
* In games with **Spreads <= 4.0 points and Totals between 40 and 46**, favored home kickers (especially in good weather or domes) have an exceptionally high floor-to-ceiling profile at sub-$6,500 salaries.
* Because field goals earn **3.0 pts (<40 yds), 4.0 pts (40–49 yds), and 5.0 pts (50+ yds)**, a kicker hitting 2 field goals and an extra point yields **7.0 to 9.0 FPTS**—completely crushing value while providing the salary relief needed to anchor an elite Alpha MVP and verified starters across the entire roster.

### Axiom 5: Structural Durability Over Single-Player Variance
* A lineup built with **Alpha Multiplier Equity (elite 1.5x MVP ceiling)**, **starter-level touch floors**, and **zero ghost punts** possesses structural durability. Even if an individual player exits early due to an unpredictable in-game injury, the remaining core has enough mathematical leverage to cash in the top percentile of the tournament.

### Axiom 6: The "Week 1 Early-Season Uncertainty Calibration"
Week 1 is mathematically the highest-variance, highest-uncertainty slate of the entire NFL season due to zero current-year regular-season data, new offensive coordinators, traded personnel, and misleading preseason usage. In Week 1, adhere to the **Early-Season Information Hierarchy**:
1. **Tier 1 (Highest Reliability) — Structural Mathematical Discipline:** Roster construction principles (leaving $200–$900 unspent, 1.5x MVP multiplier leverage, QB Rule of 3, 0.5 PPR scoring rates) do not change from year to year. When player roles are uncertain, structural math is your primary competitive edge over casual drafters.
2. **Tier 2 — Scheme Installation & Beat Reporting:** When current-season game logs do not exist, trust verified training camp installations (e.g. McVay expanding 12/13 personnel, Shanahan's goal-line tendencies) and official 2-deep depth charts over generic projections.
3. **Tier 3 — Vegas Implied Totals:** Use the opening lines and movement as the ultimate macro-blueprint for touchdown density and game pace.
4. **The "Full-Go" Assumption:** Unless a player is officially designated as **Questionable, Doubtful, or Out** on the final 90-minute injury report, treat all starters as 100% full-go assets. Do not prematurely bench studs based on vague offseason practice reports.

---

## 7. The World-Class Forensic Micro-Metrics Protocol (PFF, Scheme & Usage)

As regular-season data accumulates (Weeks 2–18), integrate these definitive forensic metrics to eliminate guesswork:

### 1. PFF Coverage & Individual CB/WR Matchup Grades
* **Alignment Mapping:** Never evaluate a WR vs. "the secondary" as a monolith. Map exact alignments:
  * **Boundary / Perimeter (X/Z):** Contested-catch rate, press-coverage win rate against outside cornerbacks.
  * **Slot Alignment (Y):** Target separation against nickel cornerbacks and linebackers in space.
* **Shadow Tracking:** Identify true shadow CBs (e.g., Patrick Surtain II, Sauce Gardner) vs. static left/right cornerbacks. If a shadow travels with WR1, leverage the WR2/Slot receiver who inherits clean coverage.

### 2. Scheme & Defensive Shell Matchups (MOFC vs. MOFO)
* **Middle-Field Closed (MOFC - Cover 1 / Cover 3):** Single-high safety shells open up 1-on-1 boundary isolation routes for alpha receivers and deep seam routes for athletic TEs.
* **Middle-Field Open (MOFO - Cover 2 / Cover 4 / Cover 6):** Two-high safety shells force intermediate crossers, underneath RB checkdowns, and screens.
* **Pressure-to-Sack (P2S) & Blitz Tendencies:** A high-blitz defense against a stationary pocket passer increases checkdown frequency to RBs and hot-route slant equity to the primary X-receiver.

### 3. Usage & Efficiency Over Raw Box Scores
* **TPRR (Targets Per Route Run):** The ultimate measure of target-earning talent. Elite alpha tier is $\ge 26\%$. Disregard WRs running routes with a sub-14% TPRR.
* **YPRR (Yards Per Route Run):** True efficiency metric ($\ge 2.20$ is elite).
* **First-Read Target Share:** The primary read designed into the playbook. QBs look to their first-read receiver on 65%+ of red-zone dropbacks.
* **High-Value Touches (HVTs):**
  * **Carries Inside the 5-Yard Line (Goal Line):** Accounts for 75%+ of rushing touchdowns.
  * **Targets Inside the 10-Yard Line:** Accounts for 80%+ of receiving touchdowns.

---

## 8. The 6-Step Pre-Lock Verification Checklist

Before locking or recommending any single-game DFS lineup, execute this verification order:

1. **Vegas Implied Blueprint:** Check spread, total, and team totals. Classify the game script (5-1 Onslaught, 4-2 Favored, or 3-3 Balanced).
2. **The 1.5x MVP Math Audit:** Calculate exact cap impact of MVP choice. Verify Multiplier Equity (9.0-pt TD upside) vs. FLEX purchasing power. Reject the "Salary Relief Fallacy."
3. **Correlation Integrity Check:** Verify no anti-correlated pieces (no D/ST with opposing RB1, no naked QBs, no 3+ WRs without their QB).
4. **Punt Route Viability Filter:** Ensure every sub-$3,500 punt meets the 25%+ route participation or designated red-zone package threshold. Zero pure-blocking fullbacks.
5. **Salary Buffer Verification:** Confirm **$200 to $900 remains unspent** ($59,100 to $59,800 total cap spent) to prevent prize duplication.
6. **Official 90-Minute Inactive Verification:** Inspect active/inactive reports to ensure all 6 rostered players are confirmed active.
7. **Anti-Bias & Steel-Manned Counter-Script Audit:** Mandatory requirement to generate and inspect the inverse game script before locking.

---

## 9. The Anti-Bias Protocol & The Rams vs. 49ers Case Study

### The Historical Precedent (Rams vs. 49ers Week 1 2026):
* **The Trap:** Prior to kickoff, pro model Mike McClure published exposure targets highlighting **Brock Purdy as his #1 overall pick and 30% MVP exposure**. 
* **The Analytical Failure:** The analytical agent succumbed to **confirmation bias and the "Contrarian Trap"**—arguing that Purdy was chalk to fade, doubling down on an aggressive 5-1 Rams onslaught, and relying on a $2,600 rotational TE (Terrance Ferguson).
* **The Result:** The 49ers blew out the Rams 27-7. Ferguson scored 0.0 points, the Rams scored only 7 points, and the 5-1 Rams build finished 28,850th of 29,761. Meanwhile, the $7,500 1st-place tournament winner (`@btbybee4`, 96.45 pts) rostered:
  - **MVP:** Brock Purdy (33.15 pts)
  - **FLEX:** Christian McCaffrey, Deebo Samuel Sr., Eddy Pineiro, Demarcus Robinson ($5,400), and Kyren Williams.
  - **Total Salary:** $59,900.

### The Permanent Safeguards:
1. **Zero Yes-Man Rule:** An analytical assistant must NEVER validate an entered lineup simply because the user asks for confirmation. It is mandatory to present the exact counter-script and how the lineup dies.
2. **The Knapsack Solution Rule:** In FanDuel single-game, evaluate the **cap relief of the MVP slot**. Purdy at $15,900 at MVP was $1,200 to $3,600 cheaper than Stafford, Puka, or CMC, allowing the 1st-place winner to roster five verified $5,400+ players without taking on a zero-point punt.
3. **The Sub-$3,500 Punt Ban in Single-Entry:** Taking a 0.0 in single-entry is fatal. All players rostered in single-entry must have a verified 60%+ snap share or multi-target role.
4. **Algorithmic Solver Tool:** Always execute `python scripts/run_showdown_optimizer.py --slate <path>` to review all 4 script options mathematically before selecting a lineup.
