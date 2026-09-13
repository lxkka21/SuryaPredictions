"""
import_espn.py - Rebuild data/results.csv from accurate (goal-minute) ESPN data
for the top-5 leagues, while preserving the existing cup matches (CI, CS, LC)
that ESPN's league feeds don't cover.

Safe steps:
  1. backs up the current results.csv -> results.backup_<ts>.csv
  2. pulls fresh accurate league results via fetch_espn.py
  3. keeps cup rows (comp in CUPS) from the backup exactly as they were
  4. writes a clean, deduplicated results.csv (header + cups + accurate leagues)

Usage:
    python import_espn.py --dry      # preview only, no changes
    python import_espn.py --from-csv # skip ESPN fetch, recompute site from existing results.csv
    python import_espn.py            # perform the rebuild
"""
import csv
import os
import sys
from datetime import datetime

import fetch_espn

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
RESULTS_CSV = os.path.join(DATA, 'results.csv')

LEAGUES = ('PL', 'LALIGA', 'BL1', 'SA', 'FL1')
# Cups preserved verbatim from the previous results.csv (not covered by the ESPN
# league/European feeds). UCL/UEL/UECL and the domestic cups fetched via
# fetch_espn.CUP_LEAGUES (LC/FAC/CDR/DFB/CI/CDF) are fetched fresh with goal
# data, so they are NOT preserved here. CS (Super Cup) has no ESPN feed so it
# is carried over unchanged.
CUPS = ('CS',)

# European competitions: keep only matches that involve a club already tracked
# on the site (a top-5 league team). Qualifying-round ties between two obscure
# non-site teams (e.g. Larne vs Iberia 1999) are dropped so the Europa League /
# Conference League sections only show clubs the site actually covers.
EURO_COMPS = ('UCL', 'UEL', 'UECL')


def load_site_teams():
    from engine import LEAGUE_TEAMS
    site = set()
    for names in LEAGUE_TEAMS.values():
        site.update(names)
    return site

HEADER = 'date,comp,stage,home,away,hg,ag,pen_h,pen_a,flags,goals\n'


def read_existing_cups():
    cups = []
    if not os.path.exists(RESULTS_CSV):
        return cups
    lines = []
    with open(RESULTS_CSV, encoding='utf-8-sig') as f:
        for line in f:
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            lines.append(line)
    if not lines:
        return cups
    for row in csv.DictReader(lines):
        comp = (row.get('comp') or '').strip()
        if comp in CUPS:
            cups.append(row)
    cups.sort(key=lambda r: (r.get('date', ''), r.get('comp', ''), r.get('home', '')))
    return cups


def main():
    dry = '--dry' in sys.argv
    from_csv = '--from-csv' in sys.argv

    if from_csv:
        if not os.path.exists(RESULTS_CSV):
            sys.exit(f'--from-csv requires existing {RESULTS_CSV}')
        print(f'Reusing existing results.csv ({sum(1 for _ in open(RESULTS_CSV, encoding="utf-8-sig"))} lines)')
        return

    # 1. fetch accurate league results
    print('Fetching accurate league results from ESPN (goal-minute data)...')
    date_start, date_end = '20260801', datetime.now().strftime('%Y%m%d')
    league_recs = []
    for comp in fetch_espn.LEAGUES:
        recs = fetch_espn.fetch_league(comp, date_start, date_end)
        print(f'  {comp}: {len(recs)} matches')
        league_recs.extend(recs)

    # 1b. fetch European competitions (UCL / UEL / UECL) from ESPN feeds
    print('Fetching European competitions from ESPN (goal-minute data)...')
    site_teams = load_site_teams()
    for comp in EURO_COMPS:
        recs = fetch_espn.fetch_europe(comp, date_start, date_end)
        before = len(recs)
        recs = [r for r in recs
                if r['home'] in site_teams or r['away'] in site_teams]
        print(f'  {comp}: {len(recs)} matches '
              f'({before - len(recs)} dropped - no site team)')
        league_recs.extend(recs)

    # 1c. fetch domestic cups with ESPN coverage (Carabao Cup), site-team only
    print('Fetching domestic cups from ESPN (goal-minute data)...')
    for comp in fetch_espn.CUP_LEAGUES:
        recs = fetch_espn.fetch_cup(comp, date_start, date_end)
        before = len(recs)
        recs = [r for r in recs
                if r['home'] in site_teams or r['away'] in site_teams]
        print(f'  {comp}: {len(recs)} matches '
              f'({before - len(recs)} dropped - no site team)')
        league_recs.extend(recs)

    league_recs.sort(key=lambda r: (r['date'], r['comp'], r['home']))

    # 2. preserve existing cups
    cups = read_existing_cups()
    print(f'Preserving {len(cups)} existing cup matches (not covered by ESPN league feed)')

    # 3. assemble final rows
    rows = []
    for r in cups:
        rows.append((r.get('date', ''), r.get('comp', ''), r.get('home', ''), r))
    for r in league_recs:
        rows.append((r['date'], r['comp'], r['home'], r))
    # dedupe on (date, comp, home, away)
    seen = set()
    final = []
    for date, comp, home, row in rows:
        away = row.get('away', '')
        key = (date, comp, home, away)
        if key in seen:
            continue
        seen.add(key)
        final.append(row)

    def format_row(r, is_league):
        if is_league:
            return fetch_espn.to_csv_line(r) + '\n'
        goals_str = r.get('goals', '')
        if isinstance(goals_str, list):
            goals_str = ';'.join(f"{g['min']}:{g['side']}" for g in goals_str)
        return (f"{r.get('date','')},{r.get('comp','')},{r.get('stage','')},"
                f"{r.get('home','')},{r.get('away','')},{r.get('hg','')},{r.get('ag','')},"
                f"{r.get('pen_h','')},{r.get('pen_a','')},{r.get('flags','')},{goals_str}\n")

    # final ordering: by date, comp, home
    def sort_key(r):
        return (r.get('date', ''), r.get('comp', ''), r.get('home', ''))
    final.sort(key=sort_key)

    lines_out = [HEADER]
    for r in final:
        comp = r.get('comp', '')
        is_league = comp in LEAGUES
        lines_out.append(format_row(r, is_league))

    all_rows = final
    if dry:
        print(f'\n--- DRY RUN: {len(all_rows)} rows would be written ---')
        print(f'  of which {sum(1 for r in all_rows if r.get("comp") in LEAGUES)} league '
              f'({sum(1 for r in all_rows if r.get("comp") in CUPS)} cups)')
        print('  leagues by comp:')
        from collections import Counter
        for c, n in sorted(Counter(r['comp'] for r in all_rows).items()):
            print(f'    {c}: {n}')
        print('  sample league rows with flags:')
        shown = 0
        for r in all_rows:
            if r.get('comp') in LEAGUES and r.get('flags'):
                print('    ', fetch_espn.to_csv_line(r))
                shown += 1
                if shown >= 15:
                    break
        return

    # backup
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = os.path.join(DATA, f'results.backup_{ts}.csv')
    if os.path.exists(RESULTS_CSV):
        with open(RESULTS_CSV, encoding='utf-8-sig') as f:
            old = f.read()
        with open(backup, 'w', encoding='utf-8') as f:
            f.write(old)
        print(f'Backed up old results.csv -> {backup}')

    with open(RESULTS_CSV, 'w', encoding='utf-8', newline='') as f:
        f.write(''.join(lines_out))
    print(f'Rebuilt results.csv with {len(all_rows)} rows.')


if __name__ == '__main__':
    main()
