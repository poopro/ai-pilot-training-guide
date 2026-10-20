"""Summarise branch_labels.py output: is any tactic better than PURSUE, where, and by how much compared with chaos noise?

  python branch_report.py labels/pilot
"""
import glob, sys
from pathlib import Path
import numpy as np

NAMES = ['pursue', 'lead', 'lag', 'break_in', 'break_out', 'high_yoyo', 'low_yoyo', 'extend', 'null']
ZONE = 3500.


def load(d):
    rows = []
    for f in sorted(glob.glob(str(Path(d) / 'g*.npz'))):
        z = np.load(f)
        if len(z['lab_dec']) == 0:
            continue
        opp = Path(f).stem.split('_', 1)[1].replace('sac-', 'sac:')      # (':' is stored as '-' in file names for Windows)
        V = z['lab_delta'] + z['lab_term']
        rows.append(dict(name=Path(f).stem, opp=opp, rng=z['lab_range'], A=V - V[:, [0]], V=V, atk=z['lab_atk'], overg=z['lab_overg']))
    return rows


def table(title, A, rng):
    print('\n=== %s  (%d states) ===' % (title, len(A)))
    if len(A) == 0:
        return
    null = np.abs(A[:, 8]) if A.shape[1] > 8 else np.zeros(len(A))
    print('chaos noise (|null - pursue|): mean %.1f  median %.1f  p90 %.1f  max %.0f   [points of advantage over the horizon]' % (null.mean(), np.median(null), np.percentile(null, 90), null.max()))
    thr = max(np.percentile(null, 90), 5.0)
    print('%-10s %9s %9s %9s %9s %9s' % ('option', 'mean', 'median', '>+thr', '<-thr', 'thr=%.0f' % thr))
    for k in range(1, 8):
        a = A[:, k]
        print('%-10s %9.1f %9.1f %8.0f%% %8.0f%%' % (NAMES[k], a.mean(), np.median(a), 100 * (a > thr).mean(), 100 * (a < -thr).mean()))
    best = A[:, :8].max(1)
    arg = A[:, :8].argmax(1)
    print('hindsight-best option vs PURSUE: mean gain %.1f   states where best beats PURSUE by > thr: %.0f%%   (optimistic: it is a max over noisy options)' % (best.mean(), 100 * (best > thr).mean()))
    cnt = np.bincount(arg[best > thr], minlength=8)
    print('which option is best when it matters:', {NAMES[k]: int(cnt[k]) for k in range(1, 8) if cnt[k]})


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else 'labels/pilot'
    rows = load(d)
    print('%d games with labels: %s' % (len(rows), ', '.join(r['name'] for r in rows)))
    A = np.concatenate([r['A'] for r in rows]); R = np.concatenate([r['rng'] for r in rows])
    table('ALL', A, R)
    table('NEAR (range < %.0f m)' % ZONE, A[R < ZONE], R[R < ZONE])
    table('FAR  (range >= %.0f m)' % ZONE, A[R >= ZONE], R[R >= ZONE])
    for opp in sorted({r['opp'] for r in rows}):
        a = np.concatenate([r['A'] for r in rows if r['opp'] == opp]); rr = np.concatenate([r['rng'] for r in rows if r['opp'] == opp])
        table('opponent %s, NEAR' % opp, a[rr < ZONE], rr[rr < ZONE])
    # decisive endings
    atk = np.concatenate([r['atk'] for r in rows])
    print('\nattack ticks gained over the horizon (blue/red), summed over all states, per option:')
    for k in range(atk.shape[1]):
        print('  %-10s blue %5d  red %5d' % (NAMES[k], atk[:, k, 0].sum(), atk[:, k, 1].sum()))


if __name__ == '__main__':
    main()
