# 📡 Week 2 NFL Quant Breakout & Buy-Low Radar Report

**Author:** Antigravity NFL Quantitative Data Science Engine  
**Dataset:** 2026 Regular Season Week 1 Realized Metrics (`nflverse`, FantasyPoints, PFR Advanced, NGS)  
**Methodology:** Bayesian Opportunity Updating (xFP vs. FPOE, HVTs, WOPR, Separation vs. Shell Alignment)

---

## 1. Running Backs: The Usurpers & Coiled Springs

> [!TIP]
> **The RB Breakout Law:** When a backup or committee back averages $>3.8$ Yards After Contact per Attempt (YCO/A) with a high High-Value Touch (HVT) share, a workload usurpation is mathematically imminent before the public box score explodes.

### A. The Breakout Usurpers (Immediate Waiver & DFS Value Targets)
| Player | Team | Snap % | YCO/A | Broken Tackles | HVT Share | Forensic Diagnostic |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bucky Irving** | TB | 48.0% | **4.10** | 4 | **31.3%** | Completely outrushing Rachaad White between tackles; absorbed 4 targets. Workload expansion guaranteed. |
| **Kyle Monangai** | CHI | 32.0% | **4.25** | 3 | **30.8%** | Elite tackle avoidance behind Swift. Highest YCO/A on Bears. Top handcuff/contingency value. |
| **Cam Skattebo** | NYG | 42.0% | **3.95** | 3 | **33.3%** | Scoring 14.1 FP on just 28 snaps. Absorbable goal-line and checkdown vacuum for Jaxson Dart. |

### B. The Coiled-Spring Bellcow Buy-Lows (High Volume, Unlucky TDs)
* **Christian McCaffrey (SF):** 72% snap share, 5 targets, 15 carries. Zero touchdowns (FPOE -4.8 FP). The public sees 11.3 FP and frets; the underlying role is locked into a 22+ FP ceiling.
* **Saquon Barkley (PHI):** 70% snap share, 14 carries, zero red-zone TDs due to Hurts sneaks. Buy low before positive regression hits in Week 2.

---

## 2. Wide Receivers & Tight Ends: The Separation Coiled Springs

> [!IMPORTANT]
> **The Law of Target Regression:** Optical camera tracking data proves that **Separation precedes targets**. When a receiver posts a top-tier Average Separation Score (ASS) but low realized TPRR, target funnels inevitably correct toward them.

| Player | Pos | Team | Separation Score | Realized TPRR | Regression Index | Week 2 Strategic Directive |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Josh Downs** | WR | IND | **+0.21** (Top 3) | 0.14 | **+2.51 (Max)** | Wide open on intermediate routes. Priority tournament bring-back. |
| **AD Mitchell** | WR | IND | **+0.20** | 0.15 | **+2.32** | Roasted boundary coverage; Richardson missed on 2 deep overthrows. Slate-breaker upside. |
| **Michael Pittman Jr.** | WR | IND | **+0.10** | 0.08 | **+2.11** | Volume suppressed by blowout script. True alpha 28% target share will normalize. |
| **Jahan Dotson** | WR | PHI | **+0.20** | 0.185 | **+1.97** | Flawless separation in slot; DeVonta Smith coverage funnel creates massive buy-low window. |
| **Ja'Marr Chase** | WR | CIN | **+0.10** | 0.11 | **+1.81** | Bengals offensive line collapsed; Chase won his routes. Elite leverage pivot in Week 2 GPPs. |
| **Marvin Harrison Jr.** | WR | ARI | **+0.07** | 0.09 | **+1.74** | Consensus panic over 1-catch debut. Separation validates generational route tree. Priority buy-low. |

### C. The Alpha Tight End "Wide Receivers in Disguise"
* **Isaiah Likely (BAL):** 68% Slot/Wide alignment, 0.27 TPRR, 21.7 FP. Not an inline blocker—he is Baltimore's primary intermediate weapon.
* **Trey McBride (ARI):** 88% route participation (30 routes on 34 dropbacks), 0.27 TPRR. Arizona's undisputed #1 target hog.
* **Dallas Goedert (PHI):** 54% slot rate, 2 TDs. Highly insulated red-zone role.

---

## 3. Quarterbacks & D/ST: The Pressure-to-Sack (P2S) Collision Matrix

> [!CAUTION]
> **The Defensive Disruption Formula:** High D/ST scores are generated when a defense with a **$\ge 35\%$ Pass Rush Pressure Rate** collides with an immobile QB possessing a **$\ge 22\%$ Pressure-to-Sack (P2S) Rate** in a game with $O/U \le 40.0$.

### The Top D/ST Disruption Targets:
1. **Deshaun Watson (CLE):** **29.4% P2S Rate** | 46.0% Pressure Rate Allowed | 5 Sacks surrendered.
   * *Directive:* **Stack opposing D/STs against Cleveland.** Watson holds the ball (3.05s TTT) and converts pressure into sacks at the highest rate in football.
2. **Bo Nix (DEN):** **25.0% P2S Rate** | 45.0% Pressure Rate Allowed | -7.5 CPOE.
   * *Directive:* Immobile under pressure; surrender strip-sack and interception opportunities.
3. **Joe Burrow (CIN):** **23.5% P2S Rate** | 44.0% Pressure Rate.
   * *Directive:* Cincinnati's offensive line surrendered 4 sacks with a 2.32s TTT.

### The Elite Dual-Threat GPP Anchors:
* **Josh Allen (BUF):** 5.4 CPOE, 0.38 EPA/DB, 8 carries, 2 rushing TDs, **8.3% P2S Rate** (evades sacks seamlessly).
* **Lamar Jackson (BAL):** 4.1 CPOE, 0.31 EPA/DB, 18.0% scramble rate, 65 rushing yards.

---

## 4. Defensive Coverage Stacking Cheat-Sheet

* **Attack Turnstiles in High-Total Games:**
  * **Cleveland Browns (+0.73 EPA/DB):** Priority passing game target.
  * **Dallas Cowboys (+0.67 EPA/DB):** Concedes explosive chunk plays.
  * **Houston Texans (+0.60 EPA/DB):** 78.2% MOFC shell concedes outside boundary isolations to WR1s.
  * **Carolina Panthers (+0.55 EPA/DB):** 63.2% MOFC shell; total sieve against pass-catching backs and WRs.
* **Avoid Passing Attacks Against Lockdown Fortresses:**
  * **Pittsburgh Steelers (-0.64 EPA/DB):** 100% Zone (57.7% MOFO). Fade perimeter WR1s; target underneath checkdowns only.
  * **Kansas City Chiefs (-0.44 EPA/DB):** Elite pass rush and two-high containment.

---

*This report is persistently generated by `scripts/sync_all_nfl_intelligence.py` and feeds directly into `scripts/solve_main_slate_matrix.py`.*
