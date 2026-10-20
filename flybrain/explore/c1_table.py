import json, sys, numpy as np
def load(paths):
    d = {}
    for p in paths:
        try:
            for l in open(p):
                r = json.loads(l)
                if 'error' in r: continue
                d[(r['policy'], r['red'], r['seed'])] = r
        except FileNotFoundError:
            pass
    return d
dirs = sys.argv[1].split(',')
d = load(['runs/%s/results.jsonl' % x for x in dirs])
pols = sorted({k[0] for k in d})
opps = [o for o in sys.argv[2].split(',')]
print('%-12s' % 'arm' + ''.join('%-13s' % o for o in opps) + '%-9s%-8s%s' % ('TOTAL', 'margin', 'collLost'))
for p in pols:
    line = '%-12s' % p; W = L = 0; ms = []
    for o in opps:
        rs = [r for (pp, red, s), r in d.items() if pp == p and red == o]
        w = sum(r['winner'] == 'blue' for r in rs); W += w; L += len(rs) - w
        ms += [np.clip(r['margin'], -5000, 5000) for r in rs]
        line += '%-13s' % ('%d-%d' % (w, len(rs) - w))
    cl = sum(1 for (pp, red, s), r in d.items() if pp == p and red in opps and r['event'] == 'collision' and r['winner'] == 'red')
    line += '%-9s%-8.0f%d' % ('%d-%d' % (W, L), np.mean(ms) if ms else 0, cl)
    print(line)
