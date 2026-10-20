"""Cut the fly brain down to the neurons that actually matter (speed-up for the simulator).

The per-step cost of the LIF simulator is dominated by dense updates over ALL neurons (138,639), even though only
~1,000 of them spike in a given 80 ms window.  Dropping neurons that (almost) never spike - and the synapses that
touch only them - makes every step several times cheaper.  What is lost: a dropped neuron can no longer fire and pass
activity on, so inputs the pruning set has never seen (e.g. a very different flight state) may recruit neurons that are
missing.  `FlyBrain.prune` therefore always keeps every input and every descending neuron, and prune_eval.py measures the
damage on games the pruning set did NOT come from.
"""
import numpy as np


class SubConn:
    """Sub-network of a Connectome: kept neurons + the synapses between kept neurons (same CSR layout)."""

    def __init__(self, conn, keep):
        keep = np.unique(np.asarray(keep, np.int64))
        N = conn.n
        remap = np.full(N, -1, np.int32)
        remap[keep] = np.arange(len(keep), dtype=np.int32)
        deg = np.diff(conn.indptr)
        rows = np.repeat(np.arange(N, dtype=np.int32), deg)
        m = (remap[rows] >= 0) & (remap[conn.post] >= 0)
        new_rows = remap[rows[m]]
        self.n = len(keep)
        self.keep = keep                                   # new index -> original neuron index
        self.remap = remap                                 # original index -> new index (-1 = dropped)
        self.post = remap[conn.post[m]].astype(np.int32)
        self.wcount = conn.wcount[m]
        self.indptr = np.concatenate([[0], np.cumsum(np.bincount(new_rows, minlength=self.n))]).astype(np.int64)
        self.n_edges = int(m.sum())


def keep_from_activity(sp_idx, n_total, min_windows=1, sp_ptr=None):
    """Original neuron indices that spiked in at least `min_windows` windows.

    sp_idx : concatenated spiking neuron ids of all windows (as stored by replay.py / fly_eval.py --record)
    sp_ptr : window boundaries (len = windows + 1); needed only for min_windows > 1
    """
    sp_idx = np.asarray(sp_idx, np.int64)
    if min_windows <= 1 or sp_ptr is None:
        return np.unique(sp_idx)
    per = np.bincount(sp_idx, minlength=n_total)           # spikes are listed once per window, so this is #windows
    return np.flatnonzero(per >= min_windows)


def keep_from_cache(cache_dir, min_games=None):
    """Neurons that spiked in at least `min_games` of the replayed games in cache_dir (replay.py stores `active_idx`, or full
    spikes for --sparse games).  Default min(3, #games): in 48 recorded games the neurons seen in only 1-2 games were exactly the
    ~9,000 that carry the full brain into a self-sustained runaway state (2 of 48 games), so dropping them also stabilises it."""
    import glob
    from pathlib import Path
    cnt = {}
    n_games = 0
    for f in sorted(glob.glob(str(Path(cache_dir) / 'g*.npz'))):
        z = np.load(f)
        if 'active_idx' in z.files:
            ids = z['active_idx']
        elif 'sp_idx' in z.files:
            ids = np.unique(z['sp_idx'][:z['sp_ptr'][-1]])
        else:
            continue
        n_games += 1
        for i in ids.tolist():
            cnt[i] = cnt.get(i, 0) + 1
    if not n_games:
        raise SystemExit('no game in %s has stored activity (active_idx / sp_idx): run replay.py first' % cache_dir)
    k = min(3, n_games) if min_games is None else int(min_games)
    return np.array(sorted(i for i, c in cnt.items() if c >= k), np.int64), n_games
