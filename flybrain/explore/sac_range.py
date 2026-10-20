"""Where (range) do counterfactual tactics help vs the fleeing SAC 25.6M?  Uses the labels of sac games only (13 games)."""
import sys, glob, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings('ignore')
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import train_branch as TB
from flybrain.options import AdvReadout, InputBuilder, N_OPT
games = [g for g in TB.load_games(['labels/d1a', 'labels/d1b_sac'], 1e9) if g['opp'].startswith('sac')]
print('sac games', len(games), 'states', sum(len(g['dec']) for g in games))
rng = np.concatenate([g['rng'] for g in games]); A = np.concatenate([g['A'] for g in games])
names = ['PURSUE', 'LEAD', 'LAG', 'BREAK_IN', 'BREAK_OUT', 'HIGH_YOYO', 'LOW_YOYO', 'EXTEND']
print('A cols = options 1..%d of %s' % (N_OPT, names))
bins = [0, 1500, 3500, 6000, 10000, 15000, 1e9]
print('%-14s %5s ' % ('range', 'n') + ' '.join('%8s' % n[:8] for n in names[1:1 + N_OPT]) + '   oracle')
for lo, hi in zip(bins[:-1], bins[1:]):
    m = (rng >= lo) & (rng < hi)
    if m.sum() == 0: continue
    a = np.clip(A[m], -300, 300)
    print('%6d-%-7d %5d ' % (lo, min(hi, 99999), m.sum()) + ' '.join('%8.1f' % x for x in a.mean(0)) + '   %6.1f' % np.maximum(a.max(1), 0).mean())
# CV ridge on raw features for several zones
for zone in (3500, 6000, 10000, 1e9):
    Xs, Ys, gs = [], [], []
    for gi, g in enumerate(games):
        m = g['rng'] < zone
        ib = InputBuilder('feat', 1, 0.9)
        allx = np.asarray([ib.push(v) for v in g['feats']], np.float32)
        Xs.append(allx[g['dec'][m]]); Ys.append(np.clip(g['A'][m], -300, 300)); gs += [gi] * int(m.sum())
    X = np.concatenate(Xs); Y = np.concatenate(Ys); grp = np.array(gs)
    if len(X) < 50: continue
    for lam in (300, 3000):
        pred = TB.cv_predict(X, Y, grp, lam, 5)
        out = []
        for tau in (0, 5, 10, 20):
            v, take, k = TB.policy_value(pred, Y, tau)
            out.append('tau%g %.1f (take %.0f%%)' % (tau, v.mean(), 100 * take.mean()))
        print('zone %-6g lam %-5g n=%d  ' % (zone, lam, len(X)) + ' | '.join(out))
