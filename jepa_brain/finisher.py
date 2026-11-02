"""Close-range gun finisher: 3D nose pursuit through the lift vector.

Wraps any base pilot (tuned2 by default). When the target is close, ahead of our nose and we are in its rear
hemisphere, a LiftPilot flies the lift vector so that the BODY X-AXIS (the judge's attack-angle reference) tracks
the line of sight; speed is used to hold ~hold_m.  Everything else (intercept, defence, collision shield of the
base law) stays with the base pilot.  Uses only OBS quantities.
"""
import math
import numpy as np
import dcsvet_core as C

G0 = 9.80665
FIN_DEFAULT = dict(enter_m=2400., exit_m=2900., enter_deg=35., exit_deg=55., aa_max=110.,
                   k_ang=2.2, k_ff=1.0, hold_m=500., k_spd=.12, n_cap=8.6, min_m=160., hca_headon=135.,
                   cas_min=280., cas_max=480., floor_m=1200., turn_deg=30., turn_cas=0., tcpa_s=3.0, miss_m=150., avoid_m=1500., merge_off_m=0.)


def nav(o):
    """NED vectors from the 26-double OBS."""
    o = np.asarray(o, dtype=np.float64)
    rel = C.rel_ned(o)                                  # own -> enemy, m
    v = o[6:9] * C.FT
    ve = o[23:26] * C.FT
    phi, th, psi = np.radians(o[3:6])
    R = C.dcm_body_to_ned(phi, th, psi)
    return rel, v, ve, R


class FinisherPilot:
    def __init__(self, base, cfg=None):
        self.base = base
        self.c = dict(FIN_DEFAULT, **(cfg or {}))
        self.low = C.LiftPilot(floor_m=self.c['floor_m'], gains=dict(rec_v2=float(self.c.get('rec_v2', 0.))))
        self.active = False
        self.n_fin_ticks = 0
        self.n_entries = 0
        self.telemetry = {}
        self.n_avoid_ticks = 0
        self.merge = False

    def set_tactic(self, t):
        if hasattr(self.base, 'set_tactic'):
            self.base.set_tactic(t)

    @property
    def mode(self):
        return 'finish' if self.active else getattr(self.base, 'mode', '')

    def geometry(self, o):
        rel, v, ve, R = nav(o)
        r = float(np.linalg.norm(rel))
        l = rel / max(r, 1.)
        nose = R[:, 0]
        ta = math.degrees(math.acos(float(np.clip(nose @ l, -1, 1))))            # our nose-to-target (judge angle)
        Ve = float(np.linalg.norm(ve))
        aa = math.degrees(math.acos(float(np.clip(ve @ l / max(Ve, 1.), -1, 1))))  # 0 = we are dead astern of him
        V = float(np.linalg.norm(v))
        hca = math.degrees(math.acos(float(np.clip(v @ ve / max(V * Ve, 1.), -1, 1))))
        closure = -float(rel @ (ve - v)) / max(r, 1.)
        return dict(rel=rel, v=v, ve=ve, R=R, r=r, l=l, nose=nose, ta=ta, aa=aa, hca=hca, V=V, closure=closure)

    def want(self, g):
        c = self.c
        if g['hca'] > c['hca_headon'] and g['closure'] > 150:      # head-on merge: never chase the snapshot
            self.merge = c['merge_off_m'] > 0 and g['r'] < c['enter_m']
            return self.merge                                       # merge mode: offset pass to our right
        self.merge = False
        if g['r'] < c['min_m'] and g['closure'] > 0:                # about to overshoot / collide: give it back
            return False
        if self.active:
            return g['r'] < c['exit_m'] and g['ta'] < c['exit_deg'] and g['aa'] < c['aa_max'] + 20
        return g['r'] < c['enter_m'] and g['ta'] < c['enter_deg'] and g['aa'] < c['aa_max']

    def lift_cmd(self, o, g):
        """Required specific force so the nose swings onto the LOS; returns (mu_deg, n_g, cas_kt)."""
        c = self.c
        v, l, nose, rel = g['v'], g['l'], g['nose'], g['rel']
        if self.merge:     # aim merge_off_m to the right of him (both jets using the rule pass left-to-left)
            right = np.cross(np.array([0., 0., 1.]), l)
            right /= max(np.linalg.norm(right), 1e-6)
            p = rel + c['merge_off_m'] * right
            l = p / max(np.linalg.norm(p), 1.)
        V = max(g['V'], 60.)
        ev, eu, es, ok = C.vel_frame(v)
        # direction the VELOCITY must take so that the nose (offset by AoA/sideslip) lies on the LOS
        d = l - (nose - ev)
        d /= max(np.linalg.norm(d), 1e-6)
        e = d - (d @ ev) * ev
        ang = math.atan2(float(np.linalg.norm(e)), float(d @ ev))
        ehat = e / max(np.linalg.norm(e), 1e-9)
        # LOS angular rate (vector of dl/dt), only the part perpendicular to our velocity
        rv = g['ve'] - v
        ldot = (rv - (rv @ l) * l) / max(g['r'], 1.)
        ldot -= (ldot @ ev) * ev
        dev = c['k_ang'] * ang * ehat + c['k_ff'] * ldot             # desired d(ev)/dt, rad/s
        grav = np.array([0., 0., G0])
        f = V * dev - (grav - (grav @ ev) * ev)                      # specific force perpendicular to v
        n_up, n_side = float(f @ eu) / G0, float(f @ es) / G0
        mu, n = C.lift_to_cmd(n_up, n_side)
        cas = o[12] * C.FPS_TO_KT
        n_lim = float(np.clip(3. + (cas - 250.) / 80. * 5.6, 3., c['n_cap']))   # corner-speed aware cap
        n = min(n, n_lim)
        # speed: hold hold_m behind; enemy CAS as the reference
        enemy_cas = cas * float(np.linalg.norm(g['ve'])) / V
        cas_t = enemy_cas + c['k_spd'] * (g['r'] - c['hold_m']) * 1.94384 - .05 * max(g['closure'], 0.) * 1.94384 * (g['r'] < 900)
        if c['turn_cas'] > 0 and math.degrees(ang) > c['turn_deg']:   # turning fight: fly corner speed, full power
            cas_t = max(cas_t, c['turn_cas'])
        cas_t = float(np.clip(cas_t, c['cas_min'], c['cas_max']))
        return mu, n, cas_t, math.degrees(ang)

    def collision_threat(self, g):
        """Time / distance of closest approach on straight lines; returns (threat, miss vector at CPA)."""
        c = self.c
        rv = g['ve'] - g['v']
        vv = float(rv @ rv)
        if vv < 1. or g['r'] > c['avoid_m']:
            return False, None
        tc = -float(g['rel'] @ rv) / vv
        if not 0. < tc < c['tcpa_s']:
            return False, None
        m = g['rel'] + rv * tc
        return float(np.linalg.norm(m)) < c['miss_m'], m

    def avoid_cmd(self, o, g, m):
        """Pull the lift vector away from where he will be at closest approach."""
        ev, eu, es, ok = C.vel_frame(g['v'])
        away = -(m - (m @ ev) * ev)
        if np.linalg.norm(away) < 1.:                       # dead-centre: go up relative to our velocity
            away = eu.copy()
        mu = math.degrees(math.atan2(float(away @ es), float(away @ eu)))
        cas = o[12] * C.FPS_TO_KT
        n = float(np.clip(3. + (cas - 250.) / 80. * 5.6, 3., self.c['n_cap']))
        return mu, n, max(cas, 350.)

    def act(self, observation, residual=None, started=True):
        if not started:
            return self.base.act(observation, residual, started)
        o = np.asarray(observation, dtype=np.float64)
        g = self.geometry(o)
        w = self.want(g)
        if w and not self.active:
            self.n_entries += 1
            self.low.last = np.array(self.base.last, dtype=np.float64).copy() if hasattr(self.base, 'last') else self.low.last
            self.low.ni = 0.; self.low.si = 0.; self.low.recovering = False
        if not w and self.active and hasattr(self.base, 'last'):
            self.base.last = self.low.last.copy()
        self.active = w
        if not w:
            return self.base.act(observation, residual, started)
        self.n_fin_ticks += 1
        threat, m = self.collision_threat(g)
        if threat:
            self.n_avoid_ticks += 1
            mu, n, cas_t = self.avoid_cmd(o, g, m)
            ang = float('nan')
        else:
            mu, n, cas_t, ang = self.lift_cmd(o, g)
        out, guard = self.low.command(o, mu, n, cas_t)
        self.telemetry = dict(r=g['r'], ta=g['ta'], aa=g['aa'], mu=mu, n=n, cas_t=cas_t, ang=ang, mode=self.low.mode)
        return out, guard
