"""DCSVET data: DCS export CSV (+ dcs.log) -> behaviour-cloning samples.

Per fight and per perspective (B as own / R as own) every 1/30 s:
  X  = dcsvet_core.features(obs26)   obs26 rebuilt exactly like the combat_v3 ICD
  Y  = [n_up, n_side, dcas_kt]       lift vector (g) in the own velocity frame, averaged over t+0.1..t+0.6 s,
                                     and CAS change over the next 2 s
Usage:
  python dcsvet_data.py OUT.npz rec1.csv [rec2.csv ...] [--log dcs.log ...]
"""
import sys, re, math, csv, json
from collections import defaultdict
import os
import numpy as np
from scipy.signal import savgol_filter
import dcsvet_core as C

R_E = 6378137.
LAT0, LON0 = 23.060552, 121.948555
HZ = float(os.environ.get('DCSVET_HZ', 30))
STRIDE = int(os.environ.get('DCSVET_STRIDE', 1))
G = np.array([0., 0., C.G0])                    # NED gravity


# ------------------------------------------------------------------------------------------------ loading
def load_csv(path):
    tracks = defaultdict(lambda: defaultdict(list))
    import gzip
    opener = (lambda q: gzip.open(q, 'rt', newline='')) if str(path).endswith('.gz') else (lambda q: open(q, newline=''))
    with opener(path) as f:
        for r in csv.DictReader(f):
            tr = tracks[r['name']]
            tr['t'].append(float(r['t']))
            tr['n'].append(float(r['x'])); tr['e'].append(float(r['z'])); tr['d'].append(-float(r['y']))
            tr['hdg'].append(float(r['hdg'])); tr['pitch'].append(float(r['pitch'])); tr['bank'].append(float(r['bank']))
    out = {}
    for name, tr in tracks.items():
        a = {k: np.asarray(v, dtype=np.float64) for k, v in tr.items()}
        o = np.argsort(a['t'], kind='stable')
        a = {k: v[o] for k, v in a.items()}
        keep = np.concatenate([[True], np.diff(a['t']) > 1e-6])
        out[name] = {k: v[keep] for k, v in a.items()}
    return out


NAME_RE = re.compile(r'^DV_([BR])_(\d+)_(\d+)_1$')


def pair_fights(tracks, tag=''):
    fights = defaultdict(dict)
    for name, tr in tracks.items():
        m = NAME_RE.match(name)
        if not m:
            continue
        side, seed, idx = m.group(1), int(m.group(2)), int(m.group(3))
        fights[(seed, idx, tag)][side] = tr
    return {k: v for k, v in fights.items() if 'B' in v and 'R' in v}


def load_logs(paths):
    """(seed, idx) -> list of {'start':{...}, 'end':{...}, 'hits':{...}} in log order."""
    meta = defaultdict(list)
    cur = {}
    for p in paths:
        for line in open(p, encoding='utf-8', errors='replace'):
            i = line.find('DCSVET|')
            if i < 0:
                continue
            parts = line[i:].strip().split('|')
            kind = parts[1]
            if kind == 'START':
                kv = dict(x.split('=', 1) for x in parts[3:] if '=' in x)
                seed = int(kv.get('seed', 0)) % 100000
                rec = {'start': kv, 'end': None, 'hits': {}}
                meta[(seed, int(parts[2]))].append(rec)
                cur[int(parts[2])] = rec
            elif kind == 'END':
                kv = dict(x.split('=', 1) for x in parts[3:] if '=' in x)
                rec = cur.get(int(parts[2]))
                if rec is not None and rec['end'] is None:
                    rec['end'] = kv
    return meta


# ------------------------------------------------------------------------------------------------ kinematics
def resample(tr, tg):
    """Linear resample of positions / attitude to grid tg; returns dict + max raw gap around each grid point."""
    t = tr['t']
    out = {k: np.interp(tg, t, tr[k]) for k in ('n', 'e', 'd', 'pitch')}
    out['hdg'] = np.interp(tg, t, np.unwrap(tr['hdg']))
    out['bank'] = np.interp(tg, t, np.unwrap(tr['bank']))
    j = np.clip(np.searchsorted(t, tg), 1, len(t) - 1)
    out['gap'] = t[j] - t[j - 1]
    return out


def dcm_series(phi, theta, psi):
    return np.stack([C.dcm_body_to_ned(a, b, c) for a, b, c in zip(phi, theta, psi)])


def kinematics(rs, win_s=.5):
    w = int(round(win_s * HZ)) | 1
    dt = 1. / HZ
    P = np.stack([rs['n'], rs['e'], rs['d']], 1)
    V = savgol_filter(P, w, 3, deriv=1, delta=dt, axis=0)
    A = savgol_filter(P, w, 3, deriv=2, delta=dt, axis=0)
    phi, th, psi = rs['bank'], rs['pitch'], rs['hdg']
    Rm = dcm_series(phi, th, psi)                                  # body -> NED
    # body rates: Omega_hat = R^T dR/dt (smoothed derivative of attitude angles via Euler kinematics)
    phid = savgol_filter(phi, w, 3, deriv=1, delta=dt)
    thd = savgol_filter(th, w, 3, deriv=1, delta=dt)
    psid = savgol_filter(psi, w, 3, deriv=1, delta=dt)
    p = phid - psid * np.sin(th)
    q = thd * np.cos(phi) + psid * np.cos(th) * np.sin(phi)
    r = -thd * np.sin(phi) + psid * np.cos(th) * np.cos(phi)
    return P, V, A, Rm, np.stack([p, q, r], 1)


def build_obs(own, enemy, Pe, Ve):
    """own: dict with P, V, A, R, pqr, rs; returns (T, 26) obs and specific force (T,3)."""
    P, V, A, Rm, pqr = own['P'], own['V'], own['A'], own['R'], own['pqr']
    T = len(P)
    o = np.zeros((T, 26))
    cl = math.cos(math.radians(LAT0))
    o[:, 0] = LAT0 + np.degrees(P[:, 0] / R_E)
    o[:, 1] = LON0 + np.degrees(P[:, 1] / (R_E * cl))
    o[:, 2] = -P[:, 2] / C.FT
    o[:, 3] = np.degrees(C_wrap(own['rs']['bank']))
    o[:, 4] = np.degrees(own['rs']['pitch'])
    o[:, 5] = np.degrees(own['rs']['hdg']) % 360.
    o[:, 6:9] = V / C.FT
    o[:, 9:12] = pqr
    tas = np.linalg.norm(V, axis=1)
    o[:, 13] = tas / C.FT
    o[:, 12] = np.array([C.tas_to_cas(v, -d) for v, d in zip(tas, P[:, 2])]) / C.FT
    F = A - G                                                       # specific force, NED
    vb = np.einsum('tji,tj->ti', Rm, V)                             # body velocity (R^T v)
    fb = np.einsum('tji,tj->ti', Rm, F)
    o[:, 14] = fb[:, 2] / C.G0
    o[:, 15:18] = vb / C.FT
    o[:, 18] = np.degrees(np.arctan2(vb[:, 2], vb[:, 0]))
    o[:, 19] = np.degrees(np.arcsin(np.clip(vb[:, 1] / np.maximum(tas, 1.), -1, 1)))
    o[:, 20] = LAT0 + np.degrees(Pe[:, 0] / R_E)
    o[:, 21] = LON0 + np.degrees(Pe[:, 1] / (R_E * cl))
    o[:, 22] = -Pe[:, 2] / C.FT
    o[:, 23:26] = Ve / C.FT
    return o, F


def C_wrap(x):
    return (x + math.pi) % (2 * math.pi) - math.pi


def lift_components(V, F):
    """(n_up, n_side, frame_ok) of the specific force perpendicular to V, per sample."""
    out = np.zeros((len(V), 3))
    for i in range(len(V)):
        ev, eu, es, ok = C.vel_frame(V[i])
        f = F[i] - np.dot(F[i], ev) * ev
        out[i] = (np.dot(f, eu) / C.G0, np.dot(f, es) / C.G0, float(ok))
    return out


def fight_samples(fB, fR, lead=None, horizon_s=2.):
    if lead is None:
        lead = (max(1, int(round(.1 * HZ))), max(2, int(round(.6 * HZ))))
    t0 = max(fB['t'][0], fR['t'][0]) + 1.5
    t1 = min(fB['t'][-1], fR['t'][-1]) - 1.0
    if t1 - t0 < 5:
        return None
    tg = np.arange(t0, t1, 1. / HZ)
    rs = {'B': resample(fB, tg), 'R': resample(fR, tg)}
    kin = {}
    for s in 'BR':
        P, V, A, Rm, pqr = kinematics(rs[s])
        kin[s] = dict(P=P, V=V, A=A, R=Rm, pqr=pqr, rs=rs[s])
    H = int(horizon_s * HZ)
    res = []
    for own, en in (('B', 'R'), ('R', 'B')):
        k, ke = kin[own], kin[en]
        o, F = build_obs(k, None, ke['P'], ke['V'])
        L = lift_components(k['V'], F)
        T = len(tg)
        valid = np.ones(T, bool)
        valid &= (rs[own]['gap'] < .25) & (rs[en]['gap'] < .25)
        valid &= L[:, 2] > 0
        valid &= o[:, 2] * C.FT > 30.
        X = np.zeros((T, C.N_FEAT), np.float32)
        sel = np.zeros(T, bool)
        sel[::STRIDE] = True
        sel &= valid
        for i in np.nonzero(sel)[0]:
            X[i] = C.features(o[i])
        Y = np.full((T, 3), np.nan)
        cas_kt = o[:, 12] * C.FPS_TO_KT
        a, b = lead
        for i in range(T - max(b, H)):
            if not valid[i:i + max(b, H)].all():
                continue
            Y[i, 0] = L[i + a:i + b, 0].mean()
            Y[i, 1] = L[i + a:i + b, 1].mean()
            Y[i, 2] = cas_kt[i + H] - cas_kt[i]
        m = np.isfinite(Y).all(1) & sel
        # attitude-vs-trajectory consistency: body-up mu vs lift mu (only where loaded)
        mu_body = np.zeros(T)
        for i in np.nonzero(sel)[0]:
            mu_body[i] = C.body_up_mu(*np.radians(o[i, 3:6]), *C.vel_frame(k['V'][i])[:3])
        mu_lift = np.degrees(np.arctan2(L[:, 1], L[:, 0]))
        loaded = (np.hypot(L[:, 0], L[:, 1]) > 2.) & sel
        res.append(dict(own=own, t=tg, obs=o, X=X, Y=Y, mask=m, lift=L,
                        mu_err=C.wrap180(mu_body - mu_lift), loaded=loaded))
    return res


def main(argv):
    out = argv[0]
    logs = []
    recs = []
    min_alt, doom_s = 1000., 30.     # drop own samples below min_alt; drop the last doom_s s before a deck/crash loser first went below it
    i = 1
    while i < len(argv):
        if argv[i] == '--log':
            logs.append(argv[i + 1]); i += 2
        elif argv[i] == '--min_alt':
            min_alt = float(argv[i + 1]); i += 2
        elif argv[i] == '--doom_s':
            doom_s = float(argv[i + 1]); i += 2
        else:
            recs.append(argv[i]); i += 1
    meta = load_logs(logs) if logs else {}
    Xs, Ys, info = [], [], []
    rows = []
    mu_errs = []
    for ri, rp in enumerate(recs):
        fights = pair_fights(load_csv(rp), tag=str(ri))
        for (seed, idx, tag), f in sorted(fights.items()):
            res = fight_samples(f['B'], f['R'])
            if res is None:
                continue
            ends = [m['end'] for m in meta.get((seed, idx), []) if m['end']]
            end = ends[0] if ends else {}
            starts = [m['start'] for m in meta.get((seed, idx), [])]
            st = starts[0] if starts else {}
            for r in res:
                own_unit = 'DV_%s_%d_%05d_1' % (r['own'], seed, idx)
                opp_unit = 'DV_%s_%d_%05d_1' % ('R' if r['own'] == 'B' else 'B', seed, idx)
                loser = end.get('loser')
                result = 'loss' if loser == own_unit else ('win' if loser == opp_unit else 'draw')
                alt_m = r['obs'][:, 2] * C.FT
                low = alt_m < min_alt
                m = r['mask'] & ~low
                doomed = False
                if result == 'loss' and end.get('reason') in ('deck', 'softdeck', 'S_EVENT_CRASH', 'S_EVENT_PILOT_DEAD', 'S_EVENT_EJECTION') and low.any():
                    t_low = r['t'][np.argmax(low)]
                    m &= r['t'] < t_low - doom_s
                    doomed = True
                Xs.append(r['X'][m]); Ys.append(r['Y'][m])
                fid = len(rows)
                info.append(np.stack([np.full(m.sum(), fid), r['t'][m]], 1))
                mu_errs.append(r['mu_err'][r['loaded']])
                L = r['lift']
                rows.append(dict(fid=fid, rec=rp.split('/')[-1], seed=seed, idx=idx, own=r['own'],
                                 n=int(m.sum()), dur=float(r['t'][-1] - r['t'][0]),
                                 reason=end.get('reason'), loser=end.get('loser'), result=result, doomed=doomed,
                                 n_low_dropped=int((r['mask'] & low).sum()),
                                 dist_ft=st.get('dist_ft'), side=st.get('side'), skill=st.get('skill' + r['own'], st.get('skill')),
                                 skill_opp=st.get('skill' + ('R' if r['own'] == 'B' else 'B'), st.get('skill')), slot=st.get('slot'),
                                 alt_min_m=float(r['obs'][:, 2].min() * C.FT),
                                 n_p95=float(np.percentile(np.hypot(L[:, 0], L[:, 1]), 95)),
                                 mu_err_med=float(np.median(np.abs(r['mu_err'][r['loaded']]))) if r['loaded'].any() else None))
    X = np.concatenate(Xs).astype(np.float32)
    Y = np.concatenate(Ys).astype(np.float32)
    I = np.concatenate(info)
    np.savez_compressed(out, X=X, Y=Y, fid=I[:, 0].astype(np.int32), t=I[:, 1].astype(np.float32),
                        rows=json.dumps(rows))
    me = np.abs(np.concatenate(mu_errs)) if mu_errs else np.array([np.nan])
    print('samples', len(X), 'perspectives', len(rows))
    print('mu consistency (body-up vs lift, |n|>2): median %.1f deg, p90 %.1f deg' % (np.median(me), np.percentile(me, 90)))
    if len(rows) <= 40:
        for r in rows:
            print(r)
    from collections import Counter
    print('results', Counter(r['result'] for r in rows), 'reasons', Counter(r['reason'] for r in rows if r['own'] == 'B'))
    print('doomed perspectives', sum(r['doomed'] for r in rows), 'low samples dropped', sum(r['n_low_dropped'] for r in rows))
    return X, Y, rows


if __name__ == '__main__':
    main(sys.argv[1:])
