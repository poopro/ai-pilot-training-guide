"""Offline: does giving the fly slow (EMA) channels make its DN activity as informative as raw+EMA?"""
import argparse, sys, time, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings('ignore')
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import train_branch as TB
from flybrain.pilot import load_brain, FlyBrain
from flybrain.options import AdvReadout
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

ap = argparse.ArgumentParser(); ap.add_argument('--labels', nargs='+', required=True); ap.add_argument('--cache', default='cacheE'); ap.add_argument('--k', type=int, default=1)
ap.add_argument('--tag', default='flyE'); a = ap.parse_args()
games = TB.load_games(a.labels, 3500.)
t0 = time.time()
brain = load_brain(a.cache, 'numba')
dns = []
for s in range(a.k):
    for g in games:
        brain.reset(g['seed'] + 1000 * s)
        g.setdefault('dn_all', []).append(np.asarray([brain.observe(f) for f in g['feats']], np.int16))
print('replayed %.0fs (%d seeds)' % (time.time() - t0, a.k), flush=True)
Xs = []
for s in range(a.k):
    for g in games: g['dn'] = g['dn_all'][s]
    X, Y, grp, opp = TB.build(games, 'dn', 3500., pool=1)
    Xs.append(X)
Xd = np.mean(Xs, 0)
Xf, _, _, _ = TB.build(games, 'feat', 3500., ema=0.9)
Yc = np.clip(Y, -300, 300); core = np.isin(opp, ('guide', 'lag', 'lead'))
print(len(games), 'games', len(Y), 'states', flush=True)


def evaluate(name, X, kind, **kw):
    t0 = time.time(); ps = []
    for sd in range(2):
        pred = np.zeros_like(Yc)
        ug = np.unique(grp); rng = np.random.default_rng(sd); rng.shuffle(ug)
        for i in range(5):
            te = np.isin(grp, ug[i::5])
            if kind == 'ridge':
                pred[te] = AdvReadout().fit(X[~te], Yc[~te], kw['lam']).predict(X[te])
            else:
                sc = StandardScaler().fit(X[~te]); Z = sc.transform(X[~te]); Zt = sc.transform(X[te])
                if kw.get('pca'):
                    p = PCA(kw['pca'], random_state=0).fit(Z); Z = p.transform(Z); Zt = p.transform(Zt); s2 = Z.std(0) + 1e-6; Z /= s2; Zt /= s2
                out = 0
                for m_ in range(3):
                    m = MLPRegressor(hidden_layer_sizes=(64, 64), alpha=kw.get('alpha', 3.), max_iter=400, early_stopping=True, validation_fraction=.15, random_state=sd * 100 + m_, n_iter_no_change=20)
                    out = out + m.fit(Z, Yc[~te] / 100.).predict(Zt)
                pred[te] = out / 3 * 100.
        ps.append(pred)
    best = None
    for tau in (0., 5., 10., 20.):
        v = np.mean([TB.policy_value(p, Y, tau)[0] for p in ps], 0)
        if best is None or v[core].mean() > best[0]: best = (v[core].mean(), tau, v)
    c, tau, v = best
    print('%-28s core %5.1f all %5.1f tau %g %s (%.0fs)' % (name, c, v.mean(), tau, {o: round(float(v[opp == o].mean()), 1) for o in ('guide', 'lag', 'lead', 'breaker', 'mix')}, time.time() - t0), flush=True)


evaluate('raw+ema ridge (ref)', Xf, 'ridge', lam=1000.)
evaluate('%s DN ridge lam3000' % a.tag, Xd, 'ridge', lam=3000.)
evaluate('%s DN ridge lam300' % a.tag, Xd, 'ridge', lam=300.)
evaluate('%s DN pca32 mlp a3' % a.tag, Xd, 'mlp', pca=32, alpha=3.)
evaluate('%s DN pca64 mlp a3' % a.tag, Xd, 'mlp', pca=64, alpha=3.)
