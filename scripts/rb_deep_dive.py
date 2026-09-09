import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import sqlite3
import pandas as pd
import json
import asyncio
from src.adapters.betting.props_client import vegas_props_client
from src.adapters.nfl.schedule_client import nfl_schedule_client

async def full_rb_deep_dive():
    csv_path = 'data/FanDuel-NFL-2026 MDT-09 MDT-13 MDT-133104-players-list.csv'
    df_all = pd.read_csv(csv_path)

    # Schedule mapping
    sched = await nfl_schedule_client.fetch_week_schedule(season=2026, week=1)
    team_vegas = {}
    for g in sched:
        team_vegas[g.home_team] = {
            'opponent': g.away_team,
            'is_home': True,
            'over_under': g.over_under,
            'spread': g.spread,
            'team_implied': g.home_implied_total,
            'opp_implied': g.away_implied_total,
            'is_fav': g.spread < 0,
            'fav_margin': abs(g.spread) if g.spread < 0 else -abs(g.spread),
            'is_dome': g.is_dome,
            'venue': g.venue_name
        }
        team_vegas[g.away_team] = {
            'opponent': g.home_team,
            'is_home': False,
            'over_under': g.over_under,
            'spread': -g.spread,
            'team_implied': g.away_implied_total,
            'opp_implied': g.home_implied_total,
            'is_fav': g.spread > 0,
            'fav_margin': abs(g.spread) if g.spread > 0 else -abs(g.spread),
            'is_dome': g.is_dome,
            'venue': g.venue_name
        }
    team_vegas['WAS'] = team_vegas.get('WSH', {})
    team_vegas['JAC'] = team_vegas.get('JAX', {})

    # DvP mapping
    conn = sqlite3.connect('data/fantasy.db')
    df_dvp = pd.read_sql_query("SELECT * FROM defense_vs_position WHERE position='RB'", conn)
    dvp_map = {}
    for _, row in df_dvp.iterrows():
        team = row['pro_team']
        stats = json.loads(row['supporting_stats_json']) if row['supporting_stats_json'] else {}
        dvp_map[team] = {
            'softness_rank': row['rank_softness'], # 1 = softest (easiest for RB), 32 = toughest
            'defense_rank': row['rank_defense'],   # 32 = worst defense, 1 = best defense
            'tier': row['tier'],
            'tier_label': row['tier_label'],
            'fd_fpa': row['fd_fpa'],
            'dk_fpa': row['dk_fpa'],
            'vs_avg': row['vs_avg'],
            'rush_yds_allowed': stats.get('rush_yds', 0.0),
            'rush_td_allowed': stats.get('rush_td', 0.0),
            'rec_allowed': stats.get('rec', 0.0),
            'rec_yds_allowed': stats.get('rec_yds', 0.0),
        }
    if 'WAS' in dvp_map and 'WSH' not in dvp_map:
        dvp_map['WSH'] = dvp_map['WAS']
    elif 'WSH' in dvp_map and 'WAS' not in dvp_map:
        dvp_map['WAS'] = dvp_map['WSH']
    if 'JAC' in dvp_map and 'JAX' not in dvp_map:
        dvp_map['JAX'] = dvp_map['JAC']
    elif 'JAX' in dvp_map and 'JAC' not in dvp_map:
        dvp_map['JAC'] = dvp_map['JAX']

    # RBs
    rbs = df_all[df_all['Position'] == 'RB'].copy()
    
    rb_list = []
    for _, rb in rbs.iterrows():
        name = rb['Nickname']
        team = rb['Team']
        opp = rb['Opponent']
        salary = rb['Salary']
        fppg = rb['FPPG']
        played = rb['Played']
        inj = rb['Injury Indicator'] if pd.notna(rb['Injury Indicator']) else ''
        inj_det = rb['Injury Details'] if pd.notna(rb['Injury Details']) else ''

        v = team_vegas.get(team, {})
        if not v:
            continue
        
        opp_key = 'WSH' if opp == 'WAS' else ('JAX' if opp == 'JAC' else opp)
        dvp = dvp_map.get(opp, dvp_map.get(opp_key, {}))

        # Fetch Vegas props
        pid = int(rb['Id'].split('-')[1]) if '-' in str(rb['Id']) else 0
        props = await vegas_props_client.get_player_props(
            player_id=pid,
            player_name=name,
            position='RB',
            team=team,
            opponent=opp,
            week=1,
            season=2026,
            implied_team_total=v.get('team_implied', 22.0),
            spread=v.get('spread', 0.0),
            over_under=v.get('over_under', 44.0),
            projected_points=fppg if fppg > 0 else 10.0
        )

        fd_implied = props.implied_ppr_points - (props.receptions_ou or 0.0) * 0.5
        value_fd = round(fd_implied / (salary / 1000), 2)
        value_fppg = round(fppg / (salary / 1000), 2)

        # Composite RB Score combining:
        # 1. Base Vegas Implied FD points
        # 2. Matchup softness bonus (softness_rank 1-32: rank 1 adds ~+2.0, rank 32 subtracts ~-2.0)
        # 3. Game Script bonus: Favorites by 3+ points get positive game script bonus (+1.0 to +2.5)
        # 4. Implied Total bonus: team total >= 24 adds equity (+1.0 to +2.0)
        # 5. TD probability bonus
        matchup_adj = (16.5 - dvp.get('softness_rank', 16)) * 0.15 # e.g. Rank 1 = +2.3 pts, Rank 32 = -2.3 pts
        game_script_adj = 1.5 if (v.get('is_fav') and v.get('fav_margin', 0) >= 3.0) else (-1.0 if (not v.get('is_fav') and abs(v.get('spread', 0)) >= 6.0) else 0.0)
        
        composite_proj = fd_implied + matchup_adj + game_script_adj
        salary_efficiency = composite_proj / (salary / 1000)

        rb_list.append({
            'name': name,
            'team': team,
            'opp': opp,
            'salary': salary,
            'fppg': round(fppg, 2),
            'played': played,
            'injury': inj,
            'inj_details': inj_det,
            'game': f"{opp}@{team}" if v.get('is_home') else f"{team}@{opp}",
            'is_home': v.get('is_home'),
            'is_dome': v.get('is_dome'),
            'team_implied': v.get('team_implied'),
            'game_ou': v.get('over_under'),
            'spread': v.get('spread'),
            'is_fav': v.get('is_fav'),
            'fav_margin': v.get('fav_margin'),
            'opp_softness_rank': dvp.get('softness_rank'),
            'opp_tier': dvp.get('tier'),
            'opp_fd_fpa': dvp.get('fd_fpa'),
            'opp_rush_yds_allowed': dvp.get('rush_yds_allowed'),
            'opp_rush_td_allowed': dvp.get('rush_td_allowed'),
            'rush_yds_ou': props.rush_yards_ou,
            'rush_att_ou': props.rush_att_ou,
            'rec_ou': props.receptions_ou,
            'atd_prob': props.anytime_td_prob,
            'atd_odds': props.anytime_td_odds,
            'vegas_implied_fd': round(fd_implied, 2),
            'value_fd': value_fd,
            'composite_proj': round(composite_proj, 2),
            'salary_efficiency': round(salary_efficiency, 2),
            'vegas_grade': props.vegas_grade,
            'vegas_takeaway': props.vegas_takeaway
        })

    df_rbs = pd.DataFrame(rb_list)
    # Exclude injured players like Josh Jacobs (IR)
    df_rbs = df_rbs[~df_rbs['injury'].isin(['IR', 'O'])].copy()
    
    # Save to a structured CSV for review
    df_rbs.to_csv('data/analyzed_rbs_slate.csv', index=False)
    
    # Let's see top by composite_proj and salary_efficiency
    print("--- TOP 15 RBs BY COMPOSITE PROJECTION ---")
    print(df_rbs.sort_values(by='composite_proj', ascending=False)[['name', 'team', 'opp', 'salary', 'team_implied', 'spread', 'opp_softness_rank', 'rush_yds_ou', 'atd_prob', 'vegas_implied_fd', 'composite_proj', 'salary_efficiency']].head(15).to_string())

    print("\n--- TOP 15 RBs BY SALARY EFFICIENCY (Min Salary $5000) ---")
    print(df_rbs[df_rbs['salary'] >= 5000].sort_values(by='salary_efficiency', ascending=False)[['name', 'team', 'opp', 'salary', 'team_implied', 'spread', 'opp_softness_rank', 'rush_yds_ou', 'atd_prob', 'vegas_implied_fd', 'composite_proj', 'salary_efficiency']].head(15).to_string())

    print("\n--- TOP VALUE RBs ($4500 - $6500) ---")
    print(df_rbs[(df_rbs['salary'] >= 4500) & (df_rbs['salary'] <= 6500)].sort_values(by='salary_efficiency', ascending=False)[['name', 'team', 'opp', 'salary', 'team_implied', 'spread', 'opp_softness_rank', 'rush_yds_ou', 'atd_prob', 'vegas_implied_fd', 'composite_proj', 'salary_efficiency']].head(15).to_string())

if __name__ == '__main__':
    asyncio.run(full_rb_deep_dive())
