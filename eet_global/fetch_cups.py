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

NAME_MAP = {
    'Bayern Munich': 'Bayern Munich', 'FC Bayern Munich': 'Bayern Munich',
    'Bayer Leverkusen': 'Bayer Leverkusen', 'RB Leipzig': 'RB Leipzig',
    'Borussia Dortmund': 'Borussia Dortmund', 'Eintracht Frankfurt': 'Eintracht Frankfurt',
    'VfB Stuttgart': 'VfB Stuttgart', 'SC Freiburg': 'SC Freiburg',
    'Borussia Monchengladbach': 'Borussia Monchengladbach',
    'Borussia Mönchengladbach': 'Borussia Monchengladbach',
    'Hoffenheim': 'Hoffenheim', 'TSG Hoffenheim': 'Hoffenheim',
    'Mainz 05': 'Mainz 05', 'Mainz': 'Mainz 05',
    'Union Berlin': 'Union Berlin', 'FC Augsburg': 'FC Augsburg',
    'Werder Bremen': 'Werder Bremen', '1. FC Koln': '1. FC Koln',
    'Schalke 04': 'FC Schalke 04', 'FC Schalke 04': 'FC Schalke 04',
    'Hertha': 'Hertha BSC', 'Hertha BSC': 'Hertha BSC',
    'Hannover 96': 'Hannover 96', 'Bochum': 'VfL Bochum', 'VfL Bochum': 'VfL Bochum',
    'Darmstadt': 'SV Darmstadt 98', 'SV Darmstadt 98': 'SV Darmstadt 98',
    'Nürnberg': '1. FC Nurnberg', '1. FC Nurnberg': '1. FC Nurnberg',
    'Arminia Bielefeld': 'Arminia Bielefeld', 'Karlsruhe': 'Karlsruher SC',
    'Karlsruher SC': 'Karlsruher SC', 'Kaiserslautern': '1. FC Kaiserslautern',
    '1. FC Kaiserslautern': '1. FC Kaiserslautern', 'Heidenheim': '1. FC Heidenheim',
    '1. FC Heidenheim': '1. FC Heidenheim', 'Magdeburg': '1. FC Magdeburg',
    '1. FC Magdeburg': '1. FC Magdeburg', 'St Pauli': 'FC St. Pauli',
    'FC St. Pauli': 'FC St. Pauli', 'Paderborn': 'SC Paderborn 07',
    'SC Paderborn 07': 'SC Paderborn 07', 'Elversberg': 'SV Elversberg',
    'SV Elversberg': 'SV Elversberg', '1. FC Saarbrücken': '1. FC Saarbrucken',
    '1. FC Saarbrucken': '1. FC Saarbrucken', 'Dynamo Dresden': 'Dynamo Dresden',
    'Paris Saint-Germain': 'Paris Saint-Germain', 'PSG': 'Paris Saint-Germain',
    'Marseille': 'Marseille', 'Olympique de Marseille': 'Marseille',
    'AS Monaco': 'AS Monaco', 'Monaco': 'AS Monaco',
    'Lyon': 'Lyon', 'Olympique Lyonnais': 'Lyon',
    'Lille': 'Lille', 'LOSC Lille': 'Lille',
    'Nice': 'Nice', 'OGC Nice': 'Nice',
    'Rennes': 'Rennes', 'Stade Rennais': 'Rennes',
    'Lens': 'Lens', 'RC Lens': 'Lens',
    'Strasbourg': 'Strasbourg', 'RC Strasbourg Alsace': 'Strasbourg',
    'Brest': 'Brest', 'Stade Brestois 29': 'Brest',
    'Toulouse': 'Toulouse', 'Toulouse FC': 'Toulouse',
    'Le Havre': 'Le Havre', 'Le Havre AC': 'Le Havre',
    'Angers': 'Angers', 'Angers SCO': 'Angers',
    'Auxerre': 'Auxerre', 'AJ Auxerre': 'Auxerre',
    'Le Mans': 'Le Mans', 'Le Mans FC': 'Le Mans',
    'Troyes': 'Troyes', 'ESTAC Troyes': 'Troyes',
    'Paris FC': 'Paris FC', 'Lorient': 'Lorient', 'FC Lorient': 'Lorient',
}

TEAM_IDS = [
    # Bundesliga
    133650, 134695, 133666, 133814, 133664, 133660,
    133653, 134779, 133657, 133665, 134690, 133652,
    133662, 133654, 133661, 133658, 133656, 133839,
    134693, 133659, 133852, 135293, 133663, 134696,
    136194, 133813, 134551, 138411,
    # Ligue 1
    133691, 133707, 133823, 133713, 133719, 133712,
    133822, 133882, 133704, 133703, 133862, 134709,
    134788, 133848, 134789, 135465, 133715,
]

existing = read_existing()
print(f'Existing: {len(existing)}')
added = 0

for tsdb_id in TEAM_IDS:
    time.sleep(3)
    data = api_get(f'/eventslast.php?id={tsdb_id}')
    if not data or not data.get('results'):
        continue
    results = data['results']
    if not isinstance(results, list):
        results = [results]
    for e in results:
        league = e.get('strLeague', '')
        if league not in ('DFB-Pokal', 'Coupe de France'):
            continue
        if e.get('strStatus') != 'FT':
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
        comp = 'DFB' if league == 'DFB-Pokal' else 'CDF'
        rnd_str = (e.get('intRound', '') or '').lower()
        stage = 'R1'
        if 'final' in rnd_str:
            stage = 'F'
        elif 'semi' in rnd_str:
            stage = 'SF'
        elif 'quarter' in rnd_str:
            stage = 'QF'
        elif 'third' in rnd_str:
            stage = 'R3'
        elif 'second' in rnd_str:
            stage = 'R2'
        elif 'first' in rnd_str:
            stage = 'R1'
        else:
            raw = e.get('intRound', '1')
            stage = f'R{raw}'
        key = (date, comp, h, a)
        if key in existing:
            continue
        with open(RESULTS_CSV, 'a', encoding='utf-8') as f:
            f.write(f'{date},{comp},{stage},{h},{a},{hg},{ag},,,\n')
        existing.add(key)
        added += 1
        print(f'  + {date} {comp} {h} {hg}-{ag} {a} ({stage})')

print(f'Added {added} DFB/CDF results')
