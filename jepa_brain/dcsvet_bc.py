"""DCSVET behaviour cloning: numpy MLP (no torch needed at runtime or training).

  python dcsvet_bc.py train DATA.npz OUT_weights.npz [epochs]
Model: features(24) -> 256 -> 256 -> 3 (n_up, n_side, dcas_kt), tanh, Huber loss, Adam.
Validation split is by fight (both perspectives of a fight stay together).
"""
import sys, json, math
import numpy as np
import dcsvet_core as C


class MLP:
    def __init__(self, sizes, rng):
        self.W = [rng.normal(0, math.sqrt(1. / a), (a, b)) for a, b in zip(sizes[:-1], sizes[1:])]
        self.b = [np.zeros(b) for b in sizes[1:]]

    def forward(self, x, keep=False):
        hs = [x]
        h = x
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            h = h @ W + b
            if i < len(self.W) - 1:
                h = np.tanh(h)
            hs.append(h)
        return (h, hs) if keep else h

    def grads(self, hs, dy):
        gW, gb = [None] * len(self.W), [None] * len(self.W)
        d = dy
        for i in range(len(self.W) - 1, -1, -1):
            gW[i] = hs[i].T @ d
            gb[i] = d.sum(0)
            if i > 0:
                d = (d @ self.W[i].T) * (1 - hs[i] ** 2)
        return gW, gb


def huber_grad(e, k=1.):
    return np.where(np.abs(e) < k, e, k * np.sign(e))


# feature indices that flip sign under left/right reflection (see dcsvet_core.features)
MIRROR_X = (4, 7, 8, 9, 18)
MIRROR_Y = (1,)


def mirror_xy(X, Y):
    X, Y = X.copy(), Y.copy()
    X[:, MIRROR_X] *= -1
    Y[:, MIRROR_Y] *= -1
    return X, Y


def train(data, out, epochs=40, seed=0, hidden=256, lr=1e-3, bs=512, mirror=True):
    d = np.load(data, allow_pickle=True)
    X, Y, fid = d['X'].astype(np.float32), d['Y'].astype(np.float32), d['fid']
    rows = json.loads(str(d['rows']))
    fight_of = {r['fid']: (r['rec'], r['seed'], r['idx']) for r in rows}
    fights = sorted(set(fight_of.values()))
    rng = np.random.default_rng(seed)
    rng.shuffle(fights)
    nval = max(1, len(fights) // 5)
    valf = set(fights[:nval])
    fid_val = np.array([fight_of[k] in valf for k in range(len(rows))]) if all(r['fid'] == i for i, r in enumerate(rows)) else None
    isval = fid_val[fid] if fid_val is not None else np.array([fight_of[int(f)] in valf for f in fid])
    # normalisation from train split (mirror leaves std unchanged; mirrored dims get zero mean)
    xm, xs = X[~isval].mean(0), X[~isval].std(0) + 1e-6
    ym, ys = Y[~isval].mean(0), Y[~isval].std(0) + 1e-6
    xm[list(MIRROR_X)] = 0.; ym[list(MIRROR_Y)] = 0.
    Xv, Yv = (X[isval] - xm) / xs, (Y[isval] - ym) / ys
    Xt, Yt = (X[~isval] - xm) / xs, (Y[~isval] - ym) / ys
    if mirror:   # left/right reflection about the vertical plane through the velocity: doubles data, enforces symmetry
        Xm, Ym = mirror_xy(X[~isval], Y[~isval])
        Xt = np.concatenate([Xt, (Xm - xm) / xs]); Yt = np.concatenate([Yt, (Ym - ym) / ys])
        del Xm, Ym
    del X, Y
    net = MLP([Xt.shape[1], hidden, hidden, Yt.shape[1]], rng)
    params = net.W + net.b
    m1 = [np.zeros_like(p) for p in params]
    m2 = [np.zeros_like(p) for p in params]
    step = 0
    best = (1e9, None)
    for ep in range(epochs):
        perm = rng.permutation(len(Xt))
        for i in range(0, len(perm), bs):
            j = perm[i:i + bs]
            yp, hs = net.forward(Xt[j], keep=True)
            dy = huber_grad(yp - Yt[j]) / len(j)
            gW, gb = net.grads(hs, dy)
            grads = gW + gb
            step += 1
            a = lr * (.5 * (1 + math.cos(math.pi * ep / epochs)) + .02)
            for k, (p, g) in enumerate(zip(params, grads)):
                m1[k] = .9 * m1[k] + .1 * g
                m2[k] = .999 * m2[k] + .001 * g * g
                p -= a * (m1[k] / (1 - .9 ** step)) / (np.sqrt(m2[k] / (1 - .999 ** step)) + 1e-8)
        yv = net.forward(Xv) if len(Xv) else np.zeros((0, Yt.shape[1]))
        r2 = 1 - ((yv - Yv) ** 2).mean(0) / Yv.var(0) if len(Xv) else np.zeros(3)
        vloss = float(np.abs(yv - Yv).mean()) if len(Xv) else 0.
        if vloss < best[0]:
            best = (vloss, [w.copy() for w in net.W], [b.copy() for b in net.b], r2)
        if ep % 5 == 0 or ep == epochs - 1:
            print('ep %d val_mae(norm) %.3f R2 n_up %.3f n_side %.3f dcas %.3f' % (ep, vloss, *r2), flush=True)
    _, W, b, r2 = best
    # report in physical units
    net.W, net.b = W, b
    yv = net.forward(Xv) * ys + ym
    Yp = Yv * ys + ym
    mu_p = np.degrees(np.arctan2(yv[:, 1], yv[:, 0])); mu_t = np.degrees(np.arctan2(Yp[:, 1], Yp[:, 0]))
    loaded = np.hypot(Yp[:, 0], Yp[:, 1]) > 2.
    rep = dict(n_train=int((~isval).sum()), n_val=int(isval.sum()), fights=len(fights), val_fights=nval,
               r2=[float(x) for x in r2],
               mae_n_up=float(np.abs(yv[:, 0] - Yp[:, 0]).mean()), mae_n_side=float(np.abs(yv[:, 1] - Yp[:, 1]).mean()),
               mae_dcas_kt=float(np.abs(yv[:, 2] - Yp[:, 2]).mean()),
               mu_err_med_deg_loaded=float(np.median(np.abs(C.wrap180(mu_p - mu_t))[loaded])) if loaded.any() else None)
    np.savez(out, *W, *b, nlayers=len(W), xm=xm, xs=xs, ym=ym, ys=ys, report=json.dumps(rep))
    print(json.dumps(rep, indent=1))
    return rep


class DcsVetPolicy:
    """features -> (mu_deg, n_g, dcas_kt)."""
    def __init__(self, path):
        z = np.load(path, allow_pickle=True)
        n = int(z['nlayers'])
        self.W = [z['arr_%d' % i] for i in range(n)]
        self.b = [z['arr_%d' % (n + i)] for i in range(n)]
        self.xm, self.xs, self.ym, self.ys = z['xm'], z['xs'], z['ym'], z['ys']

    def predict(self, feat):
        h = (np.asarray(feat, np.float64) - self.xm) / self.xs
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            h = h @ W + b
            if i < len(self.W) - 1:
                h = np.tanh(h)
        y = h * self.ys + self.ym
        mu, n = C.lift_to_cmd(y[0], y[1])
        return mu, n, float(y[2])


if __name__ == '__main__':
    if sys.argv[1] == 'train':
        train(sys.argv[2], sys.argv[3], epochs=int(sys.argv[4]) if len(sys.argv) > 4 else 40)
