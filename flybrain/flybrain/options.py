"""Option tactician trained on counterfactual branch labels (branch_labels.py).

AdvReadout     ridge head: input (DN activity of the fly brain, or the 27 raw features as a control)  ->  predicted advantage
               A_k(x) of "fly tactic k for `hold` decisions, then PURSUE" over plain PURSUE, for k = 1..7, in judge points.
FlyOptionPolicy  drop-in policy for jepa_brain's harness (reset / decide): PURSUE (the proven default) unless the readout
               predicts a gain above `tau` for some tactic, only while the enemy is closer than `zone` metres; a chosen
               tactic is then COMMITTED for `hold` decisions (a 0.33 s decision is too short to do anything - README 6.6/6.8).
"""
import json
import numpy as np
from .pilot import FlyBrain, action_mask, PURSUE, N_ACT

N_OPT = N_ACT - 1


class AdvReadout:
    def __init__(self, n_in=0):
        self.W = np.zeros((n_in, N_OPT), np.float32)
        self.b = np.zeros(N_OPT, np.float32)
        self.mu = np.zeros(n_in, np.float32)
        self.sd = np.ones(n_in, np.float32)
        self.meta = {}
        self.enc_stats = None

    def fit(self, X, Y, lam, min_active=0.01):
        """ridge on standardised inputs, per-output intercept; silent columns (rarely non-minimal) get zero weight"""
        X = np.asarray(X, np.float64); Y = np.asarray(Y, np.float64)
        n, d_all = X.shape
        self.mu = X.mean(0).astype(np.float32)
        self.sd = np.maximum(X.std(0), 1e-3).astype(np.float32)
        act = (X > X.min(0) + 1e-9).mean(0) >= min_active
        cols = np.flatnonzero(act)
        Z = (X[:, cols] - self.mu[cols]) / self.sd[cols]
        yb = Y.mean(0)
        G = Z.T @ Z + lam * np.eye(len(cols))
        Wc = np.linalg.solve(G, Z.T @ (Y - yb))
        W = np.zeros((d_all, N_OPT)); W[cols] = Wc
        self.W, self.b = W.astype(np.float32), yb.astype(np.float32)
        self.meta.update(n=int(n), n_cols=int(len(cols)), lam=float(lam))
        return self

    def predict(self, X):
        X = np.asarray(X, np.float32)
        return ((X - self.mu) / self.sd) @ self.W + self.b

    def save(self, path, **meta):
        self.meta.update(meta)
        extra = {} if self.enc_stats is None else dict(enc_mu=self.enc_stats[0], enc_sd=self.enc_stats[1])
        np.savez(path, W=self.W, b=self.b, mu=self.mu, sd=self.sd, meta=json.dumps(self.meta), **extra)

    @classmethod
    def load(cls, path):
        z = np.load(path)
        r = cls(z['W'].shape[0])
        r.W, r.b, r.mu, r.sd = z['W'], z['b'], z['mu'], z['sd']
        r.meta = json.loads(str(z['meta'])) if 'meta' in z.files else {}
        r.enc_stats = (z['enc_mu'], z['enc_sd']) if 'enc_mu' in z.files else None
        return r


class MLPReadout:
    """small MLP ensemble head (numpy-only inference).  input -> standardise -> [optional PCA] -> (relu, relu) -> 7 advantages.
    Trained with scikit-learn in train_mlp.py; the saved file contains plain arrays only, so the deployed policy needs numpy only."""

    def __init__(self):
        self.mu = self.sd = None
        self.pca_mean = self.pca_comp = self.pca_scale = None
        self.members = []                 # list of [(W, b), ...]
        self.y_scale = 100.0
        self.meta = {}
        self.enc_stats = None

    @classmethod
    def from_sklearn(cls, scaler, pca, pca_scale, models, y_scale=100.0):
        r = cls()
        r.mu, r.sd = scaler.mean_.astype(np.float32), scaler.scale_.astype(np.float32)
        if pca is not None:
            r.pca_mean, r.pca_comp, r.pca_scale = pca.mean_.astype(np.float32), pca.components_.astype(np.float32), np.asarray(pca_scale, np.float32)
        r.members = [[(w.astype(np.float32), b.astype(np.float32)) for w, b in zip(m.coefs_, m.intercepts_)] for m in models]
        r.y_scale = float(y_scale)
        return r

    def predict(self, X):
        Z = (np.asarray(X, np.float32) - self.mu) / self.sd
        if self.pca_comp is not None:
            Z = ((Z - self.pca_mean) @ self.pca_comp.T) / self.pca_scale
        out = 0.0
        for layers in self.members:
            h = Z
            for i, (w, b) in enumerate(layers):
                h = h @ w + b
                if i < len(layers) - 1:
                    h = np.maximum(h, 0.0)
            out = out + h
        return out / len(self.members) * self.y_scale

    def save(self, path, **meta):
        self.meta.update(meta, model='mlp')
        d = dict(mu=self.mu, sd=self.sd, y_scale=np.float32(self.y_scale), n_members=np.int32(len(self.members)),
                 n_layers=np.int32(len(self.members[0])), meta=json.dumps(self.meta))
        if self.pca_comp is not None:
            d.update(pca_mean=self.pca_mean, pca_comp=self.pca_comp, pca_scale=self.pca_scale)
        for i, layers in enumerate(self.members):
            for j, (w, b) in enumerate(layers):
                d['m%d_w%d' % (i, j)], d['m%d_b%d' % (i, j)] = w, b
        if self.enc_stats is not None:
            d.update(enc_mu=self.enc_stats[0], enc_sd=self.enc_stats[1])
        np.savez(path, **d)

    @classmethod
    def load(cls, path):
        z = np.load(path)
        r = cls()
        r.mu, r.sd, r.y_scale = z['mu'], z['sd'], float(z['y_scale'])
        if 'pca_comp' in z.files:
            r.pca_mean, r.pca_comp, r.pca_scale = z['pca_mean'], z['pca_comp'], z['pca_scale']
        nl = int(z['n_layers'])
        r.members = [[(z['m%d_w%d' % (i, j)], z['m%d_b%d' % (i, j)]) for j in range(nl)] for i in range(int(z['n_members']))]
        r.meta = json.loads(str(z['meta']))
        r.enc_stats = (z['enc_mu'], z['enc_sd']) if 'enc_mu' in z.files else None
        return r


class EnsembleReadout:
    """average of the advantage predictions of several raw-feature heads that share the same input (27 features + EMA 0.9).
    path syntax for load_readout:  a.npz+b.npz  (equal weights)  or  a.npz*0.3+b.npz*0.7"""

    def __init__(self, members, weights=None):
        self.members = list(members)
        w = np.ones(len(self.members)) if weights is None else np.asarray(weights, np.float64)
        self.w = (w / w.sum()).astype(np.float32)
        m0 = dict(self.members[0].meta or {})
        emas = {float((r.meta or {}).get('ema', 0.0)) for r in self.members}
        assert len(emas) == 1, 'ensemble members must share the input (same ema): %s' % emas
        m0['tau'] = float(sum(wi * float((r.meta or {}).get('tau', 0.)) for wi, r in zip(self.w, self.members)))
        m0['kind'] = 'feat'; m0['model'] = 'ensemble'
        self.meta = m0
        self.enc_stats = None

    def predict(self, X):
        return sum(wi * r.predict(X) for wi, r in zip(self.w, self.members))


def load_readout(path):
    """AdvReadout (ridge), MLPReadout, or an EnsembleReadout ('a.npz+b.npz' / 'a.npz*w+b.npz*w'), decided by the file"""
    if '+' in str(path):
        parts = [t.partition('*') for t in str(path).split('+')]
        return EnsembleReadout([load_readout(a) for a, _, _ in parts], [float(w) if w else 1.0 for _, _, w in parts])
    z = np.load(path)
    if 'n_members' in z.files:
        return MLPReadout.load(path)
    return AdvReadout.load(path)


class InputBuilder:
    """per-decision input of the readout, identical in training (train_branch.py) and in the policy:
       kind 'dn'  : mean of the last `pool` Anscombe-transformed DN count vectors (1 decision = 80 ms of brain time; pooling
                    averages out the Poisson input noise that dominates single windows)
       kind 'feat': the 27 raw features, plus (if ema > 0) their exponential moving average = a crude memory of the recent past"""

    def __init__(self, kind='dn', pool=1, ema=0.0):
        self.kind, self.pool, self.ema = kind, max(int(pool), 1), float(ema)
        self.reset()

    def reset(self):
        self.buf, self.m = [], None

    def push(self, v):
        v = np.asarray(v, np.float32)
        if self.kind == 'dn':
            self.buf.append(v)
            if len(self.buf) > self.pool:
                self.buf.pop(0)
            return np.mean(self.buf, axis=0) if self.pool > 1 else v
        if self.ema > 0:
            self.m = v.copy() if self.m is None else self.ema * self.m + (1 - self.ema) * v
            return np.concatenate([v, self.m])
        return v


class FlyOptionPolicy:
    name = 'fly_opt'

    def __init__(self, brain, readout, mode='dn', hold=6, zone=3500., tau=0., cooldown=3, runaway=300, only=None):
        self.brain, self.readout, self.mode = brain, readout, mode
        self.hold, self.zone, self.tau, self.cooldown, self.runaway = int(hold), float(zone), float(tau), int(cooldown), int(runaway)
        self.only = None if only is None else set(int(k) for k in only)        # restrict the options (e.g. {1} = LEAD only)
        if brain is not None and getattr(readout, 'enc_stats', None) is not None:
            brain.enc.mu, brain.enc.sd = readout.enc_stats
        m = getattr(readout, 'meta', {}) or {}
        self.inp = InputBuilder('dn' if mode == 'dn' else 'feat', m.get('pool', 1), m.get('ema', 0.0))
        self.n_resets = 0
        self.n_options = 0
        self.log = []

    def reset(self, cfg):
        if self.brain is not None:
            self.brain.reset(cfg.get('seed', 0))
        self.inp.reset()
        self.left, self.cool, self.opt = 0, 0, PURSUE
        self.n_resets = self.n_options = 0
        self.log = []

    def decide(self, feat, ob, arena):
        if self.mode == 'dn':
            dn = self.brain.observe(feat)                         # the brain runs at every decision, whatever we do with it
            if self.runaway and int(dn.sum()) > self.runaway:      # over-excited brain: reset it and fly PURSUE
                self.brain.lif.reset(); self.n_resets += 1
                self.left, self.cool, self.opt = 0, self.cooldown, PURSUE
                return PURSUE
            x = self.inp.push(FlyBrain.dn_features(dn))
        else:
            x = self.inp.push(feat)
        if self.left > 0:
            self.left -= 1
            if self.left == 0:
                self.cool = self.cooldown
            return self.opt
        if self.cool > 0:
            self.cool -= 1
            return PURSUE
        if arena.geo['distance_m'] >= self.zone:
            return PURSUE
        a = self.readout.predict(x[None])[0]
        ok = action_mask(ob[2])[1:]
        if self.only is not None:
            ok = ok & np.array([(k + 1) in self.only for k in range(N_OPT)])
        a = np.where(ok, a, -1e9)
        k = int(a.argmax())
        if a[k] > self.tau:
            self.opt, self.left = k + 1, self.hold - 1
            self.n_options += 1
            if self.left == 0:
                self.cool = self.cooldown
            return self.opt
        return PURSUE


class RandomOptionPolicy:
    """CONTROL (no information): while the enemy is closer than `zone`, with probability `p` per free decision commit a random tactic
    (drawn from `probs`) for `hold` decisions.  Used to ask whether a head's gain is just 'varied behaviour' (dithering)."""
    name = 'random_opt'

    def __init__(self, p=0.15, probs=None, hold=6, zone=3500., cooldown=3, seed=0):
        self.p, self.hold, self.zone, self.cooldown = float(p), int(hold), float(zone), int(cooldown)
        self.probs = dict(probs or {1: .6, 2: .1, 3: .2, 6: .1})
        self.seed = int(seed)
        self.n_options = 0
        self.reset(dict(seed=seed))

    def reset(self, cfg):
        self.rng = np.random.default_rng(1234567 + int(cfg.get('seed', 0)) + self.seed)
        self.left, self.cool, self.opt = 0, 0, PURSUE
        self.n_options = 0

    def decide(self, feat, ob, arena):
        if self.left > 0:
            self.left -= 1
            if self.left == 0:
                self.cool = self.cooldown
            return self.opt
        if self.cool > 0:
            self.cool -= 1
            return PURSUE
        if arena.geo['distance_m'] >= self.zone or self.rng.random() >= self.p:
            return PURSUE
        ok = action_mask(ob[2])
        ks = [k for k in self.probs if ok[k]]
        if not ks:
            return PURSUE
        w = np.array([self.probs[k] for k in ks], float)
        self.opt = int(self.rng.choice(ks, p=w / w.sum()))
        self.left = self.hold - 1
        self.n_options += 1
        if self.left == 0:
            self.cool = self.cooldown
        return self.opt
