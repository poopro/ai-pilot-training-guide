"""Compare benchmark arms with the frozen baseline (same seeds): python compare_bfm.py runs/eval_baseline runs/eval_baseline_sac314 runs/bfm_user ...
Writes runs/bfm_report.md"""
import json, sys, os
REF = os.environ.get('REF', 'base')       # policy name treated as the reference ('baseline' column); e.g. REF=base_t3
from pathlib import Path
from collections import defaultdict
import numpy as np
HERE = Path(__file__).resolve().parent
rows = []
for d in sys.argv[1:]:
    p = HERE / d / 'results.jsonl'
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            r = json.loads(line)
            if r.get('policy') == REF:
                r['policy'] = 'baseline'          # rollout_bfm 'base' arm == frozen repair_guide pursuit
            if 'error' not in r:
                rows.append(r)
by = defaultdict(dict)       # (red, seed) -> policy -> row
for r in rows:
    by[(r['red'], r['seed'])][r['policy']] = r
arms = sorted({r['policy'] for r in rows if r['policy'] != 'baseline'})
opps = sorted({r['red'] for r in rows})
out = ['| 對手 | arm | n | 勝-負 | 擊殺(blue_kill) | 碰撞輸 | 平均 margin | 對 baseline Δmargin | baseline 勝-負 | 平均攻擊tick | minAGL |', '|---|---|---|---|---|---|---|---|---|---|---|']
tot = defaultdict(lambda: [0, 0, 0, 0, 0.])
for red in opps:
    base = {s: v['baseline'] for (rd, s), v in by.items() if rd == red and 'baseline' in v}
    bw = sum(v['winner'] == 'blue' for v in base.values()); bl = sum(v['winner'] == 'red' for v in base.values())
    for arm in arms:
        rs = [v[arm] for (rd, s), v in by.items() if rd == red and arm in v]
        if not rs:
            continue
        w = sum(r['winner'] == 'blue' for r in rs); l = sum(r['winner'] == 'red' for r in rs)
        k = sum(r['event'] == 'blue_kill' for r in rs); col = sum(r['event'] == 'collision' and r['winner'] == 'red' for r in rs)
        pair = [r['margin'] - by[(red, r['seed'])]['baseline']['margin'] for r in rs if 'baseline' in by[(red, r['seed'])]]
        out.append('| %s | %s | %d | %d-%d | %d | %d | %.0f | %s | %d-%d | %.0f | %.0f |' % (
            red, arm, len(rs), w, l, k, col, np.mean([r['margin'] for r in rs]),
            ('%+.0f' % np.mean(pair)) if pair else '-', bw, bl, np.mean([r['atk_b'] for r in rs]), min(r['min_agl_m'] for r in rs)))
        t = tot[arm]; t[0] += w; t[1] += l; t[2] += k; t[3] += col; t[4] += sum(pair)
out += ['', '| arm | 總勝-負 | 擊殺 | 碰撞輸 |', '|---|---|---|---|']
for arm, t in sorted(tot.items()):
    out.append('| %s | %d-%d | %d | %d |' % (arm, t[0], t[1], t[2], t[3]))
(HERE / 'runs' / 'bfm_report.md').write_text('\n'.join(out), encoding='utf-8')
print('\n'.join(out))
