"""
backfill_free.py - Complete missing top-5 league results from free no-key sources.

Sources (no registration, no API key):
  * football-data.co.uk  -> PL (E0), La Liga (SP1), Serie A (I1), Ligue 1 (F1)
  * OpenLigaDB           -> Bundesliga (bl1) with full 2026 fixtures

Only appends matches NOT already present in data/results.csv. Derives
comeback/blown-lead drama flags from half-time vs full-time score (minute-level
flags like f15/late_win need goal events we don't have here, so they're omitted).

Usage:
    python backfill_free.py            # fetch and append
    python backfill_free.py --dry      # preview without writing
"""
import csv
import io
import json
import os
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
RESULTS_CSV = os.path.join(DATA, 'results.csv')

FD_BASE = 'https://www.football-data.co.uk/mmz4281/2627/'
OPENLIGA = 'https://www.openligadb.de/api/getmatchdata/bl1/2026'

# football-data.co.uk short team name -> canonical engine name
FD_TEAMS = {
    # PL
    'Arsenal': 'Arsenal', 'Aston Villa': 'Aston Villa', 'Bournemouth': 'Bournemouth',
    'Brentford': 'Brentford', 'Brighton': 'Brighton & Hove Albion', 'Chelsea': 'Chelsea',
    'Coventry': 'Coventry City', 'Crystal Palace': 'Crystal Palace', 'Everton': 'Everton',
    'Fulham': 'Fulham', 'Hull': 'Hull City', 'Ipswich': 'Ipswich Town',
    'Leeds': 'Leeds United', 'Liverpool': 'Liverpool', 'Man City': 'Manchester City',
    'Man United': 'Manchester United', 'Newcastle': 'Newcastle United',
    "Nott'm Forest": 'Nottingham Forest', 'Sunderland': 'Sunderland',
    'Tottenham': 'Tottenham Hotspur',
    # La Liga
    'Alaves': 'Alaves', 'Ath Bilbao': 'Athletic Club', 'Ath Madrid': 'Atletico Madrid',
    'Barcelona': 'Barcelona', 'Betis': 'Real Betis', 'Celta': 'Celta Vigo',
    'Elche': 'Elche', 'Espanol': 'Espanyol', 'Getafe': 'Getafe',
    'La Coruna': 'Deportivo La Coruna', 'Levante': 'Levante', 'Malaga': 'Malaga',
    'Osasuna': 'Osasuna', 'Real Madrid': 'Real Madrid', 'Santander': 'Racing Santander',
    'Sevilla': 'Sevilla', 'Sociedad': 'Real Sociedad', 'Valencia': 'Valencia',
    'Vallecano': 'Rayo Vallecano', 'Villarreal': 'Villarreal',
    # Serie A
    'Atalanta': 'Atalanta', 'Bologna': 'Bologna', 'Cagliari': 'Cagliari',
    'Como': 'Como', 'Fiorentina': 'Fiorentina', 'Frosinone': 'Frosinone',
    'Genoa': 'Genoa', 'Inter': 'Inter Milan', 'Juventus': 'Juventus',
    'Lazio': 'Lazio', 'Lecce': 'Lecce', 'Milan': 'AC Milan', 'Monza': 'Monza',
    'Napoli': 'Napoli', 'Parma': 'Parma', 'Roma': 'Roma', 'Sassuolo': 'Sassuolo',
    'Torino': 'Torino', 'Udinese': 'Udinese', 'Venezia': 'Venezia',
    # Ligue 1
    'Angers': 'Angers', 'Auxerre': 'Auxerre', 'Brest': 'Brest',
    'Le Havre': 'Le Havre', 'Le Mans': 'Le Mans', 'Lens': 'Lens', 'Lille': 'Lille',
    'Lorient': 'Lorient', 'Lyon': 'Lyon', 'Marseille': 'Marseille',
    'Monaco': 'AS Monaco', 'Nice': 'Nice', 'Paris FC': 'Paris FC',
    'Paris SG': 'Paris Saint-Germain', 'Rennes': 'Rennes', 'Strasbourg': 'Strasbourg',
    'Toulouse': 'Toulouse', 'Troyes': 'Troyes',
}

# OpenLigaDB team name -> canonical engine name (Bundesliga)
OL_TEAMS = {
    '1. FC Köln': '1. FC Koln', '1. FC Union Berlin': 'Union Berlin',
    '1. FSV Mainz 05': 'Mainz 05', 'Bayer 04 Leverkusen': 'Bayer Leverkusen',
    'Borussia Dortmund': 'Borussia Dortmund',
    'Borussia Mönchengladbach': 'Borussia Monchengladbach',
    'Eintracht Frankfurt': 'Eintracht Frankfurt', 'FC Augsburg': 'FC Augsburg',
    'FC Bayern München': 'Bayern Munich', 'FC Schalke 04': 'FC Schalke 04',
    'Hamburger SV': 'Hamburger SV', 'RB Leipzig': 'RB Leipzig',
    'SC Freiburg': 'SC Freiburg', 'SC Paderborn 07': 'SC Paderborn 07',
    'SV 07 Elversberg': 'SV Elversberg', 'SV Werder Bremen': 'Werder Bremen',
    'TSG Hoffenheim': 'Hoffenheim', 'VfB Stuttgart': 'VfB Stuttgart',
}

# OpenLigaDB returns points as strings; goal team names use the same operator names
OL_TEAM_ALT = {
    '1. FC Köln': '1. FC Köln', '1. FC Union Berlin': '1. FC Union Berlin',
    '1. FSV Mainz 05': '1. FSV Mainz 05', 'Bayer 04 Leverkusen': 'Bayer 04 Leverkusen',
    'Borussia Dortmund': 'Borussia Dortmund',
    'Borussia Mönchengladbach': 'Borussia Mönchengladbach',
    'Eintracht Frankfurt': 'Eintracht Frankfurt', 'FC Augsburg': 'FC Augsburg',
    'FC Bayern München': 'FC Bayern München', 'FC Schalke 04': 'FC Schalke 04',
    'Hamburger SV': 'Hamburger SV', 'RB Leipzig': 'RB Leipzig',
    'SC Freiburg': 'SC Freiburg', 'SC Paderborn 07': 'SC Paderborn 07',
    'SV 07 Elversberg': 'SV 07 Elversberg', 'SV Werder Bremen': 'SV Werder Bremen',
    'TSG Hoffenheim': 'TSG Hoffenheim', 'VfB Stuttgart': 'VfB Stuttgart',
}


def read_existing():
    keys = set()
    if not os.path.exists(RESULTS_CSV):
        return keys
    lines = []
    with open(RESULTS_CSV, encoding='utf-8-sig') as f:
        for line in f:
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            lines.append(line)
    if not lines:
        return keys
    for row in csv.DictReader(lines):
        d = (row.get('date') or '').strip()
        c = (row.get('comp') or '').strip()
        h = (row.get('home') or '').strip()
        a = (row.get('away') or '').strip()
        if d and c and h and a:
            keys.add((d, c, h, a))
    return keys


def fmt_date(ddmmyyyy):
    """'21/08/2026' -> '2026-08-21'"""
    d, m, y = ddmmyyyy.strip().split('/')
    return f'{y}-{m.zfill(2)}-{d.zfill(2)}'


def derive_flags(ht_h, ht_a, ft_h, ft_a, home, away):
    """Infer comeback/blown-lead from half-time vs full-time score.
    Flags mirror engine convention: comeback_<side>, blown_<side>."""
    flags = []
    # Home comeback: losing at HT, but level or ahead at FT
    if ht_h < ht_a and ft_h >= ft_a:
        flags.append('comeback_H')
    # Away comeback: losing at HT, but level or ahead at FT
    if ht_a < ht_h and ft_a >= ft_h:
        flags.append('comeback_A')
    # Home blown lead: ahead at HT, but level or behind at FT
    if ht_h > ht_a and ft_h <= ft_a:
        flags.append('blown_H')
    # Away blown lead: ahead at HT, but level or behind at FT
    if ht_a > ht_h and ft_a <= ft_h:
        flags.append('blown_A')
    return flags


def fetch_fd_rows(code):
    """Return list of dicts with canonical teams + scores for a football-data contest."""
    url = FD_BASE + code + '.csv'
    body = urllib.request.urlopen(url, timeout=30).read().decode('utf-8', errors='replace')
    out = []
    for r in csv.DictReader(io.StringIO(body)):
        home = FD_TEAMS.get((r.get('HomeTeam') or '').strip())
        away = FD_TEAMS.get((r.get('AwayTeam') or '').strip())
        fthg = (r.get('FTHG') or '').strip()
        ftag = (r.get('FTAG') or '').strip()
        hthg = (r.get('HTHG') or '').strip()
        htag = (r.get('HTAG') or '').strip()
        if not home or not away or not fthg or not ftag:
            continue
        try:
            ft_h, ft_a = int(fthg), int(ftag)
            ht_h = int(hthg) if hthg else None
            ht_a = int(htag) if htag else None
        except ValueError:
            continue
        flags = derive_flags(ht_h, ht_a, ft_h, ft_a, home, away) if ht_h is not None and ht_a is not None else []
        out.append(dict(
            date=fmt_date(r['Date']), comp='', home=home, away=away,
            hg=ft_h, ag=ft_a, flags=';'.join(flags),
        ))
    return out


def fetch_openliga():
    """Return Bundesliga finished matches with canonical names."""
    d = json.loads(urllib.request.urlopen(OPENLIGA, timeout=30).read())
    out = []
    for m in d:
        if not m.get('matchIsFinished'):
            continue
        h = m['team1']['teamName']
        a = m['team2']['teamName']
        home = OL_TEAMS.get(h)
        away = OL_TEAMS.get(a)
        if not home or not away:
            continue
        res = m.get('matchResults', [])
        if not res:
            continue
        # last result entry holds the final points
        try:
            ft_h = int(res[-1].get('pointsTeam1'))
            ft_a = int(res[-1].get('pointsTeam2'))
        except (TypeError, ValueError):
            continue
        dt = (m.get('matchDateTime') or '')[:10]
        out.append(dict(date=dt, comp='', home=home, away=away, hg=ft_h, ag=ft_a, flags=''))
    return out


def main():
    dry = '--dry' in sys.argv
    existing = read_existing()
    print(f'Existing results: {len(existing)}')

    fds = {
        'PL': ('E0',),
        'LALIGA': ('SP1',),
        'SA': ('I1',),
        'FL1': ('F1',),
    }
    all_new = []
    for comp, (code,) in fds.items():
        try:
            rows = fetch_fd_rows(code)
        except Exception as e:
            print(f'  {comp}: fetch failed: {e}')
            continue
        n = 0
        for r in rows:
            r['comp'] = comp
            key = (r['date'], comp, r['home'], r['away'])
            if key in existing:
                continue
            all_new.append(r)
            n += 1
        print(f'  {comp}: {n} new from football-data.co.uk ({code})')

    try:
        bl = fetch_openliga()
        n = 0
        for r in bl:
            r['comp'] = 'BL1'
            key = (r['date'], 'BL1', r['home'], r['away'])
            if key in existing:
                continue
            all_new.append(r)
            n += 1
        print(f'  BL1: {n} new from OpenLigaDB')
    except Exception as e:
        print(f'  BL1: fetch failed: {e}')

    print(f'\n--- {len(all_new)} new results ---')
    if dry:
        for r in all_new:
            print(f"  DRY: {r['date']} {r['comp']:>5} {r['home']} {r['hg']}-{r['ag']} {r['away']}"
                  f"{' [' + r['flags'] + ']' if r['flags'] else ''}")
        return

    for r in all_new:
        line = f"{r['date']},{r['comp']},,{r['home']},{r['away']},{r['hg']},{r['ag']},,,{r['flags']}\n"
        with open(RESULTS_CSV, 'a', encoding='utf-8') as f:
            f.write(line)
        existing.add((r['date'], r['comp'], r['home'], r['away']))
        print(f"  + {r['date']} {r['comp']:>5} {r['home']} {r['hg']}-{r['ag']} {r['away']}"
              f"{' [' + r['flags'] + ']' if r['flags'] else ''}")

    print(f'\nDone. {len(all_new)} results appended.')


if __name__ == '__main__':
    main()
