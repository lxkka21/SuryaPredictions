import json, time, urllib.request, csv, os

API_BASE = 'https://www.thesportsdb.com/api/v1/json/3'
RESULTS_CSV = 'data/results.csv'

def api_get(path):
    try:
        with urllib.request.urlopen(API_BASE + path, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f'  API error: {e}')
        return None

def read_existing():
    keys = set()
    lines = []
    with open(RESULTS_CSV, encoding='utf-8-sig') as f:
        for line in f:
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            lines.append(line)
    if not lines:
        return keys
    for row in csv.DictReader(lines):
        d = row.get('date', '').strip()
        c = row.get('comp', '').strip()
        h = row.get('home', '').strip()
        a = row.get('away', '').strip()
        if d and c and h and a:
            keys.add((d, c, h, a))
    return keys

PL_TEAMS = {
    133604: 'Arsenal', 133610: 'Chelsea', 133616: 'Everton',
    133612: 'Manchester United', 133613: 'Manchester City',
    133602: 'Liverpool', 133611: 'Tottenham Hotspur',
    133618: 'Newcastle United', 133619: 'Brighton & Hove Albion',
    133620: 'West Ham United', 133621: 'Aston Villa',
    133608: 'Crystal Palace', 133623: 'Wolverhampton Wanderers',
    133622: 'Nottingham Forest', 133601: 'Fulham',
    133624: 'Bournemouth', 133625: 'Brentford',
    133627: 'Leeds United', 133628: 'Leicester City',
    133629: 'Ipswich Town', 133609: 'Southampton',
    133615: 'Sunderland', 133626: 'Coventry City', 133614: 'Hull City',
}

NAME_MAP = {
    'Chelsea': 'Chelsea', 'Luton Town': 'Luton Town',
    'Everton': 'Everton', 'Manchester United': 'Manchester United',
    'Arsenal': 'Arsenal', 'Liverpool': 'Liverpool',
    'Manchester City': 'Manchester City', 'Tottenham Hotspur': 'Tottenham Hotspur',
    'Newcastle United': 'Newcastle United', 'Brighton & Hove Albion': 'Brighton & Hove Albion',
    'West Ham United': 'West Ham United', 'Aston Villa': 'Aston Villa',
    'Crystal Palace': 'Crystal Palace', 'Wolverhampton Wanderers': 'Wolverhampton Wanderers',
    'Nottingham Forest': 'Nottingham Forest', 'Fulham': 'Fulham',
    'Bournemouth': 'Bournemouth', 'Brentford': 'Brentford',
    'Leeds United': 'Leeds United', 'Leicester City': 'Leicester City',
    'Ipswich Town': 'Ipswich Town', 'Southampton': 'Southampton',
    'Sunderland': 'Sunderland', 'Coventry City': 'Coventry City',
    'Hull City': 'Hull City',
}

existing = read_existing()
print(f'Existing: {len(existing)}')
added = 0

for tsdb_id, team_name in PL_TEAMS.items():
    time.sleep(4)
    data = api_get(f'/eventslast.php?id={tsdb_id}')
    if not data or not data.get('results'):
        continue
    results = data['results']
    if not isinstance(results, list):
        results = [results]
    for e in results:
        if e.get('strLeague') != 'EFL Cup' or e.get('strStatus') != 'FT':
            continue
        home_api = e.get('strHomeTeam', '')
        away_api = e.get('strAwayTeam', '')
        date = e.get('dateEvent', '')
        hg = e.get('intHomeScore')
        ag = e.get('intAwayScore')
        if hg is None or ag is None:
            continue
        h = NAME_MAP.get(home_api, home_api)
        a = NAME_MAP.get(away_api, away_api)
        rnd_str = (e.get('intRound', '') or '').lower()
        stage = 'R2'
        if 'final' in rnd_str:
            stage = 'F'
        elif 'semi' in rnd_str:
            stage = 'SF'
        elif 'quarter' in rnd_str:
            stage = 'QF'
        elif 'third' in rnd_str or rnd_str == '3':
            stage = 'R3'
        elif 'first' in rnd_str or rnd_str == '1':
            stage = 'R1'
        elif 'second' in rnd_str or rnd_str == '2':
            stage = 'R2'
        elif rnd_str in ('64', 'round of 64'):
            stage = 'R64'
        elif rnd_str in ('32', 'round of 32'):
            stage = 'R32'
        key = (date, 'LC', h, a)
        if key in existing:
            continue
        with open(RESULTS_CSV, 'a', encoding='utf-8') as f:
            f.write(f'{date},LC,{stage},{h},{a},{hg},{ag},,,\n')
        existing.add(key)
        added += 1
        print(f'  + {date} LC {h} {hg}-{ag} {a} ({stage})')

print(f'Added {added} Carabao Cup results')
