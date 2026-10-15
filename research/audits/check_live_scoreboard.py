import urllib.request
import json

url = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print('Week:', data.get('week', {}).get('number'))
        print('Season:', data.get('season', {}).get('year'))
        events = data.get('events', [])
        print(f'Total events: {len(events)}')
        for ev in events:
            ev_id = ev.get('id')
            name = ev.get('name')
            status = ev.get('status', {}).get('type', {}).get('description')
            detail = ev.get('status', {}).get('type', {}).get('detail')
            comp = ev.get('competitions', [{}])[0]
            scores = []
            for c in comp.get('competitors', []):
                tm = c.get('team', {}).get('abbreviation')
                sc = c.get('score')
                scores.append(f"{tm} {sc}")
            print(f"ID {ev_id}: {name} | {status} ({detail}) | {' - '.join(scores)}")
except Exception as e:
    print('Error:', e)
