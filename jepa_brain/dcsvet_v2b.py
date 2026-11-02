"""DCS imitation v2b (2026-10-27): the v2 INTENT model (dcsvet_v2.py) trained on ~all Ace data instead of only the
winners of the 503 gun-kill fights (~6 % of the night run).

Selection per perspective (one jet's view of one fight), fights keyed by (seed, idx) -- v2 keyed kill fights by idx
only, which mislabels a few fights whose idx repeats across mission runs:
  * drop the perspective if that jet was shot down (gun kill / missing / pilot dead with it as loser)
  * keep it if the jet is Ace-skilled (blue is always Ace; red is 'Excellent' = Ace in ~half the fights) or it won the fight
  * a jet that lost by going below the deck / crashing: drop its last 30 s before it first went below 1000 m
  * samples below 1000 m are dropped anyway (as in v2)
  * the winners of gun-kill fights are repeated `win_rep` times (they are the behaviour we most want)
Label and inputs exactly as v2 (2 s-ahead velocity direction up/side + CAS change; copy-cat inputs zeroed).

  DCSVET_HZ=15 DCSVET_STRIDE=2 python dcsvet_v2b.py build OUT.npz LINES.log bucket*.csv.gz   (2 processes)
  python dcsvet_v2.py train OUT.npz WEIGHTS.npz 20
"""
import sys, json, math
from multiprocessing import Pool
import numpy as np
import dcsvet_core as C
import dcsvet_data as D
import dcsvet_v2 as V

KILL = ('S_EVENT_UNIT_LOST', 'missing', 'S_EVENT_PILOT_DEAD')
DECK = ('deck', 'softdeck', 'S_EVENT_CRASH', 'S_EVENT_EJECTION')
LINES = None


def samples_t(fB, fR, own_side, min_alt=1000.):
    """dcsvet_v2.intent_samples + the time of every sample (to cut the doomed tail)."""
    HZ = D.HZ
    t0 = max(fB['t'][0], fR['t'][0]) + 1.5
    t1 = min(fB['t'][-1], fR['t'][-1]) - 1.0
    if t1 - t0 < 8:
        return None
    tg = np.arange(t0, t1, 1. / HZ)
    rs = {'B': D.resample(fB, tg), 'R': D.resample(fR, tg)}
    kin = {}
    for s in 'BR':
        P, Vv, A, Rm, pqr = D.kinematics(rs[s])
        kin[s] = dict(P=P, V=Vv, A=A, R=Rm, pqr=pqr, rs=rs[s])
    en = 'R' if own_side == 'B' else 'B'
    k, ke = kin[own_side], kin[en]
    o, F = D.build_obs(k, None, ke['P'], ke['V'])
    T = len(tg)
    H = int(V.H_S * HZ)
    cas = o[:, 12] * C.FPS_TO_KT
    alt = o[:, 2] * C.FT
    X, Y, TT = [], [], []
    for i in range(0, T - H, D.STRIDE):
        if alt[i] < min_alt or rs[own_side]['gap'][i:i + H].max() > .25 or rs[en]['gap'][i:i + H].max() > .25:
            continue
        ev, eu, es, ok = C.vel_frame(k['V'][i])
        if not ok:
            continue
        d = k['V'][i + H] / max(np.linalg.norm(k['V'][i + H]), 1.)
        f = C.features(o[i]).copy()
        f[list(V.DROP)] = 0.
        X.append(f)
        Y.append([math.atan2(d @ eu, d @ ev), math.atan2(d @ es, d @ ev), cas[i + H] - cas[i]])
        TT.append(tg[i])
    if not X:
        return None
    low = np.nonzero(alt < min_alt)[0]
    t_low = float(tg[low[0]]) if len(low) else None
    return np.array(X, np.float32), np.array(Y, np.float32), np.array(TT, np.float32), t_low


def one_file(args):
    path, meta = args
    out = []
    for (seed, idx, _), fr in D.pair_fights(D.load_csv(path)).items():
        ms = meta.get((seed, idx))
        if not ms:
            continue
        st, end = ms[0]['start'], (ms[0]['end'] or {})
        loser, reason = end.get('loser', '-'), end.get('reason')
        for own in 'BR':
            unit = 'DV_%s_%d_%05d_1' % (own, seed, idx)
            opp = 'DV_%s_%d_%05d_1' % ('R' if own == 'B' else 'B', seed, idx)
            result = 'loss' if loser == unit else ('win' if loser == opp else 'draw')
            skill = st.get('skill' + own, st.get('skill'))      # START carries skillB / skillR ('Excellent' = DCS Ace)
            if result == 'loss' and reason in KILL:
                continue                                   # shot down: not a teacher
            if skill not in ('Ace', 'Excellent') and result != 'win':
                continue
            r = samples_t(fr['B'], fr['R'], own)
            if r is None:
                continue
            X, Y, T, t_low = r
            if result == 'loss' and reason in DECK and t_low is not None:
                m = T < t_low - 30.
                X, Y = X[m], Y[m]
            if len(X) == 0:
                continue
            out.append((X, Y, dict(rec=path.split('/')[-1], seed=seed, idx=idx, own=own, skill=skill, result=result,
                                   reason=reason, gunwin=bool(result == 'win' and reason in KILL), n=int(len(X)))))
    return out


def build(out, lines, files, win_rep=2, workers=2):
    meta = D.load_logs([lines])
    meta = {k: v for k, v in meta.items()}
    Xs, Ys, fid, rows = [], [], [], []
    with Pool(workers) as p:
        for res in p.imap_unordered(one_file, [(f, meta) for f in files]):
            for X, Y, info in res:
                rep = win_rep if info['gunwin'] else 1
                info['fid'] = len(rows)
                rows.append(info)
                for _ in range(rep):
                    Xs.append(X); Ys.append(Y); fid.append(np.full(len(X), info['fid'], np.int32))
            print('file done, perspectives so far', len(rows), flush=True)
    X, Y = np.concatenate(Xs), np.concatenate(Ys)
    np.savez(out, X=X, Y=Y, fid=np.concatenate(fid), t=np.zeros(len(X), np.float32), rows=json.dumps(rows))
    from collections import Counter
    print('perspectives', len(rows), 'samples', len(X), 'gun-kill winners', sum(r['gunwin'] for r in rows))
    print('by skill/result', Counter((r['skill'], r['result']) for r in rows))
    print('label |turn angle| deg p50/p90', np.percentile(np.degrees(np.hypot(Y[:, 0], Y[:, 1])), [50, 90]).round(1))


if __name__ == '__main__':
    if sys.argv[1] == 'build':
        build(sys.argv[2], sys.argv[3], sys.argv[4:])
