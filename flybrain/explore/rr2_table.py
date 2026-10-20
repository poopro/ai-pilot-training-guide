import json, numpy as np
from math import comb
def sp(a, b):
    n = a + b
    if n == 0: return 1.0
    k = min(a, b); return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
nm = {'opt_b1_frozen.feat.npz': 'F1', 'opt_mlp_v3.npz': 'M3', 'opt_mlp_v4.npz': 'M4'}
res = {}
for H in ('M4', 'M3', 'F1'):
    try: f = open('runs/rr2_%s/results.jsonl' % H)
    except FileNotFoundError: continue
    for l in f:
        r = json.loads(l)
        if 'error' in r: continue
        res.setdefault((H, nm[r['red'].split('/')[-1]]), {})[r['seed']] = r
print('blue\\red   F1      M3      M4')
for b in ('M4', 'M3', 'F1'):
    print('%-8s' % b + ''.join('%-8s' % ('%d/%d' % (sum(x['winner'] == 'blue' for x in res[(b, r)].values()), len(res[(b, r)])) if (b, r) in res else '-') for r in ('F1', 'M3', 'M4')))
for o in ('F1', 'M3'):
    w = l = 0
    d = res.get(('M4', o), {}); w += sum(x['winner'] == 'blue' for x in d.values()); l += sum(x['winner'] != 'blue' for x in d.values())
    d = res.get((o, 'M4'), {}); w += sum(x['winner'] == 'red' for x in d.values()); l += sum(x['winner'] != 'red' for x in d.values())
    print('M4 vs %s (both colours): %d-%d  p=%.4f' % (o, w, l, sp(w, l)))
col = [(k, x['seed'], x['winner']) for k, d in res.items() for x in d.values() if x['event'] == 'collision']
print('collisions:', col)
