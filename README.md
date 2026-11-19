# SuryaBetting

EET V2.3 — Emotional Expectation Terror

Europe's top 5 leagues + cups — ELO ratings, emotional analysis, and momentum tracking.

[Live Demo](https://suryabetting-47401.web.app) · [GitHub Repository](https://github.com/lxkka21/SuryaBetting) · Firebase Hosting

---

A pure-stdlib sports analytics model that assigns each match an Emotional Outcome (EO) score based on ELO-based pre-match win probability, expectation surprise, drama/incident scoring, competition importance, momentum, performance vs. xG, and humiliation factors.

The model produces per-team ratings (ELO, TEAM_SCORE, ES, RP, PJI, EX, SI, CI, MOT, EO, PE) that update chronologically from results alone — no future information, fully deterministic.

## Leagues Covered
- Premier League (PL)
- La Liga (LALIGA)
- Bundesliga (BL1)
- Serie A (SA)
- Ligue 1 (FL1)

## Key Metrics
- **ELO** — Team strength rating (starts at 1500)
- **TEAM_SCORE** — Composite score = ES − RP + previous ELO
- **ES** — Emotional Stability
- **RP** — Retrospective Power
- **PJI** — Penalty-adjusted xG difference
- **EX** — Expectation Surprise
- **SI** — Drama/Incident Score
- **CI** — Competition Importance
- **MOT** — Momentum
- **EO** — Emotional Outcome
- **PE** — Performance Edge

## Data Pipeline
```
results.csv ← ESPN scraped results
│
import_espn.py ← fetches latest results, writes results.csv
fetch_fixtures.py ← fetches upcoming fixtures
fetch_xg.py backfill ← adds xG values from FBref (optional)
run_week.py ← recomputes site JSON, team data
│
site/data/ ← JSON consumed by the frontend (index.html)
```

## Site Features
- 7 tabs: Overview, Matches, Fixtures, Leagues, Teams, Top Moments, Late Goals
- Color-coded EO grid — green (+) / red (−) Elo-weighted cells
- Late-goal analysis — games where a goal after the 85th minute changed the result
- Team pages — detailed match history, xG proxy, ELO trajectory chart
- Responsive design — works from mobile to 1440p+
- Dark theme — EET branded colors

## Development
```bash
# Recompute site JSON (without fetching new data)
python run_week.py

# Run the dev server
python -m http.server 8000 --directory site

# Deploy to Firebase
firebase deploy --only hosting --project suryabetting-47401
```

## License
MIT — feel free to use, modify, and distribute.

---

Built with ❤️ by [lxkka21](https://github.com/lxkka21)