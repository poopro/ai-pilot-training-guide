"""DCS imitation v2: learn INTENT, not the current load.

Differences from v1 (dcsvet_data/dcsvet_bc):
  * label = where the velocity vector points H s later, as two angles in the current velocity frame
    (up / side, rad) + CAS change; not the next-0.5 s lift (which the net copied from the current state)
  * the copy-cat inputs are removed (current lift direction sin/cos mu, AoA)
  * only the WINNER of fights that ended in a real gun kill (S_EVENT_UNIT_LOST / missing with a loser)
  * in the arena the intent is turned into a lift command (same law as finisher.py) and the finisher
    takes over at close range (arm 'dcsv2f:<weights>')

  python dcsvet_v2.py build OUT.npz LINES.log bucket1.csv.gz ...      (env DCSVET_HZ=15 DCSVET_STRIDE=2)
  python dcsvet_v2.py train DATA.npz OUT_weights.npz [epochs]
"""
import sys, json, math
import numpy as np
import dcsvet_core as C
try:                      # only the data-building code needs dcsvet_data (scipy); the pilot does not
    import dcsvet_data as D
except ImportError:
    D = None

DROP = (18, 19, 20)            # sin mu, cos mu, alpha: current-state copy-cat inputs
H_S = 2.0


def kill_fights(lines):
    """{idx: winner side} for fights that ended in a real kill."""
    out = {}
    for line in open(lines, encoding='utf-8', errors='replace'):
        i = line.find('DCSVET|END|')
        if i < 0:
            continue
        p = line[i:].strip().split('|')
        kv = dict(x.split('=', 1) for x in p[3:] if '=' in x)
        if kv.get('reason') in ('S_EVENT_UNIT_LOST', 'missing', 'S_EVENT_PILOT_DEAD') and kv.get('loser'):
            ls = kv['loser'].split('_')[1]
            out[int(p[2])] = 'R' if ls == 'B' else 'B'
    return out


def intent_samples(fB, fR, own_side, min_alt=1000.):
    HZ = D.HZ
    t0 = max(fB['t'][0], fR['t'][0]) + 1.5
    t1 = min(fB['t'][-1], fR['t'][-1]) - 1.0
    if t1 - t0 < 8:
        return None
    tg = np.arange(t0, t1, 1. / HZ)
    rs = {'B': D.resample(fB, tg), 'R': D.resample(fR, tg)}
    kin = {}
    for s in 'BR':
        P, V, A, Rm, pqr = D.kinematics(rs[s])
        kin[s] = dict(P=P, V=V, A=A, R=Rm, pqr=pqr, rs=rs[s])
    en = 'R' if own_side == 'B' else 'B'
    k, ke = kin[own_side], kin[en]
    o, F = D.build_obs(k, None, ke['P'], ke['V'])
    T = len(tg)
    H = int(H_S * HZ)
    cas = o[:, 12] * C.FPS_TO_KT
    X, Y = [], []
    for i in range(0, T - H, D.STRIDE):
        if o[i, 2] * C.FT < min_alt or rs[own_side]['gap'][i:i + H].max() > .25 or rs[en]['gap'][i:i + H].max() > .25:
            continue
        ev, eu, es, ok = C.vel_frame(k['V'][i])
        if not ok:
            continue
        d = k['V'][i + H] / max(np.linalg.norm(k['V'][i + H]), 1.)
        f = C.features(o[i]).copy()
        f[list(DROP)] = 0.
        X.append(f)
        Y.append([math.atan2(d @ eu, d @ ev), math.atan2(d @ es, d @ ev), cas[i + H] - cas[i]])
    if not X:
        return None
    return np.array(X, np.float32), np.array(Y, np.float32)


def build(out, lines, files):
    win = kill_fights(lines)
    Xs, Ys, fid, rows = [], [], [], []
    for f in files:
        for (seed, idx, _), fr in D.pair_fights(D.load_csv(f)).items():
            if idx not in win:
                continue
            r = intent_samples(fr['B'], fr['R'], win[idx])
            if r is None:
                continue
            Xs.append(r[0]); Ys.append(r[1]); fid.append(np.full(len(r[0]), len(rows), np.int32))
            rows.append(dict(fid=len(rows), rec=f.split('/')[-1], seed=seed, idx=idx, own=win[idx]))
    X, Y = np.concatenate(Xs), np.concatenate(Ys)
    np.savez(out, X=X, Y=Y, fid=np.concatenate(fid), t=np.zeros(len(X), np.float32), rows=json.dumps(rows))
    print('kill fights', len(win), 'used', len(rows), 'samples', len(X))
    print('label |turn angle| deg p50/p90', np.percentile(np.degrees(np.hypot(Y[:, 0], Y[:, 1])), [50, 90]).round(1))


class DcsV2Pilot:
    """Far: fly the learned 2 s intent through the lift vector.  Close: finisher.FinisherPilot law."""
    def __init__(self, weights, fin_cfg=None, every=4):
        from finisher import FinisherPilot, FIN_DEFAULT
        self.net = _load(weights)
        self.every = every
        self.tick = 0
        self.cmd = None
        if fin_cfg is None:
            fin_cfg = dict(aa_max=180., enter_deg=180., exit_deg=180., enter_m=3000., exit_m=3500., turn_cas=340., n_cap=8., merge_off_m=400.)
        # rec_v2 (2026-10-27) applies to the far-range low-level pilot as well as the finisher's
        self.low = C.LiftPilot(floor_m=1200., gains=dict(rec_v2=float(fin_cfg.get('rec_v2', 0.))))
        self.fin = FinisherPilot(self, fin_cfg)      # finisher wraps us: we are its 'base'
        self.last = self.low.last.copy()
        self.mode = 'intent'

    def set_tactic(self, t):
        pass

    def act_far(self, o):
        self.low.last = np.array(self.last, dtype=np.float64)
        if self.cmd is None or self.tick % self.every == 0:
            f = C.features(o).copy()
            f[list(DROP)] = 0.
            th_up, th_side, dcas = self.net(f)
            ev, eu, es, ok = C.vel_frame(o[6:9] * C.FT)
            V = max(float(np.linalg.norm(o[6:9] * C.FT)), 60.)
            dev = (th_up * eu + th_side * es) / H_S * 1.6          # reach the intended direction a bit early
            grav = np.array([0., 0., 9.80665])
            fv = V * dev - (grav - (grav @ ev) * ev)
            mu, n = C.lift_to_cmd(float(fv @ eu) / 9.80665, float(fv @ es) / 9.80665)
            cas = o[12] * C.FPS_TO_KT
            n = min(n, float(np.clip(3. + (cas - 250.) / 80. * 5.6, 3., 8.6)))
            self.cmd = (mu, n, float(np.clip(cas + dcas, 330., 480.)))
        self.tick += 1
        out, guard = self.low.command(o, *self.cmd)
        self.last = self.low.last.copy()
        return out, guard

    # FinisherPilot calls base.act(...) when it is not engaged
    def act(self, observation, residual=None, started=True):
        o = np.asarray(observation, dtype=np.float64)
        if self.fin.c.get('v2_shield'):
            # 2026-10-28: the far-range intent net has no collision shield (tuned2 has shield v3); when the finisher
            # hands back (< min_m and closing) or before it engages, use the finisher's CPA avoidance
            g = self.fin.geometry(o)
            threat, m = self.fin.collision_threat(g)
            if threat:
                self.n_shield = getattr(self, 'n_shield', 0) + 1
                self.low.last = np.array(self.last, dtype=np.float64)
                mu, n, cas = self.fin.avoid_cmd(o, g, m)
                out, guard = self.low.command(o, mu, n, cas)
                self.last = self.low.last.copy()
                self.cmd = None
                self.tick += 1
                return out, guard
        return self.act_far(o)


def _load(path):
    z = np.load(path, allow_pickle=True)
    nl = int(z['nlayers'])
    W = [z['arr_%d' % i] for i in range(nl)]
    b = [z['arr_%d' % (nl + i)] for i in range(nl)]
    xm, xs, ym, ys = z['xm'], z['xs'], z['ym'], z['ys']

    def f(x):
        h = (np.asarray(x, np.float64) - xm) / xs
        for i in range(nl):
            h = h @ W[i] + b[i]
            if i < nl - 1:
                h = np.tanh(h)
        return h * ys + ym
    return f


if __name__ == '__main__':
    if sys.argv[1] == 'build':
        build(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif sys.argv[1] == 'train':
        import dcsvet_bc
        dcsvet_bc.train(sys.argv[2], sys.argv[3], epochs=int(sys.argv[4]) if len(sys.argv) > 4 else 30)
