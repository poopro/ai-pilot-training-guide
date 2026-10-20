import json, glob, numpy as np
from math import comb
def sp(a, b):
    n = a + b
    if n == 0: return 1.0
    k = min(a, b); return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
D = {}
for T in (0, 20, 40, 80):
    try: f = open('runs/tau_%d/results.jsonl' % T)
    except FileNotFoundError: continue
    for l in f:
        r = json.loads(l)
        if 'error' in r: continue
        D.setdefault(T, {})[(r['red'].split('/')[-1], r['seed'])] = r
print('tau   lead(w-l  margin)      selfplay vs F1 red (w-l  margin)   options/game(lead, sp)')
for T, d in D.items():
    out = []
    for o in ('lead', 'opt_b1_frozen.feat.npz'):
        rs = [r for (red, s), r in d.items() if red == o]
        w = sum(r['winner'] == 'blue' for r in rs)
        out.append('%2d-%-2d %6.0f   n=%d  noPURSUE ticks %.0f' % (w, len(rs) - w, np.mean([np.clip(r['margin'], -5000, 5000) for r in rs]) if rs else 0, len(rs), np.mean([sum(r['tactics'][1:]) for r in rs]) if rs else 0))
    print('%-4d  %s   |   %s' % (T, out[0], out[1]))
base = D.get(0, {})
for T, d in D.items():
    if T == 0: continue
    for o in ('lead', 'opt_b1_frozen.feat.npz'):
        ks = [k for k in d if k[0] == o and k in base]
        a = sum(d[k]['winner'] == 'blue' and base[k]['winner'] != 'blue' for k in ks); b = sum(base[k]['winner'] == 'blue' and d[k]['winner'] != 'blue' for k in ks)
        print('tau %d vs tau 0 on %s: n=%d only-higher-tau %d only-tau0 %d p=%.3f' % (T, o[:8], len(ks), a, b, sp(a, b)))
