"""Nonlinear heads on raw+EMA features (no brain needed): is there headroom beyond ridge?"""
import argparse, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import train_branch as TB
from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, ExtraTreesRegressor
from sklearn.preprocessing import StandardScaler
from flybrain.options import AdvReadout

ap = argparse.ArgumentParser(); ap.add_argument('--labels', nargs='+', required=True); ap.add_argument('--seeds', type=int, default=2)
a = ap.parse_args()
games = TB.load_games(a.labels, 3500.)
X, Y, grp, opp = TB.build(games, 'feat', 3500., ema=0.9)
Yc = np.clip(Y, -300, 300)
core = np.isin(opp, ['guide', 'lag', 'lead'])
print(len(games), 'games', X.shape, 'core states', core.sum(), flush=True)


def cv(fit_predict, seed):
    pred = np.zeros_like(Yc)
    ug = np.unique(grp); rng = np.random.default_rng(seed); rng.shuffle(ug)
    for i in range(5):
        te = np.isin(grp, ug[i::5])
        pred[te] = fit_predict(X[~te], Yc[~te], X[te])
    return pred


def ridge(lam):
    return lambda Xtr, Ytr, Xte: AdvReadout().fit(Xtr, Ytr, lam).predict(Xte)


def mlp(h, alpha, seed=0):
    def f(Xtr, Ytr, Xte):
        sc = StandardScaler().fit(Xtr); ys = 100.
        m = MLPRegressor(hidden_layer_sizes=(h, h), alpha=alpha, max_iter=300, early_stopping=True, validation_fraction=.15, random_state=seed, n_iter_no_change=15)
        m.fit(sc.transform(Xtr), Ytr / ys)
        return m.predict(sc.transform(Xte)) * ys
    return f


def hgb(depth, lr, it):
    def f(Xtr, Ytr, Xte):
        out = np.zeros((len(Xte), Ytr.shape[1]))
        for j in range(Ytr.shape[1]):
            m = HistGradientBoostingRegressor(max_depth=depth, learning_rate=lr, max_iter=it, min_samples_leaf=20, l2_regularization=1.0, random_state=0)
            out[:, j] = m.fit(Xtr, Ytr[:, j]).predict(Xte)
        return out
    return f


def et():
    def f(Xtr, Ytr, Xte):
        return ExtraTreesRegressor(150, min_samples_leaf=8, max_features=0.5, n_jobs=1, random_state=0).fit(Xtr, Ytr).predict(Xte)
    return f

cands = {'ridge1000': ridge(1000.), 'mlp32_a1': mlp(32, 1.0), 'mlp64_a3': mlp(64, 3.0), 'hgb3_.05_120': hgb(3, .05, 120), 'extratrees': et()}
ref = None
for name, fp in cands.items():
    t0 = time.time()
    ps = [cv(fp, s) for s in range(a.seeds)]
    best = None
    for tau in (0., 5., 10., 20.):
        vs = [TB.policy_value(p, Y, tau)[0] for p in ps]
        m = np.mean([v.mean() for v in vs])
        if best is None or m > best[0]:
            best = (m, tau, vs)
    m, tau, vs = best
    v = np.mean(vs, 0)
    pg = np.mean([np.array([x[grp == g].mean() for g in np.unique(grp)]) for x in vs], 0)
    if ref is None: ref = pg
    d = pg - ref
    rng = np.random.default_rng(0); bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(1000)]
    po = {o: round(float(v[opp == o].mean()), 1) for o in ('guide', 'lag', 'lead', 'breaker', 'mix')}
    print('%-14s value %5.1f (tau %g) core %5.1f  vs ridge %+5.1f [%+.1f,%+.1f]  %s  (%.0fs)' % (name, m, tau, v[core].mean(), d.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5), po, time.time() - t0), flush=True)
