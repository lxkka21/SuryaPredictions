"""
fetch_sportsdb.py - Fetch results from TheSportsDB (free API, covers 2026-27 season).

Usage:
    python fetch_sportsdb.py          # fetch all available results
    python fetch_sportsdb.py --dry    # preview without writing

Appends new results to data/results.csv. Never duplicates.
"""
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
RESULTS_CSV = os.path.join(DATA, 'results.csv')

API_BASE = "https://www.thesportsdb.com/api/v1/json/3"

# TheSportsDB league IDs -> our comp codes
LEAGUE_MAP = {
    4328: 'PL',
    4335: 'LALIGA',
    4331: 'BL1',
    4332: 'SA',
    4334: 'FL1',
    4480: 'UCL',
    4481: 'UEL',
    4482: 'UECL',
    4509: 'FAC',
    4522: 'CDR',
    4527: 'DFB',
    4524: 'CI',
    4531: 'CDF',
    4529: 'CS',
    4570: 'LC',
}

# Max rounds to check per league
MAX_ROUNDS = {
    'PL': 38, 'LALIGA': 38, 'BL1': 34, 'SA': 38, 'FL1': 34,
    'UCL': 15, 'UEL': 15, 'UECL': 15,
    'FAC': 10, 'CDR': 8, 'DFB': 6, 'CI': 8, 'CDF': 8, 'CS': 1,
    'LC': 8,
}

# Our team names -> TheSportsDB team IDs (we'll build a reverse map)
# TheSportsDB team name -> our name mapping
TEAM_OVERRIDES = {
    'Manchester United': 'Manchester United',
    'Manchester City': 'Manchester City',
    'Arsenal': 'Arsenal',
    'Tottenham Hotspur': 'Tottenham Hotspur',
    'Tottenham': 'Tottenham Hotspur',
    'Newcastle United': 'Newcastle United',
    'Brighton & Hove Albion': 'Brighton & Hove Albion',
    'Brighton': 'Brighton & Hove Albion',
    'West Ham United': 'West Ham United',
    'West Ham': 'West Ham United',
    'Aston Villa': 'Aston Villa',
    'Crystal Palace': 'Crystal Palace',
    'Wolverhampton Wanderers': 'Wolverhampton Wanderers',
    'Wolves': 'Wolverhampton Wanderers',
    'Nottingham Forest': 'Nottingham Forest',
    'Fulham': 'Fulham',
    'Bournemouth': 'Bournemouth',
    'AFC Bournemouth': 'Bournemouth',
    'Brentford': 'Brentford',
    'Everton': 'Everton',
    'Leeds United': 'Leeds United',
    'Leeds': 'Leeds United',
    'Leicester City': 'Leicester City',
    'Leicester': 'Leicester City',
    'Ipswich Town': 'Ipswich Town',
    'Ipswich': 'Ipswich Town',
    'Southampton': 'Southampton',
    'Chelsea': 'Chelsea',
    'Liverpool': 'Liverpool',
    'Sunderland': 'Sunderland',
    'Coventry City': 'Coventry City',
    'Coventry': 'Coventry City',
    'Hull City': 'Hull City',
    'Real Madrid': 'Real Madrid',
    'Barcelona': 'Barcelona',
    'FC Barcelona': 'Barcelona',
    'Atletico Madrid': 'Atletico Madrid',
    'Atletico de Madrid': 'Atletico Madrid',
    'Real Sociedad': 'Real Sociedad',
    'Villarreal': 'Villarreal',
    'Sevilla': 'Sevilla',
    'Sevilla FC': 'Sevilla',
    'Athletic Club': 'Athletic Club',
    'Athletic Bilbao': 'Athletic Club',
    'Real Betis': 'Real Betis',
    'Valencia': 'Valencia',
    'Valencia CF': 'Valencia',
    'Celta Vigo': 'Celta Vigo',
    'RC Celta Vigo': 'Celta Vigo',
    'Osasuna': 'Osasuna',
    'CA Osasuna': 'Osasuna',
    'Rayo Vallecano': 'Rayo Vallecano',
    'Getafe': 'Getafe',
    'Getafe CF': 'Getafe',
    'Alaves': 'Alaves',
    'Deportivo Alaves': 'Alaves',
    'Deportivo Alavés': 'Alaves',
    'Espanyol': 'Espanyol',
    'RCD Espanyol': 'Espanyol',
    'Racing Santander': 'Racing Santander',
    'Levante': 'Levante',
    'Levante UD': 'Levante',
    'Elche': 'Elche',
    'Elche CF': 'Elche',
    'Malaga': 'Malaga',
    'Málaga': 'Malaga',
    'Deportivo La Coruna': 'Deportivo La Coruna',
    'Deportivo de La Coruña': 'Deportivo La Coruna',
    'Bayern Munich': 'Bayern Munich',
    'Bayern München': 'Bayern Munich',
    'FC Bayern Munich': 'Bayern Munich',
    'Bayer Leverkusen': 'Bayer Leverkusen',
    'RB Leipzig': 'RB Leipzig',
    'Borussia Dortmund': 'Borussia Dortmund',
    'Eintracht Frankfurt': 'Eintracht Frankfurt',
    'VfB Stuttgart': 'VfB Stuttgart',
    'Stuttgart': 'VfB Stuttgart',
    'Mainz': 'Mainz 05',
    'Paderborn': 'SC Paderborn 07',
    'Hamburg': 'Hamburger SV',
    'Atlético Madrid': 'Atletico Madrid',
    'Atlético': 'Atletico Madrid',
    'SC Freiburg': 'SC Freiburg',
    'Borussia Monchengladbach': 'Borussia Monchengladbach',
    'Borussia Mönchengladbach': 'Borussia Monchengladbach',
    'Hoffenheim': 'Hoffenheim',
    'TSG Hoffenheim': 'Hoffenheim',
    'Mainz 05': 'Mainz 05',
    '1. FSV Mainz 05': 'Mainz 05',
    'Union Berlin': 'Union Berlin',
    'FC Augsburg': 'FC Augsburg',
    'Werder Bremen': 'Werder Bremen',
    '1. FC Koln': '1. FC Koln',
    '1. FC Köln': '1. FC Koln',
    'Hamburger SV': 'Hamburger SV',
    'FC Schalke 04': 'FC Schalke 04',
    'SC Paderborn 07': 'SC Paderborn 07',
    'SV Elversberg': 'SV Elversberg',
    'Inter Milan': 'Inter Milan',
    'Inter': 'Inter Milan',
    'Internazionale': 'Inter Milan',
    'FC Internazionale Milano': 'Inter Milan',
    'Juventus': 'Juventus',
    'Juventus FC': 'Juventus',
    'AC Milan': 'AC Milan',
    'Milan': 'AC Milan',
    'Atalanta': 'Atalanta',
    'Atalanta BC': 'Atalanta',
    'Roma': 'Roma',
    'AS Roma': 'Roma',
    'SS Roma': 'Roma',
    'Napoli': 'Napoli',
    'SSC Napoli': 'Napoli',
    'Lazio': 'Lazio',
    'SS Lazio': 'Lazio',
    'Bologna': 'Bologna',
    'Bologna FC': 'Bologna',
    'Fiorentina': 'Fiorentina',
    'ACF Fiorentina': 'Fiorentina',
    'Fiorentina ACF': 'Fiorentina',
    'Udinese': 'Udinese',
    'Udinese Calcio': 'Udinese',
    'Torino': 'Torino',
    'Torino FC': 'Torino',
    'Como': 'Como',
    'Como 1907': 'Como',
    'Cagliari': 'Cagliari',
    'Cagliari Calcio': 'Cagliari',
    'Monza': 'Monza',
    'AC Monza': 'Monza',
    'Genoa': 'Genoa',
    'Genoa CFC': 'Genoa',
    'Lecce': 'Lecce',
    'US Lecce': 'Lecce',
    'Parma': 'Parma',
    'Parma Calcio 1913': 'Parma',
    'Venezia': 'Venezia',
    'Venezia FC': 'Venezia',
    'Sassuolo': 'Sassuolo',
    'US Sassuolo': 'Sassuolo',
    'Frosinone': 'Frosinone',
    'Frosinone Calcio': 'Frosinone',
    'Paris Saint-Germain': 'Paris Saint-Germain',
    'Paris Saint Germain': 'Paris Saint-Germain',
    'PSG': 'Paris Saint-Germain',
    'Marseille': 'Marseille',
    'Olympique de Marseille': 'Marseille',
    'Olympique Marseille': 'Marseille',
    'AS Monaco': 'AS Monaco',
    'Monaco': 'AS Monaco',
    'Olympique Lyonnais': 'Lyon',
    'Lyon': 'Lyon',
    'Lille': 'Lille',
    'LOSC Lille': 'Lille',
    'Nice': 'Nice',
    'OGC Nice': 'Nice',
    'Rennes': 'Rennes',
    'Stade Rennais': 'Rennes',
    'RC Lens': 'Lens',
    'Lens': 'Lens',
    'Strasbourg': 'Strasbourg',
    'RC Strasbourg Alsace': 'Strasbourg',
    'Brest': 'Brest',
    'Stade Brestois 29': 'Brest',
    'Toulouse': 'Toulouse',
    'Toulouse FC': 'Toulouse',
    'Le Havre': 'Le Havre',
    'Le Havre AC': 'Le Havre',
    'Angers': 'Angers',
    'Angers SCO': 'Angers',
    'Auxerre': 'Auxerre',
    'AJ Auxerre': 'Auxerre',
    'Le Mans': 'Le Mans',
    'Le Mans FC': 'Le Mans',
    'Troyes': 'Troyes',
    'ESTAC Troyes': 'Troyes',
    'Paris FC': 'Paris FC',
    'Lorient': 'Lorient',
    'FC Lorient': 'Lorient',
    'Racing de Santander': 'Racing Santander',
    'Racing Santander': 'Racing Santander',
    'Deportivo de A Coruña': 'Deportivo La Coruna',
    'Deportivo de La Coruña': 'Deportivo La Coruna',
    'Deportivo La Coruña': 'Deportivo La Coruna',
    'Deportivo La Coruna': 'Deportivo La Coruna',
}


def api_get(path, retries=5):
    """GET an endpoint, retrying on rate-limit (429) with backoff."""
    url = API_BASE + path
    req = urllib.request.Request(url)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                wait = 2 * attempt
                print(f"  rate-limited (429), retry {attempt}/{retries} in {wait}s")
                time.sleep(wait)
                continue
            print(f"  API error {e.code}")
            return None
        except Exception as e:
            print(f"  Request failed: {e}")
            return None
    return None


def _deaccent(s):
    """Fold common Latin accents to ASCII so accented API names still match."""
    table = {
        'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a', 'å': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'ô': 'o', 'ö': 'o', 'õ': 'o', 'ő': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u', 'ű': 'u',
        'ý': 'y', 'ÿ': 'y',
        'ñ': 'n', 'ç': 'c', 'š': 's', 'ß': 'ss',
    }
    return ''.join(table.get(c, c) for c in s.lower())


def map_team_name(api_name):
    if not api_name:
        return None
    api_name = api_name.strip()
    if api_name in TEAM_OVERRIDES:
        return TEAM_OVERRIDES[api_name]
    folded = _deaccent(api_name)
    for key, val in TEAM_OVERRIDES.items():
        if _deaccent(key) == folded:
            return val
    return None


def read_existing_results():
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
        date = row.get('date', '').strip()
        comp = row.get('comp', '').strip()
        home = row.get('home', '').strip()
        away = row.get('away', '').strip()
        if date and comp and home and away:
            keys.add((date, comp, home, away))
    return keys


def map_round_to_stage(round_str, comp):
    if comp in ('PL', 'LALIGA', 'BL1', 'SA', 'FL1'):
        return ''
    r = (round_str or '').lower().strip()
    if 'group' in r or 'grp' in r:
        return 'GRP'
    if 'round of 32' in r or 'r32' in r:
        return 'R32'
    if 'round of 16' in r or 'r16' in r:
        return 'R16'
    if 'quarter' in r or 'qf' in r:
        return 'QF'
    if 'semi' in r or 'sf' in r:
        return 'SF'
    if 'final' in r:
        return 'F'
    if 'first' in r or 'round 1' in r or r == '1':
        return 'R1'
    if 'second' in r or 'round 2' in r or r == '2':
        return 'R2'
    if 'third' in r or 'round 3' in r or r == '3':
        return 'R3'
    if 'fourth' in r or 'round 4' in r or r == '4':
        return 'R4'
    if 'round of 64' in r or 'r64' in r:
        return 'R64'
    if comp == 'CS':
        return 'F'
    return ''


def main():
    # Make console output safe for accented team names (Windows cp1252).
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    # SAFETY: never write to results.csv directly. Only append new rows.
    if not os.path.exists(RESULTS_CSV):
        print(f"ERROR: {RESULTS_CSV} does not exist. Create it first.")
        sys.exit(1)

    dry = '--dry' in sys.argv
    existing = read_existing_results()
    print(f"Existing results: {len(existing)}")

    all_new = []
    total_api = 0

    for tsdb_id, comp in LEAGUE_MAP.items():
        max_round = MAX_ROUNDS.get(comp, 10)
        print(f"\n=== {comp} (TheSportsDB ID {tsdb_id}) ===")

        for rnd in range(1, max_round + 1):
            if total_api > 200:
                print("  Stopping to avoid rate limits")
                break

            data = api_get(f"/eventsround.php?id={tsdb_id}&r={rnd}&season=2026-2027")
            total_api += 1
            time.sleep(0.3)

            if not data or not data.get('events'):
                continue

            events = data['events']
            finished = [e for e in events if e.get('strStatus') == 'FT']
            if not finished:
                # No more played rounds
                break

            for e in finished:
                home_api = e.get('strHomeTeam', '')
                away_api = e.get('strAwayTeam', '')
                home = map_team_name(home_api)
                away = map_team_name(away_api)
                if not home or not away:
                    print(f"  Skipping unknown: {home_api} vs {away_api}")
                    continue

                date = e.get('dateEvent', '')
                hg = e.get('intHomeScore')
                ag = e.get('intAwayScore')
                if hg is None or ag is None:
                    continue

                stage = map_round_to_stage(e.get('intRound', ''), comp)
                key = (date, comp, home, away)
                if key in existing:
                    continue

                line = f"{date},{comp},{stage},{home},{away},{hg},{ag},,,\n"
                all_new.append((key, line))
                print(f"  + {date} {comp:>5} {home} {hg}-{ag} {away} (R{e.get('intRound', '?')})")

            # If all events in this round were not finished, stop
            if not finished:
                break

    print(f"\n--- {len(all_new)} new results ---")
    if dry:
        for _, line in all_new:
            print(f"  DRY: {line.strip()}")
        return

    for key, line in all_new:
        with open(RESULTS_CSV, 'a', encoding='utf-8') as f:
            f.write(line)
        existing.add(key)

    print(f"Done. {len(all_new)} results appended to {RESULTS_CSV}")
    print(f"  NEVER edit this file by hand for new data - only run this script.")
    print(f"API requests used: {total_api}")


if __name__ == '__main__':
    main()
