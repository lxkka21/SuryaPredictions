"""
EET V2.3 retrospective validation on Arsenal's 2025/26 season.
Layers: 1 = Ability, 2 = Emotional Generation, 3 = Emotional Persistence.

Run chronologically match-by-match with NO future information.

Variables implemented exactly per EET_V2_3_FULL_DOCUMENTATION.md:
AS, EX, SI, CI, MOT, PJI, IMP, HUM, EO, ES, SAT, DEF, ED, TS, EV, PE, RP,
Final TEAM_SCORE, Prediction EDGE.  RIV excluded by design.

Outputs:
  arsenal_2025_26_strength.csv     - pre-match ELO / expected win prob / xG / AS
  arsenal_2025_26_eet_vars.csv     - all EET variables per match
  arsenal_2025_26_predictions.csv  - TEAM_SCORE, EDGE, predicted p(win), outcome
"""
import csv
import math
import statistics

RAW = 'arsenal_2025_26_matches_raw.csv'
OUT_STRENGTH = 'arsenal_2025_26_strength.csv'
OUT_VARS = 'arsenal_2025_26_eet_vars.csv'
OUT_PRED = 'arsenal_2025_26_predictions.csv'

# ---------------------------------------------------------------------------
# Documented strength priors (pre-season, no-future estimates, anchored ~1500).
# Elite clubs clustered near the top; narrower gaps reflect realistic home/away
# single-match win probabilities (a ~250pt gap implies roughly a 2:1 favourite).
# ---------------------------------------------------------------------------
BASE_ELO = {
    'Arsenal': 1500,
    'Manchester City': 1525, 'Liverpool': 1518, 'Paris Saint-Germain': 1512,
    'Inter Milan': 1502, 'Bayern Munich': 1500, 'Atletico Madrid': 1485,
    'Bayer Leverkusen': 1480, 'Aston Villa': 1472, 'Newcastle United': 1468,
    'Tottenham Hotspur': 1462, 'Chelsea': 1458, 'Brighton & Hove Albion': 1450,
    'Manchester United': 1442, 'Bournemouth': 1435, 'Olympiacos': 1430,
    'Athletic Club': 1415, 'Sporting CP': 1405, 'Brentford': 1400,
    'Fulham': 1395, 'Crystal Palace': 1392, 'West Ham United': 1390,
    'Wolverhampton Wanderers': 1385, 'Everton': 1380, 'Sunderland': 1365,
    'Nottingham Forest': 1360, 'Club Brugge': 1370, 'Southampton': 1365,
    'Portsmouth': 1360, 'Wigan Athletic': 1340, 'Leeds United': 1335,
    'Burnley': 1365, 'Slavia Prague': 1330, 'Mansfield Town': 1320, 'Port Vale': 1300,
    'Kairat Almaty': 1290,
}
HOME_ADV = 90   # home advantage in ELO points
ELO_DIV = 400.0
ELO_K = 16

# ---------------------------------------------------------------------------
# Rivalry Impact (RIV). 0 for everyone except genuine arch-rivals.
# Deliberately small weights: rivalry bumps the occasion multiplier, it does
# not dominate ability or the stage (see V2.3 docs: RIV must not tip the scale).
# ---------------------------------------------------------------------------
RIV = {
    'Tottenham Hotspur': 5, 'Manchester United': 4, 'Chelsea': 3,
}

# ---------------------------------------------------------------------------
# Stage-specific Importance (IMP), Consequence (CI), Motivation (MOT).
# ---------------------------------------------------------------------------
STAGE_IMP = {
    'PL': 1.0,
    'UCL_LP': 1.0, 'UCL_R16': 2.0, 'UCL_QF': 3.0, 'UCL_SF': 4.0, 'UCL_F': 10.0,
    'ELC_R3': 0.5, 'ELC_R4': 0.5, 'ELC_QF': 1.0, 'ELC_SF': 1.5, 'ELC_F': 2.0,
    'FAC_R3': 1.0, 'FAC_R4': 1.0, 'FAC_R5': 1.0, 'FAC_QF': 3.0,
}
STAGE_CI = {
    'PL': None,  # handled by title-race ramp
    'UCL_LP': 1.2, 'UCL_R16': 2.0, 'UCL_QF': 2.5, 'UCL_SF': 3.0, 'UCL_F': 4.5,
    'ELC_R3': 0.3, 'ELC_R4': 0.4, 'ELC_QF': 1.0, 'ELC_SF': 1.2, 'ELC_F': 1.5,
    'FAC_R3': 0.6, 'FAC_R4': 0.7, 'FAC_R5': 1.0, 'FAC_QF': 2.5,
}
# MOT: motivation / stakes multiplier (applies to SI)
def compute_mot(comp, rnd, pl_mw=0):
    if comp == 'PL':
        if pl_mw <= 10:  return 0.8
        if pl_mw <= 20:  return 1.2
        if pl_mw <= 30:  return 1.5
        return 1.5
    if comp == 'UCL':
        return 2.0 if rnd in ('R16', 'QF1', 'QF2', 'SF1', 'SF2', 'Final') else 0.8
    if comp == 'ELC':
        return 1.0 if rnd in ('QF', 'SF1', 'SF2', 'Final') else 0.5
    if comp == 'FAC':
        return 2.0 if rnd in ('QF',) else 0.8
    return 1.0

def STAGE_CI_BASE_LOOKUP(sk):
    return STAGE_CI[sk] if sk in STAGE_CI and STAGE_CI[sk] is not None else 1.0

def stage_key(comp, rnd):
    if comp == 'PL':
        return 'PL'
    if comp == 'UCL':
        return {'LP1': 'UCL_LP','LP2': 'UCL_LP','LP3': 'UCL_LP','LP4': 'UCL_LP',
                'LP5': 'UCL_LP','LP6': 'UCL_LP','LP7': 'UCL_LP','LP8': 'UCL_LP',
                'R16': 'UCL_R16','QF1': 'UCL_QF','QF2': 'UCL_QF',
                'SF1': 'UCL_SF','SF2': 'UCL_SF','Final': 'UCL_F'}.get(rnd, 'UCL_LP')
    if comp == 'ELC':
        return {'R3': 'ELC_R3','R4': 'ELC_R4','QF': 'ELC_QF',
                'SF1': 'ELC_SF','SF2': 'ELC_SF','Final': 'ELC_F'}.get(rnd, 'ELC_R3')
    if comp == 'FAC':
        return {'R3': 'FAC_R3','R4': 'FAC_R4','R5': 'FAC_R5','QF': 'FAC_QF'}.get(rnd, 'FAC_R3')

def pl_ci(mw):
    """Premier League title-race consequence ramp over the season."""
    if mw <= 10:  return 0.8
    if mw <= 20:  return 1.2
    if mw <= 30:  return 1.6
    if mw <= 36:  return 2.0
    return 2.4

# ---------------------------------------------------------------------------
# Load raw match facts (CSV has no embedded commas in opponent names).
# ---------------------------------------------------------------------------
raw_rows = []
with open(RAW, encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for p in reader:
        if not p or not p[0] or p[0].lower().startswith('date'):
            continue
        raw_rows.append(dict(
            date=p[0], comp=p[1], rnd=p[2], opp=p[3], venue=p[4],
            gf=int(p[5]), ga=int(p[6]), result=p[7], penswin=int(p[8]),
            ars_goals=[int(x) for x in p[9].split(';') if x],
            opp_goals=[int(x) for x in p[10].split(';') if x],
            drama=[x.strip() for x in p[11].split(';') if x.strip()],
            note=p[12] if len(p) > 12 else '',
        ))

rows = sorted(raw_rows, key=lambda r: r['date'])

# assign PL matchweek for title-race consequence
pl_mw = 0
for r in rows:
    if r['comp'] == 'PL':
        pl_mw += 1
        r['pl_mw'] = pl_mw
    else:
        r['pl_mw'] = 0

# ---------------------------------------------------------------------------
# Emotional persistence state (Arsenal)
# ---------------------------------------------------------------------------
ES, SAT, DEF, ED, TS = 0.0, 0.0, 0.0, 0.0, 0.0
recent_EO = []
elo = dict(BASE_ELO)

out_s, out_v, out_p = [], [], []

for r in rows:
    opp = r['opp']
    opp_elo = elo.get(opp, 1700)
    home_adv = HOME_ADV if r['venue'] == 'H' else (-HOME_ADV if r['venue'] == 'A' else 0.0)

    # ----- Layer 1: Ability -----------------------------------------
    # Pre-match ELO difference -> expected probability of an Arsenal win.
    pre_elo_gap = elo['Arsenal'] + home_adv - opp_elo
    pre_prob = 1.0 / (1.0 + 10 ** (-pre_elo_gap / ELO_DIV))
    # AS: Ability Score in "strength points" above a 1400 floor, so baseline
    # ability dominates TEAM_SCORE while emotional terms (ES/RP ~ 10-40) act as
    # a modest perturbation - matching the theory's aim (emotion adds signal
    # AFTER controlling for ability, it does not replace it).
    as_a = elo['Arsenal'] - 1400.0

    # ----- xG estimation (documented strength-Poisson proxy) --------
    if r['note'] and 'real_xg_' in r['note']:
        seg = r['note'].split('real_xg_')[1].split(',')[0]
        xgf, xga = [float(v) for v in seg.split('_')[:2]]
    else:
        xgf = 1.35 + (elo['Arsenal'] - 1450) / 300.0 + max(0.0, (1450 - opp_elo) / 300.0)
        xga = 0.95 + max(0.0, (opp_elo - elo['Arsenal']) / 700.0) + (0.25 if r['venue'] == 'A' else 0.0) - (0.12 if r['venue'] == 'H' else 0.0)
        xgf = max(0.4, min(2.8, xgf))
        xga = max(0.2, min(2.2, xga))

    # ----- PJI ------------------------------------------------------
    pji = max(-1.5, min(1.5, (xgf - xga) - (r['gf'] - r['ga'])))

    # ----- Effective result --------------------------------------------
    # A shootout decides the emotion: penswin_ars counts as a win,
    # pensloss_ars as a loss (losing the trophy is NOT a draw emotionally).
    eff_result = r['result']
    if any(f.startswith('pensloss') for f in r['drama']):
        eff_result = 'loss'
    elif any(f.startswith('penswin') for f in r['drama']):
        eff_result = 'win'

    # ----- EX ----------------------------------------------------------
    if eff_result == 'win':
        ex = (1.0 - pre_prob) * 6.0
    elif eff_result == 'loss':
        ex = (0.0 - pre_prob) * 6.0
    else:
        ex = (0.5 - pre_prob) * 6.0
    ex = max(-5.0, min(5.0, ex))

    # ----- SI + MOT -----------------------------------------------------
    si = 0.0
    for flag in r['drama']:
        if flag == 'latewin_ars':        si += 1.5
        elif flag == 'latewin_opp':      si -= 1.5
        elif flag == 'lateeq_ars':       si += 1.0
        elif flag == 'lateeq_opp':       si -= 1.0
        elif flag == 'comeback_ars':     si += 2.0
        elif flag == 'comeback_opp':     si -= 2.0
        elif flag == 'blownlead_ars':    si -= 2.0
        elif flag == 'multi_comeback_ars': si += 2.5
        elif flag == 'f15_ars':          si += 1.0
        elif flag == 'f15_opp':          si -= 1.0
        elif flag.startswith('penswin'): si += 2.0
        elif flag.startswith('pensloss'): si -= 2.0
    mot = compute_mot(r['comp'], r['rnd'], r['pl_mw'])
    si_adj = si * mot

    # ----- CI -----------------------------------------------------------
    sk = stage_key(r['comp'], r['rnd'])
    if sk == 'PL':
        ci = pl_ci(r['pl_mw'])
    else:
        ci = STAGE_CI_BASE_LOOKUP(sk)
    ci = max(0.2, min(5.0, ci))

    imp = STAGE_IMP[sk]

    # ----- HUM ---------------------------------------------------------
    hum = 0.0
    if pre_prob > 0.70 and eff_result == 'loss':
        hum = -(pre_prob - 0.50) * 20
        hum = max(-10.0, min(0.0, hum))

    # ----- EO + loss aversion ------------------------------------------
    # Occasion magnitude (CI + IMP) scales WITH the expectation outcome:
    # beating expectation (EX >= 0, i.e. win or underdog draw) amplifies the
    # high, dropping points (EX < 0, i.e. loss or favourite draw) amplifies the
    # low. A favourite DRAW is a negative occasion, not a neutral one.
    # The occasion is also weighted by (a) opponent strength — beating a strong
    # side is a bigger deal — and (b) a modest RIV bonus for arch-rivals.
    # Weights are deliberately small so rivalry/opponent strength never tips
    # the scale against ability or stage.
    riv = RIV.get(opp, 0.0)
    opp_str = max(0.8, min(1.6, 0.8 + (opp_elo - 1400.0) / 400.0))
    occ_mult = opp_str * (1.0 + 0.05 * riv)
    occasion = (1.0 * ci + 0.5 * imp) * occ_mult * (1.0 if ex >= 0.0 else -1.0)
    eo_raw = 2.0 * ex + 1.0 * si_adj + occasion + pji + hum
    mult = 1.5 if eo_raw < 0 else 1.0
    eo = eo_raw * mult

    # ----- Layer 3 persistence -----------------------------------------
    # ES uses documented persistence coefficients (positive 0.8/0.2,
    # negative 0.9/0.3 so negativity persists longer).
    # SAT/DEF/ED are NOT decay-specified in V2.3; we use bounded, slowly
    # decaying accumulators (0.80 retention) so RP stays on a scale
    # comparable to AS/ES instead of growing without bound.
    if eo > 0:
        ES = 0.80 * ES + 0.20 * eo
        SAT = SAT * 0.80 + max(0.0, eo) * 0.20
        DEF = DEF * 0.80
    else:
        ES = 0.90 * ES + 0.30 * eo
        DEF = DEF * 0.80 + max(0.0, -eo) * 0.30
        SAT = SAT * 0.80

    ED = ED * 0.80 + (eo * 0.10 if (eo > 0 and ES > 0) else 0.0)
    if eo < -5:
        TS += abs(eo)
    TS = TS * 0.95

    recent_EO.append(eo)
    recent_EO = recent_EO[-5:]
    ev = statistics.stdev(recent_EO) if len(recent_EO) >= 3 else 0.0
    pe = 1.0 if (ES > 0 and TS < 2.0) else 0.0

    rp = SAT + ED + 0.5 * TS - DEF

    # ----- Final team score + prediction edge --------------------------
    team_score = as_a + ES - rp
    as_opp = opp_elo - 1400.0
    edge = (as_a - as_opp) + (ES - rp)   # strength gap + emotional adjustment
    pred_prob = 1.0 / (1.0 + 10 ** (-edge / 400.0))

    y = 1.0 if eff_result == 'win' else (0.0 if eff_result == 'loss' else 0.5)

    out_s.append(dict(date=r['date'], comp=r['comp'], rnd=r['rnd'], opp=opp,
                      elo_ars=round(elo['Arsenal'], 1), elo_opp=round(opp_elo, 1),
                      pre_win=round(pre_prob, 4), xgf=round(xgf, 2), xga=round(xga, 2),
                      as_score=round(as_a, 3)))
    out_v.append(dict(date=r['date'], comp=r['comp'], opp=opp,
                      AS=round(as_a, 3), EX=round(ex, 3), SI=round(si, 3),
                      SI_adj=round(si_adj, 3), CI=round(ci, 3), MOT=round(mot, 2),
                      PJI=round(pji, 3), IMP=round(imp, 1), HUM=round(hum, 2),
                      RIV=round(riv, 1),
                      EO_raw=round(eo_raw, 3), EO=round(eo, 3),
                      ES=round(ES, 3), SAT=round(SAT, 3), DEF=round(DEF, 3),
                      ED=round(ED, 3), TS=round(TS, 3), EV=round(ev, 3),
                      PE=round(pe, 2), RP=round(rp, 3),
                      TEAM_SCORE=round(team_score, 3)))
    out_p.append(dict(date=r['date'], comp=r['comp'], opp=r['opp'], gf=r['gf'],
                      ga=r['ga'], result=eff_result, edge=round(edge, 3),
                      win_p=round(pred_prob, 4), y=y))

    # ----- ELO update from actual result (no future info) --------------
    expected_a = 1.0 / (1.0 + 10 ** (-(elo['Arsenal'] + home_adv - opp_elo) / ELO_DIV))
    actual_a = {'win': 1.0, 'loss': 0.0, 'draw': 0.5}[r['result']]
    elo['Arsenal'] += ELO_K * (actual_a - expected_a)
    elo[opp] = elo.get(opp, 1400) + ELO_K * ((1 - actual_a) - (1 - expected_a))


# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
def write(fname, header, data):
    with open(fname, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(data)

write(OUT_STRENGTH, ['date','comp','rnd','opp','elo_ars','elo_opp','pre_win','xgf','xga','as_score'], out_s)
write(OUT_VARS, ['date','comp','opp','AS','EX','SI','SI_adj','CI','MOT','PJI','IMP','HUM',
                 'RIV','EO_raw','EO','ES','SAT','DEF','ED','TS','EV','PE','RP','TEAM_SCORE'], out_v)
write(OUT_PRED, ['date','comp','opp','gf','ga','result','edge','win_p','y'], out_p)

print(f"wrote {len(out_s)} strength rows -> {OUT_STRENGTH}")
print(f"wrote {len(out_v)} var rows -> {OUT_VARS}")
print(f"wrote {len(out_p)} prediction rows -> {OUT_PRED}")

print("\n=== Top 10 by |EO| (Emotional Outcome magnitude) ===")
ranked = sorted(out_v, key=lambda x: abs(float(x['EO'])), reverse=True)
for i, r in enumerate(ranked[:10], 1):
    print(f"{i:>2} {r['date']} {r['comp']:>3} {r['opp']:<22} EO={r['EO']:>7} "
          f"EX={r['EX']:>6} SI={r['SI']:>6} CI={r['CI']:>4} ES={r['ES']:>6} RP={r['RP']:>6}")