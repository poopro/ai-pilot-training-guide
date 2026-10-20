"""the decision layer of portable/fighter_opt.py must never crash the player: inject exceptions into features() and into the head"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
for p in (str(HERE.parent / 'jepa_brain'), str(HERE), str(HERE / 'portable'), str(HERE.parent / 'campaign_2026' / 'repair_v1')):
    sys.path.insert(0, p)
import rollout, rollout_bfm as RB, fighter_opt
orig = RB.make_arm
made = []
def patched(name):
    if isinstance(name, str) and name.startswith('popt:'):
        p = fighter_opt.build(name[5:]); made.append(p); return p, None
    return orig(name)
RB.make_arm = patched
cfg = dict(rollout.game_config(0, 1020000, 'lead', 3000), host_fidelity=True)
# 1) features() raises at every decision
f0 = fighter_opt.features
def bad(*a, **k): raise RuntimeError('injected')
fighter_opt.features = bad
r = RB.play_game(cfg, 'popt:opt_mlp:tuned'); p = made[-1]
print('features raise : game finished (%s), n_errors=%d, non-PURSUE ticks=%d' % (r['event'], p.n_errors, p.n_def_ticks))
fighter_opt.features = f0
# 2) head returns NaN
orig_pred = fighter_opt._Readout.predict
import numpy as np
fighter_opt._Readout.predict = lambda self, x: np.full((1, 7), np.nan, np.float32)
r = RB.play_game(cfg, 'popt:opt_ridge:tuned'); p = made[-1]
print('head returns NaN: game finished (%s), n_errors=%d, non-PURSUE ticks=%d' % (r['event'], p.n_errors, p.n_def_ticks))
fighter_opt._Readout.predict = orig_pred
# 3) normal
r = RB.play_game(cfg, 'popt:opt_ridge:tuned'); p = made[-1]
print('normal         : game finished (%s), n_errors=%d, non-PURSUE ticks=%d, margin %.1f' % (r['event'], p.n_errors, p.n_def_ticks, r['margin']))
