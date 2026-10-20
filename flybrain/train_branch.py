"""Train the option tactician on counterfactual labels (branch_labels.py) and evaluate it OFFLINE without playing a game.

Because every label file contains the counterfactual advantage of ALL seven tactics at each labelled state, a decision rule can be
scored exactly (one step): value(rule) = mean over held-out states of A[chosen option]  (0 when it keeps PURSUE).
Cross-validation is grouped by game.  Compared: the fly (DN activity of the pruned brain), the raw 27 features (control),
'always LEAD', and the hindsight oracle.

  python train_branch.py --labels labels/b1 labels/pilot --cache cache480 --out ro/opt_b1.npz
"""
import argparse, glob, json, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from flybrain.options import AdvReadout, InputBuilder, N_OPT


def load_games(dirs, zone):
    games = []
    for d in dirs:
        for f in sorted(glob.glob(str(Path(d) / 'g*.npz'))):
            z = np.load(f)
            if len(z['lab_dec']) == 0:
                continue
            V = z['lab_delta'] + z['lab_term']
            games.append(dict(name=Path(f).stem, opp=Path(f).stem.split('_', 1)[1].replace('sac-', 'sac:'), seed=int(Path(f).stem[1:].split('_')[0]),
                              feats=z['feats'], dec=z['lab_dec'], rng=z['lab_range'], A=(V - V[:, [0]])[:, 1:1 + N_OPT]))
    return games


def replay_dn(games, cache_dir, backend):
    """open-loop brain replay of each game's decision features (what the brain sees in closed loop when PURSUE is flown)"""
    from flybrain.pilot import load_brain
    brain = load_brain(cache_dir, backend)
    for g in games:
        t0 = time.time()
        brain.reset(g['seed'])
        g['dn'] = np.asarray([brain.observe(f) for f in g['feats']], np.int16)
        print('  replayed %s (%d decisions, %.1fs)' % (g['name'], len(g['feats']), time.time() - t0), flush=True)
    return brain


def build(games, kind, zone, near_only=True, pool=1, ema=0.0):
    from flybrain.pilot import FlyBrain
    X, Y, grp, opp = [], [], [], []
    for gi, g in enumerate(games):
        m = g['rng'] < zone if near_only else np.ones(len(g['dec']), bool)
        idx = g['dec'][m]
        ib = InputBuilder(kind, pool, ema)
        src = FlyBrain.dn_features(g['dn']) if kind == 'dn' else g['feats']
        allx = np.asarray([ib.push(v) for v in src], np.float32)
        X.append(allx[idx])
        Y.append(g['A'][m]); grp += [gi] * int(m.sum()); opp += [g['opp']] * int(m.sum())
    return np.concatenate(X), np.concatenate(Y), np.array(grp), np.array(opp)


def core_val(v, opp, core_list, macro=True):
    """value on the opponents that decide games.  macro = every opponent type counts equally (SAC has few labelled states but is the weak spot)"""
    ms = [v[opp == o] for o in core_list if (opp == o).any()]
    if not ms:
        return float('nan')
    return float(np.mean([x.mean() for x in ms])) if macro else float(np.concatenate(ms).mean())


def policy_value(pred, Y, tau):
    k = pred.argmax(1)
    take = pred[np.arange(len(pred)), k] > tau
    return np.where(take, Y[np.arange(len(Y)), k], 0.0), take, k


def folds(grp, n_folds, seed=0):
    ug = np.unique(grp)
    rng = np.random.default_rng(seed)
    rng.shuffle(ug)
    return [ug[i::n_folds] for i in range(n_folds)]


def cv_predict(X, Yc, grp, lam, n_folds):
    pred = np.zeros_like(Yc)
    for test_groups in folds(grp, min(n_folds, len(np.unique(grp)))):
        te = np.isin(grp, test_groups)
        pred[te] = AdvReadout().fit(X[~te], Yc[~te], lam).predict(X[te])
    return pred


def boot_ci(vals, grp, n=2000, seed=0):
    """95% bootstrap interval of the mean over games (resampling whole games)"""
    ug = np.unique(grp)
    per = np.array([vals[grp == g].mean() for g in ug])
    rng = np.random.default_rng(seed)
    m = np.array([per[rng.integers(0, len(per), len(per))].mean() for _ in range(n)])
    return per.mean(), np.percentile(m, 2.5), np.percentile(m, 97.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', nargs='+', required=True)
    ap.add_argument('--cache', required=True, help='dir with enc_stats.npz and the games that define the pruned brain (cache480)')
    ap.add_argument('--backend', default='numba')
    ap.add_argument('--zone', type=float, default=3500.)
    ap.add_argument('--clip', type=float, default=300., help='labels are clipped to +-clip points (kills; collisions are huge)')
    ap.add_argument('--lams', default='300,3000,30000')
    ap.add_argument('--taus', default='0,3,6,10,15')
    ap.add_argument('--folds', type=int, default=5)
    ap.add_argument('--hold', type=int, default=6)
    ap.add_argument('--pool', default='1,3,6,12', help='DN pooling lengths to compare (decisions)')
    ap.add_argument('--ema', default='0,0.9,0.97', help='EMA coefficients to compare for the raw-feature control')
    ap.add_argument('--out', default=None, help='save the final DN readout (and <out>.feat.npz for the raw-feature control)')
    ap.add_argument('--core', default='guide,lag,lead,sac:25600000', help='opponent types the model selection looks at (macro average over types)')
    ap.add_argument('--micro', action='store_true', help='pool the core states instead of averaging per opponent type')
    ap.add_argument('--select', default='core', help='core = pick lam / tau / variant by the value on guide+lag+lead states; all = on every state')
    a = ap.parse_args()

    games = load_games(a.labels, a.zone)
    print('%d games, %d labelled states (%d near)' % (len(games), sum(len(g['dec']) for g in games), sum(int((g['rng'] < a.zone).sum()) for g in games)))
    brain = replay_dn(games, a.cache, a.backend)
    lams = [float(x) for x in a.lams.split(',')]
    taus = [float(x) for x in a.taus.split(',')]
    best = {}
    for kind, variants in (('dn', [dict(pool=int(x)) for x in a.pool.split(',')]), ('feat', [dict(ema=float(x)) for x in a.ema.split(',')])):
        for var in variants:
            X, Y, grp, opp = build(games, kind, a.zone, **var)
            Yc = np.clip(Y, -a.clip, a.clip)
            if 'ref' not in best:
                print('\nreference over %d near states: oracle (hindsight) %.1f | always LEAD %.1f | always PURSUE 0.0   [mean true advantage per state, judge points / 15 s]' % (
                    len(X), np.maximum(Y.max(1), 0).mean(), Y[:, 0].mean()))
                best['ref'] = True
            top = None
            core = np.isin(opp, a.core.split(','))       # the opponents that decide games; mix / breaker / level are saturated
            for lam in lams:
                pred = cv_predict(X, Yc, grp, lam, a.folds)
                for tau in taus:
                    v, take, k = policy_value(pred, Y, tau)
                    crit = core_val(v, opp, a.core.split(','), not a.micro) if a.select == 'core' and core.any() else v.mean()
                    if top is None or crit > top[0]:
                        top = (crit, lam, tau, take.mean(), v, grp.copy(), np.mean([np.corrcoef(pred[:, j], Yc[:, j])[0, 1] for j in range(N_OPT)]), core_val(v, opp, a.core.split(','), not a.micro))
            mean, lo, hi = boot_ci(top[4], top[5])
            print('%-5s %-12s -> cv value %6.1f  [95%% CI over games %5.1f .. %5.1f]  core(%s) %5.1f  (lam %g, tau %g, takes an option in %.0f%% of near states, corr %.2f)' % (
                kind, ','.join('%s=%g' % kv for kv in var.items()), mean, lo, hi, a.core, top[7], top[1], top[2], 100 * top[3], top[6]))
            if kind not in best or top[0] > best[kind][-1]:
                best[kind] = (mean, top[1], top[2], var, top[0])
    ll = Y[:, 0]
    m, lo, hi = boot_ci(ll, grp)
    print('always LEAD (same states): %.1f [%.1f .. %.1f]' % (m, lo, hi))
    print('\nbest per input type:', {k: dict(value=round(float(v[0]), 1), lam=v[1], tau=v[2], **v[3]) for k, v in best.items() if k != 'ref'})
    if a.out:
        for kind, out in (('dn', a.out), ('feat', str(Path(a.out).with_suffix('')) + '.feat.npz')):
            mean, lam, tau, var, _ = best[kind]
            X, Y, grp, opp = build(games, kind, a.zone, **var)
            r = AdvReadout().fit(X, np.clip(Y, -a.clip, a.clip), lam)
            if kind == 'dn':
                r.enc_stats = (brain.enc.mu, brain.enc.sd)
            r.save(out, kind=kind, hold=a.hold, zone=a.zone, tau=tau, clip=a.clip, games=len(games), states=int(len(X)), **var)
            print('saved', out, 'lam', lam, 'tau', tau, var)


if __name__ == '__main__':
    main()
