"""Replay recorded games through the fly brain (open loop: the fly only watches) and cache DN activity.

  python replay.py --data <dir with g*.npz> --out cache --max-games 12 [--device cuda]
"""
import argparse, glob, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flybrain.pilot import FlyBrain


def replay_game(brain, feats, seed, keep_sparse=False):
    brain.reset(seed)
    dn, sp = [], []
    active = np.zeros(brain.conn.n, bool)
    for f in feats:
        d, s = brain.observe(f, full=True)
        active[s[0]] = True
        dn.append(d)
        if keep_sparse:
            sp.append(s)
    return np.asarray(dn, np.int16), sp, np.flatnonzero(active).astype(np.int32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', default='cache')
    ap.add_argument('--max-games', type=int, default=12)
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--dt', type=float, default=1.0)
    ap.add_argument('--sparse', default='', help='comma list of game names whose full spike activity is also stored (for the viewer)')
    ap.add_argument('--window-ms', type=float, default=80.0)
    ap.add_argument('--threads', type=int, default=0)
    ap.add_argument('--every', type=int, default=1, help='replay every k-th game only (e.g. 10 -> a spread-out 10%% sample)')
    ap.add_argument('--offset', type=int, default=0, help='first game index when --every is used')
    ap.add_argument('--backend', default='torch', help='torch | numba  (numba: ~6x faster on the full network, ~30x on a pruned one)')
    ap.add_argument('--prune-cache', default='', help='simulate only neurons that spiked in games already in this cache dir (about 3-4x faster; see README)')
    a = ap.parse_args()
    import torch
    if a.threads: torch.set_num_threads(a.threads)
    all_files = sorted(glob.glob(str(Path(a.data) / 'g*.npz')))
    files = all_files[a.offset::max(a.every, 1)][:a.max_games]
    games = [np.load(f) for f in files]
    brain = FlyBrain(device=a.device, dt_ms=a.dt, window_ms=a.window_ms)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if (out / 'enc_stats.npz').exists():          # never refit: older cached games were made with these statistics
        st = np.load(out / 'enc_stats.npz'); brain.enc.mu, brain.enc.sd = st['mu'], st['sd']
        print('using existing enc_stats.npz')
    else:
        brain.enc.fit_stats([np.load(f)['feats'] for f in all_files])     # statistics over ALL games, not only the replayed ones
        np.savez(out / 'enc_stats.npz', mu=brain.enc.mu, sd=brain.enc.sd)
    if a.backend == 'numba' and not a.prune_cache:
        brain.use_numba()
    if a.prune_cache:
        from flybrain.prune import keep_from_cache
        keep, ng = keep_from_cache(a.prune_cache)
        sub = brain.prune(keep, backend='numba' if a.backend == 'numba' else 'torch')
        print('pruned to %d neurons (%.1f%%) using %d cached games' % (sub.n, 100 * sub.n / brain.conn.n, ng))
    for f, g in zip(files, games):
        name = Path(f).stem
        if (out / (name + '.npz')).exists():
            print('skip', name); continue
        t0 = time.time()
        seed = int(name[1:].split('_')[0])
        want_sparse = name in [x for x in a.sparse.split(',') if x]
        dn, sp, active = replay_game(brain, g['feats'], seed, keep_sparse=want_sparse)
        extra = dict(active_idx=active)
        if want_sparse:
            extra.update(sp_idx=np.concatenate([s[0] for s in sp]), sp_cnt=np.concatenate([s[1] for s in sp]),
                         sp_ptr=np.concatenate([[0], np.cumsum([len(s[0]) for s in sp])]))
        np.savez_compressed(out / (name + '.npz'), dn=dn, acts=g['acts'], returns=g['returns'], feats=g['feats'], **extra)
        print('%s  %d decisions  %.0fs  DN spikes/decision mean=%.1f  active DN=%.0f%%' % (
            name, len(dn), time.time() - t0, dn.sum(1).mean(), 100 * (dn.sum(0) > 0).mean()), flush=True)


if __name__ == '__main__':
    main()
