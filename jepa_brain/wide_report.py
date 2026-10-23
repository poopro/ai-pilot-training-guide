"""Paired report for runs/wide1 (or any eval_pool3 run): per opponent W-L for each arm, paired sign tests vs a base arm.
  python wide_report.py runs/wide1 --base tuned2
"""
import argparse, json, math, collections
from pathlib import Path
import numpy as np


def sign_p(a, b):
    n = a + b
    if n == 0:
        return 1.
    k = min(a, b)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1., 2 * p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--base', default='tuned2')
    a = ap.parse_args()
    rows = [json.loads(l) for l in (Path(a.run) / 'results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    rows = [r for r in rows if 'error' not in r]
    arms = sorted({r['policy'] for r in rows}, key=lambda x: (x != a.base, x))
    opps = list(dict.fromkeys(r['red'] for r in rows))
    g = {(r['policy'], r['red'], r['seed']): r for r in rows}
    win = lambda r: 1 if r['winner'] == 'blue' else 0
    lines = ['| 對手 | ' + ' | '.join(arms) + ' | ' + ' | '.join('%s vs %s 配對' % (x, a.base) for x in arms[1:]) + ' |',
             '|' + '---|' * (1 + len(arms) + len(arms) - 1)]
    tot = collections.Counter(); totn = collections.Counter()
    for o in opps:
        cells, pairs = [], []
        seeds = sorted({r['seed'] for r in rows if r['red'] == o})
        for arm in arms:
            rs = [g[(arm, o, s)] for s in seeds if (arm, o, s) in g]
            w = sum(win(r) for r in rs); l = sum(r['winner'] == 'red' for r in rs)
            bad = sum(r['event'] in ('blue_crash', 'red_kill') for r in rs) + sum(r['event'] == 'collision' and r['winner'] == 'red' for r in rs)
            med = np.median([r['margin'] for r in rs]) if rs else 0
            cells.append('%d-%d%s (中位 %+.0f)' % (w, l, (' ⚠%d' % bad) if bad else '', med))
            tot[arm] += w; totn[arm] += len(rs)
        for arm in arms[1:]:
            only_a = sum(1 for s in seeds if (arm, o, s) in g and (a.base, o, s) in g and win(g[(arm, o, s)]) and not win(g[(a.base, o, s)]))
            only_b = sum(1 for s in seeds if (arm, o, s) in g and (a.base, o, s) in g and win(g[(a.base, o, s)]) and not win(g[(arm, o, s)]))
            pairs.append('%d 對 %d, p=%.3f' % (only_a, only_b, sign_p(only_a, only_b)))
        lines.append('| %s | %s | %s |' % (o, ' | '.join(cells), ' | '.join(pairs)))
    lines.append('| **合計** | ' + ' | '.join('%d/%d' % (tot[x], totn[x]) for x in arms) + ' | |')
    agl = {arm: min(r['min_agl_m'] for r in rows if r['policy'] == arm) for arm in arms}
    lines.append('')
    lines.append('最低離地高度（全部局）：' + '、'.join('%s %.0f m' % (k, v) for k, v in agl.items()))
    lines.append('⚠ = 我方墜機／被擊落／碰撞判輸的局數')
    out = '\n'.join(lines)
    print(out)
    (Path(a.run) / 'report.md').write_text(out + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
