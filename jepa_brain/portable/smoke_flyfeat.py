"""Smoke test: every profile builds through fighter.build (as player_fighter does); time fly_feat.act() per tick. Run from jepa_brain."""
import time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent.parent
_src = open(HERE / 'portable' / 'check_equiv_syn.py', encoding='utf-8').read().split('import os\nNTICK')[0]
exec(_src)
for prof in ('base', 'base_t3', 'tuned', 'tuned_open:6', 'fly_feat'):
    p = fighter.build(prof); print('build ok:', prof, type(p).__name__)
try:
    fighter.build('nonsense')
except ValueError as e:
    print('unknown profile ->', e)
obs = scenario('abeamL', 0, 1200)
for prof in ('fly_feat', 'base_t3'):
    p = fighter.build(prof); ts = []
    for ob in obs:
        t = time.perf_counter(); p.act(ob); ts.append((time.perf_counter() - t) * 1000)
    ts = np.array(ts)
    print('%-8s act() ms/tick: mean %.3f  p99 %.3f  max %.3f  (budget 16.7)' % (prof, ts.mean(), np.percentile(ts, 99), ts.max()))
p = fighter.build('fly_feat')
for ob in obs:
    p.act(ob)
print('fly_feat after 1200 ticks: options chosen %d, decision-code errors %d, tactic histogram %s' % (p.n_options, p.n_errors, p.hist))
print('not-started frame ->', fighter.build('fly_feat').act(obs[0], None, False))
