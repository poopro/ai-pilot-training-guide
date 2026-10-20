"""Fly-brain pilot: competition-legal features -> Poisson drive on sensory neurons -> whole-brain LIF ->
descending-neuron (DN) activity -> tactic.

Rule adaptation (AI 飛行員擂台賽, 2026/09/03 公告)
  * Input  : only the 20 own-ship + 6 target values the Host sends every frame (via jepa_brain.feats.features,
             which already uses nothing else) -> 27 numbers, each turned into a PUSH-PULL pair of sensory pools:
             value above its mean drives right-side neurons, below its mean drives left-side neurons
             (a fly's two antennae / two eyes work the same way).
  * Output : the fly never touches the 4 UDP controls (aileron, elevator, rudder, throttle). It only picks one of
             the 8 tactics every 20 ticks (3 Hz); the frozen 60 Hz controller (rate limits, 9 G guard, ground
             recovery) still produces every command.  So the legal packet format / 60 Hz / local-only rules are
             unchanged by construction.
"""
import numpy as np
import torch
from .connectome import Connectome
from .lif import FlyLIF
from .prune import SubConn

N_ACT = 8
TACTICS = ['pursue', 'lead', 'lag', 'break_in', 'break_out', 'high_yoyo', 'low_yoyo', 'extend']
PURSUE, LEAD, LAG, BREAK_IN, BREAK_OUT, HIGH_YOYO, LOW_YOYO, EXTEND = range(8)

# feature index groups of jepa_brain/feats.py (FEAT_DIM = 27)
ENEMY_FEATS = [0, 1, 2, 3, 4, 5, 6, 16, 17]                      # distance, closing, angles, aspect, enemy alt/speed
OWN_FEATS = [7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21]    # attitude, alpha/beta, G, speed, altitude, vdown, p q r
STATE_FEATS = [22, 23, 24, 25, 26]                               # attack counter, clock, in-envelope flags


class Encoder:
    """feature vector -> (neuron indices, Poisson rates in Hz)"""

    def __init__(self, conn, feat_dim=27, k=20, r_max=100.0, seed=0, extra_groups=()):
        rng = np.random.default_rng(seed)
        feat_dim_base = feat_dim
        feat_dim = feat_dim_base + len(extra_groups)
        A = conn.ann
        side = A['side'].to_numpy()
        infl = conn.influence()
        ct, sc, ss, cc = A['cell_type'], A['super_class'], A['cell_sub_class'], A['cell_class']
        # Which sensory neurons stand in for which kind of feature (our design choice, not biology):
        #  own-ship dynamics   -> Johnston's-organ wind/gravity neurons + head bristles   (a fly's attitude/airspeed sensors)
        #  enemy geometry      -> visual projection neurons LC / LPLC / LLPC / LPC        (looming + target-tracking cells)
        #  mission-state flags -> gustatory neurons
        # Olfactory / hygro- / thermosensory neurons are NOT used: driving just 10 of them ignites a ~10,000-neuron
        # avalanche (seizure-like) that carries no information (see README, 'probe_classes').
        pools = {
            'own': np.flatnonzero((ss == 'wind_gravity') | (ss == 'head bristle')),
            'enemy': np.flatnonzero((sc == 'visual_projection') & ct.str.startswith(('LC', 'LPLC', 'LLPC', 'LPC'))),
            'state': np.flatnonzero(cc == 'gustatory'),
        }
        # keep the better-connected (towards the DNs) 70 % of every pool
        for g in pools:
            p_ = pools[g]
            pools[g] = p_[infl[p_] >= np.quantile(infl[p_], 0.30)]
        taken = set()
        self.idx = np.zeros((feat_dim, 2, k), dtype=np.int64)       # [feature, (+,-), k]
        self.gain = np.zeros((feat_dim, 2, k), dtype=np.float32)
        for f in range(feat_dim):
            if f < feat_dim_base:
                grp = 'own' if f in OWN_FEATS else 'enemy' if f in ENEMY_FEATS else 'state'
            else:                                              # extra (slow / adapted) channels: group given by the caller
                grp = extra_groups[f - feat_dim_base]
            for s, sd in enumerate(('right', 'left')):
                cand = [i for i in pools[grp] if side[i] == sd and i not in taken]
                pick = rng.choice(cand, size=k, replace=False)
                taken.update(int(i) for i in pick)
                self.idx[f, s] = pick
                self.gain[f, s] = rng.uniform(0.6, 1.0, size=k)
        self.k, self.r_max = k, float(r_max)
        self.mu = np.zeros(feat_dim, np.float32)
        self.sd = np.ones(feat_dim, np.float32)
        self.flat_idx = self.idx.reshape(-1)

    def fit_stats(self, feats):
        F = np.concatenate(feats, 0)
        self.mu = F.mean(0).astype(np.float32)
        self.sd = np.maximum(F.std(0), 0.1).astype(np.float32)

    def rates(self, feat):
        z = np.clip((np.asarray(feat, np.float32) - self.mu) / self.sd / 2.5, -1.0, 1.0)
        r = np.stack([np.maximum(z, 0.0), np.maximum(-z, 0.0)], 1)[:, :, None] * self.gain * self.r_max
        return self.flat_idx, r.reshape(-1)

    def state_dict(self):
        return dict(enc_mu=self.mu, enc_sd=self.sd)


class FlyBrain:
    """Whole-brain simulator + encoder.  One call to observe() = one tactical decision (every 20 ticks)."""

    def __init__(self, conn=None, device='cpu', dt_ms=1.0, window_ms=80.0, seed=0, k=20, r_max=100.0, w_syn_mv=0.275,
                 ema_feats=(), ema=0.9):
        self.conn = conn or Connectome()
        self._lif_kw = dict(dt_ms=dt_ms, device=device, seed=seed, w_syn_mv=w_syn_mv)
        self.lif = FlyLIF(self.conn, **self._lif_kw)
        self.keep = self.remap = None                    # set by prune()
        self.backend = 'torch'
        # ema_feats: indices of raw features that also get a SLOW channel (exponential moving average over decisions, like a
        # sensory neuron's adaptation).  They are extra sensory pools appended after the 27 original ones.
        self.ema_feats = np.asarray(ema_feats, np.int64)
        self.ema = float(ema)
        self._m = None
        groups = tuple('own' if f in OWN_FEATS else 'enemy' if f in ENEMY_FEATS else 'state' for f in self.ema_feats)
        self.enc = Encoder(self.conn, k=k, r_max=r_max, seed=seed, extra_groups=groups)
        self.steps = int(round(window_ms / dt_ms))
        self.window_s = self.steps * dt_ms * 1e-3
        self.dn = self.conn.select(super_class='descending')
        self.dn_local = self.dn
        self.seed = seed

    def use_numba(self):
        """Full 138,639-neuron network on the numba engine (~6x faster than torch on CPU; needs `pip install numba`)."""
        from .lif_fast import FastLIF
        self.lif = FastLIF(self.conn, **self._lif_kw)
        self.lif.gen.manual_seed(int(self.seed))
        self.backend = 'numba'

    def prune(self, keep, backend='auto'):
        """Simulate only the neurons in `keep` (original indices).  All inputs and all descending neurons are always kept,
        so observe() still returns the same 1,299 DN counts.  See flybrain/prune.py for the trade-off."""
        keep = np.union1d(np.asarray(keep, np.int64), np.union1d(self.enc.flat_idx, self.dn))
        sub = SubConn(self.conn, keep)
        self.keep, self.remap = sub.keep, sub.remap
        self.dn_local = sub.remap[self.dn].astype(np.int64)
        if backend == 'auto':
            try:
                import numba  # noqa: F401
                backend = 'numba'
            except ImportError:
                backend = 'torch'
        if backend == 'numba':
            from .lif_fast import FastLIF            # ~20x faster than torch on a few-thousand-neuron network
            self.lif = FastLIF(sub, **self._lif_kw)
        else:
            self.lif = FlyLIF(sub, **self._lif_kw)
        self.backend = backend
        self.lif.gen.manual_seed(int(self.seed))
        return sub

    def reset(self, seed=None):
        self._m = None
        self.lif.reset()
        self.lif.gen.manual_seed(int(self.seed if seed is None else seed))

    def observe(self, feat, full=False, steps=None):
        """Run one window (`steps` time steps, default = window_ms).  Returns DN spike counts [n_dn]
        (and, if full, the sparse (idx, count) of all spikers, in ORIGINAL neuron indices)."""
        feat = np.asarray(feat, np.float32)
        if len(self.ema_feats):
            self._m = feat.copy() if self._m is None else self.ema * self._m + (1 - self.ema) * feat
            feat = np.concatenate([feat, self._m[self.ema_feats]])
        idx, rate = self.enc.rates(feat)
        if self.remap is not None:
            idx = self.remap[idx]
        counts = self.lif.run(self.steps if steps is None else int(steps), idx, rate)
        c = counts.cpu().numpy() if hasattr(counts, 'cpu') else counts
        dn = c[self.dn_local]
        if full:
            nz = np.flatnonzero(c)
            orig = nz if self.keep is None else self.keep[nz]
            return dn, (orig.astype(np.int32), c[nz].astype(np.int16))
        return dn

    @staticmethod
    def dn_features(dn_counts):
        return np.sqrt(np.asarray(dn_counts, np.float32) + 0.375)    # Anscombe variance stabilisation


class Readout:
    """Linear Q-head on DN activity:  Q_a(x) = V(x) + A_a(x)  (ridge, standardised inputs)."""

    def __init__(self, n_in, n_act=N_ACT):
        self.W = np.zeros((n_in, n_act), np.float32)
        self.b = np.zeros(n_act, np.float32)
        self.mu = np.zeros(n_in, np.float32)
        self.sd = np.ones(n_in, np.float32)
        self.meta = {}

    def _z(self, X):
        return (np.asarray(X, np.float32) - self.mu) / self.sd

    def q(self, x):
        return self._z(x) @ self.W + self.b

    def fit(self, X, A, G, lam_v=30.0, lam_a=300.0, min_n=25, min_active=0.005, chunk=20000):
        """Ridge fit via accumulated Gram matrices (memory ~ d^2, so 400k decisions x 1,299 DNs is fine).
        Columns that are non-baseline in fewer than `min_active` of the rows (silent DNs) get zero weight."""
        X = np.asarray(X, np.float32); A = np.asarray(A); G = np.asarray(G, np.float64)
        n, d_all = X.shape
        self.mu = X.mean(0)
        self.sd = np.maximum(X.std(0), 1e-3)
        act = (X > X.min(0)).mean(0) >= min_active
        cols = np.flatnonzero(act)
        d = len(cols)
        mu, sd = self.mu[cols], self.sd[cols]

        def Z(rows):
            return ((X[rows][:, cols] - mu) / sd).astype(np.float64)

        starts = list(range(0, n, chunk))
        gram = np.zeros((d, d)); zg = np.zeros(d); sz = np.zeros(d)
        for s0 in starts:
            sl = slice(s0, min(s0 + chunk, n)); z = Z(sl)
            gram += z.T @ z; zg += z.T @ G[sl]; sz += z.sum(0)
        bv = float(G.mean())
        wv = np.linalg.solve(gram + lam_v * np.eye(d), zg - bv * sz)          # = ridge on centred targets
        gram_a = np.zeros((N_ACT, d, d)); zr = np.zeros((N_ACT, d)); s1 = np.zeros((N_ACT, d)); sr = np.zeros(N_ACT); na = np.zeros(N_ACT)
        for s0 in starts:
            sl = slice(s0, min(s0 + chunk, n)); z = Z(sl)
            r = G[sl] - (z @ wv + bv); Ac = A[sl]
            for a in range(N_ACT):
                m = Ac == a
                if m.any():
                    za = z[m]
                    gram_a[a] += za.T @ za; zr[a] += za.T @ r[m]; s1[a] += za.sum(0); sr[a] += r[m].sum(); na[a] += m.sum()
        W = np.zeros((d_all, N_ACT)); b = np.zeros(N_ACT)
        for a in range(N_ACT):
            if na[a] >= min_n:
                rbar = sr[a] / na[a]
                W[cols, a] = np.linalg.solve(gram_a[a] + lam_a * np.eye(d), zr[a] - rbar * s1[a])
                b[a] = rbar
        Wv = np.zeros(d_all); Wv[cols] = wv
        self.W = (W + Wv[:, None]).astype(np.float32)
        self.b = (b + bv).astype(np.float32)
        self.meta = dict(n=int(n), n_cols=int(d), per_action=[int((A == a).sum()) for a in range(N_ACT)], lam_v=lam_v, lam_a=lam_a)

    def save(self, path, enc=None):
        extra = enc.state_dict() if enc is not None else {}
        import json
        np.savez(path, W=self.W, b=self.b, mu=self.mu, sd=self.sd, meta=json.dumps(self.meta), **extra)

    @classmethod
    def load(cls, path):
        z = np.load(path)
        r = cls(z['W'].shape[0])
        r.W, r.b, r.mu, r.sd = z['W'], z['b'], z['mu'], z['sd']
        r.enc_stats = (z['enc_mu'], z['enc_sd']) if 'enc_mu' in z.files else None
        if 'meta' in z.files:
            import json
            r.meta = json.loads(str(z['meta']))
        return r


def action_mask(altitude_ft):
    """Same safety masking as jepa_brain.rollout.BrainPolicy."""
    m = np.ones(N_ACT, dtype=bool)
    agl = altitude_ft * 0.3048
    if agl < 2500:
        m[LOW_YOYO] = False
    if agl < 1800:
        m[[BREAK_IN, BREAK_OUT, HIGH_YOYO, LOW_YOYO]] = False
    return m


class FlyPolicy:
    """Drop-in for jepa_brain.rollout policies: reset(cfg) / decide(feat, ob, arena) -> tactic id.

    mode='passive'  : the fly only watches (PURSUE is flown) -> pure visualisation, zero risk
    mode='q'        : tactic = argmax of the trained linear readout over DN activity (with hysteresis)
    """
    name = 'fly'

    def __init__(self, brain, readout=None, mode='q', margin=0.01, record=False, pursue_bonus=0.0, runaway=300):
        self.brain, self.readout, self.mode, self.margin, self.record = brain, readout, mode, margin, record
        self.pursue_bonus = float(pursue_bonus)      # added to Q(PURSUE): the fly overrides the proven default only when it expects a clear gain
        if brain is not None and readout is not None and getattr(readout, 'enc_stats', None) is not None:
            brain.enc.mu, brain.enc.sd = readout.enc_stats
        self.runaway = int(runaway)                  # DN spikes per window above this = over-excited brain: reset it, fly PURSUE
        self.n_resets = 0
        self.log = []

    def reset(self, cfg):
        self.n_resets = 0
        if self.brain is not None:
            self.brain.reset(cfg.get('seed', 0))
        self.cur = PURSUE
        self.log = []

    def decide(self, feat, ob, arena):
        if self.mode == 'feat':                      # control arm: same read-out idea on the 27 raw features, no brain
            dn, sparse = np.zeros(1, np.int16), None
        elif self.record:
            dn, sparse = self.brain.observe(feat, full=True)
        else:
            dn, sparse = self.brain.observe(feat), None
        a = PURSUE
        q = None
        if self.mode == 'feat' and self.readout is not None:
            q = self.readout.q(np.asarray(feat, np.float32)).copy()
            mask = action_mask(ob[2])
            q[PURSUE] += self.pursue_bonus
            qm = np.where(mask, q, -1e9)
            best = int(qm.argmax())
            a = self.cur if (mask[self.cur] and qm[best] - qm[self.cur] < self.margin) else best
            self.cur = a
        elif self.runaway and int(dn.sum()) > self.runaway:
            self.brain.lif.reset(); self.n_resets += 1
            self.cur = PURSUE
        elif self.mode == 'q' and self.readout is not None:
            q = self.readout.q(FlyBrain.dn_features(dn))
            mask = action_mask(ob[2])
            q = q.copy(); q[PURSUE] += self.pursue_bonus
            qm = np.where(mask, q, -1e9)
            best = int(qm.argmax())
            a = self.cur if (mask[self.cur] and qm[best] - qm[self.cur] < self.margin) else best
            self.cur = a
        if self.record:
            self.log.append(dict(dn=dn.astype(np.int16), sparse=sparse, tactic=a, feat=np.asarray(feat, np.float32),
                                 q=None if q is None else q.astype(np.float32)))
        return a


def load_brain(cache_dir, backend='numba', device='cpu'):
    """FlyBrain configured like the cache it was pruned with: encoder statistics, optional EMA channels (enc_stats.npz keys
    ema_feats / ema), pruned to the neurons active in the cache's games."""
    from pathlib import Path
    from .prune import keep_from_cache
    st = np.load(Path(cache_dir) / 'enc_stats.npz')
    ef = st['ema_feats'] if 'ema_feats' in st.files else ()
    brain = FlyBrain(device=device, dt_ms=1.0, window_ms=80.0, ema_feats=ef, ema=float(st['ema']) if 'ema' in st.files else 0.9)
    brain.enc.mu, brain.enc.sd = st['mu'], st['sd']
    brain.prune(keep_from_cache(cache_dir)[0], backend=backend)
    return brain
