# EET V2.3 — Emotional Expectation Terror

**Europe's top 5 leagues + cups — ELO ratings, emotional analysis, and momentum tracking.**

[Live Demo](https://suryabetting-47401.web.app) · [GitHub](https://github.com/lxkka21/SuryaBetting) · Firebase Hosting

---

## 📊 What It Is

EET (Emotional Expectation Terror) is a pure‑stdlib sports analytics model that assigns each match an **Emotional Outcome (EO)** score based on:

- **Pre‑match win probability** (ELO‑based)
- **Expectation Surprise (EX)** — how surprising the result was
- **Drama/SI** — comeback/blow‑lead intensity, late‑goal impact
- **Consequence (CI)** — competition importance (league ramp, cup stages)
- **Momentum (MOT)** — matchstage weighting
- **PJI** — performance vs. xG over/under‑achievement
- **IMP** — competition importance multiplier
- **HUM** — humiliation factor (only when deserved)

The model produces per‑team ratings (ELO, TEAM_SCORE, ES, RP, etc.) that update chronologically from results alone — no future information, fully deterministic.

---

## 🏆 Leagues & Cups Covered

| League | Code | Teams |
|--------|------|-------|
| Premier League | PL | 20 |
| La Liga | LALIGA | 20 |
| Bundesliga | BL1 | 18 |
| Serie A | SA | 20 |
| Ligue 1 | FL1 | 20 |

| Competition | Code | Stage Types |
|-------------|------|-------------|
| UEFA Champions League | UCL | GRP, R32, R16, QF, SF, F |
| UEFA Europa League | UEL | GRP, R32, R16, QF, SF, F |
| UEFA Conference League | UECL | GRP, R32, R16, QF, SF, F |
| FA Cup | FAC | R1–R7, QF, SF, F |
| Copa del Rey | CDR | R1–R7, QF, SF, F |
| DFB‑Pokal | DFB | R1–R7, QF, SF, F |
| Coppa Italia | CI | R1–R7, QF, SF, F |
| Coupe de France | CDF | R1–R7, QF, SF, F |
| Carabao Cup | LC | — |
| Super Cup | CS | F |

---

## 📈 Key Metrics Explained

| Metric | Meaning |
|--------|---------|
| **ELO** | Team strength rating (starts at 1500, adjusts after each match) |
| **TEAM_SCORE** | Composite score = ES − RP + previous ELO (higher = better season) |
| **ES** | Emotional Stability — how consistently a team over/under‑performs |
| **RP** | Retrospective Power — weighted sum of EO, ES, ED, TS, DEF |
| **PJI** | Penalty‑adjusted xG difference — clinicality vs. luck |
| **EX** | Expectation Surprise — emotional impact of the result |
| **SI** | Drama/Incident Score — comebacks, blown leads, late goals |
| **CI** | Competition Importance — builds through the season (title race ramp) |
| **MOT** | Momentum — match‑stage weight (group → final) |
| **EO** | Emotional Outcome — the core “EET” score (positive = good, negative = bad) |
| **PE** | Performance Edge — under‑ or over‑performing vs. predicted |

---

## 🚀 Getting Started

### 1. Install & Run Locally

```bash
# Clone the repo
git clone https://github.com/lxkka21/SuryaBetting.git
cd SuryaBetting

# Install Firebase CLI (for deploy)
npm install -g firebase-tools

# Serve the site locally
python -m http.server 8000 --directory site
# then open http://localhost:8000
```

### 2. Update Data (fetch + recompute)

```bash
# Full update: fetch ESPN results, rebuild, recompute EOT, deploy
python update.py

# Dry run (no deploy, no ESPN fetch)
python update.py --dry

# Recompute only from existing results.csv
python update.py --recompute
```

### 3. Understand the Data Pipeline

```
results.csv           ← ESPN scraped results (date, comp, stage, home, away, hg, ag, flags)
│
import_espn.py        ← fetches latest results, writes results.csv
fetch_fixtures.py     ← fetches upcoming fixtures
fetch_xg.py backfill  ← adds xG values from FBref (optional)
run_week.py           ← recomputes summary.json, team data, site JSON
                      │
site/data/            ← JSON consumed by the frontend (index.html)
                      │
app.js                ← renders all tabs/visualizations
style.css             ← EET‑themed dark UI
```

---

## 📁 Project Structure

```
eet_global/
├── site/               ← Static website (HTML/CSS/JS)
│   ├── index.html      ← Main app shell
│   ├── style.css       ← EET dark theme with color-coded EO grids
│   └── app.js          ← EET model renderer
├── data/               ← Input/derived data
│   ├── results.csv     ← Match results (source of truth)
│   ├── fixtures.csv    ← Upcoming fixtures
│   ├── summary.json    ← Recomputed season summary
│   ├── teams.json      ← Team-level aggregated stats
│   ├── rankings.json   ← Top moments / TEAM_SCORE rankings
│   └── xg_cache.csv    ← Optional FBref xG values
├── engine.py           ← Core EET math (pure stdlib)
├── update.py           ← One‑command update pipeline
├── import_espn.py      ← Fetch ESPN results & fixtures
├── fetch_*.py          ← Data fetchers (Cups, ESPN, xG, etc.)
├── run_week.py         ← Recompute engine, output JSON
└── README.md           ← You are here
```

---

## 🎨 Site Features

- **7 tabs**: Overview, Matches, Fixtures, Leagues, Teams, Top Moments, Late Goals
- **Color‑coded EO grid** — green (+) / red (−) Elo‑weighted cells
- **Late‑goal analysis** — games where a goal after the 85th minute changed the result
- **Team pages** — detailed match history, xG proxy, ELO trajectory chart
- **Responsive design** — works from mobile to 1440p+
- **Dark theme** — EET branded colors (--acc: #e63946, --pos: #2ea043, --neg: #d1242f, --gold: #d4a017)

---

## 🛠️ Development

### Recompute the site JSON (without fetching new data)

```bash
python run_week.py
```

This reads `data/results.csv`, runs the full EET model, and outputs:
- `site/data/summary.json` — season summary
- `site/data/rankings.json` — top moments ranking
- `site/data/teams.json` — per‑team stats
- `site/data/matches.json` — all match records
- `site/data/fixtures.json` — upcoming fixtures

### Run the dev server

```bash
python -m http.server 8000 --directory site
```

Visit <http://localhost:8000> to see the site with live data.

### Deploy to Firebase

```bash
firebase deploy --only hosting --project suryabetting-47401
```

Or use the one‑command `python update.py` (full: fetch + recompute + deploy).

---

## 📜 License

MIT — feel free to use, modify, and distribute. See the `engine.py` header for full model documentation.

---

## 🙏 Acknowledgments

- Data provided by ESPN and FBref (xG cache optional)
- Model inspired by ELO‑based football analytics
- Firebase Hosting for the live demo

---

<div align="center">
  <sub>Built with ❤️ by <a href="https://github.com/lxkka21">lxkka21</a></sub>
</div>