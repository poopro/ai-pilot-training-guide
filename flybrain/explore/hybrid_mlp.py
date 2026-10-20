"""MLP on [raw+EMA features | PCA(fly DN)]: does the fly add anything on top of the raw features?"""
import sys, time, pickle, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings('ignore')
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import train_branch as TB
from explore.offline_explore import dn_inputs, feat_inputs
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

games = TB.load_games(['labels/pilot', 'labels/b1'], 3500.)
store = pickle.load(open('explore/dn_cache.pkl', 'rb'))
for g in games: g['dn_all'] = store[g['name']]; g['dn'] = g['dn_all'][0]
Xf, Y, grp, opp = feat_inputs(games, 3500., 0.9)
Xd3 = dn_inputs(games, 3500., 1, 3)[0]
Yc = np.clip(Y, -300, 300); core = np.isin(opp, ('guide', 'lag', 'lead'))


def run(name, use_dn, npca, alpha=3., seeds=2):
    t0 = time.time(); ps = []
    for sd in range(seeds):
        pred = np.zeros_like(Yc)
        ug = np.unique(grp); rng = np.random.default_rng(sd); rng.shuffle(ug)
        for i in range(5):
            te = np.isin(grp, ug[i::5])
            sc = StandardScaler().fit(Xf[~te]); Z = sc.transform(Xf[~te]); Zt = sc.transform(Xf[te])
            if use_dn:
                sd_ = StandardScaler().fit(Xd3[~te]); D = sd_.transform(Xd3[~te]); Dt = sd_.transform(Xd3[te])
                p = PCA(npca, random_state=0).fit(D); D = p.transform(D); Dt = p.transform(Dt); s2 = D.std(0) + 1e-6
                Z = np.hstack([Z, D / s2]); Zt = np.hstack([Zt, Dt / s2])
            out = 0
            for m_ in range(3):
                m = MLPRegressor(hidden_layer_sizes=(64, 64), alpha=alpha, max_iter=400, early_stopping=True, validation_fraction=.15, random_state=sd * 100 + m_, n_iter_no_change=20)
                out = out + m.fit(Z, Yc[~te] / 100.).predict(Zt)
            pred[te] = out / 3 * 100.
        ps.append(pred)
    best = None
    for tau in (0., 5., 10., 20.):
        v = np.mean([TB.policy_value(p, Y, tau)[0] for p in ps], 0)
        if best is None or v[core].mean() > best[0]: best = (v[core].mean(), tau, v)
    c, tau, v = best
    print('%-24s core %5.1f all %5.1f tau %g %s (%.0fs)' % (name, c, v.mean(), tau, {o: round(float(v[opp == o].mean()), 1) for o in ('guide', 'lag', 'lead', 'breaker', 'mix')}, time.time() - t0), flush=True)


run('raw+ema only', False, 0)
run('raw+ema + DNpca8', True, 8)
run('raw+ema + DNpca16', True, 16)
