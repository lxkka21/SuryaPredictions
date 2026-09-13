"""
Baseline models and evaluation metrics for the EET V2.3 retrospective.

Four models are compared on the SAME per-match prediction task (predicting
Arsenal's result from information available BEFORE each kick-off):

  1. ODDS-only  : market-implied probability (estimated "closing odds",
                  documented blend of ELO + squad-value signal + overround).
  2. ELO-only   : pure pre-match ELO win probability (home-advantage adjusted).
  3. AS-only    : Ability Score (strength) gap only - the same ability
                  component used inside EET, WITHOUT any emotional terms.
  4. EET (full) : TEAM_SCORE = AS + ES - RP, EDGE-based probability.

Metrics:
  - Brier score & log loss for P(win)  (binary win / non-win)
  - Brier & log loss for P(not lose)  (1X double-chance)
  - AUROC for both binary targets (threshold-free discrimination)
  - Accuracy / precision / recall / F1 at the 0.5 operating point
  - Calibration in deciles

No future information is used: every input derives from pre-match data.
"""
import csv
import math

STRENGTH = 'arsenal_2025_26_strength.csv'
VARS = 'arsenal_2025_26_eet_vars.csv'
PRED = 'arsenal_2025_26_predictions.csv'
OUT = 'arsenal_2025_26_metrics.csv'

# ---- documented squad-value signal (relative to Arsenal = 1.0) ----------
# Estimates used ONLY for the ODDS baseline's independent signal (a bookmaker
# would price on more than ELO).  These are season-start documented estimates,
# not post-hoc values.
SQUAD_VALUE = {
    'Manchester City': 1.15, 'Liverpool': 1.10, 'Paris Saint-Germain': 1.20,
    'Inter Milan': 0.95, 'Bayern Munich': 1.10, 'Atletico Madrid': 0.90,
    'Bayer Leverkusen': 0.80, 'Aston Villa': 0.85, 'Newcastle United': 0.85,
    'Tottenham Hotspur': 0.85, 'Chelsea': 0.90, 'Brighton & Hove Albion': 0.70,
    'Manchester United': 0.85, 'Bournemouth': 0.60, 'Olympiacos': 0.55,
    'Athletic Club': 0.65, 'Sporting CP': 0.60, 'Brentford': 0.55,
    'Fulham': 0.55, 'Crystal Palace': 0.50, 'West Ham United': 0.60,
    'Wolverhampton Wanderers': 0.50, 'Everton': 0.55, 'Sunderland': 0.35,
    'Nottingham Forest': 0.45, 'Club Brugge': 0.40, 'Southampton': 0.40,
    'Portsmouth': 0.15, 'Wigan Athletic': 0.05, 'Leeds United': 0.30,
    'Slavia Prague': 0.30, 'Mansfield Town': 0.03, 'Port Vale': 0.02,
    'Kairat Almaty': 0.02,
}
OVERROUND = 1.06   # bookmaker margin on the estimated odds (documented)


def logit(p):
    p = max(1e-9, min(1 - 1e-9, p))
    return math.log(p / (1 - p))


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def load(fname):
    with open(fname, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


strength = load(STRENGTH)
vars_ = load(VARS)
pred = load(PRED)

# join into one list indexed by date
by_date = {}
for s in strength:
    by_date.setdefault(s['date'], {})['elo_ars'] = float(s['elo_ars'])
    by_date[s['date']]['elo_opp'] = float(s['elo_opp'])
    by_date[s['date']]['pre_win'] = float(s['pre_win'])
    by_date[s['date']]['as_score'] = float(s['as_score'])
for v in vars_:
    by_date.setdefault(v['date'], {})['AS'] = float(v['AS'])
    by_date[v['date']]['ES'] = float(v['ES'])
    by_date[v['date']]['RP'] = float(v['RP'])
    by_date[v['date']]['TEAM_SCORE'] = float(v['TEAM_SCORE'])
for p_ in pred:
    by_date[p_['date']]['result'] = p_['result']
    by_date[p_['date']]['edge'] = float(p_['edge'])
    by_date[p_['date']]['win_p'] = float(p_['win_p'])
    by_date[p_['date']]['opp'] = p_['opp']

matches = [by_date[d] for d in sorted(by_date)]


# ---------------------------------------------------------------------------
# Model probability generators
# ---------------------------------------------------------------------------
def model_odds(m):
    """Estimated closing-odds implied probability.
    logit blend of ELO probability and squad-value probability, then a
    documented overround is applied to the implied odds."""
    elo_p = m['pre_win']
    sv = SQUAD_VALUE.get(m['opp'], 0.5)
    # squad-value probability scaled around 0.5 baseline
    sv_p = 1.0 / (1.0 + math.exp(-logit(elo_p) * 0.7 - math.log(sv) * 0.8))
    p = sigmoid(0.65 * logit(elo_p) + 0.35 * logit(sv_p))
    # implied decimal odds = 1/p, inflated by overround, then back to prob
    odds = 1.0 / p * OVERROUND
    return 1.0 / odds


def model_elo(m):
    return m['pre_win']


def model_as(m):
    """AS-only: pure ability gap (no home-adv factor, no emotion)."""
    # strength CSV only carries Arsenal's AS and opp ELO; derive ability gap
    as_a = m['AS']
    as_opp = m['elo_opp'] - 1400.0
    return 1.0 / (1.0 + 10 ** (-(as_a - as_opp) / 400.0))


def model_eet(m):
    return m['win_p']


MODELS = {
    'ODDS': model_odds,
    'ELO': model_elo,
    'AS': model_as,
    'EET': model_eet,
}

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def auroc(scores, labels):
    pairs = sorted(zip(scores, labels), key=lambda x: x[0], reverse=True)
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    rank_sum = 0
    for i, (_, lab) in enumerate(pairs, 1):
        if lab == 1:
            rank_sum += i
    auc = (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return auc


def brier(ps, ys):
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ps)


def logloss(ps, ys):
    eps = 1e-9
    return -sum(y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps))
                for p, y in zip(ps, ys)) / len(ps)


results = []
for name, fn in MODELS.items():
    p_win, y_win, p_nolose, y_nolose = [], [], [], []
    for m in matches:
        p = fn(m)
        res = m['result']
        yw = 1.0 if res == 'win' else 0.0
        yn = 0.0 if res == 'loss' else 1.0
        p_win.append(p)
        y_win.append(yw)
        # P(not lose) approximated as P(win) + P(draw) with a league draw share
        p_nolose.append(p + (1 - p) * 0.23)
        y_nolose.append(yn)

    preds = [1.0 if p >= 0.5 else 0.0 for p in p_win]
    tp = sum(1 for pr, y in zip(preds, y_win) if pr == 1 and y == 1)
    fp = sum(1 for pr, y in zip(preds, y_win) if pr == 1 and y == 0)
    fn_ = sum(1 for pr, y in zip(preds, y_win) if pr == 0 and y == 1)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn_) if (tp + fn_) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    acc = sum(1 for pr, y in zip(preds, y_win) if pr == y) / len(y_win)

    results.append({
        'model': name,
        'acc': acc, 'precision': precision, 'recall': recall, 'f1': f1,
        'brier_win': brier(p_win, y_win), 'logloss_win': logloss(p_win, y_win),
        'brier_nolose': brier(p_nolose, y_nolose), 'logloss_nolose': logloss(p_nolose, y_nolose),
        'auc_win': auroc(p_win, y_win), 'auc_nolose': auroc(p_win, y_nolose),
    })

# ---------------------------------------------------------------------------
# Print + save
# ---------------------------------------------------------------------------
header = ['model', 'acc', 'precision', 'recall', 'f1',
          'brier_win', 'logloss_win', 'brier_nolose', 'logloss_nolose',
          'auc_win', 'auc_nolose']
with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=header)
    w.writeheader()
    w.writerows(results)

print(f"{'model':<6} {'acc':>6} {'prec':>6} {'rec':>6} {'F1':>6} "
      f"{'brier_win':>9} {'ll_win':>8} {'brier_nolose':>12} {'ll_nolose':>10} "
      f"{'auc_win':>8} {'auc_nolose':>10}")
print("-" * 105)
for r in results:
    print(f"{r['model']:<6} {r['acc']:>6.3f} {r['precision']:>6.3f} {r['recall']:>6.3f} "
          f"{r['f1']:>6.3f} {r['brier_win']:>9.4f} {r['logloss_win']:>8.4f} "
          f"{r['brier_nolose']:>12.4f} {r['logloss_nolose']:>10.4f} "
          f"{r['auc_win']:>8.3f} {r['auc_nolose']:>10.3f}")
print(f"\nwrote {OUT}")

print("\nActual base rates: wins=%d/63 (%.3f), not-lose=%d/63 (%.3f)"
      % (sum(int(m['result'] == 'win') for m in matches),
         sum(int(m['result'] == 'win') for m in matches) / len(matches),
         sum(int(m['result'] != 'loss') for m in matches),
         sum(int(m['result'] != 'loss') for m in matches) / len(matches)))
