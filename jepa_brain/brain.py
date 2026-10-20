"""JEPA-style latent world model + short-horizon tactic planner.

Encoder  : window of (features, previous action) tokens -> latent z (LayerNorm'ed)
Target   : EMA copy of the encoder (JEPA target, no gradient)
Predictor: (z_t, tactic) -> z_{t+1}, trained in latent space (no pixel/state decoding)
Heads    : reward (score-gap increment), value, risks (red hit soon / low altitude)
Planner  : evaluates every tactic sequence of length H inside latent space and
           returns the first tactic of the best sequence (with hysteresis).
The 60 Hz flight loop is NOT touched: tactics only retarget the frozen controller.
"""
import copy
import itertools
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from feats import FEAT_DIM, N_ACT, WINDOW, TOKEN_DIM


class Brain(nn.Module):
    def __init__(self, zdim=64, hid=192):
        super().__init__()
        self.zdim = zdim
        in_dim = WINDOW * TOKEN_DIM
        self.enc = nn.Sequential(nn.Linear(in_dim, hid), nn.GELU(), nn.Linear(hid, hid), nn.GELU(), nn.Linear(hid, zdim))
        self.ema_enc = copy.deepcopy(self.enc)
        for p in self.ema_enc.parameters():
            p.requires_grad_(False)
        self.pred = nn.Sequential(nn.Linear(zdim + N_ACT, hid), nn.GELU(), nn.Linear(hid, hid), nn.GELU(), nn.Linear(hid, zdim))
        self.rew = nn.Sequential(nn.Linear(zdim + N_ACT, hid // 2), nn.GELU(), nn.Linear(hid // 2, 1))
        self.val = nn.Sequential(nn.Linear(zdim, hid // 2), nn.GELU(), nn.Linear(hid // 2, 1))
        self.risk = nn.Sequential(nn.Linear(zdim + N_ACT, hid // 2), nn.GELU(), nn.Linear(hid // 2, 2))
        self._seq_cache = {}

    # ---- latent ops ----
    def encode(self, window):
        return F.layer_norm(self.enc(window), (self.zdim,))

    @torch.no_grad()
    def target_encode(self, window):
        return F.layer_norm(self.ema_enc(window), (self.zdim,))

    def step(self, z, a_onehot):
        return F.layer_norm(z + self.pred(torch.cat([z, a_onehot], -1)), (self.zdim,))

    @torch.no_grad()
    def update_ema(self, tau=0.99):
        for pe, p in zip(self.ema_enc.parameters(), self.enc.parameters()):
            pe.mul_(tau).add_(p.detach(), alpha=1 - tau)

    # ---- planning ----
    def _seqs(self, horizon):
        if horizon not in self._seq_cache:
            self._seq_cache[horizon] = torch.as_tensor(
                list(itertools.product(range(N_ACT), repeat=horizon)), dtype=torch.long)
        return self._seq_cache[horizon]

    @torch.no_grad()
    def plan(self, window, mask, current, horizon=3, gamma=0.95, lam_hit=0.5, lam_low=0.5, margin=0.02):
        seqs = self._seqs(horizon)
        n = seqs.shape[0]
        x = torch.as_tensor(np.asarray(window, dtype=np.float32)).reshape(1, -1)
        z = self.encode(x).expand(n, -1)
        total = torch.zeros(n)
        for i in range(horizon):
            a = F.one_hot(seqs[:, i], N_ACT).float()
            za = torch.cat([z, a], -1)
            r = self.rew(za).squeeze(-1)
            risk = torch.sigmoid(self.risk(za))
            total = total + (gamma ** i) * (r - lam_hit * risk[:, 0] - lam_low * risk[:, 1])
            z = self.step(z, a)
        total = total + (gamma ** horizon) * self.val(z).squeeze(-1)
        first = seqs[:, 0]
        q = torch.full((N_ACT,), -1e9)
        for a in range(N_ACT):
            if mask[a]:
                q[a] = total[first == a].max()
        best = int(q.argmax())
        if mask[current] and float(q[best] - q[current]) < margin:
            best = int(current)
        return best, q.numpy()


def save_brain(brain, path, extra=None):
    torch.save({'state_dict': brain.state_dict(), 'zdim': brain.zdim, 'extra': extra or {}}, str(path))


def load_brain(path):
    ck = torch.load(str(path), map_location='cpu')
    brain = Brain(zdim=ck['zdim'])
    brain.load_state_dict(ck['state_dict'])
    brain.eval()
    torch.set_num_threads(1)
    return brain
