import csv
from collections import defaultdict, OrderedDict

team_history = list(csv.DictReader(open('team_match_history.csv', encoding='utf-8-sig')))
master_list = list(csv.DictReader(open('world_cup_2022_eet_master.csv', encoding='utf-8-sig')))
goals_list = list(csv.DictReader(open('world_cup_2022_goal_events.csv', encoding='utf-8-sig')))

master_by_id = {r['match_id']: r for r in master_list}

goals_by_match_team = defaultdict(lambda: defaultdict(list))
for g in goals_list:
    mid = g['match_id']
    team = g['team']
    minute = int(g['minute'])
    goals_by_match_team[mid][team].append(minute)

gs_match_count = defaultdict(int)
stage_order = {
    'Group Stage': 0, 'Round of 16': 1, 'Quarter Final': 2,
    'Semi Final': 3, 'Third Place Playoff': 4, 'Final': 5
}

results = []
for row in team_history:
    team = row['team']
    opponent = row['opponent']
    date = row['date']
    mid = row['match_id']
    result = row['result']
    mr = master_by_id[mid]
    stage = mr['stage']

    if stage == 'Group Stage':
        gs_match_count[team] += 1
        match_num = gs_match_count[team]
    else:
        match_num = 0

    exp_win = float(row['expected_win_probability'])

    if result == 'win':
        ex = (1.0 - exp_win) * 6.0
    elif result == 'loss':
        ex = (0.0 - exp_win) * 6.0
    else:
        ex = (0.5 - exp_win) * 6.0
    ex = max(-5.0, min(5.0, ex))

    si = 0.0
    if row['late_winner'] == '1':
        si += 1.5
    if row['late_equalizer'] == '1':
        si += 1.0
    if row['comeback_win'] == '1':
        si += 2.0
    if row['blown_lead'] == '1':
        si += -2.0

    if mid in goals_by_match_team and team in goals_by_match_team[mid]:
        for gmin in goals_by_match_team[mid][team]:
            if 75 <= gmin <= 90:
                si += 1.0
                break

    if row['penalty_shootout'] == '1':
        sw = mr.get('shootout_winner', '').strip()
        if sw == team:
            si += 2.0
        elif sw == opponent:
            si += -2.0

    if stage == 'Group Stage':
        ci_map = {1: 0.8, 2: 1.0, 3: 1.2}
        ci = ci_map.get(match_num, 1.0)
    elif stage == 'Round of 16':
        ci = 2.0
    elif stage == 'Quarter Final':
        ci = 2.5
    elif stage == 'Semi Final':
        ci = 3.0
    elif stage == 'Third Place Playoff':
        ci = 0.5
    elif stage == 'Final':
        ci = 4.5
    else:
        ci = 1.0

    pji = float(row['pji_raw'])
    pji = max(-1.5, min(1.5, pji))

    imp_map = {
        'Group Stage': 1, 'Round of 16': 2, 'Quarter Final': 3,
        'Semi Final': 4, 'Third Place Playoff': 1, 'Final': 10
    }
    imp = imp_map.get(stage, 1)

    hum = 0.0
    if exp_win > 0.70 and result == 'loss':
        hum = -(exp_win - 0.50) * 20
        hum = max(-10.0, min(0.0, hum))

    eo_raw = 2.0 * ex + 1.0 * si + 1.0 * ci + 0.5 * imp + pji + hum
    multiplier = 1.5 if eo_raw < 0 else 1.0
    eo = eo_raw * multiplier

    results.append({
        'team': team, 'opponent': opponent, 'date': date,
        'match_id': mid, 'stage': stage,
        'EX': round(ex, 3), 'SI': round(si, 3), 'CI': round(ci, 3),
        'PJI': round(pji, 3), 'IMP': round(imp, 3), 'HUM': round(hum, 3),
        'EO_raw': round(eo_raw, 3), 'EO': round(eo, 3)
    })

results.sort(key=lambda r: (r['date'], r['match_id']))

with open('eet_match_emotions.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=[
        'team', 'opponent', 'date', 'match_id', 'stage',
        'EX', 'SI', 'CI', 'PJI', 'IMP', 'HUM', 'EO_raw', 'EO'
    ])
    w.writeheader()
    w.writerows(results)

print("eet_match_emotions.csv written (" + str(len(results)) + " rows)")

top50 = sorted(results, key=lambda r: r['EO'], reverse=True)[:50]
print()
print(f"{'Rank':<5} {'Team':<22} {'Opponent':<22} {'Stage':<22} {'EX':<8} {'SI':<8} {'CI':<8} {'PJI':<8} {'IMP':<8} {'HUM':<8} {'EO':<8}")
print("-" * 130)
for i, r in enumerate(top50, 1):
    print(f"{i:<5} {r['team']:<22} {r['opponent']:<22} {r['stage']:<22} {r['EX']:<8} {r['SI']:<8} {r['CI']:<8} {r['PJI']:<8} {r['IMP']:<8} {r['HUM']:<8} {r['EO']:<8}")
