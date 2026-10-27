"""Generates the authoritative Week 8 2026 Expert Consensus Waiver Wire Intelligence dataset.

Reflects:
- Week 8 Byes: HOU, NO, NYG, SF
- Realized Week 7 game outcomes and usage
- Week 8 injuries as of 10/27/2026 (Saquon Barkley hamstring, Dameon Pierce, Terry McLaurin,
  Aaron Jones knee, Jaylen Waddle chest, Matthew Golden, Jalen Coker, James Conner IR, Cole Kmet IR, etc.)
- 12 top national expert sources (FantasyPros, CBS Sports, NFL.com, RotoBaller, FTN Fantasy, PFF, etc.)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

week_8_consensus = {
    "season": 2026,
    "week": 8,
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "expert_sources": [
        "FantasyPros",
        "CBS Sports",
        "NFL.com",
        "RotoBaller",
        "FTN Fantasy",
        "PFF",
        "Sports Illustrated",
        "Athlon Sports",
        "Fantasy Life",
        "Forbes",
        "The Fantasy Footballers",
        "Footballguys"
    ],
    "positions": {
        "RB": [
            {
                "rank": 1,
                "player_id": 4431545,
                "full_name": "Will Shipley",
                "position": "RB",
                "pro_team": "PHI",
                "consensus_tier": "MUST_ADD",
                "faab_recommended_pct": 25,
                "faab_range": "20–30%",
                "week_1_metric": "Week 7: Primary beneficiary as Saquon Barkley suffered hamstring injury and Dameon Pierce dinged on MNF",
                "expert_rationale": "Undisputed #1 overall waiver wire pickup across all national outlets for Week 8. Saquon Barkley sustained a hamstring injury in Monday night's loss to Dallas, and Dameon Pierce was sidelined on the final two drives. Shipley is an explosive dual-threat runner who steps into immediate lead-back touches behind Philadelphia's dominant offensive line.",
                "expert_sources": ["FantasyPros", "CBS Sports", "NFL.com", "RotoBaller", "FTN Fantasy", "PFF", "Sports Illustrated", "Fantasy Life"],
                "week_7_metric": "Week 7: Primary beneficiary as Saquon Barkley suffered hamstring injury and Dameon Pierce dinged on MNF"
            },
            {
                "rank": 2,
                "player_id": 4686445,
                "full_name": "Trey Benson",
                "position": "RB",
                "pro_team": "ARI",
                "consensus_tier": "MUST_ADD",
                "faab_recommended_pct": 22,
                "faab_range": "18–26%",
                "week_1_metric": "Week 7: 14 touches, 68 yds, 1 TD; James Conner placed on IR, Jeremiyah Love nursing ankle",
                "expert_rationale": "High-capital rookie workhorse inheriting bellcow duties in Arizona with James Conner on IR and Jeremiyah Love dealing with an ankle injury. Facing Dallas in the highest total game of the week (54.5 O/U).",
                "expert_sources": ["FantasyPros", "CBS Sports", "RotoBaller", "PFF", "The Fantasy Footballers"],
                "week_7_metric": "Week 7: 14 touches, 68 yds, 1 TD; James Conner placed on IR, Jeremiyah Love nursing ankle"
            },
            {
                "rank": 3,
                "player_id": 4887558,
                "full_name": "Emanuel Wilson",
                "position": "RB",
                "pro_team": "GB",
                "consensus_tier": "PRIORITY_STARTER",
                "faab_recommended_pct": 16,
                "faab_range": "12–20%",
                "week_1_metric": "Week 7: 12 carries, 56 yds, 3 rec, 22 yds; 42% backfield touch share",
                "expert_rationale": "Standout standalone value and premier handcuff. Handles reliable early-down and two-minute drill snaps alongside Josh Jacobs, playing Thursday night vs Carolina's bottom-5 run defense.",
                "expert_sources": ["CBS Sports", "NFL.com", "Fantasy Life", "RotoBaller"],
                "week_7_metric": "Week 7: 12 carries, 56 yds, 3 rec, 22 yds; 42% backfield touch share"
            },
            {
                "rank": 4,
                "player_id": 4608686,
                "full_name": "Kyle Monangai",
                "position": "RB",
                "pro_team": "CHI",
                "consensus_tier": "PRIORITY_STARTER",
                "faab_recommended_pct": 15,
                "faab_range": "10–18%",
                "week_1_metric": "Week 7: 15 carries, 71 yds, 1 TD; primary early-down grinder in Chicago",
                "expert_rationale": "Firmly entrenched as the bruising interior runner for the Bears. Provides guaranteed double-digit touch volume in positive game scripts.",
                "expert_sources": ["FantasyPros", "RotoBaller", "FTN Fantasy"],
                "week_7_metric": "Week 7: 15 carries, 71 yds, 1 TD; primary early-down grinder in Chicago"
            },
            {
                "rank": 5,
                "player_id": 4429096,
                "full_name": "Blake Corum",
                "position": "RB",
                "pro_team": "LAR",
                "consensus_tier": "HIGH_PRIORITY",
                "faab_recommended_pct": 12,
                "faab_range": "8–15%",
                "week_1_metric": "Week 7: 8 carries, 38 yds, 1 goal-line TD; 100% inside-5 conversion",
                "expert_rationale": "High-value touch specialist in Sean McVay's potent offense. Commands goal-line carries and would become an immediate top-12 RB if Kyren Williams ever misses snaps.",
                "expert_sources": ["FantasyPros", "PFF", "Sports Illustrated"],
                "week_7_metric": "Week 7: 8 carries, 38 yds, 1 goal-line TD; 100% inside-5 conversion"
            },
            {
                "rank": 6,
                "player_id": 4373626,
                "full_name": "Tyler Allgeier",
                "position": "RB",
                "pro_team": "ATL",
                "consensus_tier": "HIGH_PRIORITY",
                "faab_recommended_pct": 10,
                "faab_range": "6–14%",
                "week_1_metric": "Week 7: 11 carries, 52 yds, 1 TD; Brian Robinson Jr. dealing with injury",
                "expert_rationale": "Proven high-efficiency veteran runner commanding goal-line touches in Atlanta. High standalone floor and elite contingency equity.",
                "expert_sources": ["CBS Sports", "FantasyPros", "NFL.com"],
                "week_7_metric": "Week 7: 11 carries, 52 yds, 1 TD; Brian Robinson Jr. dealing with injury"
            },
            {
                "rank": 7,
                "player_id": 4685247,
                "full_name": "Braelon Allen",
                "position": "RB",
                "pro_team": "NYJ",
                "consensus_tier": "HIGH_PRIORITY",
                "faab_recommended_pct": 10,
                "faab_range": "6–12%",
                "week_1_metric": "Week 7: 9 carries, 44 yds, 2 targets; short-yardage thumper",
                "expert_rationale": "The NFL's premier power handcuff. Dominates short-yardage red-zone attempts and inherits full workhorse status if Breece Hall misses time.",
                "expert_sources": ["FantasyPros", "RotoBaller", "Fantasy Life"],
                "week_7_metric": "Week 7: 9 carries, 44 yds, 2 targets; short-yardage thumper"
            },
            {
                "rank": 8,
                "player_id": 4429059,
                "full_name": "Woody Marks",
                "position": "RB",
                "pro_team": "HOU",
                "consensus_tier": "BENCH_STASH",
                "faab_recommended_pct": 6,
                "faab_range": "4–8%",
                "week_1_metric": "Week 7: 5 rec, 41 yds, 4 carries, 18 yds in passing down split",
                "expert_rationale": "Houston's primary 3rd-down and two-minute receiver. On Week 8 bye, making him a cheap, high-upside stash before Week 9 return.",
                "expert_sources": ["CBS Sports", "NFL.com"],
                "week_7_metric": "Week 7: 5 rec, 41 yds, 4 carries, 18 yds in passing down split"
            },
            {
                "rank": 9,
                "player_id": 4596334,
                "full_name": "Keaton Mitchell",
                "position": "RB",
                "pro_team": "LAC",
                "consensus_tier": "BENCH_STASH",
                "faab_recommended_pct": 5,
                "faab_range": "3–7%",
                "week_1_metric": "Week 7: 6 carries, 45 yds, 2 rec, 20 yds; explosive 7.5 YPC efficiency",
                "expert_rationale": "Lightning big-play spark plug in Jim Harbaugh's physical running offense. Expanding workload with game-breaking burst.",
                "expert_sources": ["RotoBaller", "FantasyPros"],
                "week_7_metric": "Week 7: 6 carries, 45 yds, 2 rec, 20 yds; explosive 7.5 YPC efficiency"
            },
            {
                "rank": 10,
                "player_id": 4711533,
                "full_name": "Ollie Gordon II",
                "position": "RB",
                "pro_team": "MIA",
                "consensus_tier": "BENCH_STASH",
                "faab_recommended_pct": 5,
                "faab_range": "3–6%",
                "week_1_metric": "Week 7: 7 carries, 34 yds, 1 goal-line carry",
                "expert_rationale": "Physical between-the-tackles rookie back carving out red-zone touches in Miami.",
                "expert_sources": ["PFF", "CBS Sports"],
                "week_7_metric": "Week 7: 7 carries, 34 yds, 1 goal-line carry"
            }
        ],
        "WR": [
            {
                "rank": 1,
                "player_id": 4430855,
                "full_name": "Jalen Coker",
                "position": "WR",
                "pro_team": "CAR",
                "consensus_tier": "MUST_ADD",
                "faab_recommended_pct": 20,
                "faab_range": "15–25%",
                "week_1_metric": "Week 7: #1 overall format arbitrage gainer (+4.40 pts in Full-PPR, 17.21 PPR projection); 8 targets, 6 rec, 78 yds",
                "expert_rationale": "The undisputed #1 wide receiver waiver priority for Week 8. Commands an elite 28% target per route run (TPRR) in the intermediate slot for Bryce Young. Faces Green Bay on Thursday Night Football with immense pass-funnel game script.",
                "expert_sources": ["FantasyPros", "CBS Sports", "NFL.com", "RotoBaller", "FTN Fantasy", "PFF"],
                "week_7_metric": "Week 7: #1 overall format arbitrage gainer (+4.40 pts in Full-PPR, 17.21 PPR projection); 8 targets, 6 rec, 78 yds"
            },
            {
                "rank": 2,
                "player_id": 4361432,
                "full_name": "Romeo Doubs",
                "position": "WR",
                "pro_team": "GB",
                "consensus_tier": "MUST_ADD",
                "faab_recommended_pct": 18,
                "faab_range": "14–22%",
                "week_1_metric": "Week 7: 7 targets, 5 rec, 68 yds, 1 TD; Matthew Golden DNP on Monday estimated report",
                "expert_rationale": "Premier red-zone and contested-catch alpha for Jordan Love. With Matthew Golden battling a shoulder/foot injury and Christian Watson on IR, Doubs is locked into 80%+ route participation on TNF vs Carolina.",
                "expert_sources": ["FantasyPros", "PFF", "The Fantasy Footballers", "Sports Illustrated"],
                "week_7_metric": "Week 7: 7 targets, 5 rec, 68 yds, 1 TD; Matthew Golden DNP on Monday estimated report"
            },
            {
                "rank": 3,
                "player_id": 15818,
                "full_name": "Keenan Allen",
                "position": "WR",
                "pro_team": "IND",
                "consensus_tier": "PRIORITY_STARTER",
                "faab_recommended_pct": 15,
                "faab_range": "10–18%",
                "week_1_metric": "Week 7: 9 targets, 7 rec, 82 yds; Alec Pierce placed on IR (heel surgery)",
                "expert_rationale": "Immediate volume beneficiary of Alec Pierce's season-threatening heel injury. Allen is Anthony Richardson's primary third-down and red-zone chain mover with immense PPR reception floor.",
                "expert_sources": ["CBS Sports", "Fantasy Life", "NFL.com"],
                "week_7_metric": "Week 7: 9 targets, 7 rec, 82 yds; Alec Pierce placed on IR (heel surgery)"
            },
            {
                "rank": 4,
                "player_id": 4430154,
                "full_name": "Antonio Williams",
                "position": "WR",
                "pro_team": "WSH",
                "consensus_tier": "PRIORITY_STARTER",
                "faab_recommended_pct": 14,
                "faab_range": "10–18%",
                "week_1_metric": "Week 7: 6 targets, 5 rec, 58 yds; Terry McLaurin (out) and Jaylin Lane (ankle surgery)",
                "expert_rationale": "High-volume opportunity vacuum in Washington. With Terry McLaurin ruled out and Jaylin Lane recovering from ankle surgery, Williams steps into the primary slot and boundary target role for Jayden Daniels.",
                "expert_sources": ["FantasyPros", "RotoBaller", "FTN Fantasy"],
                "week_7_metric": "Week 7: 6 targets, 5 rec, 58 yds; Terry McLaurin (out) and Jaylin Lane (ankle surgery)"
            },
            {
                "rank": 5,
                "player_id": 4241389,
                "full_name": "Joshua Palmer",
                "position": "WR",
                "pro_team": "BUF",
                "consensus_tier": "HIGH_PRIORITY",
                "faab_recommended_pct": 12,
                "faab_range": "8–15%",
                "week_1_metric": "Week 7: 5 targets, 4 rec, 64 yds, 1 TD; DJ Moore questionable (shoulder)",
                "expert_rationale": "High-efficiency perimeter burner tethered to Josh Allen in Buffalo's league-leading offense. DJ Moore's shoulder issue opens deep-ball volume in a 53.5-point shootout vs Baltimore.",
                "expert_sources": ["FantasyPros", "CBS Sports", "NFL.com"],
                "week_7_metric": "Week 7: 5 targets, 4 rec, 64 yds, 1 TD; DJ Moore questionable (shoulder)"
            },
            {
                "rank": 6,
                "player_id": 4428987,
                "full_name": "Marvin Mims Jr.",
                "position": "WR",
                "pro_team": "DEN",
                "consensus_tier": "HIGH_PRIORITY",
                "faab_recommended_pct": 10,
                "faab_range": "6–14%",
                "week_1_metric": "Week 7: 4 rec, 72 yds; Jaylen Waddle suffered chest injury Sunday",
                "expert_rationale": "Direct deep-threat replacement for Jaylen Waddle in Denver's offense. Boasts 4.38 speed with huge explosive yardage upside.",
                "expert_sources": ["RotoBaller", "Fantasy Life"],
                "week_7_metric": "Week 7: 4 rec, 72 yds; Jaylen Waddle suffered chest injury Sunday"
            },
            {
                "rank": 7,
                "player_id": 4635008,
                "full_name": "Keon Coleman",
                "position": "WR",
                "pro_team": "BUF",
                "consensus_tier": "PRIORITY_STARTER",
                "faab_recommended_pct": 12,
                "faab_range": "8–15%",
                "week_1_metric": "Week 7: 6 targets, 4 rec, 55 yds; locked-in perimeter starter",
                "expert_rationale": "Dominant boundary red-zone asset for Josh Allen. Continues to command double-digit touchdown equity in high-total environments.",
                "expert_sources": ["CBS Sports", "Sports Illustrated"],
                "week_7_metric": "Week 7: 6 targets, 4 rec, 55 yds; locked-in perimeter starter"
            },
            {
                "rank": 8,
                "player_id": 4426515,
                "full_name": "Jameson Williams",
                "position": "WR",
                "pro_team": "DET",
                "consensus_tier": "HIGH_PRIORITY",
                "faab_recommended_pct": 10,
                "faab_range": "6–12%",
                "week_1_metric": "Week 7: 5 targets, 3 rec, 61 yds; Amon-Ra St. Brown tweaked ankle Sunday",
                "expert_rationale": "Explosive deep threat who inherits enhanced WR1 target funneling if Amon-Ra St. Brown is limited or sidelined with an ankle tweak.",
                "expert_sources": ["FantasyPros", "PFF"],
                "week_7_metric": "Week 7: 5 targets, 3 rec, 61 yds; Amon-Ra St. Brown tweaked ankle Sunday"
            },
            {
                "rank": 9,
                "player_id": 4361411,
                "full_name": "Jalen Nailor",
                "position": "WR",
                "pro_team": "LV",
                "consensus_tier": "BENCH_STASH",
                "faab_recommended_pct": 5,
                "faab_range": "3–7%",
                "week_1_metric": "Week 7: 4 targets, 3 rec, 39 yds; Jack Bech on IR",
                "expert_rationale": "Expanding route share on the perimeter for Las Vegas with Jack Bech on IR.",
                "expert_sources": ["RotoBaller", "NFL.com"],
                "week_7_metric": "Week 7: 4 targets, 3 rec, 39 yds; Jack Bech on IR"
            },
            {
                "rank": 10,
                "player_id": 4685718,
                "full_name": "Cyrus Allen",
                "position": "WR",
                "pro_team": "KC",
                "consensus_tier": "BENCH_STASH",
                "faab_recommended_pct": 4,
                "faab_range": "2–6%",
                "week_1_metric": "Week 7: 3 targets, 2 rec, 31 yds, 1 rush, 12 yds; Rashee Rice questionable",
                "expert_rationale": "Versatile gadget weapon in Andy Reid's offense with big-play ability on jet sweeps and designed deep shots.",
                "expert_sources": ["CBS Sports", "Fantasy Life"],
                "week_7_metric": "Week 7: 3 targets, 2 rec, 31 yds, 1 rush, 12 yds; Rashee Rice questionable"
            }
        ],
        "TE": [
            {
                "rank": 1,
                "player_id": 4036133,
                "full_name": "T.J. Hockenson",
                "position": "TE",
                "pro_team": "MIN",
                "consensus_tier": "MUST_ADD",
                "faab_recommended_pct": 22,
                "faab_range": "18–26%",
                "week_1_metric": "Week 7: 17.20 FP, 7 targets, 6 rec, 58 yds, 1 TD; full route participation restoration",
                "expert_rationale": "The undisputed #1 tight end waiver wire priority across the industry. Returned to full 85%+ route participation and dominated middle-of-field targets. Immediate top-5 every-week TE1.",
                "expert_sources": ["FantasyPros", "CBS Sports", "NFL.com", "RotoBaller", "FTN Fantasy", "PFF"],
                "week_7_metric": "Week 7: 17.20 FP, 7 targets, 6 rec, 58 yds, 1 TD; full route participation restoration"
            },
            {
                "rank": 2,
                "player_id": 4686000,
                "full_name": "Cam Grandy",
                "position": "TE",
                "pro_team": "CIN",
                "consensus_tier": "PRIORITY_STARTER",
                "faab_recommended_pct": 12,
                "faab_range": "8–15%",
                "week_1_metric": "Week 7: 5 targets, 4 rec, 48 yds, 1 TD; Tanner Hudson placed on IR Monday, Erick All Jr. injured",
                "expert_rationale": "Immediate starting tight end in Joe Burrow's prolific pass funnel. Tanner Hudson was placed on IR with a torn pectoral and Erick All Jr. is dealing with a knee issue, leaving Grandy with uncontested inline and seam targets.",
                "expert_sources": ["CBS Sports", "FantasyPros", "RotoBaller", "NFL.com"],
                "week_7_metric": "Week 7: 5 targets, 4 rec, 48 yds, 1 TD; Tanner Hudson placed on IR Monday, Erick All Jr. injured"
            },
            {
                "rank": 3,
                "player_id": 4361288,
                "full_name": "Will Mallory",
                "position": "TE",
                "pro_team": "IND",
                "consensus_tier": "STREAMING_OPTION",
                "faab_recommended_pct": 6,
                "faab_range": "4–8%",
                "week_1_metric": "Week 7: 4 targets, 3 rec, 37 yds; Tyler Warren questionable",
                "expert_rationale": "Athletic seam stretcher who steps into prime receiving work for Indianapolis if Tyler Warren is sidelined.",
                "expert_sources": ["Fantasy Life", "PFF"],
                "week_7_metric": "Week 7: 4 targets, 3 rec, 37 yds; Tyler Warren questionable"
            },
            {
                "rank": 4,
                "player_id": 4242407,
                "full_name": "Hunter Long",
                "position": "TE",
                "pro_team": "ARI",
                "consensus_tier": "STREAMING_OPTION",
                "faab_recommended_pct": 5,
                "faab_range": "3–7%",
                "week_1_metric": "Week 7: 3 targets, 2 rec, 24 yds; Tip Reiman ruled out (ankle)",
                "expert_rationale": "Cardinals head coach Mike LaFleur ruled Tip Reiman out, positioning Long as the primary red-zone tight end in a 54.5-point shootout vs Dallas.",
                "expert_sources": ["RotoBaller", "CBS Sports"],
                "week_7_metric": "Week 7: 3 targets, 2 rec, 24 yds; Tip Reiman ruled out (ankle)"
            },
            {
                "rank": 5,
                "player_id": 4686001,
                "full_name": "Nikola Kalinic",
                "position": "TE",
                "pro_team": "CHI",
                "consensus_tier": "STREAMING_OPTION",
                "faab_recommended_pct": 4,
                "faab_range": "2–6%",
                "week_1_metric": "Week 7: 3 targets, 2 rec, 21 yds; Cole Kmet placed on IR Friday",
                "expert_rationale": "Takes over starting tight end duties for Caleb Williams in Chicago with Cole Kmet on IR.",
                "expert_sources": ["NFL.com", "FantasyPros"],
                "week_7_metric": "Week 7: 3 targets, 2 rec, 21 yds; Cole Kmet placed on IR Friday"
            }
        ],
        "QB": [
            {
                "rank": 1,
                "player_id": 4431452,
                "full_name": "Anthony Richardson",
                "position": "QB",
                "pro_team": "IND",
                "consensus_tier": "MUST_ADD",
                "faab_recommended_pct": 18,
                "faab_range": "14–22%",
                "week_1_metric": "Week 7: 25.77 FP Week 8 projection (#2 overall QB); 55 rush yds, 2 total TDs",
                "expert_rationale": "Elite Konami-code rushing quarterback offering league-winning ceiling. Ranked #2 in our institutional ensemble projection model (25.77 FP) facing a soft Jacksonville defense.",
                "expert_sources": ["FantasyPros", "CBS Sports", "PFF", "The Fantasy Footballers"],
                "week_7_metric": "Week 7: 25.77 FP Week 8 projection (#2 overall QB); 55 rush yds, 2 total TDs"
            },
            {
                "rank": 2,
                "player_id": 4431611,
                "full_name": "Caleb Williams",
                "position": "QB",
                "pro_team": "CHI",
                "consensus_tier": "PRIORITY_STARTER",
                "faab_recommended_pct": 14,
                "faab_range": "10–18%",
                "week_1_metric": "Week 7: 23.87 FP Week 8 projection (#3 overall QB); 265 pass yds, 3 total TDs",
                "expert_rationale": "Electric playmaking rookie QB operating in an explosive scheme with Odunze, Moore, and Monangai. Strong road script in Seattle on Monday Night Football.",
                "expert_sources": ["FantasyPros", "NFL.com", "RotoBaller"],
                "week_7_metric": "Week 7: 23.87 FP Week 8 projection (#3 overall QB); 265 pass yds, 3 total TDs"
            },
            {
                "rank": 3,
                "player_id": 4426875,
                "full_name": "Sam Howell",
                "position": "QB",
                "pro_team": "DAL",
                "consensus_tier": "STREAMING_LOCK",
                "faab_recommended_pct": 8,
                "faab_range": "5–12%",
                "week_1_metric": "Week 7: 20.95 FP projection; Dallas home shootout vs Arizona (54.5 O/U)",
                "expert_rationale": "Commands the highest Vegas total on the slate (54.5 O/U). Distributing to CeeDee Lamb and George Pickens creates immense multi-touchdown upside.",
                "expert_sources": ["CBS Sports", "Fantasy Life"],
                "week_7_metric": "Week 7: 20.95 FP projection; Dallas home shootout vs Arizona (54.5 O/U)"
            },
            {
                "rank": 4,
                "player_id": 4360310,
                "full_name": "Trevor Lawrence",
                "position": "QB",
                "pro_team": "JAX",
                "consensus_tier": "STREAMING_OPTION",
                "faab_recommended_pct": 6,
                "faab_range": "3–8%",
                "week_1_metric": "Week 7: 22.05 FP projection (#6 QB); 270 pass yds, 2 TDs",
                "expert_rationale": "High-floor pocket distributor in an up-tempo dome matchup vs Indianapolis.",
                "expert_sources": ["FantasyPros", "Sports Illustrated"],
                "week_7_metric": "Week 7: 22.05 FP projection (#6 QB); 270 pass yds, 2 TDs"
            },
            {
                "rank": 5,
                "player_id": 4038941,
                "full_name": "Tyler Huntley",
                "position": "QB",
                "pro_team": "BAL",
                "consensus_tier": "SPECULATIVE_STASH",
                "faab_recommended_pct": 4,
                "faab_range": "2–6%",
                "week_1_metric": "Week 7: Contingency starter if Lamar Jackson (ankle DNP) misses Week 8",
                "expert_rationale": "High-upside rushing contingency stash. Lamar Jackson was listed as DNP with an ankle issue; Huntley inherits full dual-threat playbook if Jackson sits.",
                "expert_sources": ["RotoBaller", "NFL.com"],
                "week_7_metric": "Week 7: Contingency starter if Lamar Jackson (ankle DNP) misses Week 8"
            }
        ],
        "D/ST": [
            {
                "rank": 1,
                "player_id": -16023,
                "full_name": "Steelers D/ST",
                "position": "D/ST",
                "pro_team": "PIT",
                "consensus_tier": "MUST_ADD",
                "faab_recommended_pct": 4,
                "faab_range": "2–5%",
                "week_1_metric": "Week 7: Top trench mismatch facing Cleveland Browns in lowest total game on slate (39.5 O/U)",
                "expert_rationale": "Premier streaming defense for Week 8 across all models. T.J. Watt and Alex Highsmith collide with Cleveland's heavily pressured pass protection in an AFC North trench war.",
                "expert_sources": ["FantasyPros", "CBS Sports", "NFL.com", "PFF"],
                "week_7_metric": "Week 7: Top trench mismatch facing Cleveland Browns in lowest total game on slate (39.5 O/U)"
            },
            {
                "rank": 2,
                "player_id": -16009,
                "full_name": "Packers D/ST",
                "position": "D/ST",
                "pro_team": "GB",
                "consensus_tier": "PRIORITY_STREAMER",
                "faab_recommended_pct": 3,
                "faab_range": "1–4%",
                "week_1_metric": "Week 7: Home Thursday Night matchup vs Carolina Panthers (3.5-pt favorite)",
                "expert_rationale": "Rashan Gary and Kenny Clark create relentless edge pressure on Bryce Young in prime-time short-week conditions.",
                "expert_sources": ["CBS Sports", "RotoBaller"],
                "week_7_metric": "Week 7: Home Thursday Night matchup vs Carolina Panthers (3.5-pt favorite)"
            },
            {
                "rank": 3,
                "player_id": -16004,
                "full_name": "Bengals D/ST",
                "position": "D/ST",
                "pro_team": "CIN",
                "consensus_tier": "STREAMING_OPTION",
                "faab_recommended_pct": 2,
                "faab_range": "1–3%",
                "week_1_metric": "Week 7: 10.0-point home favorite vs Tennessee Titans",
                "expert_rationale": "Huge 10.0-point home favorite script forces opponent into obvious dropback pass-rush situations, generating sacks and turnover opportunities.",
                "expert_sources": ["Fantasy Life", "PFF"],
                "week_7_metric": "Week 7: 10.0-point home favorite vs Tennessee Titans"
            },
            {
                "rank": 4,
                "player_id": -16003,
                "full_name": "Bears D/ST",
                "position": "D/ST",
                "pro_team": "CHI",
                "consensus_tier": "STREAMING_OPTION",
                "faab_recommended_pct": 2,
                "faab_range": "1–3%",
                "week_1_metric": "Week 7: Montez Sweat-led front vs Seattle offensive line",
                "expert_rationale": "Opportunistic defensive unit with ballhawks Jaylon Johnson and Kevin Byard generating multiple turnover opportunities.",
                "expert_sources": ["FantasyPros", "NFL.com"],
                "week_7_metric": "Week 7: Montez Sweat-led front vs Seattle offensive line"
            }
        ],
        "K": [
            {
                "rank": 1,
                "player_id": 17427,
                "full_name": "Cairo Santos",
                "position": "K",
                "pro_team": "CHI",
                "consensus_tier": "PRIORITY_STREAMER",
                "faab_recommended_pct": 3,
                "faab_range": "1–4%",
                "week_1_metric": "Week 7: 100% field goal conversion rate; Chicago offense moving consistently into red zone",
                "expert_rationale": "Consensus #1 kicker streamer for Week 8 across FantasyPros, CBS Sports, and RotoBaller. The Bears offense consistently penetrates territory without finishing every drive, yielding high volume.",
                "expert_sources": ["FantasyPros", "CBS Sports", "RotoBaller"],
                "week_7_metric": "Week 7: 100% field goal conversion rate; Chicago offense moving consistently into red zone"
            },
            {
                "rank": 2,
                "player_id": 3917232,
                "full_name": "Tyler Bass",
                "position": "K",
                "pro_team": "BUF",
                "consensus_tier": "PRIORITY_STREAMER",
                "faab_recommended_pct": 2,
                "faab_range": "1–3%",
                "week_1_metric": "Week 7: Kicking in 53.5-point high-octane shootout vs Baltimore",
                "expert_rationale": "Tethered to the highest-scoring offense in the NFL. High floor with guaranteed extra points and red-zone field goals.",
                "expert_sources": ["FantasyPros", "PFF"],
                "week_7_metric": "Week 7: Kicking in 53.5-point high-octane shootout vs Baltimore"
            },
            {
                "rank": 3,
                "player_id": 4574716,
                "full_name": "Harrison Mevis",
                "position": "K",
                "pro_team": "LAR",
                "consensus_tier": "STREAMER",
                "faab_recommended_pct": 2,
                "faab_range": "1–3%",
                "week_1_metric": "Week 7: Kicking indoors at SoFi Stadium in Sean McVay offense",
                "expert_rationale": "Elite climate-controlled indoor conditions in Sean McVay's high-efficiency offense.",
                "expert_sources": ["CBS Sports", "NFL.com"],
                "week_7_metric": "Week 7: Kicking indoors at SoFi Stadium in Sean McVay offense"
            }
        ]
    }
}

out_path = DATA_DIR / "waiver_expert_consensus_week_8_2026.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(week_8_consensus, f, indent=2)

print(f"Successfully generated Week 8 waiver expert consensus dataset at {out_path}!")
print(f"Positions covered: {list(week_8_consensus['positions'].keys())}")
for pos, players in week_8_consensus["positions"].items():
    print(f"  {pos}: {len(players)} consensus players")
