"""python def_report.py runs/def_sweep1 runs/def_sweep2 ...  -> per arm x opponent x side win/loss, mean margin, own/enemy position score, defence usage."""
import json, sys, collections
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
rows = {}
for d in sys.argv[1:]:
    p = HERE / d / 'results.jsonl'
    if p.exists():
        for l in p.read_text(encoding='utf-8').splitlines():
            r = json.loads(l)
            if 'error' not in r:
                rows[(r['policy'], r['red'], r['seed'])] = r
rows = list(rows.values())
def sc(r): return 1. if r['winner'] == 'blue' else (0. if r['winner'] == 'red' else .5)
opps = sorted({r['red'] for r in rows}); arms = sorted({r['policy'] for r in rows}, key=lambda a: (a != 'tuned', a))
for o in opps:
    print('\n### opponent', o)
    print('%-34s %-9s %-9s %-9s %7s %7s %7s %6s %5s %4s' % ('arm', 'all W-L', 'side+1', 'side-1', 'margin', 'posB', 'posR', 'defTk', 'coll', 'kill'))
    ref = {r['seed']: r for r in rows if r['red'] == o and r['policy'] == 'tuned'}
    for a in arms:
        rs = [r for r in rows if r['red'] == o and r['policy'] == a]
        if not rs: continue
        def wl(x): return '%d-%d' % (sum(r['winner'] == 'blue' for r in x), sum(r['winner'] == 'red' for r in x))
        s1 = [r for r in rs if r['side'] == 1]; s2 = [r for r in rs if r['side'] == -1]
        pair = [sc(r) - sc(ref[r['seed']]) for r in rs if r['seed'] in ref and a != 'tuned']
        print('%-34s %-9s %-9s %-9s %7.0f %7.0f %7.0f %6.0f %5d %4d  %s' % (a, wl(rs), wl(s1), wl(s2), np.mean([r['margin'] for r in rs]), np.mean([r['pos_b'] for r in rs]), np.mean([r['pos_r'] for r in rs]),
              np.mean([r.get('def_ticks', 0) for r in rs]), sum(r['event'] == 'collision' and r['winner'] == 'red' for r in rs), sum(r['event'] == 'blue_kill' for r in rs),
              ('paired d=%+.2f (n=%d)' % (np.mean(pair), len(pair))) if pair else ''))
