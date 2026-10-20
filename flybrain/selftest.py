"""Quick health check (1-2 minutes).

  python selftest.py                 # CPU
  python selftest.py --device cuda   # your RTX GPU

Checks: data present -> connectome loads -> LIF runs -> activity is graded (no seizure-like avalanche, not silent)
-> seconds per tactical decision (the number that decides how many games you can afford).
"""
import argparse, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import torch
from flybrain.connectome import Connectome
from flybrain.lif import FlyLIF
from flybrain.pilot import FlyBrain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--dt', type=float, default=1.0)
    a = ap.parse_args()
    t0 = time.time()
    C = Connectome()
    print('load %.1fs' % (time.time() - t0))
    dn = C.select(super_class='descending')
    rng = np.random.default_rng(0)
    # 1) raw model: 200 visual-projection neurons driven at 100 Hz for one biological second
    L = FlyLIF(C, dt_ms=a.dt, device=a.device, seed=0)
    pool = C.select(super_class='visual_projection')
    idx = rng.choice(pool, 200, replace=False)
    L.run(10, idx, np.full(200, 100.0))        # warm-up (CUDA init)
    L.reset()
    t0 = time.time()
    c = L.run(int(1000 / a.dt), idx, np.full(200, 100.0)).cpu().numpy()
    if a.device != 'cpu': torch.cuda.synchronize()
    print('1 s of fly-brain time: %.2f s wall | neurons spiking %d | spikes %d | DN spiking %d' % (
        time.time() - t0, (c > 0).sum(), c.sum(), (c[dn] > 0).sum()))
    ok1 = 100 < (c > 0).sum() < 5000 and c[dn].sum() > 0
    # 2) the pilot (encoder + brain), one tactical decision = 80 ms window
    B = FlyBrain(conn=C, device=a.device, dt_ms=a.dt)
    feats = rng.normal(0, 1, size=(30, 27)).astype(np.float32)
    B.enc.fit_stats([feats])
    B.reset(1)
    B.observe(feats[0])
    t0 = time.time()
    act = []
    for f in feats[1:]:
        d, (si, sc) = B.observe(f, full=True)
        act.append((len(si), int(d.sum())))
    if a.device != 'cpu': torch.cuda.synchronize()
    per = (time.time() - t0) / (len(feats) - 1)
    act = np.array(act)
    print('per decision: %.3f s -> one 300 s game (900 decisions) ~ %.1f min | neurons active/window %.0f | DN spikes/window %.0f' % (
        per, per * 900 / 60, act[:, 0].mean(), act[:, 1].mean()))
    ok2 = act[:, 0].max() < 5000 and act[:, 1].mean() > 0
    print('SELFTEST', 'OK' if (ok1 and ok2) else 'FAILED (activity out of the graded regime - see README, "seizure")')


if __name__ == '__main__':
    main()
