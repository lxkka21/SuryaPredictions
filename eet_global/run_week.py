"""
run_week.py - EET V2.3 weekly update for Europe's top 5 leagues.

Usage (after each weekend's fixtures are known):
    1. Append the week's scores to  data/results.csv
       (one line per match:  date,comp,stage,home,away,hg,ag,pen_h,pen_a,flags)
       and optionally add upcoming fixtures to data/fixtures.csv.
    2.  python run_week.py
    3. Open the local site:   python -m http.server 8000 --directory site
       then browse http://localhost:8000  (site/data/*.json are rewritten here)

The whole season is recomputed deterministically each run, so editing an
old result also corrects everything downstream.  Pure stdlib.
"""
import csv
import json
import os
import sys
from datetime import datetime

from engine import (
    LEAGUES, LEAGUE_NAME, EURO_CUPS, DOM_CUPS, SUPER_CUPS,
    BASE_ELO, DEFAULT_ELO, process_match, fresh_state,
)

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
SITE_DATA = os.path.join(BASE, 'site', 'data')
RESULTS_CSV = os.path.join(DATA, 'results.csv')
FIXTURES_CSV = os.path.join(DATA, 'fixtures.csv')

OUT_SUMMARY = os.path.join(SITE_DATA, 'summary.json')
OUT_MATCHES = os.path.join(SITE_DATA, 'matches.json')
OUT_TEAMS = os.path.join(SITE_DATA, 'teams.json')
OUT_FIXTURES = os.path.join(SITE_DATA, 'fixtures.json')
OUT_RANKINGS = os.path.join(SITE_DATA, 'rankings.json')


def read_csv(fname, required=False):
    rows = []
    if not os.path.exists(fname):
        if required:
            sys.exit(f"missing required input: {fname}")
        return rows
    lines = []
    with open(fname, encoding='utf-8-sig') as f:
        for line in f:
            if not line.strip():
                continue
            if line.lstrip().startswith('#'):
                continue
            lines.append(line)
    if not lines:
        if required:
            sys.exit(f"missing required input: {fname}")
        return rows
    for row in csv.DictReader(lines):
        if not row or not (row.get('date') or '').strip():
            continue
        rows.append(row)
    return rows


def parse_int(v):
    v = (v or '').strip()
    return int(v) if v else None


def parse_goals(s):
    """Parse goals string like '45:H,67:A,89:H' into list of {min, side}."""
    s = (s or '').strip()
    if not s:
        return []
    out = []
    for part in s.split(';'):
        if ':' not in part:
            continue
        m, side = part.split(':', 1)
        try:
            out.append({'min': int(m), 'side': side})
        except ValueError:
            pass
    return out


def build_matches():
    raw = read_csv(RESULTS_CSV, required=True)
    matches = []
    league_count = {}  # team -> running league games
    for i, r in enumerate(raw):
        try:
            date = r['date'].strip()
            comp = r['comp'].strip()
            home = r['home'].strip()
            away = r['away'].strip()
            hg, ag = int(r['hg']), int(r['ag'])
            stage = (r.get('stage') or '').strip()
        except (KeyError, ValueError) as e:
            print(f"  ! skipping bad result row {i+1}: {e} -- {dict(r)}")
            continue
        if comp in LEAGUES:
            league_count.setdefault(home, 0)
            league_count.setdefault(away, 0)
            league_count[home] += 1
            league_count[away] += 1
            mw = league_count[home]
            mw_a = league_count[away]
        else:
            mw = 0
            mw_a = 0
        matches.append(dict(
            id=f"{date}_{comp}_{home}_v_{away}", i=i, date=date, comp=comp,
            stage=stage, home=home, away=away, hg=hg, ag=ag,
            pen_h=parse_int(r.get('pen_h')), pen_a=parse_int(r.get('pen_a')),
            flags=[x.strip() for x in (r.get('flags') or '').split(';') if x.strip()],
            goals=parse_goals(r.get('goals', '')),
            mw=mw, mw_h=mw, mw_a=mw_a,
        ))
    matches.sort(key=lambda m: (m['date'], m['i']))
    return matches


def build_fixtures():
    rows = read_csv(FIXTURES_CSV)
    out = []
    for i, r in enumerate(rows):
        try:
            out.append(dict(
                date=r['date'].strip(), comp=r['comp'].strip(),
                kickoff_utc=(r.get('kickoff_utc') or '').strip(),
                stage=(r.get('stage') or '').strip(),
                home=r['home'].strip(), away=r['away'].strip(),
            ))
        except KeyError:
            print(f"  ! skipping bad fixture row {i+1}: {dict(r)}")
    out.sort(key=lambda f: (f.get('kickoff_utc') or f['date'], f['comp'], f['home']))
    return out


def main():
    os.makedirs(SITE_DATA, exist_ok=True)
    matches = build_matches()
    fixtures = build_fixtures()

    state = {}
    team_records = []   # flat per-team records (2 per match)
    match_out = []
    # per-team rolling W/D/L/GF/GA/points for context tables
    table = {}

    for m in matches:
        if m['comp'] not in LEAGUES and not m.get('stage'):
            print(f"  ! {m['date']} {m['home']} v {m['away']}: no stage for cup/Europe - using default")
        try:
            hrec, arec = process_match(state, m)
        except Exception as e:
            print(f"  ! engine failed on {m['home']} v {m['away']}: {e}")
            continue

        for rec in (hrec, arec):
            team_records.append(rec)
            t = table.setdefault(rec['team'], dict(W=0, D=0, L=0, GF=0, GA=0, P=0))
            t['GF'] += rec['gf']
            t['GA'] += rec['ga']
            if rec['result'] == 'win':
                t['W'] += 1
                t['P'] += 3
            elif rec['result'] == 'draw':
                t['D'] += 1
                t['P'] += 1
            else:
                t['L'] += 1

        match_out.append(dict(
            id=m['id'], date=m['date'], comp=m['comp'],
            stage=m.get('stage', ''), home=m['home'], away=m['away'],
            hg=m['hg'], ag=m['ag'], pen_h=m['pen_h'], pen_a=m['pen_a'],
            result_h='win' if m['hg'] > m['ag'] else ('loss' if m['hg'] < m['ag'] else 'draw'),
            home_rec=hrec, away_rec=arec,
            goals=m.get('goals', []),
        ))

    # ---------------- team summary ----------------
    teams = {}
    for rec in team_records:
        team = rec['team']
        s = state[team]
        t = table.get(team, dict(W=0, D=0, L=0, GF=0, GA=0, P=0))
        teams[team] = teams.get(team, dict(
            team=team, elo=round(s['elo'], 1), AS=round(s['elo'] - 1400.0, 3),
            ES=s['ES'], SAT=s['SAT'], DEF=s['DEF'], ED=s['ED'], TS=s['TS'],
            EV=s['ev'], PE=s['pe'], RP=round(s['SAT'] + s['ED'] + 0.5 * s['TS'] - s['DEF'], 3),
            TEAM_SCORE=round((s['elo'] - 1400.0) + s['ES'] - (s['SAT'] + s['ED'] + 0.5 * s['TS'] - s['DEF']), 3),
            W=t['W'], D=t['D'], L=t['L'], P=t['P'], GF=t['GF'], GA=t['GA'],
            form=[], league='', last_date='',
        ))
        d = teams[team]
        d['form'].insert(0, dict(date=rec['date'], comp=rec['comp'], opp=rec['opp'],
                                 result=rec['result'], EO=rec['EO'], MW=rec['MW'],
                                 score=f"{rec['gf']}-{rec['ga']}", PJI=rec.get('PJI', 0.0),
                                 team=team))
        d['last_date'] = rec['date']

    for rec in team_records:
        if rec['comp'] in LEAGUES:
            teams[rec['team']]['league'] = LEAGUE_NAME[rec['comp']]

    # Compute rolling 5-game average EO per team
    for team, d in teams.items():
        form = d.get('form', [])
        recent5 = form[:5]
        if recent5:
            d['avg_5eo'] = round(sum(f['EO'] for f in recent5) / len(recent5), 3)
        else:
            d['avg_5eo'] = 0.0
        # plain (unweighted) average of the last two played EOs - shown next to
        # each team in the fixtures tab.
        recent2 = form[:2]
        if recent2:
            d['avg_last2'] = round(sum(f['EO'] for f in recent2) / len(recent2), 3)
        else:
            d['avg_last2'] = 0.0

    # Seed every club of each league (even those yet to play) so the site's
    # EO grid shows the full 20-team list from day one.
    from engine import LEAGUE_TEAMS
    for comp, names in LEAGUE_TEAMS.items():
        for name in names:
            if name in teams:
                continue
            teams[name] = dict(
                team=name, elo=round(BASE_ELO.get(name, DEFAULT_ELO), 1),
                AS=round(BASE_ELO.get(name, DEFAULT_ELO) - 1400.0, 3),
                ES=0.0, SAT=0.0, DEF=0.0, ED=0.0, TS=0.0,
                EV=0.0, PE=0.0, RP=0.0, TEAM_SCORE=round(BASE_ELO.get(name, DEFAULT_ELO) - 1400.0, 3),
                W=0, D=0, L=0, P=0, GF=0, GA=0, form=[], league=LEAGUE_NAME[comp],
                last_date='', avg_5eo=0.0, avg_last2=0.0,
            )
    team_list = sorted(teams.values(), key=lambda x: x['TEAM_SCORE'], reverse=True)

    # ---------------- rankings ----------------
    team_records.sort(key=lambda r: abs(r['EO']), reverse=True)
    top_moments = [dict(r) for r in team_records[:60]]

    # ---------------- write JSON ----------------
    # Include all competitions (leagues + cups + Europe) in the summary
    all_comps = sorted({m['comp'] for m in match_out})
    summary = dict(
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
        match_count=len(match_out),
        team_count=len(team_list),
        leagues={comp: dict(
            name=LEAGUE_NAME.get(comp, comp),
            matches=sum(1 for m in match_out if m['comp'] == comp),
        ) for comp in sorted(LEAGUES)},
        cups={comp: dict(
            name=LEAGUE_NAME.get(comp, comp),
            matches=sum(1 for m in match_out if m['comp'] == comp),
        ) for comp in all_comps if comp not in LEAGUES},
        competitions=all_comps,
        teams_seen=len(state),
    )
    with open(OUT_SUMMARY, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=1)
    with open(OUT_MATCHES, 'w', encoding='utf-8') as f:
        json.dump(match_out, f, indent=1)
    with open(OUT_TEAMS, 'w', encoding='utf-8') as f:
        json.dump(team_list, f, indent=1)
    with open(OUT_RANKINGS, 'w', encoding='utf-8') as f:
        json.dump(top_moments, f, indent=1)
    # Enrich fixtures with each team's last-2-EO average (plain mean) for the
    # fixtures tab, plus extra context fields.
    for fx in fixtures:
        fx['home_avg2'] = teams.get(fx['home'], {}).get('avg_last2', 0.0)
        fx['away_avg2'] = teams.get(fx['away'], {}).get('avg_last2', 0.0)
        fx['home_avg5eo'] = teams.get(fx['home'], {}).get('avg_5eo', 0.0)
        fx['away_avg5eo'] = teams.get(fx['away'], {}).get('avg_5eo', 0.0)
        fx['home_es'] = teams.get(fx['home'], {}).get('ES', 0.0)
        fx['away_es'] = teams.get(fx['away'], {}).get('ES', 0.0)
        fx['home_ts'] = teams.get(fx['home'], {}).get('TEAM_SCORE', 0.0)
        fx['away_ts'] = teams.get(fx['away'], {}).get('TEAM_SCORE', 0.0)
    with open(OUT_FIXTURES, 'w', encoding='utf-8') as f:
        json.dump(fixtures, f, indent=1)

    # ---------------- console summary ----------------
    from collections import Counter
    comp_counts = Counter(m['comp'] for m in match_out)
    print(f"EET V2.3 global update  ({summary['generated_at']})")
    print(f"  {summary['match_count']} matches, {summary['team_count']} teams, "
          f"{summary['teams_seen']} clubs seen")
    print("  by competition:")
    for comp, n in sorted(comp_counts.items()):
        print(f"    {LEAGUE_NAME.get(comp, comp):<28} {n}")
    print("\n  Top moments (by |EO|):")
    for i, r in enumerate(team_records[:8], 1):
        print(f"    {i:>2} {r['date']} {r['team']:<24} {r['comp']:>4} "
              f"{r['opp']:<24} EO={r['EO']:>6} EX={r['EX']:>6} SI={r['SI']:>5}")
    print("\n  Top teams (by TEAM_SCORE):")
    for i, r in enumerate(team_list[:8], 1):
        print(f"    {i:>2} {r['team']:<26} {r['elo']:>7.1f} TS={r['TEAM_SCORE']:>7.1f} "
              f"ES={r['ES']:>6.1f} RP={r['RP']:>6.1f}")
    print("\n  Serve the site with:  python -m http.server 8000 --directory site")
    print("  then open http://localhost:8000")


if __name__ == '__main__':
    main()
