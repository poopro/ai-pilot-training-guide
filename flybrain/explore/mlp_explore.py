"""MLP heads (numpy-deployable) on raw+EMA features and on PCA'd fly DN features; core-opponent-weighted evaluation."""
import argparse, sys, time, pickle, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings('ignore')
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import train_branch as TB
from explore.offline_explore import replay_multi, dn_inputs, feat_inputs
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from flybrain.options import AdvReadout

ap = argparse.ArgumentParser(); ap.add_argument('--labels', nargs='+', required=True); ap.add_argument('--cache', default='cache480')
ap.add_argument('--dn-cache', default='explore/dn_cache.pkl'); ap.add_argument('--k', type=int, default=3); ap.add_argument('--seeds', type=int, default=2)
a = ap.parse_args()
games = TB.load_games(a.labels, 3500.)
dc = Path(a.dn_cache)
store = pickle.load(open(dc, 'rb')) if dc.exists() else {}
need = [g for g in games if g['name'] not in store]
if need:
    t0 = time.time(); replay_multi(need, a.cache, a.k)
    for g in need: store[g['name']] = g['dn_all']
    pickle.dump(store, open(dc, 'wb')); print('replayed %d games %.0fs' % (len(need), time.time() - t0), flush=True)
for g in games: g['dn_all'] = store[g['name']]; g['dn'] = g['dn_all'][0]
Xf, Y, grp, opp = feat_inputs(games, 3500., 0.9)
Xf0 = feat_inputs(games, 3500., 0.0)[0]
Xd1 = dn_inputs(games, 3500., 1, 1)[0]
Xd3 = dn_inputs(games, 3500., 1, a.k)[0]
Yc = np.clip(Y, -300, 300)
core = np.isin(opp, ['guide', 'lag', 'lead'])
print(len(games), 'games', len(Y), 'states', core.sum(), 'core', flush=True)


def fit_mlp(Xtr, Ytr, h, alpha, nens, pca=None):
    sc = StandardScaler().fit(Xtr); Z = sc.transform(Xtr); p = None
    if pca:
        p = PCA(pca, random_state=0).fit(Z); Z = p.transform(Z); s2 = Z.std(0) + 1e-6; Z = Z / s2
    ms = []
    for s in range(nens):
        m = MLPRegressor(hidden_layer_sizes=(h, h), alpha=alpha, max_iter=400, early_stopping=True, validation_fraction=.15, random_state=s, n_iter_no_change=20)
        ms.append(m.fit(Z, Ytr / 100.))
    def pred(Xte):
        Zt = sc.transform(Xte)
        if p is not None: Zt = p.transform(Zt) / s2
        return np.mean([m.predict(Zt) for m in ms], 0) * 100.
    return pred


def run(name, X, h=64, alpha=3., nens=3, pca=None, ridge_lam=None):
    t0 = time.time(); vs = []; ps = []
    for sd in range(a.seeds):
        pred = np.zeros_like(Yc)
        ug = np.unique(grp); rng = np.random.default_rng(sd); rng.shuffle(ug)
        for i in range(5):
            te = np.isin(grp, ug[i::5])
            pred[te] = AdvReadout().fit(X[~te], Yc[~te], ridge_lam).predict(X[te]) if ridge_lam else fit_mlp(X[~te], Yc[~te], h, alpha, nens, pca)(X[te])
        ps.append(pred)
    best = None
    for tau in (0., 5., 10., 20.):
        v = np.mean([TB.policy_value(p, Y, tau)[0] for p in ps], 0)
        # model selection by CORE value (guide/lag/lead) so that saturated opponents do not dominate
        if best is None or v[core].mean() > best[0]: best = (v[core].mean(), tau, v)
    c, tau, v = best
    pg = np.array([v[grp == g].mean() for g in np.unique(grp)])
    po = {o: round(float(v[opp == o].mean()), 1) for o in ('guide', 'lag', 'lead', 'breaker', 'mix')}
    print('%-22s core %5.1f all %5.1f tau %g %s (%.0fs)' % (name, c, v.mean(), tau, po, time.time() - t0), flush=True)
    return pg, ps


ref, _ = run('ridge feat_e0.9', Xf, ridge_lam=1000.)
for nm, X, kw in [('mlp64 a3 x3 feat_e.9', Xf, dict(h=64, alpha=3.)), ('mlp64 a3 x3 DNens pca32', Xd3, dict(h=64, alpha=3., pca=32)),
                  ('mlp64 a3 x3 DN1 pca32', Xd1, dict(h=64, alpha=3., pca=32)), ('mlp64 a10 x3 feat_e.9', Xf, dict(h=64, alpha=10.)),
                  ('mlp64 a3 x3 feat_e0', Xf0, dict(h=64, alpha=3.)), ('mlp64 a10 x3 DNens pca16', Xd3, dict(h=64, alpha=10., pca=16))]:
    run(nm, X, **kw)
