"""
fetch_fixtures.py - Pull the next N upcoming fixtures for each top-5 league
from ESPN's public (no-key) scoreboard API and write data/fixtures.csv.

Maps ESPN display names (accents, language forms) to the engine's canonical
names so fixture rows line up with results/team state.

Usage:
    python fetch_fixtures.py            # fetch and overwrite data/fixtures.csv
    python fetch_fixtures.py --dry      # print only, no writes
"""
import csv
import json
import os
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
FIXTURES_CSV = os.path.join(DATA, 'fixtures.csv')

API = 'https://site.api.espn.com/apis/site/v2/sports/soccer'
USER_AGENT = 'Mozilla/5.0'

LEAGUES = ['PL', 'LALIGA', 'BL1', 'SA', 'FL1']
LEAGUE_SLUG = {'PL': 'eng.1', 'LALIGA': 'esp.1', 'BL1': 'ger.1',
               'SA': 'ita.1', 'FL1': 'fra.1'}

# European competitions (main feed slugs) whose fixtures we also pull.
EURO_LEAGUES = ['UCL', 'UEL', 'UECL']
EURO_SLUG = {'UCL': 'uefa.champions', 'UEL': 'uefa.europa',
             'UECL': 'uefa.europa.conf'}

# Domestic cups with ESPN coverage whose fixtures we pull.
CUP_LEAGUES = ['LC', 'FAC', 'CDR', 'DFB', 'CI', 'CDF']
CUP_SLUG = {'LC': 'eng.league_cup', 'FAC': 'eng.fa', 'CDR': 'esp.copa_del_rey',
            'DFB': 'ger.dfb_pokal', 'CI': 'ita.coppa_italia',
            'CDF': 'fra.coupe_de_france'}

ALL_COMP_SLUG = {**{c: LEAGUE_SLUG[c] for c in LEAGUES},
                 **{c: EURO_SLUG[c] for c in EURO_LEAGUES},
                 **{c: CUP_SLUG[c] for c in CUP_LEAGUES}}

NEXT = 10  # number of upcoming fixtures to keep per league


def load_site_teams():
    """Top-5 league clubs already tracked on the site. European fixtures that
    involve none of these (e.g. Olympiacos vs Jagiellonia) are dropped so the
    Europa League / Conference League tabs only show clubs the site covers."""
    from engine import LEAGUE_TEAMS
    site = set()
    for names in LEAGUE_TEAMS.values():
        site.update(names)
    return site


def api_get(path):
    req = urllib.request.Request(API + path, headers={'User-Agent': USER_AGENT})
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            last_err = e
            time.sleep(0.5 * (attempt + 1))
    print(f'  request failed after retries: {last_err}')
    return None


def load_id_map():
    # Reuse fetch_espn's TEAM_ID_MAP (id -> canonical name) if importable.
    try:
        import fetch_espn
        return dict(fetch_espn.TEAM_ID_MAP)
    except Exception:
        return {}


# Explicit extras for clubs ESPN spells differently than the engine's canonical
# name, keyed by ESPN displayName (lowercased) -> canonical.
NAME_OVERRIDES = {
    'atletico madrid': 'Atletico Madrid',
    'alaves': 'Alaves',
    'malaga': 'Malaga',
    'deportivo': 'Deportivo La Coruna',
    'deportivo la coruna': 'Deportivo La Coruna',
    'stade rennais': 'Rennes',
    'rennes': 'Rennes',
    'internazionale': 'Inter Milan',
    'inter': 'Inter Milan',
    'as roma': 'Roma',
    'roma': 'Roma',
    'borussia monchengladbach': 'Borussia Monchengladbach',
    'hamburg sv': 'Hamburger SV',
    'hamburger sv': 'Hamburger SV',
    '1. fc union berlin': 'Union Berlin',
    'union berlin': 'Union Berlin',
    'fc koln': '1. FC Koln',
    '1. fc koln': '1. FC Koln',
    'fc cologne': '1. FC Koln',
    'cologue': '1. FC Koln',
    'cologne': '1. FC Koln',
    'vfb stuttgart': 'VfB Stuttgart',
    'paris saint-germain': 'Paris Saint-Germain',
    'sc freiburg': 'SC Freiburg',
    'fc augsburg': 'FC Augsburg',
    'fc schalke 04': 'FC Schalke 04',
    'schalke 04': 'FC Schalke 04',
    'sv elversberg': 'SV Elversberg',
    'sc paderborn 07': 'SC Paderborn 07',
    'mainz 05': 'Mainz 05',
    'bayer leverkusen': 'Bayer Leverkusen',
    'levante ud': 'Levante',
    'elche cf': 'Elche',
    'reial club deportiu mallorca': 'Mallorca',
    'athletic club': 'Athletic Club',
    'real sociedad': 'Real Sociedad',
    'racing santander': 'Racing Santander',
    'celta vigo': 'Celta Vigo',
    'espanyol': 'Espanyol',
    'getafe cf': 'Getafe',
    'osasuna': 'Osasuna',
    'valencia cf': 'Valencia',
    'villareal': 'Villarreal',
    'villarreal': 'Villarreal',
    'real betis': 'Real Betis',
    'rayo vallecano': 'Rayo Vallecano',
    'sevilla fc': 'Sevilla',
    'sevilla': 'Sevilla',
    'real madrid': 'Real Madrid',
    'fc barcelona': 'Barcelona',
    'barcelona': 'Barcelona',
    'afc bournemouth': 'Bournemouth',
    'brighton & hove albion': 'Brighton & Hove Albion',
    'nottingham forest': 'Nottingham Forest',
    'tottenham hotspur': 'Tottenham Hotspur',
    'west ham united': 'West Ham United',
    'crystal palace': 'Crystal Palace',
    'newcastle united': 'Newcastle United',
    'manchester united': 'Manchester United',
    'manchester city': 'Manchester City',
    'liverpool': 'Liverpool',
    'arsenal': 'Arsenal',
    'chelsea': 'Chelsea',
    'aston villa': 'Aston Villa',
    'everton': 'Everton',
    'fulham': 'Fulham',
    'leeds united': 'Leeds United',
    'hull city': 'Hull City',
    'ipswich town': 'Ipswich Town',
    'sunderland': 'Sunderland',
    'crystal palace fc': 'Crystal Palace',
    'as monaco': 'AS Monaco',
    'monaco': 'AS Monaco',
    'paris saint germain': 'Paris Saint-Germain',
    'marseille': 'Marseille',
    'lyon': 'Lyon',
    'lille': 'Lille',
    'nice': 'Nice',
    'lens': 'Lens',
    'strasbourg': 'Strasbourg',
    'brest': 'Brest',
    'toulouse': 'Toulouse',
    'le havre': 'Le Havre',
    'le havre ac': 'Le Havre',
    'angers': 'Angers',
    'aj auxerre': 'Auxerre',
    'auxerre': 'Auxerre',
    'le mans': 'Le Mans',
    'troyes': 'Troyes',
    'paris fc': 'Paris FC',
    'lorient': 'Lorient',
    'ac milan': 'AC Milan',
    'juventus': 'Juventus',
    'inter milan': 'Inter Milan',
    'atalanta': 'Atalanta',
    'napoli': 'Napoli',
    'lazio': 'Lazio',
    'bologna': 'Bologna',
    'fiorentina': 'Fiorentina',
    'udinese': 'Udinese',
    'torino': 'Torino',
    'como': 'Como',
    'cagliari': 'Cagliari',
    'monza': 'Monza',
    'genoa': 'Genoa',
    'lecce': 'Lecce',
    'parma': 'Parma',
    'venezia': 'Venezia',
    'sassuolo': 'Sassuolo',
    'frosinone': 'Frosinone',
    'as roma': 'Roma',
    '1. fc union berlin': 'Union Berlin',
}


def to_canonical(name, tid, id_map):
    tid = str(tid)
    if id_map and tid in id_map:
        return id_map[tid]
    key = (name or '').strip().lower()
    if key in NAME_OVERRIDES:
        return NAME_OVERRIDES[key]
    # last-resort: strip diacritics + collapse to a best-effort lowercase key
    import unicodedata
    norm = ''.join(
        c for c in unicodedata.normalize('NFKD', key)
        if not unicodedata.combining(c))
    if norm in NAME_OVERRIDES:
        return NAME_OVERRIDES[norm]
    return key.title()


def load_played():
    """Set of (comp, home, away, date) already in results.csv - these are NOT
    upcoming, so we never list them as fixtures."""
    played = set()
    try:
        with open(os.path.join(DATA, 'results.csv'), encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if not (r.get('date') or '').strip():
                    continue
                played.add((r['comp'].strip(),
                            r['home'].strip(), r['away'].strip(),
                            r['date'].strip()))
    except FileNotFoundError:
        pass
    return played


def fetch_upcoming():
    id_map = load_id_map()
    played = load_played()
    site_teams = load_site_teams()
    rows = []

    def scan(comp):
        slug = ALL_COMP_SLUG[comp]
        seen = set()
        total = 0
        # scan forward in ~14-day windows until we have NEXT fixtures
        from datetime import date, timedelta
        start = date.today()
        for w in range(0, 8):
            s = (start + timedelta(days=14 * w)).strftime('%Y%m%d')
            e = (start + timedelta(days=14 * (w + 1) + 1)).strftime('%Y%m%d')
            d = api_get(f'/{slug}/scoreboard?dates={s}-{e}')
            if not d or 'events' not in d:
                return
            for ev in d['events']:
                c0 = ev['competitions'][0]
                if c0['status']['type'].get('completed'):
                    continue
                teams = {c.get('homeAway'): c for c in c0['competitors']}
                try:
                    home_name = teams['home']['team']['displayName']
                    away_name = teams['away']['team']['displayName']
                    home_id = teams['home']['team']['id']
                    away_id = teams['away']['team']['id']
                    kickoff = ev.get('date') or ''
                    dstr = kickoff[:10]
                except (KeyError, TypeError):
                    continue
                home = to_canonical(home_name, home_id, id_map)
                away = to_canonical(away_name, away_id, id_map)
                # For European + domestic-cup competitions, only keep fixtures
                # involving a site (top-5 league) team - drop ties between two
                # non-site clubs.
                if comp in EURO_LEAGUES + CUP_LEAGUES and home not in site_teams \
                        and away not in site_teams:
                    continue
                if (comp, home, away, dstr) in played:
                    continue
                key = (dstr, home, away)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(dict(date=dstr, kickoff_utc=kickoff, comp=comp, stage='',
                                 home=home, away=away))
                total += 1
            if total >= NEXT:
                return

    # each competition scans its own windows - pure network I/O, run in parallel
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(8, len(ALL_COMP_SLUG))) as ex:
        list(ex.map(scan, list(ALL_COMP_SLUG)))

    # keep only the first NEXT fixtures per league (by date)
    rows.sort(key=lambda r: (r.get('kickoff_utc') or r['date'], r['comp'], r['home']))
    out = []
    per_comp = {}
    for r in rows:
        if per_comp.get(r['comp'], 0) >= NEXT:
            continue
        per_comp[r['comp']] = per_comp.get(r['comp'], 0) + 1
        out.append(r)
    out.sort(key=lambda r: (r.get('kickoff_utc') or r['date'], r['comp'], r['home']))
    return out


def write_csv(rows, dry=False):
    fieldnames = ['date', 'kickoff_utc', 'comp', 'stage', 'home', 'away']
    if dry:
        print('=== Upcoming fixtures (dry run) ===')
        for r in rows:
            print(f"  {r.get('kickoff_utc') or r['date']} {r['comp']:<6} {r['home']:<24} v {r['away']}")
        return
    # never clobber a valid fixtures.csv with an empty/partial fetch (e.g. a
    # transient ESPN throttle) - keep the good file and say so loudly instead.
    if os.path.exists(FIXTURES_CSV):
        try:
            old = sum(1 for _ in open(FIXTURES_CSV, encoding='utf-8-sig')) - 1
        except OSError:
            old = 0
        if old > 0 and (not rows or len(rows) < max(5, old // 2)):
            print(f'  ! fetched only {len(rows)} fixtures but {old} exist - '
                  f'keeping existing {FIXTURES_CSV}, not overwriting')
            return
    with open(FIXTURES_CSV, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {len(rows)} fixtures -> {FIXTURES_CSV}")


if __name__ == '__main__':
    dry = '--dry' in sys.argv
    fixt = fetch_upcoming()
    write_csv(fixt, dry=dry)
