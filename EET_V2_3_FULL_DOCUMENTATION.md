
# EET-V2.3 (Emotional Equilibrium Theory)
## Full Research Documentation

### Research Objective
After controlling for team strength and market expectations, determine whether emotional shocks, dramatic match events, consequence, trauma, momentum, volatility and emotional persistence create measurable predictive value in football outcomes.

---

# Architecture

Layer 1: Ability

Layer 2: Emotional Generation

Layer 3: Emotional Persistence

---

# VARIABLE 1: Ability Score (AS)

Inputs:
- ELO
- Market Odds
- Squad Value
- FIFA Ranking
- Historical xG Differential
- Historical Goal Differential

Purpose:
Baseline football strength independent of emotion.

---

# VARIABLE 2: Expectation Shock (EX)

Measures how surprising a result was.

Inputs:
- Closing odds
- Implied probabilities
- Actual result

Range:
-5 to +5

Examples:
- Heavy favourite win = small positive
- Heavy favourite loss = large negative
- Massive underdog win = large positive

V2.3 NOTE:
EX is now the dominant emotional driver.

---

# VARIABLE 3: Story Impact (SI)

Measures emotional drama.

## Late Winner
Winner +1.5
Loser -1.5

## Late Equalizer
Scoring Team +1
Conceding Team -1

## Comeback Victory
Winner +2
Loser -2

## Multi Goal Comeback
Winner +2.5

## Blown Lead
Large negative impact

## Penalty Shootout
Winner +2
Loser -2

## Last 15 Minute Goal
+1

Purpose:
Capture drama but not overwhelm significance.

V2.3 EFFECTIVE-RESULT RULE:
A match decided by a penalty shootout is NEVER scored as a draw.
- Shootout WIN  → effective result = WIN
- Shootout LOSS → effective result = LOSS

All downstream variables that depend on the result (EX, HUM, occasion sign,
outcome label y) must use the EFFECTIVE result, not the 90-minute scoreline.
Losing a final on penalties is a defeat emotionally and must be scored as such.

---

# VARIABLE 4: Rivalry Impact (RIV)

Scale:
0–5

Examples:
- Arsenal vs Tottenham = 5
- Arsenal vs Manchester United = 4
- Arsenal vs Chelsea = 3
- Everything else = 0

Usage (V2.3 ACTIVE — small weight):
RIV is INCLUDED in EO as a modest occasion multiplier, not a dominant term:
occ_mult = opponent_strength × (1 + 0.05 × RIV)

Rationale:
Beating an arch-rival is worth more than beating an anonymous side, but
rivalry must never tip the scale against ability, stage or expectation.
Weights are deliberately small (0.05/RIV point; max ~1.25× for RIV=5).

Per-team convention:
RIV must be defined per team in the engine dictionary (default 0 for
unlisted opponents). It is NOT a subjective free-floating number.

---

# VARIABLE 5: Performance Justice Index (PJI)

Formula:

PJI =
xG Differential
-
Goal Differential

Range:
-1.5 to +1.5

Positive:
Unlucky

Negative:
Fortunate

---

# VARIABLE 6: Importance Impact (IMP)

Group Stage = 1
Round of 16 = 2
Quarter Final = 3
Semi Final = 4
Third Place = 1
Final = 10

Purpose:
Reflect tournament stage.

---

# VARIABLE 6A: Consequence Impact (CI)

Purpose:

Distinguish emotional drama from emotional significance.

Measures:

- Qualification implications
- Elimination implications
- Advancement implications
- Historical significance
- Tournament landscape impact

Range:
0–5

Examples:

Dead Rubber = 0.2
Minor Stakes = 0.5
Qualification Likely = 0.8
Qualification At Risk = 1.2
Must Win = 1.5
Knockout Survival = 2.0
Historical Tournament Shock = 3.0+

V2.3 NOTE:

CI is elevated because tournament-changing results matter more than simple drama.

---

# VARIABLE 6B: Motivation / Stakes Multiplier (MOT)

Already Eliminated = 0.3
Already Qualified = 0.3
Minor Stakes = 0.5
Qualification Likely = 0.8
Qualification At Risk = 1.2
Must Win = 1.5
Knockout Match = 2.0

Formula:

SI_adjusted =
SI_raw × MOT

---

# VARIABLE 7: Humiliation Impact (HUM)

Purpose:

Not all losses are equal.

Conditions:

Favourite Probability > 70%
AND
EFFECTIVE result is LOSS

(Shootout losses count as losses for HUM too.)

Range:
0 to -10

Examples:

- Saudi Arabia vs Argentina
- Japan vs Germany
- Morocco vs Belgium

These should trigger meaningful HUM values.

---

# VARIABLE 8: Emotional Outcome (EO)

Formula:

EO_raw =
2.0 × EX
+ 1.0 × SI
+ 1.0 × CI
+ 0.5 × IMP
+ PJI
+ HUM

RIV omitted.

Rationale:

Expectation Shock dominates.
Consequence matters.
Story supports but does not dominate.

V2.3 SIGN-DEPENDENT OCCASION (critical):
The occasion magnitude (CI + 0.5 × IMP) must be signed by the EXPECTATION
OUTCOME, i.e. by the sign of EX, never by the raw result:
- EX ≥ 0 (beat expectation: win, or underdog draw)  → occasion added POSITIVE
- EX < 0 (dropped points: loss, or favourite draw)   → occasion added NEGATIVE

A huge match is not a positive "event" when it is lost — and it is not a
neutral "event" when it is a dropped-points draw. A favourite DRAWING in a
title-deciding match is a negative occasion: it costs points and must be
scored as such. Scoring a CL final loss or a title-race favourite draw with
a positive CI+IMP term is a bug, not a design choice.

OCCASION WEIGHTING (opponent strength + rivalry):
Before signing, the occasion magnitude is multiplied by:
occ_mult = opp_str × (1 + 0.05 × RIV)

where opp_str = clamp(0.8 + (opp_ELO − 1400) / 400, 0.8, 1.6) — beating a
stronger opponent is a bigger deal. RIV is 0 for non-rivals (see VARIABLE 4).
Weights are deliberately small so beating a rival or a top side never
overwhelms the expectation shock, the stage, or the actual performance.

Full occasion term:
occasion = (CI + 0.5 × IMP) × opp_str × (1 + 0.05 × RIV) × sign(EX)

Per-team flag convention:
Shootout flags MUST be team-generic, e.g. `penswin` / `pensloss`, not
`penswin_ars` / `pensloss_ars`. The engine derives the effective result from
the flag alone, so any team's data runs identically.

---

# VARIABLE 9: Loss Aversion

Positive EO:
Multiplier = 1.0

Negative EO:
Multiplier = 1.5

Final:

EO = EO_raw × Multiplier

---

# VARIABLE 10: Emotional State (ES)

Initial:
ES = 0

If EO > 0:

ES_new =
0.80 × ES_old
+ 0.20 × EO

If EO < 0:

ES_new =
0.90 × ES_old
+ 0.30 × EO

Purpose:
Negative emotions persist longer.

---

# VARIABLE 11: Emotional Saturation (SAT)

Tracks accumulated positive emotion.

High SAT:
Regression risk.

---

# VARIABLE 12: Emotional Deficit (DEF)

Tracks accumulated negative emotion.

High DEF:
Rebound potential.

---

# VARIABLE 13: Emotional Debt (ED)

Tracks long-term overachievement.

Examples:
- Morocco 2022
- Croatia 2018
- Leicester 2016

---

# VARIABLE 14: Trauma Score (TS)

If EO < -5:

TS += abs(EO)

Decay:

TS *= 0.95

Purpose:

Track emotional scars that remain after recovery.

---

# VARIABLE 15: Emotional Volatility (EV)

Rolling standard deviation of recent EO values.

High EV:
Unstable

Low EV:
Stable

---

# VARIABLE 16: Psychological Elasticity (PE)

Measures recovery speed.

Recovery:

ES > 0
AND
TS < 2

Higher recovery speed = higher elasticity.

---

# VARIABLE 17: Regression Pressure (RP)

RP =
SAT
+ ED
+ 0.5 × TS
- DEF

Positive:
Regression Risk

Negative:
Bounce Potential

---

# Final Team Score

TEAM_SCORE =
AS
+ ES
- RP

---

# Prediction Edge

EDGE =
TEAM_SCORE_A
-
TEAM_SCORE_B

---

# Validation Benchmark

Target emotional significance ranking:

1. Argentina vs France
2. Saudi Arabia vs Argentina
3. Croatia vs Brazil
4. Morocco vs Portugal
5. Japan vs Germany
6. Morocco vs Spain
7. Argentina vs Netherlands
8. Morocco vs Belgium
9. Japan vs Spain
10. Argentina vs Mexico

Purpose:

Future versions should move toward this benchmark rather than rankings dominated by routine group-stage drama.

---

# Current Testing Configuration

Included:
- AS
- EX
- SI
- CI
- MOT
- PJI
- IMP
- HUM
- RIV
- EO
- ES
- SAT
- DEF
- ED
- TS
- EV
- PE
- RP

Excluded:
- (none)

Future V3:
- Live odds
- Live xG
- Red cards
- Social sentiment
- Injury shocks
- Crowd intensity
- Real-time emotional updates
