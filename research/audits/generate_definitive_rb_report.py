import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import sqlite3
import pandas as pd
import json
import asyncio
from src.adapters.betting.props_client import vegas_props_client
from src.adapters.nfl.schedule_client import nfl_schedule_client

async def generate_definitive_data():
    csv_path = 'data/FanDuel-NFL-2026 MDT-09 MDT-13 MDT-133104-players-list.csv'
    df_all = pd.read_csv(csv_path)

    # All players salary stats
    total_players = len(df_all)
    df_all['Overall_Salary_Rank'] = df_all['Salary'].rank(ascending=False, method='min').astype(int)
    df_all['Overall_Salary_Pct'] = (df_all['Salary'].rank(pct=True) * 100).round(1)

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
            'venue': g.venue_name
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
            'softness_rank': row['rank_softness'], # 1 = softest, 32 = toughest
            'defense_rank': row['rank_defense'],
            'tier': row['tier'],
            'tier_label': row['tier_label'],
            'fd_fpa': row['fd_fpa'],
            'rush_yds_allowed': stats.get('rush_yds', 0.0),
            'rush_td_allowed': stats.get('rush_td', 0.0),
            'rec_allowed': stats.get('rec', 0.0),
            'rec_yds_allowed': stats.get('rec_yds', 0.0),
        }
    if 'WAS' in dvp_map: dvp_map['WSH'] = dvp_map['WAS']
    if 'JAC' in dvp_map: dvp_map['JAX'] = dvp_map['JAC']

    # Players table mapping
    df_db_players = pd.read_sql_query("SELECT id, full_name, pro_team, injury_status, projected_points FROM players WHERE position='RB'", conn)
    db_player_map = {}
    for _, r in df_db_players.iterrows():
        db_player_map[(r['full_name'].strip().lower(), r['pro_team'])] = {
            'db_proj': r['projected_points'],
            'db_status': r['injury_status']
        }

    # Filter RBs from CSV
    rbs = df_all[df_all['Position'] == 'RB'].copy()

    records = []
    for _, rb in rbs.iterrows():
        name = rb['Nickname']
        team = rb['Team']
        opp = rb['Opponent']
        salary = rb['Salary']
        fppg = rb['FPPG']
        played = rb['Played']
        inj = rb['Injury Indicator'] if pd.notna(rb['Injury Indicator']) else ''
        inj_det = rb['Injury Details'] if pd.notna(rb['Injury Details']) else ''
        sal_rank = rb['Overall_Salary_Rank']
        sal_pct = rb['Overall_Salary_Pct']

        v = team_vegas.get(team)
        if not v:
            continue

        opp_key = 'WAS' if opp in ['WAS', 'WSH'] else ('JAC' if opp in ['JAC', 'JAX'] else opp)
        dvp = dvp_map.get(opp, dvp_map.get(opp_key, {}))

        # DB player match
        db_info = db_player_map.get((name.strip().lower(), team), {})
        db_proj = db_info.get('db_proj', fppg)
        db_status = db_info.get('db_status', 'ACTIVE')

        # Ensure valid float for projected points
        valid_proj = 10.0
        if pd.notna(db_proj) and db_proj > 0:
            valid_proj = float(db_proj)
        elif pd.notna(fppg) and fppg > 0:
            valid_proj = float(fppg)

        # Vegas Props
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
            over_under=v.get('game_ou', 44.0),
            projected_points=valid_proj
        )

        fd_implied = props.implied_ppr_points - (props.receptions_ou or 0.0) * 0.5
        value_fd_props = round(fd_implied / (salary / 1000), 2)
        value_db = round(db_proj / (salary / 1000), 2) if db_proj > 0 else 0.0

        # Composite score
        # Base projection: blend of db_proj (40%) and fd_implied (60%)
        blended_proj = round(db_proj * 0.4 + fd_implied * 0.6, 2)
        
        # Matchup impact: softness rank 1 = +2.25 pts, softness rank 32 = -2.25 pts
        soft_rank = dvp.get('softness_rank', 16)
        matchup_diff = round((16.5 - soft_rank) * 0.15, 2)
        
        # Game script impact:
        # Favorites by >= 3 pts get positive clock-killing rush volume bonus (+1.0 to +2.5)
        # Heavy dogs (spread >= +6.0) get pass-script penalty for rushing yards (-1.2) unless high pass catcher
        script_bonus = 0.0
        if v.get('is_fav') and v.get('fav_margin', 0) >= 3.0:
            script_bonus = 1.5 if v.get('fav_margin', 0) < 7.0 else 2.2
        elif not v.get('is_fav') and abs(v.get('spread', 0)) >= 6.0:
            script_bonus = -1.2

        # Final algorithm composite
        final_composite = round(blended_proj + matchup_diff + script_bonus, 2)
        value_composite = round(final_composite / (salary / 1000), 2)

        records.append({
            'name': name,
            'team': team,
            'opp': opp,
            'salary': salary,
            'sal_rank_overall': sal_rank,
            'sal_pct_overall': sal_pct,
            'injury': inj,
            'inj_details': inj_det,
            'db_status': db_status,
            'db_proj': db_proj,
            # Vegas environment
            'team_implied': v.get('team_implied'),
            'game_ou': v.get('game_ou'),
            'spread': v.get('spread'),
            'fav_margin': v.get('fav_margin'),
            'is_fav': v.get('is_fav'),
            'is_home': v.get('is_home'),
            'is_dome': v.get('is_dome'),
            # Defensive Matchup (DvP)
            'opp_soft_rank': dvp.get('softness_rank'), # 1 = softest
            'opp_tier': dvp.get('tier'),
            'opp_tier_label': dvp.get('tier_label'),
            'opp_fd_fpa': dvp.get('fd_fpa'),
            'opp_rush_yds_allowed': dvp.get('rush_yds_allowed'),
            'opp_rush_td_allowed': dvp.get('rush_td_allowed'),
            # Vegas Props
            'rush_yds_ou': props.rush_yards_ou,
            'rush_att_ou': props.rush_att_ou,
            'rec_ou': props.receptions_ou,
            'rec_yds_ou': props.rec_yards_ou,
            'atd_prob': props.anytime_td_prob,
            'atd_odds': props.anytime_td_odds,
            'fd_implied': round(fd_implied, 2),
            # Projections & Value
            'blended_proj': blended_proj,
            'final_composite': final_composite,
            'value_composite': value_composite,
            'value_db': value_db,
            'vegas_grade': props.vegas_grade,
            'vegas_takeaway': props.vegas_takeaway
        })

    df = pd.DataFrame(records)
    # Filter out IR / Out
    df = df[~df['injury'].isin(['IR', 'O']) & ~df['db_status'].isin(['IR', 'OUT', 'DAY_TO_DAY'])].copy()
    
    # Save complete table
    df.sort_values(by='final_composite', ascending=False).to_csv('data/final_rb_evaluation.csv', index=False)
    
    print("--- TOP 20 RBs BY FINAL COMPOSITE SCORE ---")
    cols = ['name', 'team', 'opp', 'salary', 'team_implied', 'spread', 'opp_soft_rank', 'rush_yds_ou', 'atd_prob', 'fd_implied', 'final_composite', 'value_composite']
    print(df.sort_values(by='final_composite', ascending=False)[cols].head(20).to_string())

    print("\n--- TOP 20 RBs BY SALARY VALUE RATIO (Pts/$1k, Min Proj >= 9.0) ---")
    print(df[df['final_composite'] >= 9.0].sort_values(by='value_composite', ascending=False)[cols].head(20).to_string())

if __name__ == '__main__':
    asyncio.run(generate_definitive_data())
