"""per-call latency of portable/fighter_opt.py profiles inside a real game (2-core container, one process, nothing else running)"""
import sys, time, numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
for p in (str(HERE.parent / 'jepa_brain'), str(HERE), str(HERE / 'portable'), str(HERE.parent / 'campaign_2026' / 'repair_v1')):
    sys.path.insert(0, p)
import rollout, rollout_bfm as RB, fighter_opt
T = []
class Timed:
    def __init__(self, inner): self.inner = inner
    def __getattr__(self, k): return getattr(self.inner, k)
    def act(self, *a, **k):
        t0 = time.perf_counter(); r = self.inner.act(*a, **k); T.append(time.perf_counter() - t0); return r
orig = RB.make_arm
def patched(name):
    if isinstance(name, str) and name.startswith('popt:'):
        return Timed(fighter_opt.build(name[5:])), None
    return orig(name)
RB.make_arm = patched
for prof in sys.argv[1:]:
    T.clear()
    cfg = dict(rollout.game_config(0, 1020000, 'lead', 3000), host_fidelity=True)
    RB.play_game(cfg, 'popt:' + prof)
    t = np.array(T) * 1000
    print('%-20s n=%d  mean %.3f ms  median %.3f  p99 %.3f  max %.3f   (every 20th call = decision tick: mean %.3f ms)' % (prof, len(t), t.mean(), np.median(t), np.percentile(t, 99), t.max(), t[::20].mean()))
