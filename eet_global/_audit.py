import csv, os

path = os.path.join('data', 'results.csv')
lines = []
with open(path, encoding='utf-8-sig') as f:
    for line in f:
        if line.strip() and not line.lstrip().startswith('#'):
            lines.append(line)

rows = list(csv.DictReader(lines))
from collections import Counter
per_comp = Counter()
flags_missing = Counter()   # matches with NO flags (potential under-score)
flag_kinds = Counter()

for r in rows:
    comp = r['comp']
    per_comp[comp] += 1
    fl = [x for x in (r.get('flags') or '').split(';') if x]
    if not fl:
        flags_missing[comp] += 1
    for x in fl:
        flag_kinds[x] += 1

print('Matches per comp (total vs no-flag):')
for comp, n in sorted(per_comp.items()):
    print(f'  {comp:>6}: {n} total, {flags_missing.get(comp,0)} with NO drama flags')

print('\nFlag kinds used (all comps):')
for k, v in sorted(flag_kinds.items()):
    print(f'  {k}: {v}')
