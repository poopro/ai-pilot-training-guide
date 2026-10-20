"""Stage A training: fit the fly brain's read-out (what the descending neurons "mean") from recorded games.

The connectome itself is NOT trained (real wiring, fixed).  What is trained is the thin interface:
  Q_a(DN activity) = V(x) + A_a(x)     (ridge regression, Monte-Carlo returns as targets)
using the games you already collected with jepa_brain (random-ish tactics => unbiased action comparison).

  python replay.py  --data ..\\jepa_brain\\runs\\collect01\\data --out cache --max-games 60 --device cuda
  python train_q.py --cache cache --out readout.npz

Diagnostics are OFFLINE only (held-out games); the arena (fly_eval.py) is the real test.
It also fits the same read-out directly on the 27 features (no brain) as a control: if the fly does not beat
that control, it is only a (very expensive) random feature map.
"""
import argparse, glob, json
from pathlib import Path
import numpy as np
from flybrain.pilot import FlyBrain, Readout, N_ACT


def load(cache):
    games = []
    for f in sorted(glob.glob(str(Path(cache) / 'g*.npz'))):
        z = np.load(f)
        games.append(dict(name=Path(f).stem, dn=z['dn'], acts=z['acts'], G=z['returns'], feats=z['feats']))
    return games


GAMMA_CACHE = 0.95      # jepa_brain/rollout.py GAMMA: the cached 'returns' are discounted with this per decision (3 Hz)


def reshape_returns(G, gamma=GAMMA_CACHE, loss_extra=0.0, death_extra=0.0):
    """Re-derive one game's returns with a different discount and/or an extra terminal penalty.

    jepa_brain already pays -3 for a loss and a kill-score difference on top (about -7..-8 when shot down), but with
    gamma = 0.95 per 0.33 s decision that penalty is only visible for the last ~7 s of a 300 s game: the opening and
    middle-game decisions that caused the loss never feel it.  gamma = 0.99 (horizon ~33 s) or 0.995 (~66 s) and an extra
    penalty spread back over that horizon let the readout learn from them.
    Game outcome is read from the last reward (heuristic): <= -5 shot down / crashed, -5..-2 lost on points.
    """
    G = np.asarray(G, np.float64)
    r = G.copy()
    r[:-1] -= GAMMA_CACHE * G[1:]                     # undo the cached discounting -> per-decision rewards
    last = r[-1]
    if last <= -5.0:
        r[-1] -= death_extra
    elif last <= -2.0:
        r[-1] -= loss_extra
    out = np.zeros_like(r); run = 0.0
    for t in range(len(r) - 1, -1, -1):
        run = r[t] + gamma * run; out[t] = run
    return out.astype(np.float32)


def stack(games, key):
    return np.concatenate([FlyBrain.dn_features(g['dn']) if key == 'dn' else g['feats'] for g in games])


def evaluate(r, X, A, G):
    Q = r._z(X) @ r.W + r.b          # batch form of Readout.q(x)
    pred = Q[np.arange(len(A)), A]
    r2 = 1 - ((G - pred) ** 2).sum() / ((G - G.mean()) ** 2).sum()
    greedy = Q.argmax(1)
    agree = greedy == A
    gain = float(G[agree].mean() - G.mean()) if agree.sum() > 20 else float('nan')
    return dict(r2=float(r2), greedy_agree=float(agree.mean()), n_agree=int(agree.sum()),
                mean_G_when_agree_minus_all=gain, greedy_hist=np.bincount(greedy, minlength=N_ACT).tolist())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default='cache')
    ap.add_argument('--out', default='readout.npz', help='read-out on fly-brain DN activity (what the pilot uses)')
    ap.add_argument('--out-feat', default=None, help='optional: control read-out on the 27 raw features, no brain (closed-loop control arm, fly_bfm.py --feat-readout)')
    ap.add_argument('--holdout-every', type=int, default=4, help='every k-th game is held out (0 = fit on everything)')
    ap.add_argument('--gamma', type=float, default=GAMMA_CACHE, help='discount per decision for the training targets (0.99 = ~33 s horizon)')
    ap.add_argument('--death-extra', type=float, default=0.0, help='extra penalty (positive number) added at the end of games where blue was shot down')
    ap.add_argument('--loss-extra', type=float, default=0.0, help='extra penalty added at the end of games lost on points')
    ap.add_argument('--lam-v', type=float, default=30000.0)
    ap.add_argument('--lam-a', type=float, default=10000.0)
    a = ap.parse_args()
    games = load(a.cache)
    assert games, 'no cached games in ' + a.cache
    for g in games:
        g['G'] = reshape_returns(g['G'], a.gamma, a.loss_extra, a.death_extra)
    hold = [g for i, g in enumerate(games) if a.holdout_every and i % a.holdout_every == a.holdout_every - 1]
    train = [g for g in games if g not in hold]
    print('games: %d train / %d held-out' % (len(train), len(hold)))
    A = np.concatenate([g['acts'] for g in train]); G = np.concatenate([g['G'] for g in train])
    Ah = np.concatenate([g['acts'] for g in hold]) if hold else None
    Gh = np.concatenate([g['G'] for g in hold]) if hold else None
    Aall = np.concatenate([g['acts'] for g in games]); Gall = np.concatenate([g['G'] for g in games])
    out = {}
    meta = dict(gamma=a.gamma, death_extra=a.death_extra, loss_extra=a.loss_extra, games=len(games))
    for key in ('dn', 'feats'):
        X = stack(train, key)
        r = Readout(X.shape[1])
        r.fit(X, A, G, lam_v=a.lam_v, lam_a=a.lam_a)
        out[key] = dict(train=evaluate(r, X, A, G))
        del X
        if hold:
            Xh = stack(hold, key)
            out[key]['heldout'] = evaluate(r, Xh, Ah, Gh)
            del Xh
        path = a.out if key == 'dn' else a.out_feat
        if path:
            Xall = stack(games, key)
            final = Readout(Xall.shape[1])
            final.fit(Xall, Aall, Gall, lam_v=a.lam_v, lam_a=a.lam_a)
            final.meta.update(meta)
            del Xall
            if key == 'dn':
                enc = np.load(Path(a.cache) / 'enc_stats.npz')
                class _E:  # carries the feature standardisation used while the cache was made
                    def state_dict(self): return dict(enc_mu=enc['mu'], enc_sd=enc['sd'])
                final.save(path, _E())
            else:
                final.save(path)
            print('saved', path)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
