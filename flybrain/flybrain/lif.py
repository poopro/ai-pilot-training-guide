"""Event-driven PyTorch re-implementation of the Shiu et al. (2024) Drosophila whole-brain LIF model.

Same equations / constants as the original Brian2 code (github.com/philshiu/Drosophila_brain_model):
    dv/dt = (v0 - v + g) / t_mbr      (membrane)       v0=-52 mV, v_th=-45 mV, v_rst=-52 mV, t_mbr=20 ms
    dg/dt = -g / tau                  (synaptic, tau=5 ms)
    a presynaptic spike adds  w = w_syn * (signed #synapses)  to g of the target after t_dly = 1.8 ms
    after a spike: v=v_rst, g=0, refractory t_rfc = 2.2 ms (v,g frozen)
    "activated" neurons receive Poisson kicks of w_syn*f_poi (= 68.75 mV) on v -> they fire at the kick rate

Differences (documented, on purpose):
  * time step dt is a parameter (original 0.1 ms; we default to 0.5 ms for speed) and the linear ODE is
    integrated exactly per step, like Brian2's method='linear'; delay / refractory are rounded to steps.
  * Only the rows of neurons that spiked are touched (spikes are sparse), so cost ~ #spikes, not #synapses.
"""
import math
import numpy as np
import torch


class FlyLIF:
    def __init__(self, conn, dt_ms=0.5, device='cpu', w_syn_mv=0.275, kick_mv=68.75, seed=0):
        self.n = conn.n
        self.dev = torch.device(device)
        self.dt = float(dt_ms)
        # constants (mV, ms)
        self.v0, self.vth, self.vrst = -52.0, -45.0, -52.0
        tm, tau = 20.0, 5.0
        self.a = math.exp(-self.dt / tm)
        self.b = tau / (tau - tm) * (math.exp(-self.dt / tau) - math.exp(-self.dt / tm))
        self.c = math.exp(-self.dt / tau)
        self.delay = max(1, int(round(1.8 / self.dt)))
        self.rfc_steps = int(round(2.2 / self.dt))
        self.kick = kick_mv                       # = w_syn*f_poi = 0.275*250 mV in the original (a spike for sure)
        self.w_syn = w_syn_mv
        # connectivity on device
        self.indptr = torch.as_tensor(conn.indptr, device=self.dev)
        self.post = torch.as_tensor(conn.post.astype(np.int64), device=self.dev) if self.dev.type == 'cpu' \
            else torch.as_tensor(conn.post, device=self.dev).long()
        self.w = torch.as_tensor(conn.wcount, device=self.dev).float() * w_syn_mv
        self.gen = torch.Generator(device='cpu').manual_seed(int(seed))
        self.ring = torch.zeros(self.delay + 1, self.n, device=self.dev)
        self.rfc = torch.full((self.n,), self.rfc_steps, dtype=torch.int16, device=self.dev)
        self._poisson_set = None
        self.reset()

    def reset(self):
        self.v = torch.full((self.n,), self.v0, device=self.dev)
        self.g = torch.zeros(self.n, device=self.dev)
        self.ref_idx = torch.zeros(0, dtype=torch.long, device=self.dev)      # neurons currently refractory (sparse list)
        self.ref_until = torch.zeros(0, dtype=torch.long, device=self.dev)    # absolute step at which they recover
        self.ring.zero_()
        self.t = 0

    def _set_poisson_targets(self, idx):
        if self._poisson_set is not None:
            self.rfc[self._poisson_set] = self.rfc_steps
        self._poisson_set = idx
        if idx is not None:
            self.rfc[idx] = 0                      # as in the original: no refractory period for Poisson targets

    @torch.no_grad()
    def run(self, steps, in_idx=None, in_rate_hz=None, record=False):
        """Advance `steps` time steps with Poisson drive (rate per input neuron, Hz).

        returns counts (int32 [n], spikes per neuron in this window) and, if record, (step, neuron) arrays.
        """
        dev, n = self.dev, self.n
        counts = torch.zeros(n, dtype=torch.int32, device=dev)
        rec_t, rec_i = [], []
        if in_idx is not None and len(in_idx):
            in_idx_t = torch.as_tensor(np.asarray(in_idx), dtype=torch.long, device=dev)
            p = torch.as_tensor(np.asarray(in_rate_hz, dtype=np.float32) * self.dt * 1e-3)
            kicks = (torch.rand(steps, len(in_idx_t), generator=self.gen) < p[None, :]).to(dev)
            self._set_poisson_targets(in_idx_t)
        else:
            in_idx_t, kicks = None, None
            self._set_poisson_targets(None)
        D = self.delay + 1
        a, b, c, v0, vth, vrst = self.a, self.b, self.c, self.v0, self.vth, self.vrst
        c0 = v0 * (1.0 - a)
        v, g, ring, rfc = self.v, self.g, self.ring, self.rfc
        indptr, post, w = self.indptr, self.post, self.w
        for s in range(steps):
            slot = self.t % D
            g.add_(ring[slot])                                   # delayed spikes arrive (also in refractory neurons)
            ring[slot].zero_()
            ri = self.ref_idx
            if ri.numel():
                v_keep, g_keep = v[ri], g[ri]                    # refractory neurons are frozen
            v.mul_(a).add_(g, alpha=b).add_(c0)                  # exact integration of the linear (v, g) system
            g.mul_(c)
            if ri.numel():
                v[ri] = v_keep; g[ri] = g_keep
            if kicks is not None:
                k = in_idx_t[kicks[s]]
                if k.numel():
                    v[k] += self.kick
            spk = torch.nonzero(v > vth).squeeze(1)
            if spk.numel():
                v[spk] = vrst
                g[spk] = 0.0
                counts[spk] += 1
                r = rfc[spk]
                m = r > 0
                if bool(m.any()):
                    new = spk[m]
                    self.ref_idx = torch.cat([ri, new])
                    self.ref_until = torch.cat([self.ref_until, self.t + 1 + r[m].long()])
                if record:
                    rec_t.append(torch.full_like(spk, s)); rec_i.append(spk)
                st = indptr[spk]
                cn = indptr[spk + 1] - st
                tot = int(cn.sum())
                if tot:
                    off = torch.cumsum(cn, 0) - cn
                    pos = torch.arange(tot, device=dev) - torch.repeat_interleave(off - st, cn)
                    ring[(self.t + self.delay) % D].index_add_(0, post[pos], w[pos])
            self.t += 1
            if self.ref_idx.numel():                             # recover
                alive = self.ref_until > self.t
                if not bool(alive.all()):
                    self.ref_idx = self.ref_idx[alive]; self.ref_until = self.ref_until[alive]
        self.v, self.g = v, g
        if record:
            if rec_t:
                return counts, (torch.cat(rec_t).cpu().numpy(), torch.cat(rec_i).cpu().numpy())
            return counts, (np.zeros(0, np.int64), np.zeros(0, np.int64))
        return counts
