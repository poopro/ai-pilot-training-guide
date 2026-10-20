"""Train the MLP option head (raw 27 features + EMA memory -> advantage of each of the 7 tactics) on branch labels.

  python train_mlp.py --labels labels/pilot labels/b1 labels/d1a --out ro/opt_mlp_v2.npz

Reports grouped (by game) cross-validated one-step policy value overall, on the 'core' opponents (guide / lag / lead - the ones that
decide games; mix / breaker / level are saturated) and per opponent type, next to ridge and always-LEAD.  Needs scikit-learn
for training only; the saved file is plain arrays (flybrain/options.py MLPReadout, numpy-only inference).
"""
import argparse, sys, time, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings('ignore')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train_branch as TB
from flybrain.options import AdvReadout, MLPReadout, N_OPT
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

CORE = ('guide', 'lag', 'lead')


def fit_mlp(X, Y, h, alpha, nens, seed0=0, y_scale=100.0):
    sc = StandardScaler().fit(X)
    Z = sc.transform(X)
    ms = []
    for s in range(nens):
        m = MLPRegressor(hidden_layer_sizes=(h, h), alpha=alpha, max_iter=400, early_stopping=True, validation_fraction=.15,
                         random_state=seed0 + s, n_iter_no_change=20)
        ms.append(m.fit(Z, Y / y_scale))
    return MLPReadout.from_sklearn(sc, None, None, ms, y_scale)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', nargs='+', required=True)
    ap.add_argument('--zone', type=float, default=3500.)
    ap.add_argument('--ema', type=float, default=0.9)
    ap.add_argument('--h', type=int, default=64)
    ap.add_argument('--alphas', default='3,10')
    ap.add_argument('--nens', type=int, default=5)
    ap.add_argument('--cv-nens', type=int, default=3)
    ap.add_argument('--folds', type=int, default=5)
    ap.add_argument('--seeds', type=int, default=2)
    ap.add_argument('--taus', default='0,5,10,20')
    ap.add_argument('--core', default='guide,lag,lead,sac:25600000', help='opponent types the model selection looks at (macro average per type)')
    ap.add_argument('--micro', action='store_true')
    ap.add_argument('--clip', type=float, default=300.)
    ap.add_argument('--hold', type=int, default=6)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    games = TB.load_games(a.labels, a.zone)
    X, Y, grp, opp = TB.build(games, 'feat', a.zone, ema=a.ema)
    Yc = np.clip(Y, -a.clip, a.clip)
    core_list = a.core.split(',')
    core = np.isin(opp, core_list)
    opps = sorted(set(opp))
    taus = [float(t) for t in a.taus.split(',')]
    print('%d games, %d near states (%d core), opponents %s' % (len(games), len(Y), core.sum(), {o: int((opp == o).sum()) for o in opps}), flush=True)

    def cv(kind, alpha=None):
        ps = []
        for sd in range(a.seeds):
            pred = np.zeros_like(Yc)
            ug = np.unique(grp); rng = np.random.default_rng(sd); rng.shuffle(ug)
            for i in range(a.folds):
                te = np.isin(grp, ug[i::a.folds])
                if kind == 'ridge':
                    pred[te] = AdvReadout().fit(X[~te], Yc[~te], 1000.).predict(X[te])
                else:
                    pred[te] = fit_mlp(X[~te], Yc[~te], a.h, alpha, a.cv_nens, seed0=sd * 100).predict(X[te])
            ps.append(pred)
        best = None
        for tau in taus:
            v = np.mean([TB.policy_value(p, Y, tau)[0] for p in ps], 0)
            c = TB.core_val(v, opp, core_list, not a.micro)
            if best is None or c > best[0]:
                best = (c, tau, v)
        return best

    print('always LEAD: core %.1f  all %.1f  %s' % (TB.core_val(Y[:, 0], opp, core_list, not a.micro), Y[:, 0].mean(), {o: round(float(Y[opp == o, 0].mean()), 1) for o in opps}))
    results = {}
    for name, (kind, alpha) in {'ridge': ('ridge', None), **{'mlp a%g' % float(al): ('mlp', float(al)) for al in a.alphas.split(',')}}.items():
        t0 = time.time()
        c, tau, v = cv(kind, alpha)
        results[name] = (c, tau, alpha, v)
        print('%-9s core %5.1f  all %5.1f  tau %g  %s  (%.0fs)' % (name, c, v.mean(), tau, {o: round(float(v[opp == o].mean()), 1) for o in opps}, time.time() - t0), flush=True)
    best_name = max((k for k in results if k != 'ridge'), key=lambda k: results[k][0])
    c, tau, alpha, _ = results[best_name]
    print('chosen:', best_name, 'tau', tau)
    if a.out:
        r = fit_mlp(X, Yc, a.h, alpha, a.nens, seed0=1000)
        r.save(a.out, kind='feat', ema=a.ema, hold=a.hold, zone=a.zone, tau=tau, clip=a.clip, games=len(games), states=int(len(X)), h=a.h, alpha=alpha, nens=a.nens)
        print('saved', a.out)


if __name__ == '__main__':
    main()
