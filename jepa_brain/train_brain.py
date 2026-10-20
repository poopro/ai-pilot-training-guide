"""Train the JEPA-style brain from collected game data.

  python train_brain.py --data runs/collect01/data [runs/collect02/data ...] --out brain_v1.pt --epochs 40
"""
import argparse, glob, json, time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from common import HERE
from feats import FEAT_DIM, N_ACT, WINDOW, TOKEN_DIM
from brain import Brain, save_brain

H = 3


def load(dirs):
    eps = []
    for d in dirs:
        for f in sorted(glob.glob(str(HERE / d / '*.npz'))):
            z = np.load(f)
            if len(z['acts']) >= 4:
                eps.append({k: z[k] for k in z.files})
    return eps


def build(eps):
    toks, acts, rew, hit, low, ret, start, end = [], [], [], [], [], [], [], []
    off = 0
    for e in eps:
        T = len(e['acts'])
        prev = np.zeros((T, N_ACT), np.float32)
        prev[np.arange(1, T), e['acts'][:-1]] = 1.
        toks.append(np.concatenate([e['feats'], prev], 1))
        acts.append(e['acts']); rew.append(e['rewards']); hit.append(e['risk_hit']); low.append(e['risk_low']); ret.append(e['returns'])
        start += [off] * T; end += [off + T - 1] * T
        off += T
    cat = lambda x: np.concatenate(x)
    return dict(tok=torch.as_tensor(cat(toks)), act=torch.as_tensor(cat(acts)), rew=torch.as_tensor(cat(rew)),
                hit=torch.as_tensor(cat(hit)), low=torch.as_tensor(cat(low)), ret=torch.as_tensor(cat(ret)),
                start=torch.as_tensor(np.array(start)), end=torch.as_tensor(np.array(end)))


def window_at(D, idx):
    """idx: [B] global indices -> [B, WINDOW*TOKEN_DIM] with per-episode clamping."""
    off = torch.arange(-(WINDOW - 1), 1)
    g = idx[:, None] + off[None, :]
    g = torch.maximum(g, D['start'][idx][:, None])
    g = torch.minimum(g, D['end'][idx][:, None])
    return D['tok'][g].reshape(len(idx), -1)


def batch_loss(brain, D, idx, w):
    B = len(idx)
    end = D['end'][idx]
    z = brain.encode(window_at(D, idx))
    z0 = z
    jepa = rewl = valuel = riskl = 0.
    den_z = den_r = den_v = 1e-6
    for k in range(H + 1):
        gk = torch.minimum(idx + k, end)
        m_state = ((idx + k) <= end).float()
        valuel = valuel + (m_state * F.smooth_l1_loss(brain.val(z).squeeze(-1), D['ret'][gk], reduction='none')).sum()
        den_v += float(m_state.sum())
        if k == H:
            break
        a = F.one_hot(D['act'][gk], N_ACT).float()
        za = torch.cat([z, a], -1)
        rl = F.smooth_l1_loss(brain.rew(za).squeeze(-1), D['rew'][gk], reduction='none')
        rewl = rewl + (m_state * rl).sum()
        rk = brain.risk(za)
        bl = F.binary_cross_entropy_with_logits(rk[:, 0], D['hit'][gk], reduction='none') + F.binary_cross_entropy_with_logits(rk[:, 1], D['low'][gk], reduction='none')
        riskl = riskl + (m_state * bl).sum()
        den_r += float(m_state.sum())
        z = brain.step(z, a)
        m_next = ((idx + k + 1) <= end).float()
        target = brain.target_encode(window_at(D, torch.minimum(idx + k + 1, end)))
        jepa = jepa + (m_next * ((z - target) ** 2).mean(-1)).sum()
        den_z += float(m_next.sum())
    std = z0.std(0)
    var = F.relu(0.5 - std).mean()
    loss = w['j'] * jepa / den_z + w['r'] * rewl / den_r + w['v'] * valuel / den_v + w['k'] * riskl / den_r + w['var'] * var
    return loss, dict(jepa=float(jepa / den_z), rew=float(rewl / den_r), val=float(valuel / den_v), risk=float(riskl / den_r), std=float(std.mean()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', nargs='+', required=True)
    ap.add_argument('--out', default='brain_v1.pt')
    ap.add_argument('--epochs', type=int, default=40)
    ap.add_argument('--bs', type=int, default=1024)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--init', default=None)
    a = ap.parse_args()
    torch.manual_seed(0); np.random.seed(0)
    eps = load(a.data)
    print('episodes', len(eps), 'decisions', sum(len(e['acts']) for e in eps), flush=True)
    n_val = max(1, len(eps) // 10)
    rng = np.random.default_rng(0); order = rng.permutation(len(eps))
    val_eps = [eps[i] for i in order[:n_val]]; tr_eps = [eps[i] for i in order[n_val:]]
    Dtr, Dva = build(tr_eps), build(val_eps)
    brain = Brain()
    if a.init:
        brain.load_state_dict(torch.load(str(HERE / a.init), map_location='cpu')['state_dict'])
    opt = torch.optim.AdamW([p for p in brain.parameters() if p.requires_grad], lr=a.lr, weight_decay=1e-4)
    N = len(Dtr['act']); steps = a.epochs * max(1, N // a.bs)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    w = dict(j=1.0, r=5.0, v=1.0, k=0.5, var=1.0)
    log = []; t0 = time.time()
    for ep in range(a.epochs):
        perm = torch.randperm(N); tot = {}
        for i in range(0, N - a.bs + 1, a.bs):
            idx = perm[i:i + a.bs]
            loss, parts = batch_loss(brain, Dtr, idx, w)
            opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(brain.parameters(), 1.0); opt.step(); sched.step()
            brain.update_ema(0.99)
            for k, v in parts.items(): tot[k] = tot.get(k, 0.) + v
        nb = max(1, N // a.bs)
        brain.eval()
        with torch.no_grad():
            vi = torch.arange(len(Dva['act'])); _, vp = batch_loss(brain, Dva, vi, w)
        brain.train()
        row = dict(epoch=ep, train={k: round(v / nb, 5) for k, v in tot.items()}, val={k: round(v, 5) for k, v in vp.items()}, sec=round(time.time() - t0))
        log.append(row); print(json.dumps(row), flush=True)
    save_brain(brain, HERE / a.out, extra=dict(episodes=len(eps), epochs=a.epochs))
    (HERE / (a.out + '.log.json')).write_text(json.dumps(log, indent=1), encoding='utf-8')
    print('SAVED', a.out)


if __name__ == '__main__':
    main()
