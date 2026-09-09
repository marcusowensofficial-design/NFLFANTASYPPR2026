import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import sqlite3
import pandas as pd
import json
import asyncio
from src.services.matchup.dvp_service import dvp_service
from src.adapters.betting.props_client import vegas_props_client
from src.adapters.nfl.schedule_client import nfl_schedule_client

async def run_analysis():
    # 1. Load FanDuel CSV
    csv_path = 'data/FanDuel-NFL-2026 MDT-09 MDT-13 MDT-133104-players-list.csv'
    df_all = pd.read_csv(csv_path)
    
    print(f"Total players on slate: {len(df_all)}")
    print(f"Salary stats across ALL players:")
    print(f"  Max salary: ${df_all['Salary'].max()} ({df_all.loc[df_all['Salary'].idxmax()]['Nickname']} - {df_all.loc[df_all['Salary'].idxmax()]['Position']})")
    print(f"  Min salary: ${df_all['Salary'].min()}")
    print(f"  Median salary: ${df_all['Salary'].median()}")
    print(f"  Mean salary: ${df_all['Salary'].mean():.1f}")
    
    # Salary percentiles across all players
    df_all['Overall_Salary_Rank'] = df_all['Salary'].rank(ascending=False, method='min')
    df_all['Overall_Salary_Percentile'] = df_all['Salary'].rank(pct=True) * 100

    # 2. Schedule & Vegas Lines
    sched = await nfl_schedule_client.fetch_week_schedule(season=2026, week=1)
    
    # Team to Vegas info mapping
    team_vegas = {}
    for g in sched:
        # Home team
        team_vegas[g.home_team] = {
            'opponent': g.away_team,
            'is_home': True,
            'game': f"{g.away_team}@{g.home_team}",
            'over_under': g.over_under,
            'spread': g.spread, # negative means favored
            'team_implied_total': g.home_implied_total,
            'opp_implied_total': g.away_implied_total,
            'is_favorite': g.spread < 0,
            'spread_margin': abs(g.spread),
            'is_dome': g.is_dome
        }
        # Away team
        team_vegas[g.away_team] = {
            'opponent': g.home_team,
            'is_home': False,
            'game': f"{g.away_team}@{g.home_team}",
            'over_under': g.over_under,
            'spread': -g.spread, # negative means favored from away perspective
            'team_implied_total': g.away_implied_total,
            'opp_implied_total': g.home_implied_total,
            'is_favorite': g.spread > 0,
            'spread_margin': abs(g.spread),
            'is_dome': g.is_dome
        }
    
    # Aliases
    if 'WSH' in team_vegas and 'WAS' not in team_vegas:
        team_vegas['WAS'] = team_vegas['WSH']
    if 'JAX' in team_vegas and 'JAC' not in team_vegas:
        team_vegas['JAC'] = team_vegas['JAX']

    # 3. DvP for RBs from DB
    conn = sqlite3.connect('data/fantasy.db')
    df_dvp = pd.read_sql_query("SELECT * FROM defense_vs_position WHERE position='RB'", conn)
    dvp_map = {}
    for _, row in df_dvp.iterrows():
        team = row['pro_team']
        stats = json.loads(row['supporting_stats_json']) if row['supporting_stats_json'] else {}
        dvp_map[team] = {
            'softness_rank': row['rank_softness'], # 1 = softest (best for offense)
            'defense_rank': row['rank_defense'],   # 32 = worst defense (best for offense)
            'tier': row['tier'],
            'tier_label': row['tier_label'],
            'fd_fpa': row['fd_fpa'],
            'dk_fpa': row['dk_fpa'],
            'vs_avg': row['vs_avg'],
            'rush_yds_allowed': stats.get('rush_yds', 0.0),
            'rush_td_allowed': stats.get('rush_td', 0.0),
            'rec_yds_allowed': stats.get('rec_yds', 0.0),
            'rec_allowed': stats.get('rec', 0.0)
        }
    if 'WSH' in dvp_map and 'WAS' not in dvp_map:
        dvp_map['WAS'] = dvp_map['WSH']
    if 'JAX' in dvp_map and 'JAC' not in dvp_map:
        dvp_map['JAC'] = dvp_map['JAX']

    # 4. Filter RBs on the slate
    rbs = df_all[df_all['Position'] == 'RB'].copy()
    print(f"\nTotal RBs on slate: {len(rbs)}")

    # Enrich each RB
    enriched_rbs = []
    for _, rb in rbs.iterrows():
        name = rb['Nickname']
        team = rb['Team']
        opp = rb['Opponent']
        salary = rb['Salary']
        fppg = rb['FPPG']
        played = rb['Played']
        inj = rb['Injury Indicator']
        inj_det = rb['Injury Details']

        # Skip players on IR or Out if known, or 0 played/backup with 0 salary utility
        v_info = team_vegas.get(team, {})
        if not v_info:
            continue
        
        # DvP of the opponent defense
        opp_alias = 'WSH' if opp == 'WAS' else ('JAX' if opp == 'JAC' else opp)
        dvp_info = dvp_map.get(opp, dvp_map.get(opp_alias, {}))

        # Vegas Props
        # Extract props from vegas_props_client
        props = await vegas_props_client.get_player_props(
            player_id=int(rb['Id'].split('-')[1]) if '-' in str(rb['Id']) else 0,
            player_name=name,
            position='RB',
            team=team,
            opponent=opp,
            week=1,
            season=2026,
            implied_team_total=v_info.get('team_implied_total', 22.0),
            spread=v_info.get('spread', 0.0),
            over_under=v_info.get('over_under', 44.0),
            projected_points=fppg if fppg > 0 else 10.0
        )

        # Calculate metrics
        # FanDuel standard value: 2.0x is minimum, 2.5x is good ($60k cap, 150 pts = 2.5x), 3.0x is tournament winning
        fd_pts_est = props.implied_ppr_points - (props.receptions_ou or 0.0) * 0.5 # FanDuel is 0.5 PPR!
        value_ratio_fppg = (fppg / (salary / 1000)) if salary > 0 else 0
        value_ratio_props = (props.implied_ppr_points / (salary / 1000)) if salary > 0 else 0
        value_ratio_fd = (fd_pts_est / (salary / 1000)) if salary > 0 else 0

        enriched_rbs.append({
            'name': name,
            'team': team,
            'opponent': opp,
            'salary': salary,
            'overall_salary_rank': int(rb['Overall_Salary_Rank']),
            'fppg': round(fppg, 2),
            'played': played,
            'injury': inj if pd.notna(inj) else '',
            'injury_details': inj_det if pd.notna(inj_det) else '',
            # Vegas team info
            'game_ou': v_info.get('over_under'),
            'team_implied': v_info.get('team_implied_total'),
            'spread': v_info.get('spread'),
            'is_fav': v_info.get('is_favorite'),
            'is_home': v_info.get('is_home'),
            'is_dome': v_info.get('is_dome'),
            # DvP info
            'opp_softness_rank': dvp_info.get('softness_rank', 16), # 1 is best
            'opp_tier': dvp_info.get('tier', 'NEUTRAL'),
            'opp_tier_label': dvp_info.get('tier_label', 'Neutral'),
            'opp_fd_fpa': dvp_info.get('fd_fpa', 20.0),
            'opp_vs_avg': dvp_info.get('vs_avg', 0.0),
            'opp_rush_yds_allowed': dvp_info.get('rush_yds_allowed', 0.0),
            'opp_rush_td_allowed': dvp_info.get('rush_td_allowed', 0.0),
            # Props
            'rush_yds_ou': props.rush_yards_ou,
            'rush_att_ou': props.rush_att_ou,
            'rec_ou': props.receptions_ou,
            'rec_yds_ou': props.rec_yards_ou,
            'atd_odds': props.anytime_td_odds,
            'atd_prob': props.anytime_td_prob,
            'vegas_implied_ppr': round(props.implied_ppr_points, 2),
            'vegas_implied_fd': round(fd_pts_est, 2),
            'vegas_grade': props.vegas_grade,
            'vegas_grade_label': props.vegas_grade_label,
            'val_ratio_fd': round(value_ratio_fd, 2),
            'val_ratio_props': round(value_ratio_props, 2),
            'val_ratio_fppg': round(value_ratio_fppg, 2),
        })

    df_res = pd.DataFrame(enriched_rbs)
    
    # Filter out IR / Inactive players (e.g. Josh Jacobs is IR in CSV)
    active_rbs = df_res[~df_res['injury'].isin(['IR', 'O'])].copy()
    
    # Sort active RBs with significant salary (>= $4500)
    viable_rbs = active_rbs[active_rbs['salary'] >= 4800].copy()
    
    print("\n--- ALL VIABLE RBs (Salary >= $4800) SORTED BY SALARY ---")
    print(viable_rbs[['name', 'team', 'opponent', 'salary', 'team_implied', 'game_ou', 'spread', 'opp_softness_rank', 'opp_tier', 'rush_yds_ou', 'atd_prob', 'vegas_implied_fd', 'val_ratio_fd']].sort_values(by='salary', ascending=False).to_string())

    # Sort by Vegas Implied FD points
    print("\n--- TOP RBs BY VEGAS IMPLIED FANDUEL POINTS ---")
    print(viable_rbs[['name', 'team', 'opponent', 'salary', 'team_implied', 'game_ou', 'spread', 'opp_softness_rank', 'rush_yds_ou', 'atd_prob', 'vegas_implied_fd', 'val_ratio_fd']].sort_values(by='vegas_implied_fd', ascending=False).head(15).to_string())

    # Sort by Value Ratio (FD Points per $1k)
    print("\n--- TOP RBs BY VALUE (Points per $1K) ---")
    print(viable_rbs[['name', 'team', 'opponent', 'salary', 'team_implied', 'game_ou', 'spread', 'opp_softness_rank', 'rush_yds_ou', 'atd_prob', 'vegas_implied_fd', 'val_ratio_fd']].sort_values(by='val_ratio_fd', ascending=False).head(15).to_string())

if __name__ == '__main__':
    asyncio.run(run_analysis())
