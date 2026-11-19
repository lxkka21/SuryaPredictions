"""
update.py - One-command EET V2.3 update.

Rebuilds results.csv with accurate (goal-minute) ESPN data for the top-5
leagues, preserves cup matches, recomputes the site JSON, verifies sanity,
and deploys to Firebase hosting.

    python update.py --dry          # fetch+rebuild+recompute only, no deploy
    python update.py --recompute    # recompute site JSON from existing results.csv, no ESPN fetch
    python update.py                # full: rebuild, recompute, deploy
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)


def run(label, args=(), shell=False):
    import subprocess
    print(f"\n=== {label} ===")
    if shell:
        rc = subprocess.call(' '.join(args), shell=True)
    else:
        rc = subprocess.call([sys.executable, '-X', 'utf8'] + list(args))
    if rc != 0:
        sys.exit(f"FAILED in {label} (exit {rc})")
    return rc


def main():
    dry = '--dry' in sys.argv
    recompute = '--recompute' in sys.argv

    if recompute:
        run('Recompute site JSON', ['run_week.py'])
        run('Deploy to Firebase', ['firebase', 'deploy', '--only', 'hosting',
                                   '--project', 'suryapredictions-47401'], shell=True)
        print('\nDone. Live site rebuilt: https://suryapredictions-47401.web.app')
        return

    run('Fetch + rebuild results.csv', ['import_espn.py'] + (['--dry'] if dry else []))
    run('Fetch upcoming fixtures', ['fetch_fixtures.py'])
    run('Backfill xG cache', ['fetch_xg.py', 'backfill'])
    run('Recompute site JSON', ['run_week.py'])

    if dry:
        print('\nDRY RUN complete (no deploy).')
        return

    run('Deploy to Firebase', ['firebase', 'deploy', '--only', 'hosting',
                               '--project', 'suryapredictions-47401'], shell=True)
    print('\nDone. Live site rebuilt: https://suryapredictions-47401.web.app')


if __name__ == '__main__':
    main()
