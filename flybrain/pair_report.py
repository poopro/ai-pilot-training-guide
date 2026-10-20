"""Paired comparison of arms on identical games.  usage: python pair_report.py base=<jsonl>[@policy] name=<jsonl>[@policy] [name2=...]
 'base' rows are the policy base_t3; all other labels use every non-base row of their file.
 Prints win-loss per opponent, paired win differences (exact sign test) and paired mean margin difference (clipped at +-CLIP, bootstrap over games)."""
import json, sys, collections
import numpy as np
from math import comb
CLIP = 5000.0


def load(spec, base):
    """spec = path  (base: rows of policy base_t3; arm: all other rows)   or   path@policy  (rows of exactly that policy)"""
    path, _, pol = spec.partition('@')
    d = {}
    for l in open(path, encoding='utf-8'):
        r = json.loads(l)
        if 'error' in r:
            continue
        if pol:
            if r['policy'] != pol:
                continue
        elif (r['policy'] == 'base_t3') != base:
            continue
        d[(r['red'], r['seed'])] = r
    return d


def sign_p(a, b):
    n = a + b
    if n == 0: return 1.0
    k = min(a, b)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    specs = [x.split('=', 1) for x in sys.argv[1:]]
    base = load(specs[0][1], True)
    arms = {lab: load(p, False) for lab, p in specs[1:]}
    opps = sorted({k[0] for k in base})
    print('%-14s %-9s' % ('opponent', specs[0][1].partition('@')[2] or 'base_t3') + ''.join('%-12s' % l for l in arms))
    rng = np.random.default_rng(0)
    for o in opps + ['ALL']:
        ks = [k for k in base if (o == 'ALL' or k[0] == o)]
        line = '%-14s %2d-%-2d    ' % (o, sum(base[k]['winner'] == 'blue' for k in ks), sum(base[k]['winner'] != 'blue' for k in ks))
        for lab, d in arms.items():
            kk = [k for k in ks if k in d]
            if not kk: line += '%-12s' % '-'; continue
            line += '%2d-%-2d       ' % (sum(d[k]['winner'] == 'blue' for k in kk), sum(d[k]['winner'] != 'blue' for k in kk))
        print(line)
    print('\npaired vs %s (all opponents pooled):' % (specs[0][1].partition('@')[2] or 'base_t3'))
    for lab, d in arms.items():
        kk = [k for k in base if k in d]
        a = sum(d[k]['winner'] == 'blue' and base[k]['winner'] != 'blue' for k in kk); b = sum(base[k]['winner'] == 'blue' and d[k]['winner'] != 'blue' for k in kk)
        diff = np.array([np.clip(d[k]['margin'], -CLIP, CLIP) - np.clip(base[k]['margin'], -CLIP, CLIP) for k in kk])
        bs = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(2000)]
        print('  %-10s %3d games: only-arm %2d only-base %2d (sign p=%.3f) | margin diff %+7.0f [%+.0f, %+.0f] | shot down %d, collision losses %d' % (
            lab, len(kk), a, b, sign_p(a, b), diff.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5),
            sum(d[k]['event'] == 'red_kill' for k in kk), sum(d[k]['event'] == 'collision' and d[k]['winner'] == 'red' for k in kk)))
    if len(arms) > 1:
        labs = list(arms)
        print('\narm vs arm (same games):')
        for i in range(len(labs)):
            for j in range(i + 1, len(labs)):
                A, B = arms[labs[i]], arms[labs[j]]
                kk = [k for k in A if k in B]
                a = sum(A[k]['winner'] == 'blue' and B[k]['winner'] != 'blue' for k in kk); b = sum(B[k]['winner'] == 'blue' and A[k]['winner'] != 'blue' for k in kk)
                diff = np.array([np.clip(A[k]['margin'], -CLIP, CLIP) - np.clip(B[k]['margin'], -CLIP, CLIP) for k in kk])
                bs = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(2000)]
                print('  %s vs %s: %d games, only-%s %d, only-%s %d (p=%.3f) | margin diff %+.0f [%+.0f, %+.0f]' % (labs[i], labs[j], len(kk), labs[i], a, labs[j], b, sign_p(a, b), diff.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)))


if __name__ == '__main__':
    main()
