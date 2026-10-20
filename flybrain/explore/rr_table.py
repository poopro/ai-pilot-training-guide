import json, glob, collections, numpy as np
from math import comb
names = {'opt_b1_frozen.feat.npz': 'F1', 'opt_v3.feat.npz': 'F3', 'opt_mlp_v3.npz': 'M3', 'opt_mlp_v2a.npz': 'M2', 'random:0.15': 'R'}
order = ['F1', 'F3', 'M3', 'M2', 'R']
res = {}   # (blue, red) -> {seed: row}
for H in order:
    try:
        f = open('runs/rr_%s/results.jsonl' % H)
    except FileNotFoundError:
        continue
    for l in f:
        r = json.loads(l)
        if 'error' in r: continue
        red = names.get(r['red'].replace('flyred:', '').split('/')[-1])
        res.setdefault((H, red), {})[r['seed']] = r
def sp(a, b):
    n = a + b
    if n == 0: return 1.0
    k = min(a, b); return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
print('rows = blue head, cols = red head; cell = blue wins/games')
print('%-6s' % '' + ''.join('%-9s' % c for c in order) + 'blue total')
for b in order:
    line = '%-6s' % b; W = N = 0
    for r in order:
        d = res.get((b, r), {})
        w = sum(x['winner'] == 'blue' for x in d.values()); W += w; N += len(d)
        line += '%-9s' % ('%d/%d' % (w, len(d)) if d else '-')
    print(line + '%d/%d' % (W, N))
# strength: each head's overall wins as blue + as red against OTHER heads
print('\noverall vs other heads (blue-side games + red-side games, excl. same-head):')
for h in order:
    W = L = 0
    for o in order:
        if o == h: continue
        d = res.get((h, o), {}); W += sum(x['winner'] == 'blue' for x in d.values()); L += sum(x['winner'] != 'blue' for x in d.values())
        d = res.get((o, h), {}); W += sum(x['winner'] == 'red' for x in d.values()); L += sum(x['winner'] != 'red' for x in d.values())
    print('%-4s %3d-%-3d  %.1f%%' % (h, W, L, 100.0 * W / max(1, W + L)))
print('\npairwise (both colours pooled; win-loss of row head vs col head, mean clipped margin from row head view):')
print('%-6s' % '' + ''.join('%-16s' % c for c in order))
for h in order:
    line = '%-6s' % h
    for o in order:
        if o == h: line += '%-16s' % '.'; continue
        w = l = 0; ms = []
        d = res.get((h, o), {})
        w += sum(x['winner'] == 'blue' for x in d.values()); l += sum(x['winner'] != 'blue' for x in d.values()); ms += [np.clip(x['margin'], -5000, 5000) for x in d.values()]
        d = res.get((o, h), {})
        w += sum(x['winner'] == 'red' for x in d.values()); l += sum(x['winner'] != 'red' for x in d.values()); ms += [-np.clip(x['margin'], -5000, 5000) for x in d.values()]
        line += '%-16s' % ('%d-%d (p=%.3f)' % (w, l, sp(w, l)) if w + l else '-')
    print(line)
col = collections.Counter()
for (b, r), d in res.items():
    for x in d.values():
        if x['event'] == 'collision': col[(b, r, x['winner'])] += 1
print('\ncollisions (blue head, red head, winner):', dict(col))
