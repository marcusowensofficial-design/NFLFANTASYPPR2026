import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import sqlite3
import pandas as pd
import numpy as np
import json
import asyncio
from scipy.optimize import milp, LinearConstraint
from src.adapters.betting.props_client import vegas_props_client
from src.adapters.nfl.schedule_client import nfl_schedule_client

async def optimize_slate():
    csv_path = 'data/FanDuel-NFL-2026 MDT-09 MDT-13 MDT-133104-players-list.csv'
    df_raw = pd.read_csv(csv_path)

    # Schedule mapping
    sched = await nfl_schedule_client.fetch_week_schedule(season=2026, week=1)
    team_vegas = {}
    for g in sched:
        team_vegas[g.home_team] = {
            'opp': g.away_team,
            'is_home': True,
            'game_ou': g.over_under,
            'spread': g.spread,
            'team_implied': g.home_implied_total,
            'opp_implied': g.away_implied_total,
            'is_fav': g.spread < 0,
            'fav_margin': abs(g.spread) if g.spread < 0 else -abs(g.spread),
            'is_dome': g.is_dome,
        }
        team_vegas[g.away_team] = {
            'opp': g.home_team,
            'is_home': False,
            'game_ou': g.over_under,
            'spread': -g.spread,
            'team_implied': g.away_implied_total,
            'opp_implied': g.home_implied_total,
            'is_fav': g.spread > 0,
            'fav_margin': abs(g.spread) if g.spread > 0 else -abs(g.spread),
            'is_dome': g.is_dome,
        }
    team_vegas['WAS'] = team_vegas.get('WSH', {})
    team_vegas['JAC'] = team_vegas.get('JAX', {})

    # DvP mapping
    conn = sqlite3.connect('data/fantasy.db')
    df_dvp = pd.read_sql_query("SELECT * FROM defense_vs_position", conn)
    dvp_map = {}
    for _, row in df_dvp.iterrows():
        team = row['pro_team']
        pos = row['position']
        dvp_map[(team, pos)] = {
            'softness_rank': row['rank_softness'], # 1 = softest
            'fd_fpa': row['fd_fpa'],
            'tier': row['tier']
        }
        if team == 'WAS': dvp_map[('WSH', pos)] = dvp_map[(team, pos)]
        if team == 'JAC': dvp_map[('JAX', pos)] = dvp_map[(team, pos)]

    # DB player projections
    df_db_players = pd.read_sql_query("SELECT id, full_name, pro_team, position, injury_status, projected_points FROM players", conn)
    db_map = {}
    for _, r in df_db_players.iterrows():
        db_map[(r['full_name'].strip().lower(), r['pro_team'])] = {
            'db_proj': r['projected_points'],
            'status': r['injury_status']
        }

    # Filter players
    players = []
    for _, r in df_raw.iterrows():
        name = r['Nickname']
        pos = r['Position']
        team = r['Team']
        opp = r['Opponent']
        salary = r['Salary']
        fppg = r['FPPG']
        played = r['Played']
        inj = r['Injury Indicator'] if pd.notna(r['Injury Indicator']) else ''
        inj_det = r['Injury Details'] if pd.notna(r['Injury Details']) else ''

        # Skip injured / inactive players
        if inj in ['IR', 'O']:
            continue

        v = team_vegas.get(team, {})
        if not v:
            continue

        # Check DB
        db_info = db_map.get((name.strip().lower(), team), {})
        if db_info.get('status') in ['IR', 'OUT', 'DAY_TO_DAY'] and db_info.get('db_proj', 0) == 0:
            continue
        
        db_proj = db_info.get('db_proj', fppg)
        
        # DvP
        opp_key = 'WAS' if opp in ['WAS', 'WSH'] else ('JAC' if opp in ['JAC', 'JAX'] else opp)
        dvp = dvp_map.get((opp, pos), dvp_map.get((opp_key, pos), {}))
        soft_rank = dvp.get('softness_rank', 16)

        # Baseline projection
        base_proj = db_proj if (pd.notna(db_proj) and db_proj > 0) else (fppg if (pd.notna(fppg) and fppg > 0) else 5.0)

        # Defense specific
        if pos == 'D':
            # D/ST scoring: heavily correlated with low opponent implied total, being a favorite, and sack potential
            opp_implied = v.get('opp_implied', 22.0)
            is_fav = v.get('is_fav', False)
            margin = v.get('fav_margin', 0.0)
            dst_proj = max(3.0, (25.0 - opp_implied) * 0.4 + (3.0 if is_fav else 0.0) + (margin * 0.2) + (fppg * 0.4))
            base_proj = round(dst_proj, 2)
        else:
            # Skill player adjustments
            # Matchup adjustment
            matchup_adj = (16.5 - soft_rank) * 0.12
            # Implied total adjustment
            implied_adj = (v.get('team_implied', 22.0) - 22.0) * 0.25
            # Game script adjustment for RBs
            script_adj = 0.0
            if pos == 'RB':
                if v.get('is_fav') and v.get('fav_margin', 0) >= 3.0:
                    script_adj = 1.2
                elif not v.get('is_fav') and abs(v.get('spread', 0)) >= 6.0:
                    script_adj = -0.8
            base_proj = round(base_proj + matchup_adj + implied_adj + script_adj, 2)

        players.append({
            'id': r['Id'],
            'name': name,
            'pos': pos,
            'team': team,
            'opp': opp,
            'salary': salary,
            'fppg': fppg,
            'proj': max(1.0, base_proj),
            'team_implied': v.get('team_implied'),
            'game_ou': v.get('game_ou'),
            'spread': v.get('spread'),
            'soft_rank': soft_rank
        })

    df = pd.DataFrame(players)
    print(f"Total viable players evaluated: {len(df)}")
    print(df.groupby('pos')['proj'].agg(['count', 'min', 'max', 'mean']))

    # Let's save evaluated players
    df.to_csv('data/optimized_player_pool.csv', index=False)

    return df

if __name__ == '__main__':
    asyncio.run(optimize_slate())
