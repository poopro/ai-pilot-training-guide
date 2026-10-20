"""Does cutting the brain down change what it says?  (and does it remove the runaway state?)

  python prune_eval.py --cache cache480 --data <dir with g*.npz> --test g600005_lead,g600085_guide --min-games 3

keep set = neurons that spiked in >= --min-games of the replayed games stored in --cache (replay.py stores `active_idx`).
Each test game (NOT among those replayed) is run through the full brain twice (seeds 0 and 1) and through the pruned brain
(seed 0).  Reference noise = full(seed 0) vs full(seed 1).  If pruned-vs-full is not worse than that, the cut is inside the
brain's own random noise.  Also counts 'runaway' windows (DN spikes > --runaway): self-sustained over-excited states that
some games trigger in the full brain.
"""
import argparse, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flybrain.connectome import Connectome
from flybrain.pilot import FlyBrain, Readout
from flybrain.prune import keep_from_cache


def run(B, feats, seed):
    B.reset(seed)
    t0 = time.time()
    out = np.stack([B.observe(f) for f in feats])
    return out, (time.time() - t0) / len(feats)


def compare(ref, x, ro=None):
    a, b = FlyBrain.dn_features(ref), FlyBrain.dn_features(x)
    cells = float(np.corrcoef(a.ravel(), b.ravel())[0, 1])
    sd = (a.std(0) > 0.05) & (b.std(0) > 0.05)
    per = [np.corrcoef(a[:, j], b[:, j])[0, 1] for j in np.flatnonzero(sd)]
    agree = float(np.mean([ro.q(u).argmax() == ro.q(v).argmax() for u, v in zip(a, b)])) if ro is not None else float('nan')
    return dict(agree_tactic=agree, corr_cells=cells, corr_per_dn=float(np.nanmean(per)), spike_ratio=float(x.sum() / max(ref.sum(), 1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default='cache')
    ap.add_argument('--data', required=True, help='directory with the recorded games (g*.npz with feats)')
    ap.add_argument('--test', required=True, help='comma list of game names to test on (must not be among the replayed ones)')
    ap.add_argument('--min-games', default='3', help='comma list; keep neurons active in >= k replayed games')
    ap.add_argument('--readout', default='readout.npz')
    ap.add_argument('--runaway', type=int, default=300, help='DN spikes per window above which a window counts as runaway')
    ap.add_argument('--n', type=int, default=400, help='max decisions per test game')
    a = ap.parse_args()
    C = Connectome()
    ro = Readout.load(a.readout) if a.readout and Path(a.readout).exists() else None
    st = np.load(Path(a.cache) / 'enc_stats.npz')
    games = [np.load(Path(a.data) / (g + '.npz'))['feats'][:a.n] for g in a.test.split(',')]

    def make(keep=None):
        B = FlyBrain(conn=C, dt_ms=1.0); B.enc.mu, B.enc.sd = st['mu'], st['sd']
        if keep is None:
            B.use_numba()
        else:
            B.prune(keep, backend='numba')
        return B
    Bf = make()
    full0 = [run(Bf, f, 0)[0] for f in games]
    full1 = [run(Bf, f, 1)[0] for f in games]
    t_full = np.mean([run(Bf, f, 0)[1] for f in games[:1]])

    def agg(refs, xs):
        rs = [compare(r, x, ro) for r, x in zip(refs, xs)]
        return {k: round(float(np.mean([r[k] for r in rs])), 3) for k in rs[0]}
    runaway = lambda xs: int(sum((x.sum(1) > a.runaway).sum() for x in xs))
    nwin = sum(len(f) for f in games)
    print('test windows %d | full brain: %.4f s/decision, runaway windows %d' % (nwin, t_full, runaway(full0)))
    print('noise ceiling (full vs full, other seed):', agg(full0, full1))
    for k in [int(x) for x in a.min_games.split(',')]:
        keep, ng = keep_from_cache(a.cache, min_games=k)
        Bp = make(keep)
        p0 = [run(Bp, f, 0)[0] for f in games]
        p1 = [run(Bp, f, 1)[0] for f in games]
        t = np.mean([run(Bp, f, 0)[1] for f in games[:1]])
        print('PRUNED min_games>=%d: %d neurons (%.1f%%)  %.4f s/decision (%.1fx) | runaway windows %d | pruned vs full: %s' % (
            k, len(Bp.keep), 100 * len(Bp.keep) / C.n, t, t_full / t, runaway(p0), agg(full0, p0)))
        print('   pruned(other seed) vs full(seed 0) = different random input, compare with the noise ceiling:', agg(full0, p1))
        del Bp


if __name__ == '__main__':
    main()
