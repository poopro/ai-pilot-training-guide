import json, numpy as np, sys
from math import comb
def sp(a, b):
    n = a + b
    if n == 0: return 1.0
    k = min(a, b); return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
runs = sys.argv[1].split(',')
names = {'lead': 'lead', 'opt_mlp_v3.npz': 'red M3', 'opt_b1_frozen.feat.npz': 'red F1'}
D = {}
for r in runs:
    try: f = open('runs/%s/results.jsonl' % r)
    except FileNotFoundError: continue
    for l in f:
        x = json.loads(l)
        if 'error' in x: continue
        D.setdefault(r, {})[(names.get(x['red'].split('/')[-1], x['red']), x['seed'])] = x
cols = ['lead', 'red M3', 'red F1']
print('%-14s' % 'blue head' + ''.join('%-22s' % c for c in cols) + 'total')
for r, d in D.items():
    line = '%-14s' % r; W = N = 0
    for c in cols:
        rs = [x for (o, s), x in d.items() if o == c]
        w = sum(x['winner'] == 'blue' for x in rs); W += w; N += len(rs)
        line += '%-22s' % ('%d-%d  m%+5.0f  coll%d' % (w, len(rs) - w, np.mean([np.clip(x['margin'], -5000, 5000) for x in rs]) if rs else 0, sum(x['event'] == 'collision' and x['winner'] == 'red' for x in rs)) if rs else '-')
    print(line + '%d-%d' % (W, N - W))
base = runs[-1]
for r in runs[:-1]:
    if r not in D or base not in D: continue
    for c in cols:
        ks = [k for k in D[r] if k[0] == c and k in D[base]]
        a = sum(D[r][k]['winner'] == 'blue' and D[base][k]['winner'] != 'blue' for k in ks); b = sum(D[base][k]['winner'] == 'blue' and D[r][k]['winner'] != 'blue' for k in ks)
        print('%s vs %s on %s: n=%d only-%s %d only-%s %d p=%.3f' % (r, base, c, len(ks), r, a, base, b, sp(a, b)))
