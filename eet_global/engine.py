"""
EET V2.3 global engine - stateful, team-agnostic.

Runs the Emotional Expectation Terror model across every match of a season for
all clubs in Europe's top 5 leagues plus their European and domestic cup runs.

Model (identical maths to eet_arsenal_engine.py, generalised to N teams):
  Layer 1  Ability   : ELO-based pre-match win probability + AS
  Layer 2  Generation : EX (expectation surprise), SI (drama x MOT),
                        occasion (CI/IMP x opponent strength), PJI, HUM -> EO
  Layer 3  Persistence: ES/SAT/DEF/ED/TS per team, then RP, TEAM_SCORE

State is carried forward per team chronologically with NO future information.
A single run recomputes the whole season deterministically from the results
table, so weekly updates are just: append results -> re-run -> refresh site.

Inputs (in data/):
  results.csv : date,comp,stage,home,away,hg,ag,pen_h,pen_a,flags
  fixtures.csv: date,comp,stage,home,away
  xg_cache.csv: date,home,away,home_xg,away_xg (optional, from FBref)

Rivalry (RIV) is deliberately 0 for now so the model generalises without
per-club hardcoding (see docs: RIV must never tip the scale).  The
drought-breaker is intentionally NOT implemented (feature deferred).

Pure stdlib.  No pandas/numpy/flask required.
"""
import csv
import math
import statistics
from pathlib import Path

# ---------------------------------------------------------------------------
# Load FBref xG cache (optional)
# ---------------------------------------------------------------------------
_XG_CACHE = {}
_XG_CACHE_PATH = Path(__file__).with_name("data") / "xg_cache.csv"
if _XG_CACHE_PATH.exists():
    with open(_XG_CACHE_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["date"], row["home"], row["away"])
            _XG_CACHE[key] = (float(row["home_xg"]), float(row["away_xg"]))

# ---------------------------------------------------------------------------
# Strength priors (pre-season estimates, anchored ~1500). Documented starter
# set for all clubs in Europe's top 5 leagues. Edit freely - they are priors.
# ---------------------------------------------------------------------------
DEFAULT_ELO = 1450.0
HOME_ADV = 60.0
ELO_K = 16.0
ELO_DIV = 400.0

BASE_ELO = {
    # Premier League 2026-27
    'Manchester City': 1525, 'Liverpool': 1518, 'Arsenal': 1535,
    'Aston Villa': 1450, 'Newcastle United': 1468, 'Tottenham Hotspur': 1462,
    'Chelsea': 1458, 'Brighton & Hove Albion': 1450, 'Manchester United': 1442,
    'Bournemouth': 1435, 'Brentford': 1400, 'Fulham': 1395,
    'Crystal Palace': 1392, 'Everton': 1380, 'Sunderland': 1365,
    'Leeds United': 1335, 'Nottingham Forest': 1360,
    'Coventry City': 1345, 'Hull City': 1330, 'Ipswich Town': 1325,
    # La Liga 2026-27
    'Real Madrid': 1545, 'Barcelona': 1530, 'Atletico Madrid': 1485,
    'Real Sociedad': 1430, 'Villarreal': 1425, 'Sevilla': 1420,
    'Athletic Club': 1415, 'Real Betis': 1410, 'Valencia': 1380, 'Celta Vigo': 1370,
    'Osasuna': 1360, 'Rayo Vallecano': 1340, 'Getafe': 1345,
    'Alaves': 1330, 'Espanyol': 1330,
    'Racing Santander': 1335, 'Levante': 1320, 'Elche': 1315,
    'Malaga': 1315, 'Deportivo La Coruna': 1325,
    # Bundesliga 2026-27
    'Bayern Munich': 1500, 'Bayer Leverkusen': 1480, 'RB Leipzig': 1445,
    'Borussia Dortmund': 1440, 'Eintracht Frankfurt': 1405, 'VfB Stuttgart': 1400,
    'SC Freiburg': 1360, 'Borussia Monchengladbach': 1355,
    'Hoffenheim': 1335, 'Mainz 05': 1330, 'Union Berlin': 1320,
    'FC Augsburg': 1315, 'Werder Bremen': 1310,
    '1. FC Koln': 1320, 'Hamburger SV': 1320, 'FC Schalke 04': 1310,
    'SC Paderborn 07': 1295, 'SV Elversberg': 1290,
    # Serie A 2026-27
    'Inter Milan': 1500, 'Juventus': 1490, 'AC Milan': 1480, 'Napoli': 1475,
    'Atalanta': 1465, 'Roma': 1455, 'Como': 1450, 'Lazio': 1435,
    'Bologna': 1415, 'Fiorentina': 1405, 'Udinese': 1350, 'Torino': 1345,
    'Cagliari': 1335, 'Monza': 1325, 'Genoa': 1320,
    'Lecce': 1305, 'Parma': 1310, 'Venezia': 1285,
    'Sassuolo': 1330, 'Frosinone': 1330,
    # Ligue 1 2026-27
    'Paris Saint-Germain': 1512, 'Marseille': 1400, 'AS Monaco': 1395,
    'Lyon': 1390, 'Lille': 1385, 'Nice': 1365, 'Rennes': 1360, 'Lens': 1350,
    'Strasbourg': 1340, 'Brest': 1305, 'Toulouse': 1300,
    'Le Havre': 1275, 'Angers': 1270, 'Auxerre': 1265,
    'Le Mans': 1300, 'Troyes': 1295, 'Paris FC': 1320, 'Lorient': 1290,
    # Cup minnows (low priors; anything unknown falls back to DEFAULT_ELO)
    'Portsmouth': 1360, 'Wigan Athletic': 1340, 'Mansfield Town': 1320,
    'Port Vale': 1300, 'Kairat Almaty': 1290,
    # Coppa Italia non-Serie A sides
    'Benevento': 1280, 'Catania': 1270, 'Arezzo': 1250, 'Avellino': 1260,
    'Mantova': 1275,
    # DFB-Pokal lower-league sides
    'Karlsruher SC': 1330, '1. FC Kaiserslautern': 1325, 'Hansa Rostock': 1300,
    'Hertha BSC': 1340, '1. FC Nurnberg': 1310, '1. FC Saarbrucken': 1305,
    'Hannover 96': 1335, 'Arminia Bielefeld': 1295, 'Holstein Kiel': 1320,
    'FC St. Pauli': 1330, 'VfL Bochum': 1310,
    'Dynamo Dresden': 1290, '1. FC Heidenheim': 1315, '1. FC Magdeburg': 1295,
    'SV Darmstadt 98': 1305,
}

# ---------------------------------------------------------------------------
# Competition definitions.  stage codes used in the input CSVs:
#   League  : stages ignored; matchweek number is derived from each team's
#             running count of league games.
#   Europe   : GRP, R32, R16, QF, SF, F
#   Domestic : R1..R7, QF, SF, F
# Each cup stage maps to (CI, IMP, MOT) - consequence, importance, motivation.
# ---------------------------------------------------------------------------
LEAGUES = {'PL', 'LALIGA', 'BL1', 'SA', 'FL1'}
EURO_CUPS = {'UCL', 'UEL', 'UECL'}
DOM_CUPS = {'FAC', 'CDR', 'DFB', 'CI', 'CDF', 'LC'}
SUPER_CUPS = {'CS'}

LEAGUE_NAME = {
    'PL': 'Premier League', 'LALIGA': 'La Liga', 'BL1': 'Bundesliga',
    'SA': 'Serie A', 'FL1': 'Ligue 1', 'UCL': 'UEFA Champions League',
    'UEL': 'UEFA Europa League', 'UECL': 'UEFA Conference League',
    'FAC': 'FA Cup', 'CDR': 'Copa del Rey', 'DFB': 'DFB-Pokal',
    'CI': 'Coppa Italia', 'CDF': 'Coupe de France', 'CS': 'Super Cup',
    'LC': 'Carabao Cup',
}

# Full 2026-27 squad lists per league (used to seed the EO grid with every
# club even before their first match of the season is played).
LEAGUE_TEAMS = {
    'PL': ['Manchester City', 'Liverpool', 'Arsenal', 'Aston Villa',
           'Newcastle United', 'Tottenham Hotspur', 'Chelsea',
           'Brighton & Hove Albion', 'Manchester United', 'Bournemouth',
           'Brentford', 'Fulham', 'Crystal Palace', 'Everton', 'Sunderland',
           'Leeds United', 'Nottingham Forest', 'Coventry City', 'Hull City',
           'Ipswich Town'],
    'LALIGA': ['Real Madrid', 'Barcelona', 'Atletico Madrid', 'Real Sociedad',
               'Villarreal', 'Sevilla', 'Athletic Club', 'Real Betis',
               'Valencia', 'Celta Vigo', 'Osasuna', 'Rayo Vallecano',
               'Getafe', 'Alaves', 'Espanyol', 'Racing Santander', 'Levante',
               'Elche', 'Malaga', 'Deportivo La Coruna'],
    'BL1': ['Bayern Munich', 'Bayer Leverkusen', 'RB Leipzig',
            'Borussia Dortmund', 'Eintracht Frankfurt', 'VfB Stuttgart',
            'SC Freiburg', 'Borussia Monchengladbach', 'Hoffenheim',
            'Mainz 05', 'Union Berlin', 'FC Augsburg', 'Werder Bremen',
            '1. FC Koln', 'Hamburger SV', 'FC Schalke 04',
            'SC Paderborn 07', 'SV Elversberg'],
    'SA': ['Inter Milan', 'Juventus', 'AC Milan', 'Atalanta', 'Roma',
           'Napoli', 'Lazio', 'Bologna', 'Fiorentina', 'Udinese', 'Torino',
           'Como', 'Cagliari', 'Monza', 'Genoa', 'Lecce', 'Parma',
           'Venezia', 'Sassuolo', 'Frosinone'],
    'FL1': ['Paris Saint-Germain', 'Marseille', 'AS Monaco', 'Lyon',
            'Lille', 'Nice', 'Rennes', 'Lens', 'Strasbourg', 'Brest',
            'Toulouse', 'Le Havre', 'Angers', 'Auxerre', 'Le Mans',
            'Troyes', 'Paris FC', 'Lorient'],
}

# league CI/MOT ramp by matchweek (title-race consequence builds through season)
def league_ramp(mw):
    if mw <= 10:
        return 0.8, 0.8
    if mw <= 20:
        return 1.2, 1.2
    if mw <= 30:
        return 1.6, 1.5
    if mw <= 36:
        return 2.0, 1.5
    return 2.4, 1.5

_EURO = {
    'UCL':  {'GRP': (1.2, 1.0, 0.8), 'R32': (1.6, 1.5, 1.5), 'R16': (2.0, 2.0, 2.0),
             'QF': (2.5, 3.0, 2.0), 'SF': (3.0, 4.0, 2.0), 'F': (4.5, 10.0, 2.0)},
    'UEL':  {'GRP': (1.0, 1.0, 0.7), 'R32': (1.4, 1.5, 1.2), 'R16': (1.8, 2.0, 1.5),
             'QF': (2.2, 3.0, 1.5), 'SF': (2.6, 4.0, 1.5), 'F': (3.5, 8.0, 1.5)},
    'UECL': {'GRP': (0.9, 1.0, 0.7), 'R32': (1.3, 1.5, 1.2), 'R16': (1.6, 2.0, 1.5),
             'QF': (2.0, 3.0, 1.5), 'SF': (2.4, 4.0, 1.5), 'F': (3.2, 8.0, 1.5)},
}
_DOM = {'R1': (0.4, 1.0, 0.7), 'R2': (0.5, 1.0, 0.7), 'R3': (0.6, 1.0, 0.8),
        'R4': (0.7, 1.0, 0.8), 'R5': (1.0, 1.0, 0.8), 'QF': (2.5, 3.0, 2.0),
        'SF': (1.2, 4.0, 1.5), 'F': (1.5, 8.0, 2.0)}
_SUPER = {'F': (1.5, 4.0, 1.5)}
DEFAULT_STAGE = (1.0, 1.0, 1.0)


def stage_params(comp, stage, mw):
    """Return (CI, IMP, MOT) for a competition / stage / league matchweek."""
    if comp in LEAGUES:
        ci, mot = league_ramp(mw)
        return ci, 1.0, mot
    if comp in EURO_CUPS:
        return _EURO[comp].get(stage, _EURO[comp].get('GRP', DEFAULT_STAGE))
    if comp in DOM_CUPS:
        return _DOM.get(stage, DEFAULT_STAGE)
    if comp in SUPER_CUPS:
        return _SUPER.get(stage, DEFAULT_STAGE)
    return DEFAULT_STAGE


# ---------------------------------------------------------------------------
# Model maths
# ---------------------------------------------------------------------------
def clip(x, lo, hi):
    return max(lo, min(hi, x))


def win_prob(eloa, elob, home_adv):
    gap = eloa + home_adv - elob
    return 1.0 / (1.0 + 10 ** (-gap / ELO_DIV))


def xg_proxy(team_elo, opp_elo, venue, date=None, home_team=None, away_team=None):
    """Return (xG_for, xG_against) for a team.
    Uses FBref cache if available for this match, otherwise falls back to ELO proxy.
    """
    # Try cache first
    if date and home_team and away_team:
        key = (date, home_team, away_team)
        if key in _XG_CACHE:
            hx, ax = _XG_CACHE[key]
            if venue == 'H':
                return clip(hx, 0.4, 2.8), clip(ax, 0.2, 2.2)
            else:
                return clip(ax, 0.4, 2.8), clip(hx, 0.2, 2.2)

    # Fallback: ELO-based proxy
    xgf = 1.35 + (team_elo - 1450.0) / 300.0 + max(0.0, (1450.0 - opp_elo) / 300.0)
    xga = 0.95 + max(0.0, (opp_elo - team_elo) / 700.0)
    xga += (0.25 if venue == 'A' else 0.0) - (0.12 if venue == 'H' else 0.0)
    return clip(xgf, 0.4, 2.8), clip(xga, 0.2, 2.2)


def expectation_surprise(pre_prob, result):
    if result == 'win':
        ex = (1.0 - pre_prob) * 6.0
    elif result == 'loss':
        ex = (0.0 - pre_prob) * 6.0
    else:
        ex = (0.5 - pre_prob) * 6.0
    return clip(ex, -5.0, 5.0)


def drama_si(flags, venue, gf=0, ga=0, comeback_details=None, result=None):
    """Surprise-incident score for the team at `venue` ('H' or 'A').

    Flag format is <kind>_<side>_<minute> e.g. late_win_H_92, comeback_A, f15_H, blown_A.

    `gf`/`ga` are this team's goals for/against, used to scale a comeback by
    how *tight* the final result was.
    `comeback_details` dict from _find_comeback_details for timing/margin scaling.
    """
    margin = gf - ga  # +ve = won by that many, 0 = draw, -ve = lost
    si = 0.0
    parsed = []  # track (kind, side) for late decider detection
    for f in flags:
        parts = f.split('_')
        if parts[0] == 'late' and len(parts) >= 3 and parts[-1].isdigit():
            kind = parts[0] + '_' + parts[1]
            side = parts[2]
            minute = int(parts[-1])
        elif parts[0] == 'late' and len(parts) == 3:
            kind = parts[0] + '_' + parts[1]
            side = parts[2]
            minute = 85
        elif len(parts) >= 2:
            kind = '_'.join(parts[:-1])
            side = parts[-1]
            minute = None
        else:
            continue

        if side not in ('H', 'A'):
            continue
        if kind == 'blown':
            # Blown only fires for the team that actually blew the lead,
            # not the opponent who capitalised (they get comeback instead).
            if side != venue:
                continue
            base = 2.5
            # Scale by how late the collapse happened
            if comeback_details and comeback_details['blown_minute'] is not None:
                bm = comeback_details['blown_minute']
                # Late collapse (75'+) = devastating, early (40') = mild
                time_mult = clip(0.4 + (bm - 30) / 70.0, 0.4, 1.2)
                # Scale by dominance: leading for 85 mins = worse than 13 mins
                dom = comeback_details.get('dominance', 0.0)
                dom_mult = clip(0.5 + dom, 0.5, 1.5)
                base *= time_mult * dom_mult
            val = base if side != venue else -base
        elif kind in ('comeback', 'multi_comeback'):
            # Comeback only fires for the team that actually came back (side == venue),
            # not the opponent who lost the lead (they get blown instead).
            if side != venue:
                continue
            base = 2.5 if kind == 'multi_comeback' else 2.0
            tight = clip(2.4 - abs(margin), 0.35, 1.2)
            # Scale by how late the comeback was and how big the deficit was
            if comeback_details and comeback_details['comeback_minute'] is not None:
                cm = comeback_details['comeback_minute']
                cd = comeback_details['comeback_deficit']
                # Late comeback (80+') from 2+ goal deficit = massive
                # Early comeback (45') from 1-goal deficit = mild
                time_mult = clip(0.3 + (cm - 30) / 60.0, 0.3, 1.3)
                deficit_mult = clip(cd / 2.0, 0.8, 1.5)
                tight *= time_mult * deficit_mult
            val = base * tight if side == venue else -base * tight
        elif kind == 'late_win':
            base = clip(2.5 + (minute - 80) * 0.1, 2.5, 4.0)
            clutch = 1.0 + clip((minute - 80) / 30.0, 0.0, 0.6)
            val = base * clutch if side == venue else -base * clutch
        elif kind == 'late_eq':
            # In draws, late_eq and blown/comeback describe the same moment.
            # Don't double-count — blown/comeback already cover the emotional arc.
            if result == 'draw' and any(
                f2.startswith(('comeback', 'blown', 'multi_comeback'))
                for f2 in flags if f2 != f
            ):
                continue
            base = clip(2.2 + (minute - 80) * 0.09, 2.2, 3.5)
            clutch = 1.0 + clip((minute - 80) / 30.0, 0.0, 0.5)
            val = base * clutch if side == venue else -base * clutch
        else:
            val = {'f15': 1.0}.get(kind, 0.0)
            # In draws, f15 is redundant — blown/comeback already capture the
            # emotional arc. Suppress it to avoid counteracting the drama signal.
            if result == 'draw' and any(
                f2.startswith(('comeback', 'blown', 'multi_comeback'))
                for f2 in flags if f2 != f
            ):
                val = 0.0
            val = val if side == venue else -val
        parsed.append((kind, side))
        si += val

    # Only cap when signals genuinely stack on the same moment. f15 is a minor
    # bonus that shouldn't count. Late_eq that was suppressed (blown/comeback
    # already present) shouldn't count either.
    drama_kinds = [k for k, _ in parsed if k not in ('f15',)]
    has_active_late = any(kind in ('late_win', 'late_eq') for kind in drama_kinds)
    if has_active_late and len(drama_kinds) >= 3:
        si *= 0.6


    return si


def _find_comeback_details(goals, target_side):
    """Parse goals timeline to find the DECISIVE comeback/blown moment —
    the last time the team came from behind or lost a lead, which is the
    one that actually decided the match.

    Returns dict with keys: comeback_minute, comeback_deficit,
    blown_minute, blown_ahead, dominance (0..1, fraction of match winning).
    """
    details = {'comeback_minute': None, 'comeback_deficit': 0,
               'blown_minute': None, 'blown_ahead': 0, 'dominance': 0.0}
    if not goals:
        return details

    timeline = sorted((g['min'], g['side']) for g in goals)
    h, a = 0, 0
    last_comeback_minute = None
    last_comeback_deficit = 0
    last_blown_minute = None
    last_blown_ahead = 0
    prev_minute = 0
    mins_winning = 0
    for minute, side in timeline:
        if h != a:
            mins_winning += (minute - prev_minute)
        prev_minute = minute

        if side == 'H':
            h += 1
        else:
            a += 1
        diff = h - a if target_side == 'H' else a - h

        if diff >= 0 and (h + a > 1):
            # Was behind before this goal? This is a comeback moment
            prev_diff = (h - 1 - a) if side == 'H' else (h - (a - 1))
            prev_diff_target = prev_diff if target_side == 'H' else -prev_diff
            if prev_diff_target < 0:
                last_comeback_minute = minute
                last_comeback_deficit = 1 if diff == 0 else abs(diff)

        if diff <= 0 and (h + a > 1):
            # Was ahead before this goal? This is a blown lead moment
            prev_diff = (h - 1 - a) if side == 'H' else (h - (a - 1))
            prev_diff_target = prev_diff if target_side == 'H' else -prev_diff
            if prev_diff_target > 0:
                last_blown_minute = minute
                last_blown_ahead = prev_diff_target

    if h != a:
        mins_winning += (90 - prev_minute)

    details['comeback_minute'] = last_comeback_minute
    details['comeback_deficit'] = last_comeback_deficit
    details['blown_minute'] = last_blown_minute
    details['blown_ahead'] = last_blown_ahead
    details['dominance'] = clip(mins_winning / 90.0, 0.0, 1.0)
    return details


def opponent_strength_mult(opp_elo):
    return clip(0.8 + (opp_elo - 1400.0) / 400.0, 0.8, 1.6)


def humiliation(pre_prob, result):
    if pre_prob > 0.70 and result == 'loss':
        return clip(-(pre_prob - 0.50) * 20.0, -10.0, 0.0)
    return 0.0


def fresh_state(elo):
    return dict(elo=elo, ES=0.0, SAT=0.0, DEF=0.0, ED=0.0, TS=0.0,
                recent=[], ev=0.0, pe=0.0)


def persistence(team_state, eo):
    """Layer 3 update in place.  Returns updated state fields."""
    s = team_state
    if eo > 0:
        s['ES'] = 0.80 * s['ES'] + 0.20 * eo
        s['SAT'] = s['SAT'] * 0.80 + eo * 0.20
        s['DEF'] = s['DEF'] * 0.80
    else:
        s['ES'] = 0.90 * s['ES'] + 0.30 * eo
        s['DEF'] = s['DEF'] * 0.80 + (-eo) * 0.30
        s['SAT'] = s['SAT'] * 0.80
    s['ED'] = s['ED'] * 0.80 + (eo * 0.10 if (eo > 0 and s['ES'] > 0) else 0.0)
    if eo < -5:
        s['TS'] += abs(eo)
    s['TS'] *= 0.95
    s['recent'].append(eo)
    s['recent'] = s['recent'][-5:]
    s['ev'] = statistics.stdev(s['recent']) if len(s['recent']) >= 3 else 0.0
    s['pe'] = 1.0 if (s['ES'] > 0 and s['TS'] < 2.0) else 0.0


# ---------------------------------------------------------------------------
# One match: compute per-team emotional record, then update both ELOs.
# ---------------------------------------------------------------------------
def process_match(state, m):
    """m: dict with date, comp, stage, home, away, hg, ag, pen_h, pen_a, flags.
    Returns (home_rec, away_rec) dicts of all computed EET fields."""
    home, away = m['home'], m['away']
    hs, as_ = state.setdefault(home, fresh_state(BASE_ELO.get(home, DEFAULT_ELO))), \
              state.setdefault(away, fresh_state(BASE_ELO.get(away, DEFAULT_ELO)))

    res_h = 'win' if m['hg'] > m['ag'] else ('loss' if m['hg'] < m['ag'] else 'draw')
    res_a = {'win': 'loss', 'loss': 'win', 'draw': 'draw'}[res_h]
    base_res_h = res_h  # normal-time result (drives ELO only)
    # penalty shootout decides the EMOTIONAL result if one occurred
    shootout = m.get('pen_h') is not None and m.get('pen_a') is not None \
        and (m['pen_h'] + m['pen_a']) > 0
    if shootout:
        if m['pen_h'] > m['pen_a']:
            res_h, res_a = 'win', 'loss'
        else:
            res_h, res_a = 'loss', 'win'

    pre_h = win_prob(hs['elo'], as_['elo'], HOME_ADV)
    pre_a = win_prob(as_['elo'], hs['elo'], -HOME_ADV)

    flags = m.get('flags') or []
    recs = {}
    for side, team, opp_team, pre_prob, res, venue in (
            ('home', home, away, pre_h, res_h, 'H'),
            ('away', away, home, pre_a, res_a, 'A')):
        s = state[team]
        opp_elo = state[opp_team]['elo']
        as_a = s['elo'] - 1400.0

        xgf, xga = xg_proxy(s['elo'], opp_elo, venue, m['date'], m['home'], m['away'])
        actual_diff = (m['hg'] - m['ag'] if side == 'home' else m['ag'] - m['hg'])
        xg_diff = xgf - xga
        # PJI = actual - xG: overperforming xG (clinical/lucky) feels good (+), underperforming feels bad (-)
        pji = clip(actual_diff - xg_diff, -1.5, 1.5)

        # Dampen positive PJI for heavy favorites winning narrowly - they should win by more
        if res == 'win' and pre_prob > 0.60 and actual_diff < xg_diff:
            # The more favored and the bigger the xG shortfall, the more dampening
            fav_factor = (pre_prob - 0.60) / 0.40  # 0..1 for 60%..100%
            shortfall = (xg_diff - actual_diff) / max(0.5, xg_diff)  # relative shortfall
            damp = clip(1.0 - fav_factor * shortfall * 0.7, 0.3, 1.0)
            pji *= damp

        ex = expectation_surprise(pre_prob, res)

        # Parse goals timeline for comeback/blown timing
        goals_raw = m.get('goals') or []
        if goals_raw and isinstance(goals_raw[0], str):
            # goals stored as "min:side" strings
            goals_list = []
            for g in goals_raw:
                parts = g.split(':')
                if len(parts) == 2:
                    goals_list.append({'min': int(parts[0]), 'side': parts[1]})
        elif goals_raw and isinstance(goals_raw[0], dict):
            goals_list = goals_raw
        else:
            goals_list = []
        comeback_details = _find_comeback_details(goals_list, 'H' if side == 'home' else 'A')

        si = drama_si(flags, 'H' if side == 'home' else 'A',
                      gf=(m['hg'] if side == 'home' else m['ag']),
                      ga=(m['ag'] if side == 'home' else m['hg']),
                      comeback_details=comeback_details,
                      result=res)
        ci, imp, mot = stage_params(m['comp'], m.get('stage', ''), m.get('mw', 0))

        # Robbery modifier: when PJI is negative (team created chances but
        # couldn't score) and they concede a late goal, that's not "expected
        # loss" — that's being robbed. Only fires when the result was close
        # (margin <= 1) or the team was actually leading — not when getting
        # hammered, because then PJI just reflects overall domination.
        robbery = 0.0
        margin = abs(m['hg'] - m['ag'])
        if si < 0 and pji < -0.3 and margin <= 2:
            robbery = -clip(abs(pji) * 1.5, 0.0, 2.0)

        # Margin dampening: drama signals (blown lead, comeback, late goal)
        # don't matter in a blowout. A 5-2 loss is just a loss — nobody cares
        # about the 1-0 lead you held for 11 minutes.
        margin_damp = clip(1.0 / max(1, margin), 0.3, 1.0)

        si_adj = (si + robbery) * mot * margin_damp

        occ_mult = opponent_strength_mult(opp_elo)
        # A 'rescue' = side trailed (was losing) then finished level or ahead.
        # For these, the pre-match underperformance ('a favourite who only
        # salvaged a draw') is irrelevant to the emotional outcome - the comeback
        # IS the story, so don't let the betting-expectation drag pull the drama
        # down. See use at the EO assembly below.
        came_back = res in ('draw', 'win') and (
            ('comeback_' + venue) in flags or ('multi_comeback_' + venue) in flags)
        occ_sign = 1.0 if (ex >= 0.0 or came_back) else -1.0
        occasion = (1.0 * ci + 0.5 * imp) * occ_mult * occ_sign

        hum = humiliation(pre_prob, res)
        # A humiliation only lands if the favourite was actually out-played.
        # If they still created chances (positive PJI / close xG), it wasn't a
        # humiliating beatdown - the scoreline says more than the performance.
        if hum < 0 and pji > 0:
            hum *= clip(1.0 - pji, 0.0, 0.6)

        # 'Breakthrough' bonus: when a genuine underdog (small pre-match chance)
        # beats a stronger side, it's a statement result - the kind of
        # promotion/drought-breaking win that deserves recognition over a
        # routine favourite comeback.
        breakthrough = 0.0
        if res == 'win' and pre_prob < 0.38:
            ups_prog = (0.38 - pre_prob) / 0.38  # 0..1 (bigger underdog -> bigger upset)
            breakthrough = 3.0 * ups_prog * mot

        # When SI is already very negative (blown lead, collapse), PJI
        # underperformance is redundant — the blown signal already tells
        # the story. Dampen to avoid double-punishing.
        if pji < 0 and si_adj < -1.0:
            pji_damp = clip(1.0 - abs(si_adj) / 5.0, 0.1, 1.0)
            pji *= pji_damp

        eo_raw = 1.0 * (ex if not came_back else max(ex, 0.0)) + 1.0 * si_adj + occasion + pji + hum + breakthrough
        # Negative EO is amplified only when a strong favourite was upset - a
        # genuinely shocking loss stings harder. A mild or expected bad result
        # (e.g. a 55-67% favourite dropping points) should NOT be supercharged.
        fav = pre_prob if res != 'win' else (1.0 - pre_prob)
        neg_boost = 1.0 + 0.8 * clip((fav - 0.70) / 0.25, 0.0, 1.0)
        eo = eo_raw * (neg_boost if eo_raw < 0 else 1.0)

        persistence(s, eo)

        rp = s['SAT'] + s['ED'] + 0.5 * s['TS'] - s['DEF']
        team_score = as_a + s['ES'] - rp
        as_opp = opp_elo - 1400.0
        edge = (as_a - as_opp) + (s['ES'] - rp)
        pred_prob = 1.0 / (1.0 + 10 ** (-edge / ELO_DIV))

        recs[side] = dict(
            team=team, opp=opp_team, comp=m['comp'], stage=m.get('stage', ''),
            date=m['date'], venue=venue, MW=m.get('mw_h' if side == 'home' else 'mw_a', 0),
            gf=(m['hg'] if side == 'home' else m['ag']),
            ga=(m['ag'] if side == 'home' else m['hg']),
            result=res,
            AS=round(as_a, 3), EX=round(ex, 3), SI=round(si, 3),
            SI_adj=round(si_adj, 3), CI=round(ci, 3), MOT=round(mot, 2),
            PJI=round(pji, 3), IMP=round(imp, 1), HUM=round(hum, 2), RIV=0.0,
            EO_raw=round(eo_raw, 3), EO=round(eo, 3),
            ES=round(s['ES'], 3), SAT=round(s['SAT'], 3), DEF=round(s['DEF'], 3),
            ED=round(s['ED'], 3), TS=round(s['TS'], 3), EV=round(s['ev'], 3),
            PE=round(s['pe'], 2), RP=round(rp, 3),
            TEAM_SCORE=round(team_score, 3),
            edge=round(edge, 3), pred_prob=round(pred_prob, 4),
            pre_prob=round(pre_prob, 4), elo=round(s['elo'], 1),
            opp_elo=round(opp_elo, 1),
        )

    # ELO update once per match from the NORMAL-TIME result (no shootout effect)
    expected_h = win_prob(hs['elo'], as_['elo'], HOME_ADV)
    actual_h = {'win': 1.0, 'loss': 0.0, 'draw': 0.5}[base_res_h]
    hs['elo'] += ELO_K * (actual_h - expected_h)
    as_['elo'] = as_['elo'] + ELO_K * ((1.0 - actual_h) - (1.0 - expected_h))

    return recs['home'], recs['away']