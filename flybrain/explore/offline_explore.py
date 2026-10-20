"""Offline exploration on the branch labels: which readout inputs / heads give the best one-step policy value?
python explore/offline_explore.py --labels labels/pilot labels/b1 [labels/d1a ...] --cache cache480
"""
import argparse, sys, time, json
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import train_branch as TB
from flybrain.options import AdvReadout, InputBuilder, N_OPT
from flybrain.pilot import FlyBrain


def replay_multi(games, cache, k_seeds, backend='numba'):
    from flybrain.prune import keep_from_cache
    brain = FlyBrain(device='cpu', dt_ms=1.0, window_ms=80.0)
    st = np.load(Path(cache) / 'enc_stats.npz'); brain.enc.mu, brain.enc.sd = st['mu'], st['sd']
    brain.prune(keep_from_cache(cache)[0], backend=backend)
    for g in games:
        outs = []
        for s in range(k_seeds):
            brain.reset(g['seed'] + 1000 * s)
            outs.append(np.asarray([brain.observe(f) for f in g['feats']], np.int16))
        g['dn_all'] = outs
        g['dn'] = outs[0]
    return brain


def feat_inputs(games, zone, ema):
    X, Y, grp, opp = TB.build(games, 'feat', zone, ema=ema)
    return X, Y, grp, opp


def dn_inputs(games, zone, pool, k=1):
    # average the DN vectors of k independent brain noise seeds (offline test whether input noise is the limiter)
    Xs = []
    for s in range(k):
        for g in games:
            g['dn'] = g['dn_all'][s]
        X, Y, grp, opp = TB.build(games, 'dn', zone, pool=pool)
        Xs.append(X)
    for g in games:
        g['dn'] = g['dn_all'][0]
    return np.mean(Xs, 0), Y, grp, opp


def cv_pred(X, Yc, grp, lam, nf, seed):
    pred = np.zeros_like(Yc)
    ug = np.unique(grp); rng = np.random.default_rng(seed); rng.shuffle(ug)
    for i in range(min(nf, len(ug))):
        te = np.isin(grp, ug[i::nf])
        pred[te] = AdvReadout().fit(X[~te], Yc[~te], lam).predict(X[te])
    return pred


def value(pred, Y, tau):
    v, take, k = TB.policy_value(pred, Y, tau)
    return v


def per_game(v, grp):
    return np.array([v[grp == g].mean() for g in np.unique(grp)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', nargs='+', required=True)
    ap.add_argument('--cache', default='cache480')
    ap.add_argument('--zone', type=float, default=3500.)
    ap.add_argument('--seeds', type=int, default=3, help='CV repeats')
    ap.add_argument('--k', type=int, default=3, help='brain noise seeds for the ensemble test')
    a = ap.parse_args()
    games = TB.load_games(a.labels, a.zone)
    print(len(games), 'games', flush=True)
    t0 = time.time(); replay_multi(games, a.cache, a.k); print('replayed %.0fs' % (time.time() - t0), flush=True)
    clip = 300.
    sets = {}
    sets['dn_p1'] = dn_inputs(games, a.zone, 1)
    sets['dn_p3'] = dn_inputs(games, a.zone, 3)
    sets['dn_p1_ens%d' % a.k] = dn_inputs(games, a.zone, 1, a.k)
    sets['dn_p3_ens%d' % a.k] = dn_inputs(games, a.zone, 3, a.k)
    for e in (0.0, 0.9, 0.97):
        sets['feat_e%g' % e] = feat_inputs(games, a.zone, e)
    Y = sets['feat_e0'][1]; grp = sets['feat_e0'][2]; opp = sets['feat_e0'][3]
    Yc = np.clip(Y, -clip, clip)
    # hybrids
    sets['hyb_p1_e0.9'] = (np.hstack([sets['dn_p1'][0], sets['feat_e0.9'][0]]), Y, grp, opp)
    sets['hyb_ens_e0.9'] = (np.hstack([sets['dn_p1_ens%d' % a.k][0], sets['feat_e0.9'][0]]), Y, grp, opp)
    res = {}
    preds = {}
    for name, (X, _, _, _) in sets.items():
        best = None
        for lam in (100., 300., 1000., 3000., 10000.):
            ps = [cv_pred(X, Yc, grp, lam, 5, s) for s in range(a.seeds)]
            for tau in (0., 5., 10., 15.):
                vs = [value(p, Y, tau) for p in ps]
                m = np.mean([v.mean() for v in vs])
                if best is None or m > best[0]:
                    best = (m, lam, tau, ps, vs)
        m, lam, tau, ps, vs = best
        pg = np.mean([per_game(v, grp) for v in vs], 0)
        res[name] = (m, lam, tau, pg)
        preds[name] = (ps, lam, tau)
        print('%-16s value %6.1f  (lam %g tau %g) n_in %d' % (name, m, lam, tau, X.shape[1]), flush=True)
    # ensembles of predictions
    for a_, b_ in (('dn_p1', 'feat_e0.9'), ('dn_p3_ens%d' % a.k, 'feat_e0.9')):
        ps = [(p + q) / 2 for p, q in zip(preds[a_][0], preds[b_][0])]
        for tau in (0., 5., 10.):
            vs = [value(p, Y, tau) for p in ps]
            print('avg(%s,%s) tau %g value %.1f' % (a_, b_, tau, np.mean([v.mean() for v in vs])), flush=True)
    # paired differences against feat_e0.9 and dn_p1
    rng = np.random.default_rng(0)
    for ref in ('feat_e0.9', 'dn_p1'):
        for name, (m, lam, tau, pg) in res.items():
            d = pg - res[ref][3]
            bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
            print('  %-16s - %-9s = %+6.1f  [%+.1f, %+.1f]' % (name, ref, d.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)))
    # per opponent value of the two main variants at their best params
    for name in ('dn_p1', 'feat_e0.9'):
        ps, lam, tau = preds[name]
        v = np.mean([value(p, Y, tau) for p in ps], 0)
        print(name, {o: round(float(v[opp == o].mean()), 1) for o in sorted(set(opp))})
    print('always LEAD per opp', {o: round(float(Y[opp == o, 0].mean()), 1) for o in sorted(set(opp))})


if __name__ == '__main__':
    main()
