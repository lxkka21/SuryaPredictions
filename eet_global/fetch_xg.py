"""
Smart xG system: 
- Auto-fetches from available sources for REAL matches
- Estimates xG from match events (goals, flags) for simulated/historical matches
- Caches everything to data/xg_cache.csv
"""
import csv
import sys
import re
from pathlib import Path
from typing import Optional

CACHE_FILE = Path(__file__).with_name("data") / "xg_cache.csv"
CACHE_FILE.parent.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def load_cache() -> dict:
    cache = {}
    if CACHE_FILE.exists():
        with open(CACHE_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["date"], row["home"], row["away"])
                cache[key] = (float(row["home_xg"]), float(row["away_xg"]))
    return cache

def save_cache(cache: dict):
    with open(CACHE_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "home", "away", "home_xg", "away_xg"])
        for (date, home, away), (hx, ax) in sorted(cache.items()):
            writer.writerow([date, home, away, hx, ax])

def estimate_xg_from_match(home: str, away: str, hg: int, ag: int, flags: list, comp: str, venue_home: bool = True) -> tuple[float, float]:
    """
    Estimate xG from match events when real xG unavailable.
    Uses goals, flags (f15, late_win, comeback, blown), and competition averages.
    """
    # Base xG per goal varies by competition
    comp_base = {
        'PL': 1.1, 'LALIGA': 1.05, 'BL1': 1.15, 'SA': 1.0, 'FL1': 1.0,
        'UCL': 1.1, 'UEL': 1.05, 'UECL': 1.0,
        'FAC': 1.0, 'CDR': 1.0, 'DFB': 1.0, 'CI': 1.0, 'CDF': 1.0, 'LC': 1.0, 'CS': 1.1,
    }
    base = comp_base.get(comp, 1.0)
    
    # Starting point: goals * base
    hx = hg * base
    ax = ag * base
    
    # Adjust based on flags
    for flag in flags:
        if '_H' in flag:
            side = 'H'
        elif '_A' in flag:
            side = 'A'
        else:
            continue
            
        parts = flag.split('_')
        kind = '_'.join(parts[:-1]) if parts[-1].isdigit() else '_'.join(parts[:2]) if len(parts) >= 3 else parts[0]
        # Normalise: late_win, late_eq, f15, comeback, multi_comeback, blown
        if parts[0] == 'late' and len(parts) >= 3:
            kind = parts[0] + '_' + parts[1]  # late_win / late_eq
        
        if kind == 'f15':
            # Early goal suggests dominance
            if side == 'H':
                hx += 0.3
            else:
                ax += 0.3
        elif kind == 'late_win':
            # Late winner suggests closer game than scoreline
            if side == 'H':
                hx += 0.2
                ax += 0.4  # opponent probably created chances
            else:
                ax += 0.2
                hx += 0.4
        elif kind == 'late_eq':
            # Late equalizer - both teams had chances
            hx += 0.3
            ax += 0.3
        elif kind == 'comeback':
            # Comeback winner - loser likely dominated early
            if side == 'H':
                hx += 0.1
                ax += 0.5
            else:
                ax += 0.1
                hx += 0.5
        elif kind == 'multi_comeback':
            # Even more dramatic
            if side == 'H':
                ax += 0.7
            else:
                hx += 0.7
        elif kind == 'blown':
            # Blown lead - winner dominated late
            if side == 'H':  # home blew lead
                hx += 0.4
                ax += 0.2
            else:
                ax += 0.4
                hx += 0.2
    
    # Clamp to reasonable ranges
    hx = max(0.3, min(hx, 3.5))
    ax = max(0.3, min(ax, 3.5))
    
    # If no goals, use competition average ~1.0-1.3
    if hg == 0 and ag == 0:
        hx = base * 1.1
        ax = base * 1.1
    elif hg == 0:
        hx = max(hx, base * 0.6)
    elif ag == 0:
        ax = max(ax, base * 0.6)
    
    return round(hx, 2), round(ax, 2)

def try_fetch_fbref(date: str, home: str, away: str, comp: str) -> Optional[tuple[float, float]]:
    """Try to fetch from FBref (may 403)."""
    try:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import quote
        
        slug_map = {
            'PL': 'premier-league', 'LALIGA': 'la-liga', 'BL1': 'bundesliga',
            'SA': 'serie-a', 'FL1': 'ligue-1', 'UCL': 'champions-league',
            'UEL': 'europa-league', 'UECL': 'europa-conference-league',
            'FAC': 'fa-cup', 'CDR': 'copa-del-rey', 'DFB': 'dfb-pokal',
            'CI': 'coppa-italia', 'CDF': 'coupe-de-france', 'LC': 'league-cup', 'CS': 'community-shield'
        }
        comp_slug = slug_map.get(comp, comp.lower())
        d = date.replace("-", "")
        home_slug = home.replace(" ", "-").replace(".", "").replace("'", "")
        away_slug = away.replace(" ", "-").replace(".", "").replace("'", "")
        
        url = f"https://fbref.com/en/matches/{d}/{home_slug}-{away_slug}-{d}-{comp_slug}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
            
        soup = BeautifulSoup(resp.content, "lxml")
        shots_table = soup.select_one("table#shots_all, table.stats_table[id*='shots']")
        if not shots_table:
            for table in soup.select("table.stats_table"):
                cap = table.select_one("caption")
                if cap and "shot" in cap.get_text().lower():
                    shots_table = table
                    break
        if not shots_table:
            return None
            
        tfoot = shots_table.select_one("tfoot")
        if not tfoot:
            return None
            
        hx = ax = None
        for row in tfoot.select("tr"):
            th = row.select_one("th[data-stat='xg']")
            if th:
                hx = float(th.get_text(strip=True))
            td = row.select_one("td[data-stat='xg']")
            if td:
                ax = float(td.get_text(strip=True))
                
        if hx is not None and ax is not None:
            return hx, ax
    except Exception:
        pass
    return None

def try_fetch_understat(date: str, home: str, away: str) -> Optional[tuple[float, float]]:
    """Try Understat (requires match ID - not practical for bulk)."""
    return None

def get_or_estimate_xg(date: str, home: str, away: str, hg: int, ag: int, flags: list, comp: str) -> tuple[float, float]:
    """Get xG from cache, or fetch, or estimate."""
    cache = load_cache()
    key = (date, home, away)
    
    if key in cache:
        return cache[key]
    
    # Try FBref for real matches
    fetched = try_fetch_fbref(date, home, away, comp)
    if fetched:
        cache[key] = fetched
        save_cache(cache)
        return fetched
    
    # Estimate from match data
    estimated = estimate_xg_from_match(home, away, hg, ag, flags, comp)
    cache[key] = estimated
    save_cache(cache)
    return estimated

def backfill_all_results(results_csv: str = "data/results.csv"):
    """Process all matches in results.csv, filling xG cache."""
    cache = load_cache()

    with open(results_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Processing {len(rows)} matches...")
    missing = []
    for row in rows:
        key = (row["date"], row["home"], row["away"])
        if key in cache:
            continue
        missing.append(row)

    def fill(row):
        key = (row["date"], row["home"], row["away"])
        fetched = try_fetch_fbref(row["date"], row["home"], row["away"], row["comp"])
        if fetched:
            return row, key, fetched, True
        flags = [x.strip() for x in (row.get("flags") or "").split(";") if x.strip()]
        hg, ag = int(row["hg"]), int(row["ag"])
        est = estimate_xg_from_match(row["home"], row["away"], hg, ag, flags, row["comp"])
        return row, key, est, False

    # FBref attempts are pure network I/O - run them in parallel
    if missing:
        from concurrent.futures import ThreadPoolExecutor
        workers = min(8, max(1, len(missing)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            filled = list(ex.map(fill, missing))
    else:
        filled = []

    for row, key, (hx, ax), _ in filled:
        cache[key] = (float(hx), float(ax))
        flags = [x.strip() for x in (row.get("flags") or "").split(";") if x.strip()]
        print(f"  {row['date']} {row['home']} {hx:.2f} - {ax:.2f} {row['away']}  (flags: {flags})")

    if filled:
        save_cache(cache)
    print(f"\nDone. Added {len(filled)} matches. Cache size: {len(cache)}")

def list_cached():
    cache = load_cache()
    for (date, home, away), (hx, ax) in sorted(cache.items()):
        print(f"{date} {home} {hx:.2f} - {ax:.2f} {away}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python fetch_xg.py backfill          # estimate xG for all results.csv")
        print("  python fetch_xg.py list              # show cache")
        print("  python fetch_xg.py add <date> <home> <away> <hx> <ax>  # manual override")
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == "backfill":
        backfill_all_results()
    elif cmd == "list":
        list_cached()
    elif cmd == "add" and len(sys.argv) == 7:
        _, _, date, home, away, hx, ax = sys.argv
        cache = load_cache()
        cache[(date, home, away)] = (float(hx), float(ax))
        save_cache(cache)
        print(f"Added: {date} {home} {hx} - {ax} {away}")
    else:
        print("Invalid command")