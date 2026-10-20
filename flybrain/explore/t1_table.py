import json, sys, numpy as np
def load(path, pol=None):
    d = {}
    for l in open(path):
        r = json.loads(l)
        if 'error' in r: continue
        if pol and r['policy'] != pol: continue
        d[(r['red'], r['seed'])] = r
    return d
def both(a, b, pol=None):
    return {**load(a, pol), **load(b, pol)}
R = 'runs/'
arms = {
 'base_t3': both(R+'t1_mlp3_b3_gl/results.jsonl', R+'t1_mlp3_b3_rest/results.jsonl', 'base_t3'),
 'tuned': both(R+'t1_mlp3_gl/results.jsonl', R+'t1_mlp3_rest/results.jsonl', 'tuned'),
 'fly_t3 mlp3': both(R+'t1_mlp3_b3_gl/results.jsonl', R+'t1_mlp3_b3_rest/results.jsonl', 'fly_t3'),
 'fly_tuned mlp3': both(R+'t1_mlp3_gl/results.jsonl', R+'t1_mlp3_rest/results.jsonl', 'fly_tuned'),
 'fly_tuned feat1': both(R+'t1_feat1_gl/results.jsonl', R+'t1_feat1_rest/results.jsonl'),
 'fly_tuned dn1 (fly)': both(R+'t1_dn1_gl/results.jsonl', R+'t1_dn1_rest/results.jsonl'),
 'fly_tuned rand': both(R+'t1_rand_gl/results.jsonl', R+'t1_rand_rest/results.jsonl'),
}
import os
if os.path.exists(R+'t1_feat3_rest/results.jsonl'):
    arms['fly_tuned feat3'] = both(R+'t1_feat3_gl/results.jsonl', R+'t1_feat3_rest/results.jsonl')
opps = ['guide', 'lag', 'lead', 'defender', 'pp0', 'ctl:tuned', 'ctl:base_t3']
print('%-20s' % 'arm' + ''.join('%-12s' % o for o in opps) + '%-9s%-8s%s' % ('TOTAL', 'margin', 'coll.lost'))
for k, d in arms.items():
    line = '%-20s' % k; W = L = 0
    for o in opps:
        rs = [r for (red, s), r in d.items() if red == o]
        w = sum(r['winner'] == 'blue' for r in rs); W += w; L += len(rs) - w
        line += '%-12s' % ('%d-%d' % (w, len(rs) - w))
    line += '%-9s%-8.0f%d' % ('%d-%d' % (W, L), np.mean([np.clip(r['margin'], -5000, 5000) for r in d.values()]), sum(r['event'] == 'collision' and r['winner'] == 'red' for r in d.values()))
    print(line)
