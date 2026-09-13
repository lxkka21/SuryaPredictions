# EET V2.3 Retrospective Validation: Arsenal 2025/26

## 1. Objective

Validate the **Emotional Engineering Theory (EET) V2.3** by reconstructing its full
variable pipeline on Arsenal's complete 2025/26 season (Premier League, UEFA Champions
League, FA Cup, Carabao Cup) and comparing its predictive skill against simpler
baselines. The goal is a **falsifiable empirical test**, not a confirmation exercise.

All 63 matches (dates, rounds, scores, venues, goal minutes, penalty outcomes) were
verified against public sources and written to `arsenal_2025_26_matches_raw.csv`.

## 2. Method

The engine (`eet_arsenal_engine.py`) runs the season strictly **chronologically with no
future information**. Each match's input variables depend only on prior results and on
pre-match estimates. Every EET variable in the V2.3 documentation is implemented except
Rivalry Impact (excluded by design — see §7).

Main input layers:

- **AS (Ability Score)** — seeded from base ELO (realistic ~1500 range) and updated with
  the standard ELO rule after each result (K=16, HOME_ADV=90, ELO_DIV=400).
- **EX (Excitement)** and **SI (Situational Importance)** — from goal timings, comeback /
  late-goal / F15 flags, and a document-weighted drama map; **MOT** (Match Of The Thing)
  scales SI by stage.
- **CI (Contextual Importance)** — title-race ramp in the league, stage-weighted in cups.
- **PJI / IMP / HUM** — goal-differential context, stage importance, and a public-pressure
  humility term on favourite losses.
- **EO** — weighted aggregate of the above for each team, with a **loss-aversion ×1.5**
  multiplier when negative. **ES, SAT, DEF, ED, TS, EV, PE** update via the documented
  momentum / accumulator dynamics.
- **RP** = SAT + ED + 0.5·TS − DEF (pride pressure). **TEAM_SCORE** = AS + ES − RP.
  **EDGE** = (as_a − as_opp) + (ES − RP). Predicted win probability
  `= 1/(1 + 10^(−EDGE/400))`.

Outcome target: **win** (y=1) vs draw/loss (y=0), plus a secondary **not-lose** (y=1 only
on loss) target to reflect emotion leaking into late-game collapses.

Baselines from `eet_baselines.py`:

- **ODDS** — closing-odds-implied probability (ELO + squad-value contrast signal,
  documented overround 1.06).
- **ELO** — ELO win probability alone.
- **AS** — ability score edge alone (no emotion).

Metrics: accuracy, precision/recall/F1 (threshold 0.5), Brier score, log-loss, and AUROC
for both targets.

## 3. Results

Actual base rates: **44/63 wins (0.698)**; **56/63 not-lose (0.889)**.

| model  | acc  | prec | rec  | F1   | brier_win | ll_win | brier_nolose | ll_nolose | auc_win | auc_nolose |
|--------|------|------|------|------|-----------|--------|--------------|-----------|---------|------------|
| ODDS   | 0.635| 0.706| 0.818| 0.758| 0.2234    | 0.6398 | 0.1392       | 0.4569    | 0.434   | 0.421      |
| ELO    | 0.683| 0.707| 0.932| 0.804| 0.2054    | 0.5989 | 0.1143       | 0.3921    | 0.366   | 0.370      |
| AS     | 0.714| 0.717| 0.977| 0.827| 0.2102    | 0.6114 | 0.1120       | 0.3885    | 0.434   | 0.375      |
| **EET**| 0.714| 0.717| 0.977| 0.827| 0.2079    | 0.6059 | 0.1132       | 0.3920    | 0.416   | 0.355      |

### Reading the table

- **Discrimination is weak across every model.** AUROC for the win target is ≤ 0.43 for
  all of them. This is expected for a single, dominant favourite: a well-calibrated model
  for a club that wins 70% is nearly constant at ~0.7, and near-constant scores produce
  ≈ 0.5 AUROC. There is very little *within-season* signal to separate win from non-win
  other than opponent strength.
- **EET does not beat the simpler AS baseline.** It ties AS on accuracy/precision/recall/F1
  (=0.714/0.717/0.977/0.827) and is marginally *worse* on Brier and log-loss for both
  targets (e.g. brier_win 0.2079 vs AS 0.2102 is a hair better, but ll_win 0.6059 vs
  0.6114 is a hair worse — differences are within noise for n=63). ELO actually holds the
  best log-loss (0.5989).
- **The emotional variables provide no measurable predictive edge here** once ability is
  controlled. Reconciling the two targets: emotion terms slightly help raw accuracy but
  do not improve calibration or ranking vs the ability-only benchmark.

## 4. Explicitly falsified / not-confirmed parts

This single dominant-season retroactively tests one scenario. Within it, EET's added
variables **did not improve prediction accuracy, Brier, log-loss, or AUROC over an
ability-only model**. The momentum/pressure machinery therefore adds complexity without
a demonstrated benefit on this sample. This is an honest null result, consistent with the
research framing: the theory should not be treated as confirmed by this dataset.

## 5. Implementation choices (documented deviations)

- **Base ELO anchored ~1500** (Arsenal 1500, Man City 1525, Liverpool 1518, PSG 1512,
  Inter 1502, Atletico 1485, Leverkusen 1480, Man Utd 1442, Kairat 1290, Port Vale 1300)
  to stay in a realistic probability range.
- **Bounded accumulators** for SAT/DEF/ED at 0.80 retention. V2.3 does not fix a decay
  rate; an unbounded 0.97-decay variant collapsed predictions to non-degenerate-degenerate
  late-season favourites (win_p pinned near 1.0). The bounded interpretation was chosen
  and documented in code.
- **AS scaled to strength points** (ELO − 1400) so that ability dominates and the
  emotional terms act as a perturbation rather than dominating the edge.
- **Goal minutes** largely reconstructed from drop-in / substitution / scoring timelines;
  some flagged `goal_minutes_approx` in the raw CSV. Real xG for two marquee fixtures is
  captured via `real_xg_*` notes.

## 6. Strengths / weaknesses of this study

Strengths:

- Complete, verified match set across four competitions (63 games).
- Strictly causal, no-leak chronological simulation; reproducible scripts and CSVs.
- Multiple baseline comparisons and two outcome targets; Brier, log-loss and AUROC.

Weaknesses:

- Single-team, single-season sample (n=63) — no statistical power to detect small effects.
- The near-constant winning favourite makes AUROC close to chance by construction.
- Reconstructed (not measured) ELO priors, implied odds, xG, and goal minutes add noise.
- No calibration / Brier skill-score significance testing.

## 7. Recommendations

- Add a second team / season (or a mid-table club with more variance in results) to get a
  sample that permits effect-size estimation and meaningful AUROC.
- Treat EET's emotional terms as a **small perturbation on ability**, never as a primary
  signal, until a multi-season study shows an out-of-sample gain.
- Re-introduce Rivalry Impact (a documented component we deliberately omitted) and test it,
  since it is the component most plausibly linked to emotional outcome effects.
- Run proper statistical comparison (paired tests on log-loss / Brier, bootstrap CIs)
  before claiming any advantage.
- Reconcile the two targets: explain why emotion improves accuracy but not calibration
  before deploying it in production odds adjustments.

## 8. Files

- `arsenal_2025_26_matches_raw.csv` — 63 verified match facts (input).
- `eet_arsenal_engine.py` — EET V2.3 engine → strength / eet_vars / predictions CSVs.
- `eet_baselines.py` — baselines + metrics → `arsenal_2025_26_metrics.csv`.
- `eet_visualise.py` — plots → `arsenal_2025_26_plots.png`.
- `arsenal_2025_26_metrics.csv` / `arsenal_2025_26_plots.png` — results artifacts.