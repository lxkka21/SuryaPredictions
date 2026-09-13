"""
fetch_espn.py - Pull complete top-5 league results from ESPN's public (no-key)
scoreboard + per-match summary API.

Unlike TheSportsDB / api-football, the per-match summary exposes per-goal
MINUTES, own-goal and penalty flags, so we can compute truly accurate drama
flags (f15, late_win, late_eq, comeback, multi_comeback, blown) - the exact
signals the engine's EO rating depends on. No key required.

Usage:
    python fetch_espn.py --dry      # print what would be produced (no writes)
    python import_espn.py           # see import_espn.py for rebuilding results.csv
"""
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
ESPN_CACHE_DIR = os.path.join(DATA, 'espn_cache')

API = 'https://site.api.espn.com/apis/site/v2/sports/soccer'
USER_AGENT = 'Mozilla/5.0'

LEAGUES = {
    'PL': 'eng.1',
    'LALIGA': 'esp.1',
    'BL1': 'ger.1',
    'SA': 'ita.1',
    'FL1': 'fra.1',
}

# European competitions: (main feed slug, qualifying feed slug). The main feed
# covers the league phase + knockout rounds; the qualifying feed covers the
# summer rounds (which are already completed and appear as results).
EURO_LEAGUES = {
    'UCL': ('uefa.champions', 'uefa.champions_qual'),
    'UEL': ('uefa.europa', 'uefa.europa_qual'),
    'UECL': ('uefa.europa.conf', 'uefa.europa.conf_qual'),
}

# Domestic cup feeds pulled fresh from ESPN (single slug, no qualifying feed).
# Covers the Carabao Cup (LC) plus the other top-5 league domestic cups.
CUP_LEAGUES = {
    'LC':  'eng.league_cup',
    'FAC': 'eng.fa',
    'CDR': 'esp.copa_del_rey',
    'DFB': 'ger.dfb_pokal',
    'CI':  'ita.coppa_italia',
    'CDF': 'fra.coupe_de_france',
}

# ESPN global team ID -> our canonical name (engine.py)
TEAM_ID_MAP = {
    '83': 'Barcelona', '85': 'Celta Vigo', '86': 'Real Madrid',
    '87': 'Racing Santander', '88': 'Espanyol', '89': 'Real Sociedad',
    '90': 'Deportivo La Coruna', '93': 'Athletic Club', '94': 'Valencia',
    '96': 'Alaves', '97': 'Osasuna', '99': 'Malaga', '101': 'Rayo Vallecano',
    '102': 'Villarreal', '103': 'AC Milan', '104': 'Roma', '105': 'Atalanta',
    '107': 'Bologna', '109': 'Fiorentina', '110': 'Inter Milan',
    '111': 'Juventus', '112': 'Lazio', '113': 'Lecce', '114': 'Napoli',
    '115': 'Parma', '118': 'Udinese', '122': '1. FC Koln',
    '124': 'Borussia Dortmund', '125': 'Eintracht Frankfurt',
    '126': 'SC Freiburg', '127': 'Hamburger SV', '131': 'Bayer Leverkusen',
    '132': 'Bayern Munich', '133': 'FC Schalke 04', '134': 'VfB Stuttgart',
    '137': 'Werder Bremen', '160': 'Paris Saint-Germain', '166': 'Lille',
    '167': 'Lyon', '169': 'Rennes', '170': 'Troyes', '172': 'Auxerre',
    '174': 'AS Monaco', '175': 'Lens', '176': 'Marseille', '179': 'Toulouse',
    '180': 'Strasbourg', '239': 'Torino', '243': 'Sevilla',
    '244': 'Real Betis', '268': 'Borussia Monchengladbach', '273': 'Lorient',
    '306': 'Hull City', '331': 'Brighton & Hove Albion', '337': 'Brentford',
    '349': 'Bournemouth', '357': 'Leeds United', '359': 'Arsenal',
    '360': 'Manchester United', '361': 'Newcastle United',
    '362': 'Aston Villa', '363': 'Chelsea', '364': 'Liverpool',
    '366': 'Sunderland', '367': 'Tottenham Hotspur', '368': 'Everton',
    '370': 'Fulham', '373': 'Ipswich Town', '382': 'Manchester City',
    '384': 'Crystal Palace', '388': 'Coventry City', '393': 'Nottingham Forest',
    '598': 'Union Berlin', '1068': 'Atletico Madrid', '1538': 'Levante',
    '2502': 'Nice', '2572': 'Como', '2697': 'Le Mans', '2922': 'Getafe',
    '2925': 'Cagliari', '2950': 'Mainz 05', '3236': 'Le Havre',
    '3263': 'Genoa', '3307': 'SC Paderborn 07', '3751': 'Elche',
    '3841': 'FC Augsburg', '3997': 'Sassuolo', '4007': 'Monza',
    '4057': 'Frosinone', '6851': 'Paris FC', '6997': 'Brest',
    '7868': 'Angers', '7911': 'Hoffenheim', '10388': 'SV Elversberg',
    '11420': 'RB Leipzig', '17530': 'Venezia',
}

# Fallback canonical names for clubs that play in European competitions but not
# in the top-5 league feeds. Keyed by ESPN team id -> canonical name used by the
# engine. Anything not listed here is normalised from ESPN's display name.
EURO_TEAM_ID_MAP = {
    '139': 'Ajax Amsterdam', '140': 'AZ Alkmaar', '142': 'Feyenoord Rotterdam',
    '147': 'NEC Nijmegen', '148': 'PSV Eindhoven', '152': 'FC Twente',
    '256': 'Celtic', '257': 'Rangers', '258': 'Hibernian',
    '262': 'Heart of Midlothian', '266': 'Motherwell',
    '432': 'Galatasaray', '433': 'Sparta Prague', '435': 'Olympiacos',
    '436': 'Fenerbahce', '437': 'FC Porto', '440': 'Dynamo Kyiv',
    '441': 'Anderlecht', '443': 'Panathinaikos', '484': 'FCSB',
    '489': 'Hajduk Split', '490': 'Levski Sofia', '493': 'Shakhtar Donetsk',
    '494': 'Slavia Prague', '497': 'BATE Borisov', '498': 'Dinamo Tbilisi',
    '502': 'HJK Helsinki', '504': 'Neftchi', '510': 'Viking FK',
    '515': 'Dinamo City', '519': 'Rapid Vienna', '521': 'Slovan Bratislava',
    '523': 'Zalgiris Vilnius', '524': 'Maccabi Tel-Aviv', '525': 'Apollon Limassol',
    '532': 'Debrecen', '540': 'Zimbru Chisinau', '541': 'Partizan Belgrade',
    '542': 'Santa Coloma', '551': 'FK Sarajevo', '557': 'St. Gallen',
    '560': 'Vardar', '561': 'Varteks', '562': 'FC Vaduz', '566': 'HB Torshavn',
    '570': 'Club Brugge', '571': 'Glentoran', '572': 'FC Midtjylland',
    '576': 'The New Saints', '597': 'Dinamo Zagreb', '605': 'PAOK',
    '612': 'Torpedo Kutaisi', '614': 'Sheriff Tiraspol', '615': 'Bohemians',
    '617': 'Omonia Nicosia', '620': 'SK Brann', '622': 'Ferencvaros',
    '887': 'AEK Athens', '909': 'FC Kobenhavn', '936': 'Sint-Truidense',
    '987': 'Lillestrom', '997': 'Trabzonspor', '1010': 'OFI Crete',
    '1037': 'Hapoel Tel Aviv', '1382': 'Austria Vienna', '1895': 'Besiktas',
    '1929': 'Benfica', '2250': 'Sporting CP', '2290': 'Red Star Belgrade',
    '2491': 'MSK Zilina', '2493': 'Pyunik', '2495': 'Hammarby IF',
    '2528': 'Kairat Almaty', '2539': 'Dinamo Minsk', '2540': 'FC Levadia Tallinn',
    '2547': 'KI Klaksvik', '2555': 'Linfield', '2556': 'IFK Goteborg',
    '2564': 'Shamrock Rovers', '2698': 'Valletta', '2710': 'NSI Runavik',
    '2712': 'Derry City', '2716': 'Vllaznia Shkoder', '2723': 'Coleraine',
    '2790': 'RB Salzburg', '2940': 'FK Sileks', '2948': 'Marsaxlokk FC',
    '2980': 'Bodo/Glimt', '2988': 'Rijeka', '2990': 'Lech Poznan',
    '2994': 'Braga', '3024': 'FC Thun', '3076': 'FC Sion',
    '3101': 'FC Nordsjaelland', '3362': 'NK Celje', '3364': 'FC Koper',
    '3611': 'KAA Gent', '3726': 'FC Inter Turku', '3746': 'SK Sturm Graz',
    '3929': 'FC Spartak Trnava', '4039': 'AEK Larnaca', '4411': 'LASK Linz',
    '5218': 'Beitar Jerusalem', '5260': 'CFR Cluj-Napoca', '5270': 'Tromso',
    '5807': 'Union St.-Gilloise', '6748': 'Tobol Kostanay', '7590': 'Caernarfon',
    '7591': 'Connahs Quay', '7672': 'FC Lugano', '7759': 'FC Differdange 03',
    '7825': 'Vojvodina', '7853': 'AGF', '7857': 'Floriana FC',
    '7858': 'Hamrun Spartans', '7914': 'Istanbul Basaksehir', '7922': 'Jablonec',
    '7949': 'Stjarnan', '8070': 'Velez Mostar', '8089': 'CSU Craiova',
    '8091': 'Universitatea Cluj', '8151': 'KF Shkendija', '8169': 'KuPS Kuopio',
    '8180': 'Gornik Zabrze', '8222': 'GAIS', '8249': 'Vikingur Reykjavik',
    '8281': 'FK Sutjeska', '8284': 'Dila Gori', '8591': 'Tre Fiori',
    '8594': 'Fiorita', '10376': 'Nomme Kalju', '10414': 'FK Qarabag',
    '10834': 'CSKA Sofia', '11440': 'FC Milsami', '11505': 'Jagiellonia Bialystok',
    '11523': 'Paksi SE', '11706': 'Viktoria Plzen', '12030': 'Rigas Futbola Skola',
    '12124': 'FC Astana', '12146': 'Flora', '12367': 'Gyori ETO FC',
    '13018': 'Ludogorets Razgrad', '13083': "Hapoel Be'er",
    '13238': 'Vikingur', '17503': 'Europa FC', '17856': 'Lincoln Red Imps',
    '17858': 'Alashkert FC', '18283': 'FK Liepaja', '18751': 'St. Josephs',
    '18754': 'Zira FK', '19243': 'Drita Gjilan', '19246': 'Riga FC',
    '19247': 'Dunajska Streda', '19248': 'FC Ilves', '19250': 'Petrocub',
    '20024': 'Ararat-Armenia', '20025': 'Iberia 1999', '20028': 'Kauno Zalgiris',
    '20038': 'Penybont FC', '20039': 'Larne', '20297': 'Shelbourne',
    '20301': 'Mjallby AIF', '20703': "Inter D'Escaldes", '20710': 'Borac Banja Luka',
    '20712': 'FC Noah', '20718': 'Paide Linnameeskond', '21001': 'Decic',
    '21004': 'Panevezys', '21005': 'Rakow Czestochowa', '21526': 'Ballkani',
    '21528': "Atletic Club d'Escaldes", '21615': 'Torreense', '21922': 'Sabah FK',
    '21943': 'Egnatia', '21944': 'Dukagjini', '21945': 'Hegelmann',
    '21947': 'CSKA 1948 Sofia', '21948': 'FK Auda', '22281': 'Pafos',
    '22287': 'KF Malisheva', '22288': 'NK Bravo', '22290': 'Mornar',
    '22291': 'UNA Strassen', '22292': 'AC Virtus', '22294': 'Polissya Zhitomir',
    '22298': 'Zeleznicar Pancevo', '131792': 'Yelimay', '131793': 'Mondorf-les-Bains',
    '131794': 'ML Vitebsk', '131795': 'LNZ Cherkasy', '131796': 'FC Atert Bissen',
    '131797': 'AF Elbasani', '131798': 'OFK Petrovac', '131799': 'Vestri',
    '131800': 'Aluminij', '131860': 'FC Hradec Kralove', '132427': 'GKS Katowice',
    '21945': 'Hegelmann',
}

TEAM_ID_MAP.update(EURO_TEAM_ID_MAP)


def normalize_name(name):
    """Last-resort canonical name: strip diacritics, collapse whitespace."""
    name = (name or '').strip()
    out = ''.join(c for c in unicodedata.normalize('NFKD', name)
                  if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', out).strip()


def to_canonical_team(tid, display):
    tid = str(tid)
    if tid in TEAM_ID_MAP:
        return TEAM_ID_MAP[tid]
    return normalize_name(display)


def stage_from_event(e, comp=''):
    """Map ESPN's season/round slug to a compact stage code used by the engine.

    `comp` distinguishes European qualifying rounds (QR*) from domestic cup
    rounds (R*), which share the same ESPN ordinal-round slugs (e.g. third-round).
    """
    slug = ((e.get('season') or {}).get('slug') or '').lower()
    if not slug:
        c = (e.get('competitions') or [{}])[0]
        slug = (((c.get('series') or {}).get('title')) or '').lower()
    if not slug:
        return ''
    if comp in CUP_LEAGUES:
        # domestic cup: ordinal rounds -> R1..R5, then R16/QF/SF/F
        if 'final' in slug:
            return 'F'
        if 'semi' in slug:
            return 'SF'
        if 'quarter' in slug:
            return 'QF'
        if 'round-of-16' in slug or 'last 16' in slug or 'eighth' in slug:
            return 'R16'
        if 'fifth' in slug or re.search(r'\b5\b', slug):
            return 'R5'
        if 'fourth' in slug or re.search(r'\b4\b', slug):
            return 'R4'
        if 'third' in slug or re.search(r'\b3\b', slug):
            return 'R3'
        if 'second' in slug or re.search(r'\b2\b', slug):
            return 'R2'
        if 'first' in slug or 'preliminary' in slug or re.search(r'\b1\b', slug):
            return 'R1'
        return normalize_name(slug)[:12].replace(' ', '-')
    if 'final' in slug:
        return 'F'
    if 'semi' in slug:
        return 'SF'
    if 'quarter' in slug:
        return 'QF'
    if 'round-of-16' in slug or 'last 16' in slug or 'eighth' in slug:
        return 'R16'
    if 'league-phase' in slug or 'league phase' in slug or 'group' in slug:
        return 'GRP'
    if 'play' in slug:
        return 'PO'
    if 'first' in slug or 'round-1' in slug:
        return 'QR1'
    if 'second' in slug or 'round-2' in slug:
        return 'QR2'
    if 'third' in slug or 'round-3' in slug:
        return 'QR3'
    return normalize_name(slug)[:12].replace(' ', '-')


def _cache_path(url):
    h = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(ESPN_CACHE_DIR, h + '.json')


def _read_cache(url):
    p = _cache_path(url)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(url, data):
    os.makedirs(ESPN_CACHE_DIR, exist_ok=True)
    with open(_cache_path(url), 'w', encoding='utf-8') as f:
        json.dump(data, f)


def api_get(path):
    url = API + path
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            _write_cache(url, data)
            return data
    except Exception as e:
        cached = _read_cache(url)
        if cached:
            print(f'  request failed ({e}), serving from cache')
            return cached
        print(f'  request failed: {e}')
        return None


def parse_minute(display):
    m = re.match(r'(\d+)', (display or '').strip())
    return int(m.group(1)) if m else None


def detect_drama_flags(goals):
    """goals: list of dicts with 'min' (minute) and 'side' ('H'/'A')."""
    flags = []
    if not goals:
        return flags

    home_min = sorted(g['min'] for g in goals if g['side'] == 'H')
    away_min = sorted(g['min'] for g in goals if g['side'] == 'A')
    timeline = sorted([(m, 'H') for m in home_min] + [(m, 'A') for m in away_min])

    total_h, total_a = len(home_min), len(away_min)
    if total_h > total_a:
        result = 'H'
    elif total_a > total_h:
        result = 'A'
    else:
        result = 'D'

    # first-15 goal
    for minute, side in timeline:
        if minute <= 15:
            flags.append('f15_H' if side == 'H' else 'f15_A')
            break

    # late goals 80+ (incl. stoppage shown as 90+): late_win / late_eq
    # Track latest minute per flag so the engine can weight later goals higher
    late_win_latest = {}   # side -> latest minute
    late_eq_latest = {}    # side -> latest minute
    for minute, side in timeline:
        if minute >= 80:
            if side == 'H':
                if result == 'H':
                    late_win_latest['H'] = max(late_win_latest.get('H', 0), minute)
                elif result == 'D':
                    late_eq_latest['H'] = max(late_eq_latest.get('H', 0), minute)
            else:
                if result == 'A':
                    late_win_latest['A'] = max(late_win_latest.get('A', 0), minute)
                elif result == 'D':
                    late_eq_latest['A'] = max(late_eq_latest.get('A', 0), minute)
    for side, m in late_win_latest.items():
        flags.append(f'late_win_{side}_{m}')
    for side, m in late_eq_latest.items():
        flags.append(f'late_eq_{side}_{m}')

    # comeback / multi-comeback (result-aware: only counts when the side that
    # was losing ends the match level or ahead)
    h_runn, a_runn = 0, 0
    was_losing = {'H': False, 'A': False}
    comeback_count = {'H': 0, 'A': 0}
    for minute, side in timeline:
        if side == 'H':
            h_runn += 1
        else:
            a_runn += 1
        if h_runn < a_runn:
            was_losing['H'] = True
        if a_runn < h_runn:
            was_losing['A'] = True
        if h_runn >= a_runn and was_losing['H']:
            comeback_count['H'] += 1
            was_losing['H'] = False
        if a_runn >= h_runn and was_losing['A']:
            comeback_count['A'] += 1
            was_losing['A'] = False

    for side, label in (('H', 'comeback_H'), ('A', 'comeback_A')):
        # a team only 'came back' if they ended level or ahead
        if comeback_count[side] >= 2 and result in ('D', side):
            flags.append('multi_comeback_' + side)
        elif comeback_count[side] == 1 and result in ('D', side):
            flags.append(label)

    # blown-lead detection (result-aware: only counts when the side that was
    # winning ends the match level or behind)
    h_runn, a_runn = 0, 0
    was_winning = {'H': False, 'A': False}
    for minute, side in timeline:
        prev_h, prev_a = h_runn, a_runn
        if side == 'H':
            h_runn += 1
        else:
            a_runn += 1
        if prev_h > prev_a:
            was_winning['H'] = True
        if prev_a > prev_h:
            was_winning['A'] = True
        if was_winning['H'] and h_runn <= a_runn:
            if result in ('D', 'A'):
                flags.append('blown_H')
            was_winning['H'] = False
        if was_winning['A'] and a_runn <= h_runn:
            if result in ('D', 'H'):
                flags.append('blown_A')
            was_winning['A'] = False

    seen = set()
    unique = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def fetch_league(comp, date_start, date_end):
    slug = LEAGUES[comp]
    return fetch_league_feed(comp, slug, date_start, date_end, is_europe=False)


def fetch_league_feed(comp, slug, date_start, date_end, with_goals=True, is_europe=True):
    d = api_get(f'/{slug}/scoreboard?dates={date_start}-{date_end}')
    if not d:
        return []
    events = []
    for e in d.get('events', []):
        c0 = e['competitions'][0]
        if not c0['status']['type']['completed']:
            continue
        home = away = None
        for c in c0['competitors']:
            tid = c['team']['id']
            entry = {'id': tid,
                     'name': to_canonical_team(tid, c['team'].get('displayName')),
                     'score': int(c.get('score') or 0)}
            if c.get('homeAway') == 'home':
                home = entry
            elif c.get('homeAway') == 'away':
                away = entry
        if not home or not away:
            print(f'  ! {comp}: missing home/away, skipping')
            continue
        events.append((e['id'], home, away, c0, e))

    # full goal timeline from the per-match summary endpoint - fetched in
    # parallel threads (pure network I/O, ~12x faster than serial)
    def get_goals(eid, home, away):
        goals = []
        sumd = api_get(f'/{slug}/summary?event={eid}')
        if sumd:
            det = sumd.get('header', {}).get('competitions', [{}])[0].get('details', [])
            for dd in det:
                if dd.get('scoringPlay') is not True:
                    continue
                tid = (dd.get('team') or {}).get('id')
                minute = parse_minute(dd.get('clock', {}).get('displayValue'))
                if tid is None or minute is None:
                    continue
                if tid == home['id']:
                    side = 'H'
                elif tid == away['id']:
                    side = 'A'
                else:
                    continue
                goals.append({'min': minute, 'side': side})
        return goals

    if with_goals and events:
        from concurrent.futures import ThreadPoolExecutor
        workers = min(12, max(4, len(events)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            goals_by_id = dict(
                ex.map(lambda t: (t[0], get_goals(t[0], t[1], t[2])), events)
            )
    else:
        goals_by_id = {}

    out = []
    for eid, home, away, c0, e in events:
        goals = goals_by_id.get(eid, []) if with_goals else []

        home_goals = sum(1 for g in goals if g['side'] == 'H')
        away_goals = sum(1 for g in goals if g['side'] == 'A')
        if with_goals and home_goals == 0 and away_goals == 0 and (home['score'] or away['score']):
            print(f'  ! {comp} {home["name"]} vs {away["name"]}: no goal data from summary')
        elif with_goals and (home_goals != home['score'] or away_goals != away['score']):
            print(f'  ! {comp} {home["name"]} vs {away["name"]}: goal-count mismatch '
                  f'({home_goals}-{away_goals} vs {home["score"]}-{away["score"]}) '
                  f'- dropping goal timeline')
            goals = []

        flags = detect_drama_flags(goals)
        date = (c0.get('date') or e.get('date') or '')[:10]
        stage = stage_from_event(e, comp) if (is_europe or comp in CUP_LEAGUES) else ''
        out.append(dict(
            date=date, comp=comp, stage=stage, home=home['name'], away=away['name'],
            hg=home['score'], ag=away['score'], pen_h='', pen_a='',
            flags=';'.join(flags),
            goals=goals,
        ))
    out.sort(key=lambda r: (r['date'], r['home']))
    return out


def fetch_europe(comp, date_start, date_end):
    """Fetch completed matches for a European competition, main + qualifying feeds.
    Full summary (goal-minute) detail is fetched for the main league-phase feed;
    qualifying rounds are fetched from the scoreboard only (no per-goal summaries,
    which would add minutes of latency for little drama value)."""
    main_slug, qual_slug = EURO_LEAGUES[comp]
    recs = fetch_league_feed(comp, main_slug, date_start, date_end, with_goals=True, is_europe=True)
    recs += fetch_league_feed(comp, qual_slug, date_start, date_end, with_goals=False, is_europe=True)
    seen = set()
    out = []
    for r in sorted(recs, key=lambda x: (x['date'], x['home'])):
        key = (r['date'], r['comp'], r['home'], r['away'])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def fetch_cup(comp, date_start, date_end):
    """Fetch completed matches for a domestic cup from its ESPN feed."""
    slug = CUP_LEAGUES[comp]
    recs = fetch_league_feed(comp, slug, date_start, date_end, with_goals=True, is_europe=False)
    return sorted(recs, key=lambda r: (r['date'], r['home']))


def to_csv_line(r):
    goals_str = ''
    if r.get('goals'):
        goals_str = ';'.join(f"{g['min']}:{g['side']}" for g in r['goals'])
    return (f"{r['date']},{r['comp']},{r['stage']},{r['home']},{r['away']},"
            f"{r['hg']},{r['ag']},{r['pen_h']},{r['pen_a']},{r['flags']},{goals_str}")


def main():
    date_start = '20260801'
    date_end = '20260901'
    all_recs = []
    for comp in LEAGUES:
        recs = fetch_league(comp, date_start, date_end)
        print(f'  {comp}: {len(recs)} completed matches')
        all_recs.extend(recs)
    all_recs.sort(key=lambda r: (r['date'], r['comp'], r['home']))
    print(f'\n--- {len(all_recs)} total league matches ---')
    for r in all_recs:
        flag_str = f" [{r['flags']}]" if r['flags'] else ''
        print(f"  {r['date']} {r['comp']:>5} {r['home']} {r['hg']}-{r['ag']} "
              f"{r['away']}{flag_str}")
    return all_recs


if __name__ == '__main__':
    main()
