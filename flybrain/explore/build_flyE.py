"""Build a pruned fly brain whose encoder has extra SLOW (EMA) sensory channels for the enemy-geometry features.
python explore/build_flyE.py --labels labels/pilot labels/b1 --out cacheE --every 2
"""
import argparse, glob, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from flybrain.pilot import FlyBrain, ENEMY_FEATS
from replay import replay_game

ap = argparse.ArgumentParser()
ap.add_argument('--labels', nargs='+', required=True); ap.add_argument('--out', default='cacheE'); ap.add_argument('--every', type=int, default=2)
ap.add_argument('--ema', type=float, default=0.9); ap.add_argument('--base-cache', default='cache480')
a = ap.parse_args()
files = sorted(f for d in a.labels for f in glob.glob(str(Path(d) / 'g*.npz')))
files = [f for f in files if len(np.load(f)['lab_dec'])][::a.every]
ef = np.asarray(ENEMY_FEATS, np.int64)
# encoder statistics: the 27 originals from the v1 cache, the slow channels from the EMA of the same label games
base = np.load(Path(a.base_cache) / 'enc_stats.npz')
allf = [np.load(f)['feats'] for f in sorted(f for d in a.labels for f in glob.glob(str(Path(d) / 'g*.npz')))]
em = []
for F in allf:
    m = None; seq = []
    for x in F:
        m = x.copy() if m is None else a.ema * m + (1 - a.ema) * x
        seq.append(m[ef])
    em.append(np.asarray(seq))
E = np.concatenate(em, 0)
mu = np.concatenate([base['mu'], E.mean(0).astype(np.float32)]); sd = np.concatenate([base['sd'], np.maximum(E.std(0), 0.1).astype(np.float32)])
out = Path(a.out); out.mkdir(exist_ok=True)
np.savez(out / 'enc_stats.npz', mu=mu, sd=sd, ema_feats=ef, ema=np.float32(a.ema))
brain = FlyBrain(device='cpu', dt_ms=1.0, window_ms=80.0, ema_feats=ef, ema=a.ema)
brain.enc.mu, brain.enc.sd = mu, sd
brain.use_numba()
print('encoder channels', brain.enc.idx.shape, 'replaying', len(files), 'games with the FULL brain (numba)', flush=True)
for f in files:
    t0 = time.time()
    z = np.load(f)
    dn, _, active = replay_game(brain, z['feats'], int(Path(f).stem[1:].split('_')[0]))
    np.savez_compressed(out / Path(f).name, dn=dn, active_idx=active, feats=z['feats'])
    print('  %s: %d decisions, %d neurons active, %.0fs' % (Path(f).name, len(dn), len(active), time.time() - t0), flush=True)
