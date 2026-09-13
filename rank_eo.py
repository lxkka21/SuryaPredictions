import csv

vars_rows = {}
with open('arsenal_2025_26_eet_vars.csv', encoding='utf-8-sig') as f:
    r = csv.DictReader(f)
    for row in r:
        vars_rows[row['date']] = row

preds = {}
with open('arsenal_2025_26_predictions.csv', encoding='utf-8-sig') as f:
    r = csv.DictReader(f)
    for row in r:
        preds[row['date']] = row

rows = []
for d, v in vars_rows.items():
    p = preds[d]
    rows.append({'rank': 0, 'date': d, 'comp': v['comp'], 'opp': v['opp'],
                 'result': p['result'], 'gf': p['gf'], 'ga': p['ga'],
                 'EO': float(v['EO']), 'EO_raw': float(v['EO_raw']),
                 'EX': float(v['EX']), 'SI': float(v['SI']),
                 'ES': float(v['ES']), 'TEAM_SCORE': float(v['TEAM_SCORE'])})

rows.sort(key=lambda x: x['EO'], reverse=True)
for i, r in enumerate(rows, 1):
    r['rank'] = i

out = 'arsenal_2025_26_eo_ranking.csv'
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['rank', 'date', 'comp', 'opp', 'result',
                                      'gf', 'ga', 'EO', 'EO_raw', 'EX', 'SI',
                                      'ES', 'TEAM_SCORE'])
    w.writeheader()
    w.writerows(rows)

for r in rows:
    print(f"{r['rank']:>2} {r['date']} {r['comp']:>3} {r['opp']:<22} {r['result']:<4} EO={r['EO']:>8}")
print(f"\nwrote {len(rows)} rows -> {out}")
