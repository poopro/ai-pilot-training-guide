"""numba version of the LIF simulator for (pruned) sub-networks.

Same equations, constants, delay and refractory handling as lif.FlyLIF (see the comments there), written as plain loops
so that a 4,000-neuron network costs ~20 microseconds per 1 ms step instead of ~450 (the torch version is limited by
per-op overhead, not by arithmetic).  Intended for networks of up to a few 10,000 neurons: it touches every neuron each
step, so on the full 138,639-neuron network the torch version (which only touches spiking rows) remains the better choice.

pip install numba     (first call compiles for ~10 s, then it is cached on disk)

Differences from FlyLIF, on purpose: the Poisson input comes from numpy's generator, not torch's, so the same seed gives a
different (statistically identical) spike train; `record=True` is not supported.
"""
import math
import numpy as np
from numba import njit


@njit(cache=True)
def _run(steps, t0, D, delay, a, b, c, c0, vth, vrst, kick, v, g, ring, until, rfc, indptr, post, w, in_idx, kicks, counts):
    n = v.shape[0]
    n_in = in_idx.shape[0]
    t = t0
    for s in range(steps):
        slot = t % D
        for i in range(n):
            g[i] += ring[slot, i]            # delayed spikes arrive (also in refractory neurons)
            ring[slot, i] = 0.0
        for i in range(n):
            if until[i] > t:                 # refractory: v and g frozen (arrivals were already added to g)
                continue
            v[i] = v[i] * a + g[i] * b + c0  # exact integration of the linear (v, g) system
            g[i] = g[i] * c
        for j in range(n_in):
            if kicks[s, j]:
                v[in_idx[j]] += kick
        tgt = (t + delay) % D
        for i in range(n):
            if v[i] > vth:
                v[i] = vrst
                g[i] = 0.0
                counts[i] += 1
                if rfc[i] > 0:
                    until[i] = t + 1 + rfc[i]
                for e in range(indptr[i], indptr[i + 1]):
                    ring[tgt, post[e]] += w[e]
        t += 1
    return t


class _Gen:
    def __init__(self, owner):
        self.owner = owner

    def manual_seed(self, seed):
        self.owner.rng = np.random.default_rng(int(seed))
        return self


class FastLIF:
    def __init__(self, conn, dt_ms=1.0, w_syn_mv=0.275, kick_mv=68.75, seed=0, **_ignored):
        self.n = int(conn.n)
        self.dt = float(dt_ms)
        self.v0, self.vth, self.vrst = -52.0, -45.0, -52.0
        tm, tau = 20.0, 5.0
        self.a = math.exp(-self.dt / tm)
        self.b = tau / (tau - tm) * (math.exp(-self.dt / tau) - math.exp(-self.dt / tm))
        self.c = math.exp(-self.dt / tau)
        self.c0 = self.v0 * (1.0 - self.a)
        self.delay = max(1, int(round(1.8 / self.dt)))
        self.rfc_steps = int(round(2.2 / self.dt))
        self.kick = kick_mv
        self.indptr = np.ascontiguousarray(conn.indptr, dtype=np.int64)
        self.post = np.ascontiguousarray(conn.post, dtype=np.int32)
        self.w = (conn.wcount.astype(np.float32) * np.float32(w_syn_mv)).astype(np.float32)
        self.D = self.delay + 1
        self.rfc = np.full(self.n, self.rfc_steps, dtype=np.int64)
        self._poisson = None
        self.gen = _Gen(self)
        self.rng = np.random.default_rng(int(seed))
        self.reset()

    def reset(self):
        self.v = np.full(self.n, self.v0, dtype=np.float32)
        self.g = np.zeros(self.n, dtype=np.float32)
        self.ring = np.zeros((self.D, self.n), dtype=np.float32)
        self.until = np.zeros(self.n, dtype=np.int64)
        self.t = 0

    def _set_poisson_targets(self, idx):
        if self._poisson is not None:
            self.rfc[self._poisson] = self.rfc_steps
        self._poisson = idx
        if idx is not None:
            self.rfc[idx] = 0                # as in the original: no refractory period for Poisson targets

    def run(self, steps, in_idx=None, in_rate_hz=None, record=False):
        if record:
            raise NotImplementedError('FastLIF does not record spike times; use FlyLIF')
        counts = np.zeros(self.n, dtype=np.int32)
        if in_idx is not None and len(in_idx):
            idx = np.ascontiguousarray(in_idx, dtype=np.int64)
            p = np.asarray(in_rate_hz, dtype=np.float32) * np.float32(self.dt * 1e-3)
            kicks = self.rng.random((steps, len(idx)), dtype=np.float32) < p[None, :]
            self._set_poisson_targets(idx)
        else:
            idx = np.zeros(0, dtype=np.int64)
            kicks = np.zeros((steps, 0), dtype=np.bool_)
            self._set_poisson_targets(None)
        self.t = _run(int(steps), int(self.t), self.D, self.delay, self.a, self.b, self.c, self.c0, self.vth, self.vrst,
                      self.kick, self.v, self.g, self.ring, self.until, self.rfc, self.indptr, self.post, self.w,
                      idx, kicks, counts)
        return counts
