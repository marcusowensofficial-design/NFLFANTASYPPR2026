import json

dvp = json.load(open('data/nfl_dvp_proprietary_2026.json'))
for pos in ['QB', 'RB', 'WR', 'TE']:
    print(f"\n=== PROPRIETARY DVP RANKINGS VS {pos} ===")
    for item in dvp[pos]:
        if item.get('pro_team') in ['BUF', 'DET']:
            team = item.get('pro_team')
            def_rank = item.get('rank_defense')
            soft_rank = item.get('rank_softness')
            tier = item.get('tier_label')
            fpa = item.get('fd_fpa')
            stats = item.get('supporting_stats', {})
            print(f"[{team}] Defense Rank: {def_rank}/32 (Softness #{soft_rank}) | Tier: {tier} | FD FPA: {fpa} pts")
            print(f"       Supporting: {stats}")
