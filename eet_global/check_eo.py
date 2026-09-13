import json
with open(r'C:\Users\surya\OneDrive\Desktop\inshallah\v2.3\eet_global\site\data\matches.json') as f:
    data = json.load(f)

for m in data:
    if 'Atalanta' in m['id'] and 'Bologna' in m['id']:
        print(f"=== {m['id']} ===")
        print(f"Home: {m['home_rec']['team']} EO={m['home_rec']['EO']:.3f} EX={m['home_rec']['EX']:.3f} SI={m['home_rec']['SI']:.3f} PJI={m['home_rec']['PJI']:.3f}")
        print(f"Away: {m['away_rec']['team']} EO={m['away_rec']['EO']:.3f} EX={m['away_rec']['EX']:.3f} SI={m['away_rec']['SI']:.3f} PJI={m['away_rec']['PJI']:.3f}")
        print()
    if 'Aston Villa' in m['id'] and 'Arsenal' in m['id']:
        print(f"=== {m['id']} ===")
        print(f"Home: {m['home_rec']['team']} EO={m['home_rec']['EO']:.3f} EX={m['home_rec']['EX']:.3f} SI={m['home_rec']['SI']:.3f} PJI={m['home_rec']['PJI']:.3f}")
        print(f"Away: {m['away_rec']['team']} EO={m['away_rec']['EO']:.3f} EX={m['away_rec']['EX']:.3f} SI={m['away_rec']['SI']:.3f} PJI={m['away_rec']['PJI']:.3f}")
        print()