"""
fetch_results.py - Pull match results from API-Football and append to results.csv.

Usage:
    1. Get a free API key from https://www.api-football.com/ (100 requests/day free)
    2. Set environment variable:  set API_FOOTBALL_KEY=your_key_here
    3. python fetch_results.py              # fetch today's results
       python fetch_results.py --days 3     # fetch last 3 days
       python fetch_results.py --date 2026-08-16  # fetch specific date

Appends new results to data/results.csv. Detects drama flags from goal events.
Never duplicates a match that's already in results.csv.
"""
import csv
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
RESULTS_CSV = os.path.join(DATA, 'results.csv')
TEAM_MAP_CSV = os.path.join(DATA, 'team_map.csv')

API_KEY = os.environ.get('API_FOOTBALL_KEY', '')
API_BASE = 'https://v3.football.api-sports.io'

# API-Football league IDs -> our comp codes
LEAGUE_MAP = {
    39:  'PL',       # Premier League
    140: 'LALIGA',   # La Liga
    78:  'BL1',      # Bundesliga
    135: 'SA',       # Serie A
    61:  'FL1',      # Ligue 1
    2:   'UCL',      # Champions League
    3:   'UEL',      # Europa League
    848: 'UECL',     # Conference League
    45:  'FAC',      # FA Cup
    143: 'CDR',      # Copa del Rey
    81:  'DFB',      # DFB-Pokal
    137: 'CI',       # Coppa Italia
    46:  'CDF',      # Coupe de France
    525: 'CS',       # Community Shield / Super Cup
}

# API stage IDs -> our stage codes
# These vary by competition; we'll map them in the function

# Pre-loaded team name map (API name -> our CSV name)
# We also load from team_map.csv if it exists
TEAM_OVERRIDES = {
    'Manchester United': 'Manchester United',
    'Manchester City': 'Manchester City',
    'Arsenal': 'Arsenal',
    'Tottenham Hotspur': 'Tottenham Hotspur',
    'Newcastle United': 'Newcastle United',
    'Brighton & Hove Albion': 'Brighton & Hove Albion',
    'West Ham United': 'West Ham United',
    'Aston Villa': 'Aston Villa',
    'Crystal Palace': 'Crystal Palace',
    'Wolverhampton Wanderers': 'Wolverhampton Wanderers',
    'Nottingham Forest': 'Nottingham Forest',
    'Fulham': 'Fulham',
    'Bournemouth': 'Bournemouth',
    'Brentford': 'Brentford',
    'Everton': 'Everton',
    'Leeds United': 'Leeds United',
    'Leicester City': 'Leicester City',
    'Ipswich Town': 'Ipswich Town',
    'Southampton': 'Southampton',
    'Chelsea': 'Chelsea',
    'Liverpool': 'Liverpool',
    'Real Madrid': 'Real Madrid',
    'Barcelona': 'Barcelona',
    'Atletico Madrid': 'Atletico Madrid',
    'Real Sociedad': 'Real Sociedad',
    'Villarreal': 'Villarreal',
    'Sevilla': 'Sevilla',
    'Athletic Club': 'Athletic Club',
    'Athletic Bilbao': 'Athletic Club',
    'Real Betis': 'Real Betis',
    'Valencia': 'Valencia',
    'Celta Vigo': 'Celta Vigo',
    'Osasuna': 'Osasuna',
    'Rayo Vallecano': 'Rayo Vallecano',
    'Getafe': 'Getafe',
    'Alaves': 'Alaves',
    'Deportivo Alaves': 'Alaves',
    'Espanyol': 'Espanyol',
    'Bayern Munich': 'Bayern Munich',
    'FC Bayern Munich': 'Bayern Munich',
    'Bayer Leverkusen': 'Bayer Leverkusen',
    'RB Leipzig': 'RB Leipzig',
    'Borussia Dortmund': 'Borussia Dortmund',
    'Eintracht Frankfurt': 'Eintracht Frankfurt',
    'VfB Stuttgart': 'VfB Stuttgart',
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
    'Juventus': 'Juventus',
    'AC Milan': 'AC Milan',
    'Milan': 'AC Milan',
    'Atalanta': 'Atalanta',
    'Roma': 'Roma',
    'AS Roma': 'Roma',
    'Napoli': 'Napoli',
    'SSC Napoli': 'Napoli',
    'Lazio': 'Lazio',
    'SS Lazio': 'Lazio',
    'Bologna': 'Bologna',
    'Fiorentina': 'Fiorentina',
    'ACF Fiorentina': 'Fiorentina',
    'Udinese': 'Udinese',
    'Torino': 'Torino',
    'Como': 'Como',
    'Cagliari': 'Cagliari',
    'Monza': 'Monza',
    'AC Monza': 'Monza',
    'Genoa': 'Genoa',
    'Lecce': 'Lecce',
    'Parma': 'Parma',
    'Parma Calcio 1913': 'Parma',
    'Venezia': 'Venezia',
    'Paris Saint-Germain': 'Paris Saint-Germain',
    'PSG': 'Paris Saint-Germain',
    'Marseille': 'Marseille',
    'Olympique de Marseille': 'Marseille',
    'AS Monaco': 'AS Monaco',
    'Monaco': 'AS Monaco',
    'Lyon': 'Lyon',
    'Olympique Lyonnais': 'Lyon',
    'Lille': 'Lille',
    'LOSC Lille': 'Lille',
    'Nice': 'Nice',
    'OGC Nice': 'Nice',
    'Rennes': 'Rennes',
    'Stade Rennais': 'Rennes',
    'Lens': 'Lens',
    'RC Lens': 'Lens',
    'Strasbourg': 'Strasbourg',
    'RC Strasbourg': 'Strasbourg',
    'Brest': 'Brest',
    'Stade Brestois': 'Brest',
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
    # Cup minnows / newly promoted
    'Racing Santander': 'Racing Santander',
    'Levante': 'Levante',
    'Elche': 'Elche',
    'Malaga': 'Malaga',
    'Deportivo La Coruna': 'Deportivo La Coruna',
    'Coventry City': 'Coventry City',
    'Hull City': 'Hull City',
    'Sunderland': 'Sunderland',
    'Mantova': 'Mantova',
    'Benevento': 'Benevento',
    'Catania': 'Catania',
    'Arezzo': 'Arezzo',
    'Avellino': 'Avellino',
    'Karlsruher SC': 'Karlsruher SC',
    '1. FC Kaiserslautern': '1. FC Kaiserslautern',
    'Hansa Rostock': 'Hansa Rostock',
    'Hertha BSC': 'Hertha BSC',
    '1. FC Nurnberg': '1. FC Nurnberg',
    '1. FC Nürnberg': '1. FC Nurnberg',
    '1. FC Saarbrucken': '1. FC Saarbrucken',
    '1. FC Saarbrücken': '1. FC Saarbrucken',
    'Hannover 96': 'Hannover 96',
    'Arminia Bielefeld': 'Arminia Bielefeld',
    'FC St. Pauli': 'FC St. Pauli',
    'VfL Bochum': 'VfL Bochum',
    'Dynamo Dresden': 'Dynamo Dresden',
    '1. FC Heidenheim': '1. FC Heidenheim',
    '1. FC Magdeburg': '1. FC Magdeburg',
    'SV Darmstadt 98': 'SV Darmstadt 98',
    'Sassuolo': 'Sassuolo',
    'Frosinone': 'Frosinone',
    'Cremonese': 'Cremonese',
    'Sampdoria': 'Sampdoria',
    'Verona': 'Verona',
    'Hellas Verona': 'Verona',
    'Empoli': 'Empoli',
    'Pisa': 'Pisa',
    'Carrarese': 'Carrarese',
    'Entella': 'Entella',
}


def load_team_map():
    """Load additional team name overrides from team_map.csv."""
    if not os.path.exists(TEAM_MAP_CSV):
        return {}
    mapping = {}
    with open(TEAM_MAP_CSV, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) >= 2:
                mapping[parts[0].strip()] = parts[1].strip()
    return mapping


def map_team_name(api_name):
    """Map API team name to our CSV name. Returns None if unknown."""
    team_map = load_team_map()
    if api_name in team_map:
        return team_map[api_name]
    if api_name in TEAM_OVERRIDES:
        return TEAM_OVERRIDES[api_name]
    # Try fuzzy: strip common prefixes
    for key, val in TEAM_OVERRIDES.items():
        if api_name.lower() == key.lower():
            return val
    return None


def map_stage(api_stage, comp):
    """Map API stage/round to our stage code."""
    if comp in ('PL', 'LALIGA', 'BL1', 'SA', 'FL1'):
        return ''  # leagues don't use stage
    s = (api_stage or '').lower()
    # European cups
    if 'group' in s or 'grp' in s:
        return 'GRP'
    if 'round of 32' in s or 'r32' in s:
        return 'R32'
    if 'round of 16' in s or 'r16' in s:
        return 'R16'
    if 'quarter' in s or 'qf' in s:
        return 'QF'
    if 'semi' in s or 'sf' in s:
        return 'SF'
    if 'final' in s:
        return 'F'
    # Domestic cups - try to extract round number
    if 'first' in s or 'round 1' in s or 'r1' in s:
        return 'R1'
    if 'second' in s or 'round 2' in s or 'r2' in s:
        return 'R2'
    if 'third' in s or 'round 3' in s or 'r3' in s:
        return 'R3'
    if 'round of 64' in s or 'r64' in s:
        return 'R64'
    if 'round of 32' in s:
        return 'R32'
    if 'round of 16' in s:
        return 'R16'
    if 'quarter' in s:
        return 'QF'
    if 'semi' in s:
        return 'SF'
    if 'final' in s:
        return 'F'
    # Super Cup is always a final
    if comp == 'CS':
        return 'F'
    return ''


def detect_drama_flags(events, home_team, away_team):
    """Analyze goal events to detect drama flags.
    
    events: list of dicts with 'minute', 'team', 'type' ('Goal'/'Own Goal')
    Returns list of flag strings.
    """
    flags = []
    if not events:
        return flags

    # Separate home/away goals by minute
    home_goals = []
    away_goals = []
    for e in events:
        team_name = e.get('team', '')
        minute = e.get('minute', 0)
        if minute > 90:
            minute = 90  # treat stoppage time as 90+
        is_own = e.get('type') == 'Own Goal'
        is_home = team_name == home_team
        
        if is_own:
            # Own goal by X benefits the other team
            if is_home:
                away_goals.append(minute)
            else:
                home_goals.append(minute)
        else:
            if is_home:
                home_goals.append(minute)
            else:
                away_goals.append(minute)

    home_goals.sort()
    away_goals.sort()

    total_h = len(home_goals)
    total_a = len(away_goals)

    # Score progression to detect comebacks / blown leads
    # Build timeline: (minute, scoring_side)
    timeline = []
    for m in home_goals:
        timeline.append((m, 'H'))
    for m in away_goals:
        timeline.append((m, 'A'))
    timeline.sort()

    if not timeline:
        return flags

    # Determine result from actual scores
    if total_h > total_a:
        result = 'H'
    elif total_a > total_h:
        result = 'A'
    else:
        result = 'D'

    # Check first-15-minute goal
    for minute, side in timeline:
        if minute <= 15:
            if side == 'H':
                flags.append('f15_H')
            else:
                flags.append('f15_A')
            break

    # Check late goals (80+) - track latest minute per side
    late_win_latest = {}
    late_eq_latest = {}
    for minute, side in timeline:
        if minute >= 80:
            if side == 'H' and result == 'H':
                late_win_latest['H'] = max(late_win_latest.get('H', 0), minute)
            elif side == 'A' and result == 'A':
                late_win_latest['A'] = max(late_win_latest.get('A', 0), minute)
            elif side == 'H' and result == 'D':
                late_eq_latest['H'] = max(late_eq_latest.get('H', 0), minute)
            elif side == 'A' and result == 'D':
                late_eq_latest['A'] = max(late_eq_latest.get('A', 0), minute)
    for side, m in late_win_latest.items():
        flags.append(f'late_win_{side}_{m}')
    for side, m in late_eq_latest.items():
        flags.append(f'late_eq_{side}_{m}')

    # Check comeback: team was losing at some point, then equalized or won
    h_running, a_running = 0, 0
    was_losing_h = False
    was_losing_a = False
    took_lead_h = False
    took_lead_a = False
    for minute, side in timeline:
        if side == 'H':
            h_running += 1
        else:
            a_running += 1
        if h_running < a_running:
            was_losing_h = True
        if a_running < h_running:
            was_losing_a = True
        if h_running > a_running and was_losing_h:
            flags.append('comeback_H')
        if a_running > h_running and was_losing_a:
            flags.append('comeback_A')

    # Check blown lead: team was winning, then conceded to draw or lose
    h_running, a_running = 0, 0
    was_winning_h = False
    was_winning_a = False
    for minute, side in timeline:
        prev_h, prev_a = h_running, a_running
        if side == 'H':
            h_running += 1
        else:
            a_running += 1
        if prev_h > prev_a:
            was_winning_h = True
        if prev_a > prev_h:
            was_winning_a = True
        if was_winning_h and h_running <= a_running:
            flags.append('blown_H')
        if was_winning_a and a_running <= h_running:
            flags.append('blown_A')

    # Deduplicate
    seen = set()
    unique = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def read_existing_results():
    """Read results.csv and return set of match keys to avoid duplicates."""
    keys = set()
    if not os.path.exists(RESULTS_CSV):
        return keys
    with open(RESULTS_CSV, encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # We'll parse to find date+comp+home+away
    with open(RESULTS_CSV, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get('date', '').strip()
            comp = row.get('comp', '').strip()
            home = row.get('home', '').strip()
            away = row.get('away', '').strip()
            if date and comp and home and away:
                keys.add((date, comp, home, away))
    return keys


def api_get(path, params=None):
    """Make a GET request to API-Football."""
    url = API_BASE + path
    if params:
        qs = '&'.join(f'{k}={v}' for k, v in params.items())
        url += '?' + qs
    req = urllib.request.Request(url)
    req.add_header('x-apisports-key', API_KEY)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"  API error {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
        return None
    except Exception as e:
        print(f"  Request failed: {e}")
        return None


def fetch_results_for_date(date_str):
    """Fetch all completed matches for a given date across configured leagues."""
    print(f"\nFetching results for {date_str}...")

    # Get fixtures for the date
    # We query each league separately to stay within rate limits
    results = []
    requests_made = 0

    for league_id, comp_code in LEAGUE_MAP.items():
        if requests_made >= 90:  # leave some buffer for event requests
            print(f"  Rate limit approaching, stopping (used {requests_made} requests)")
            break

        data = api_get('/fixtures', {
            'league': league_id,
            'date': date_str,
            'status': 'FT',  # finished
        })
        requests_made += 1

        if not data or not data.get('response'):
            continue

        for fixture in data['response']:
            match_info = fixture['fixture']
            teams = fixture['teams']
            goals = fixture['goals']
            league = fixture['league']

            home_api = teams['home']['name']
            away_api = teams['away']['name']
            home_goals = goals['home']
            away_goals = goals['away']

            if home_goals is None or away_goals is None:
                continue

            home_name = map_team_name(home_api)
            away_name = map_team_name(away_api)

            if not home_name or not away_name:
                print(f"  Skipping unknown teams: {home_api} vs {away_api}")
                continue

            # Determine stage
            stage = map_stage(league.get('round', ''), comp_code)

            # Get penalty shootout scores if applicable
            pen_h, pen_a = '', ''
            score = fixture.get('score', {})
            if score.get('penalty'):
                pen_h = score['penalty']['home']
                pen_a = score['penalty']['away']

            # Fetch goal events for drama detection (1 extra request per match)
            events = []
            if requests_made < 85:
                evt_data = api_get('/fixtures/events', {'fixture': match_info['id']})
                requests_made += 1
                if evt_data and evt_data.get('response'):
                    for e in evt_data['response']:
                        if e.get('type') in ('Goal', 'Own Goal'):
                            events.append({
                                'minute': e.get('time', {}).get('elapsed', 0),
                                'team': e.get('team', {}).get('name', ''),
                                'type': e.get('type'),
                            })

            flags = detect_drama_flags(events, home_api, away_api)

            results.append({
                'date': date_str,
                'comp': comp_code,
                'stage': stage,
                'home': home_name,
                'away': away_name,
                'hg': home_goals,
                'ag': away_goals,
                'pen_h': pen_h,
                'pen_a': pen_a,
                'flags': ';'.join(flags),
                '_api_home': home_api,
                '_api_away': away_api,
            })

    print(f"  Found {len(results)} matches ({requests_made} API requests)")
    return results, requests_made


def append_to_csv(new_results):
    """Append new results to results.csv, avoiding duplicates."""
    existing = read_existing_results()
    added = 0
    skipped = 0

    for r in new_results:
        key = (r['date'], r['comp'], r['home'], r['away'])
        if key in existing:
            skipped += 1
            continue

        # Format line
        flags = r['flags']
        pen_h = r['pen_h'] if r['pen_h'] != '' else ''
        pen_a = r['pen_a'] if r['pen_a'] != '' else ''
        line = f"{r['date']},{r['comp']},{r['stage']},{r['home']},{r['away']},{r['hg']},{r['ag']},{pen_h},{pen_a},{flags}\n"

        with open(RESULTS_CSV, 'a', encoding='utf-8') as f:
            f.write(line)
        existing.add(key)
        added += 1
        print(f"  + {r['date']} {r['comp']:>5} {r['home']} {r['hg']}-{r['ag']} {r['away']}"
              f"{' [' + flags + ']' if flags else ''}")

    return added, skipped


def check_new_teams(new_results):
    """Find teams in results not yet in engine.py's BASE_ELO."""
    from engine import BASE_ELO
    new_teams = set()
    for r in new_results:
        if r['home'] not in BASE_ELO:
            new_teams.add(r['home'])
        if r['away'] not in BASE_ELO:
            new_teams.add(r['away'])
    return new_teams


def main():
    if not API_KEY:
        print("ERROR: API_FOOTBALL_KEY not set.")
        print("  1. Sign up at https://www.api-football.com/")
        print("  2. Get your API key from the dashboard")
        print("  3. Set it:  set API_FOOTBALL_KEY=your_key")
        sys.exit(1)

    # Parse args
    days = 1
    target_date = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--days' and i < len(sys.argv) - 1:
            days = int(sys.argv[i + 1])
        elif arg == '--date' and i < len(sys.argv) - 1:
            target_date = sys.argv[i + 1]

    if target_date:
        dates = [target_date]
    else:
        today = datetime.now()
        dates = [(today - timedelta(days=d)).strftime('%Y-%m-%d')
                 for d in range(days, -1, -1)]

    all_results = []
    total_requests = 0
    for date_str in dates:
        results, reqs = fetch_results_for_date(date_str)
        all_results.extend(results)
        total_requests += reqs

    if not all_results:
        print("\nNo new results found.")
        return

    print(f"\n--- Appending {len(all_results)} results to results.csv ---")
    added, skipped = append_to_csv(all_results)

    # Check for unknown teams
    new_teams = check_new_teams(all_results)
    if new_teams:
        print(f"\n  WARNING: {len(new_teams)} teams not in BASE_ELO:")
        for t in sorted(new_teams):
            print(f"    - {t}")
        print("  Add them to engine.py BASE_ELO with estimated ELO ratings.")

    print(f"\nDone: {added} added, {skipped} skipped (duplicate)")
    print(f"API requests used: {total_requests}/100")
    print(f"\nNext steps:")
    print(f"  python run_week.py    # recompute everything")
    print(f"  firebase deploy      # update the site")


if __name__ == '__main__':
    main()
