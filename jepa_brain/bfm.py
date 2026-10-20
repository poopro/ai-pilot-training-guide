"""BFM policies for the arena benchmark (no frozen file is modified).

U  = UserPilot   : the user's idea. Nose on the enemy + a short velocity lead, closure-rate control,
                   overshoot / blow-through -> boom-and-zoom (climb, then re-engage from above).
M  = MilPolicy   : military-style receding-horizon search (Austin 1990 style). Enumerates 8^3 own tactic
                   sequences against 8 enemy-behaviour hypotheses on a point-mass model, scores with the
                   judge's own formula (attack time, position index, G), takes a robust (mean+worst-case)
                   value and hands the first tactic to the frozen-controller based TacticalPilot.
S  = ShieldMixin : predicted-closest-approach collision shield, optional on any pilot.
"""
import itertools
import math
import numpy as np
from common import repair, SETTINGS
from combat_v3.interface import validate_observation, geometry_from_observation
from combat_v3.controller import wrap_deg
from tactics import (TacticalPilot, PURSUE, LEAD, LAG, BREAK_IN, BREAK_OUT, HIGH_YOYO, LOW_YOYO, EXTEND, N_TACTICS)

FT = .3048
R_E = 6378137.0
G0 = 9.80665
KT = .514444


def frame(o):
    """Enemy position relative to own (north, east, DOWN) in m, own and enemy NED velocity in m/s."""
    lat, lat2 = math.radians(o[0]), math.radians(o[20])
    rel = np.array([(lat2 - lat) * R_E, math.radians(o[21] - o[1]) * R_E * math.cos((lat + lat2) / 2), -(o[22] - o[2]) * FT])
    return rel, o[6:9] * FT, o[23:26] * FT


# ----------------------------------------------------------------------------------------- shield
DEFAULT_SHIELD = dict(tcpa_s=2.0, miss_m=100., range_m=1500., min_dive_agl_m=3500.)


def shield_targets(o, roll_t, pitch_t, speed_t, cfg):
    rel, ov, ev = frame(o)
    d = float(np.linalg.norm(rel))
    if d > cfg['range_m']:
        return roll_t, pitch_t, speed_t, False
    vrel = ev - ov
    vv = float(np.dot(vrel, vrel))
    if vv < 1.:
        return roll_t, pitch_t, speed_t, False
    tcpa = -float(np.dot(rel, vrel)) / vv
    if tcpa <= 0. or tcpa > cfg['tcpa_s']:
        return roll_t, pitch_t, speed_t, False
    cpa = rel + vrel * tcpa
    if float(np.linalg.norm(cpa)) > cfg['miss_m']:
        return roll_t, pitch_t, speed_t, False
    dive = cpa[2] < -3. and o[2] * FT > cfg['min_dive_agl_m']      # enemy will pass above us -> go down
    pitch = o[4] + (-15. if dive else 15.)
    return 0., float(np.clip(pitch, -25., 40.)), 450., True


class ShieldMixin:
    shield_cfg = None
    shield_ticks = 0

    def enable_shield(self, cfg=None):
        self.shield_cfg = dict(DEFAULT_SHIELD, **(cfg or {}))

    def command(self, obs, roll_target, pitch_target, speed_target, rudder=0., safety=True):
        if self.shield_cfg is not None:
            o = validate_observation(obs)
            roll_target, pitch_target, speed_target, hit = shield_targets(o, roll_target, pitch_target, speed_target, self.shield_cfg)
            if hit:
                self.shield_ticks += 1
                rudder = 0.
        return super().command(obs, roll_target, pitch_target, speed_target, rudder, safety)


class ShieldedTacticalPilot(ShieldMixin, TacticalPilot):
    def __init__(self, shield=True):
        super().__init__()
        if shield:
            self.enable_shield()


# ----------------------------------------------------------------------------------------- U
class UserPilot(ShieldMixin, repair.RepairController):
    def __init__(self, tau_track=.25, hold_m=500., zoom=True, shield=False):
        super().__init__(SETTINGS, 'user')
        self.tau_track, self.hold_m, self.zoom = tau_track, hold_m, zoom
        self.zoom_left = 0
        self.cool = 0
        self.zoom_sign = 1.
        self.n_zoom = 0
        if shield:
            self.enable_shield()

    def set_tactic(self, t):
        pass

    def act(self, observation, residual=None, started=True):
        if not started:
            return np.array([0., 0., 0., .8]), False
        o = validate_observation(observation)
        geo = geometry_from_observation(o)
        rel, ov, ev = frame(o)
        d, closing, tas = geo['distance_m'], geo['closing_mps'], geo['own_tas_mps']
        agl, downward = o[2] * FT, o[8] * FT
        if self.cool > 0:
            self.cool -= 1
        # ---- overshoot detection -> boom-and-zoom
        if self.zoom and self.zoom_left <= 0 and self.cool <= 0 and agl > 2800:
            if (geo['blue_angle_deg'] > 105 and d < 1200) or (d < 350 and closing > 35):
                self.zoom_left, self.cool = 240, 480
                self.n_zoom += 1
                self.zoom_sign = 1. if geo['blue_az_deg'] >= 0 else -1.
        if self.zoom_left > 0:
            self.zoom_left -= 1
            if self.zoom_left < 120 and geo['blue_angle_deg'] < 70:
                self.zoom_left = 0
            self.mode = 'intercept'
            return self.command(o, 25. * self.zoom_sign, min(o[4] + 12., 32.), 450., 0.)
        # ---- tracking: nose on (enemy + short velocity lead); full intercept lead only when far
        near = d < 1100
        self.mode = 'track' if near else 'intercept'
        w_far = float(np.clip((d - 1200.) / 1500., 0., 1.))
        tau = w_far * min(10., d / max(tas, 150.)) + (1. - w_far) * self.tau_track
        aim = rel + ev * tau
        bearing = math.degrees(math.atan2(aim[1], aim[0])) % 360
        elev_aim = math.degrees(math.atan2(-aim[2], math.hypot(aim[0], aim[1])))
        heading_error = wrap_deg(bearing - o[5])
        if self.previous_bearing is None:
            self.bearing_rate = 0.
        else:
            rate = np.clip(wrap_deg(bearing - self.previous_bearing) * 60, -15, 15)
            self.bearing_rate = .9 * self.bearing_rate + .1 * rate
        self.previous_bearing = bearing
        ff = math.degrees(math.atan(tas * math.radians(self.bearing_rate) / G0))
        bank = float(np.clip(1.8 * heading_error + ff, -72, 72))
        altitude, enemy_altitude = o[2] * FT, o[22] * FT
        if near and geo['blue_angle_deg'] < 45:
            velocity = ev - ov
            horizontal = max(float(np.hypot(rel[0], rel[1])), 1.)
            horizontal_rate = float(np.dot(rel[:2], velocity[:2])) / horizontal
            elevation_rate = math.degrees((-horizontal * velocity[2] + rel[2] * horizontal_rate) / max(d * d, 1.))
            pitch = elev_aim + float(np.clip(.5 * elevation_rate, -4, 4))
        else:
            gamma = np.clip((enemy_altitude - altitude) * .012 + downward * .16, -8, 12)
            pitch = o[18] + gamma
        desired_close = float(np.clip((d - self.hold_m) * .07, -30, 65))
        speed = geo['enemy_equivalent_cas_kts'] + desired_close * 1.9438444924 * geo['cas_ratio']
        if abs(heading_error) > 45:
            speed = min(speed, 290.)
        speed = float(np.clip(speed, 260, 450))
        return self.command(o, float(np.clip(bank, -72, 72)), float(np.clip(pitch, -18, 25)), speed, 0.)


# ----------------------------------------------------------------------------------------- M
H_STRAIGHT, H_BL, H_BR, H_UP, H_DN, H_CONT = 8, 9, 10, 11, 12, 13
HYP_T = np.array([PURSUE, LEAD, H_STRAIGHT, H_BL, H_BR, H_UP, H_DN, H_CONT])
HYP_W = np.array([.22, .12, .10, .08, .08, .06, .04, .30])


def _wrap(a):
    return (a + 180.) % 360. - 180.


def _commands(S, O, tac, cr, cont_psi=0., cont_gam=0.):
    """Vectorised point-mass version of TacticalPilot's three targets (bank deg, flight-path deg, TAS m/s)."""
    dx, dy, dz = O['x'] - S['x'], O['y'] - S['y'], O['h'] - S['h']
    dh = np.hypot(dx, dy)
    d = np.sqrt(dh * dh + dz * dz) + 1e-6
    b0 = np.degrees(np.arctan2(dy, dx))
    el = np.degrees(np.arctan2(dz, dh + 1e-9))
    ex = O['V'] * np.cos(O['gam']) * np.cos(O['psi'])
    ey = O['V'] * np.cos(O['gam']) * np.sin(O['psi'])
    tl = np.minimum(10., d / np.maximum(S['V'], 150.))
    bl = np.degrees(np.arctan2(dy + ey * tl, dx + ex * tl))
    psi_d = np.degrees(S['psi'])
    herr0, dlead = _wrap(b0 - psi_d), _wrap(bl - b0)
    near = d < 1100.
    b = np.where((~near) & (np.abs(herr0) < 35.), b0 + np.clip(dlead, -20, 20) * .35, b0)
    b = np.where(tac == LEAD, b0 + np.clip(dlead, -30, 30) * .8, b)
    b = np.where(tac == LAG, np.where(np.abs(herr0) < 60., b0 - np.clip(dlead, -25, 25) * .6, b0), b)
    herr = _wrap(b - psi_d)
    lim = np.where(tac == LEAD, 80., 72.)
    bank = np.clip(1.8 * herr, -lim, lim)
    sgn = np.where(herr >= 0, 1., -1.)
    bank = np.where(tac == BREAK_IN, 78. * sgn, bank)
    bank = np.where(tac == BREAK_OUT, -78. * sgn, bank)
    bank = np.where(tac == HIGH_YOYO, bank * .6, bank)
    bank = np.where(tac == EXTEND, 0., bank)
    cg, sg = np.cos(S['gam']), np.sin(S['gam'])
    ang = np.degrees(np.arccos(np.clip((cg * (np.cos(S['psi']) * dx + np.sin(S['psi']) * dy) + sg * dz) / d, -1, 1)))
    base = np.clip((O['h'] - S['h']) * .012 - .16 * S['V'] * sg, -8., 12.)
    gam = np.where(near & (ang < 45.), np.clip(el, -18., 25.), base)
    gdeg = np.degrees(S['gam'])
    isb = (tac == BREAK_IN) | (tac == BREAK_OUT)
    gam = np.where(isb, gdeg + 3., gam)
    gam = np.where(tac == HIGH_YOYO, gam + 10., gam)
    gam = np.where(tac == LOW_YOYO, gam - 8., gam)
    gam = np.where(tac == EXTEND, 0., gam)
    vlo, vhi = 260 * KT / cr, 450 * KT / cr
    Vc = O['V'] + np.clip((d - 600.) * .07, -30., 65.)
    Vc = np.where(np.abs(herr) > 45., np.minimum(Vc, 290 * KT / cr), Vc)
    Vc = np.clip(Vc, vlo, vhi)
    Vc = np.where(isb, 420 * KT / cr, Vc)
    Vc = np.where(tac == HIGH_YOYO, np.minimum(Vc, 300 * KT / cr), Vc)
    Vc = np.where((tac == LOW_YOYO) | (tac == EXTEND), vhi, Vc)
    # enemy-behaviour hypotheses (ids >= 8)
    cb = np.clip(np.degrees(np.arctan(cont_psi * S['V'] / G0)), -78., 78.)
    bank = np.select([tac == H_STRAIGHT, tac == H_BL, tac == H_BR, (tac == H_UP) | (tac == H_DN), tac == H_CONT],
                     [0., -75., 75., 0., cb], bank)
    gam = np.select([tac == H_STRAIGHT, tac == H_BL, tac == H_BR, tac == H_UP, tac == H_DN, tac == H_CONT],
                    [0., 0., 0., 25., -20., gdeg + np.clip(np.degrees(cont_gam), -10., 10.)], gam)
    Vc = np.select([(tac == H_STRAIGHT) | (tac == H_CONT), (tac >= H_BL) & (tac <= H_DN)], [S['V'], vhi], Vc)
    brk = isb | (tac == H_BL) | (tac == H_BR)
    return bank, gam, Vc, brk


def _advance(S, bank_deg, gam_deg, Vc, brk, dt):
    phi_c = np.radians(bank_deg)
    S['phi'] = S['phi'] + np.clip((phi_c - S['phi']) / .35, -1.75, 1.75) * dt
    nh = 1. / np.maximum(np.cos(np.abs(S['phi'])), .2)
    nh = np.where(brk, np.minimum(nh * 1.35, 7.), nh)
    psi_dot = G0 * np.sign(S['phi']) * np.sqrt(np.maximum(nh * nh - 1., 0.)) / np.maximum(S['V'], 100.)
    gam_dot = np.clip((np.radians(gam_deg) - S['gam']) / .6, -.17, .17)
    nv = S['V'] * gam_dot / G0
    n2 = nh * nh + nv * nv
    vdot = np.clip(.5 * (Vc - S['V']), -3., 4.) - .2 * (n2 - 1.) - G0 * np.sin(S['gam'])
    S['psi'] = S['psi'] + psi_dot * dt
    S['gam'] = np.clip(S['gam'] + gam_dot * dt, -1.3, 1.3)
    S['V'] = np.clip(S['V'] + vdot * dt, 110., 330.)
    cg = np.cos(S['gam'])
    S['x'] = S['x'] + S['V'] * cg * np.cos(S['psi']) * dt
    S['y'] = S['y'] + S['V'] * cg * np.sin(S['psi']) * dt
    S['h'] = S['h'] + S['V'] * np.sin(S['gam']) * dt
    return n2


def _dfac(d):
    return np.select([d < 150., d < 500., d < 1500., d <= 3000.], [.1, 1.2, 1., .5], .1)


class MilPolicy:
    name = 'mil'

    def __init__(self, stages=2, stage_s=1.5, dt=.2, cone_deg=5., robust=.5, margin=300., w_energy=.6, w_range=1.5, hyp_w=None):
        self.stages, self.stage_s, self.dt = stages, stage_s, dt
        self.cone, self.robust, self.margin, self.w_energy, self.w_range = cone_deg, robust, margin, w_energy, w_range
        self.w = np.asarray(hyp_w if hyp_w is not None else HYP_W, dtype=float)
        self.seqs = np.array(list(itertools.product(range(N_TACTICS), repeat=stages)), dtype=np.int64)
        self.reset(None)
        self.last_q = None
        self.plan_ms = []

    def reset(self, cfg):
        self.cur = PURSUE
        self.prev_en = None
        self.psi_dot_e = 0.
        self.gam_dot_e = 0.

    @staticmethod
    def _kin(v):
        sp = float(np.linalg.norm(v))
        return sp, math.atan2(v[1], v[0]), math.atan2(-v[2], math.hypot(v[0], v[1]))

    def _score(self, own0, en0, cr):
        S_n, K = self.seqs.shape[0], len(HYP_T)
        N = S_n * K
        own = {k: np.full(N, float(v)) for k, v in own0.items()}
        en = {k: np.full(N, float(v)) for k, v in en0.items()}
        tac_seq = np.repeat(self.seqs, K, axis=0)
        hyp = np.tile(HYP_T, S_n)
        nsteps = int(round(self.stages * self.stage_s / self.dt))
        total = np.zeros(N)
        min_d = np.full(N, 1e9)
        min_h = np.full(N, 1e9)
        for i in range(nsteps):
            st = min(int(i * self.dt / self.stage_s), self.stages - 1)
            to = tac_seq[:, st]
            bo, go, vo, bko = _commands(own, en, to, cr)
            be, ge, ve, bke = _commands(en, own, hyp, cr, self.psi_dot_e, self.gam_dot_e)
            _advance(own, bo, go, vo, bko, self.dt)
            _advance(en, be, ge, ve, bke, self.dt)
            dx, dy, dz = en['x'] - own['x'], en['y'] - own['y'], en['h'] - own['h']
            d = np.sqrt(dx * dx + dy * dy + dz * dz) + 1e-6
            lx, ly, lz = dx / d, dy / d, dz / d
            def nose(S):
                c = np.cos(S['gam'])
                return c * np.cos(S['psi']), c * np.sin(S['psi']), np.sin(S['gam'])
            nxo, nyo, nzo = nose(own)
            nxe, nye, nze = nose(en)
            a_o = np.degrees(np.arccos(np.clip(nxo * lx + nyo * ly + nzo * lz, -1, 1)))
            a_e = np.degrees(np.arccos(np.clip(-(nxe * lx + nye * ly + nze * lz), -1, 1)))
            band = (d >= 152.4) & (d <= 914.4)
            att_o = band * np.clip(1. - a_o / self.cone, 0., 1.) ** 2
            att_e = band * np.clip(1. - a_e / self.cone, 0., 1.) ** 2
            df = _dfac(d)
            pos_o = (np.maximum(0., (90. - a_o) / 90.) + np.maximum(0., (90. - np.abs(180. - a_e)) / 90.)) * df
            pos_e = (np.maximum(0., (90. - a_e) / 90.) + np.maximum(0., (90. - np.abs(180. - a_o)) / 90.)) * df
            total += self.dt * (10000. * (att_o - att_e) + 60. * (pos_o - pos_e))
            min_d = np.minimum(min_d, d)
            min_h = np.minimum(min_h, own['h'])
        e_o = own['h'] + own['V'] ** 2 / (2 * G0)
        e_e = en['h'] + en['V'] ** 2 / (2 * G0)
        total += self.w_energy * (e_o - e_e)
        total -= self.w_range * np.maximum(d - 900., 0.)
        total -= 40000. * np.clip((150. - min_d) / 90., 0., 1.)
        total -= 20000. * np.clip((1500. - min_h) / 700., 0., 1.)
        return total.reshape(S_n, K)

    def plan(self, o, mask=None):
        import time
        t0 = time.perf_counter()
        o = validate_observation(o)
        rel, ov, ev = frame(o)
        so, po, go = self._kin(ov)
        se, pe, ge = self._kin(ev)
        if self.prev_en is not None:
            dt_dec = 20. / 60.
            pd = math.atan2(math.sin(pe - self.prev_en[0]), math.cos(pe - self.prev_en[0])) / dt_dec
            gd = (ge - self.prev_en[1]) / dt_dec
            self.psi_dot_e = .5 * self.psi_dot_e + .5 * pd
            self.gam_dot_e = .5 * self.gam_dot_e + .5 * gd
        self.prev_en = (pe, ge)
        phi_e = math.atan(self.psi_dot_e * se / G0)
        own0 = dict(x=0., y=0., h=o[2] * FT, V=so, psi=po, gam=go, phi=math.radians(o[3]))
        en0 = dict(x=rel[0], y=rel[1], h=o[22] * FT, V=se, psi=pe, gam=ge, phi=phi_e)
        cr = float(np.clip(o[12] / max(o[13], 1.), .4, 1.2))
        sc = self._score(own0, en0, cr)
        mean = sc @ self.w
        worst = sc[:, self.w >= .06].min(axis=1)
        val = (1. - self.robust) * mean + self.robust * worst
        first = self.seqs[:, 0]
        q = np.full(N_TACTICS, -1e18)
        for a in range(N_TACTICS):
            if mask is None or mask[a]:
                q[a] = val[first == a].max()
        best = int(q.argmax())
        if (mask is None or mask[self.cur]) and q[best] - q[self.cur] < self.margin:
            best = self.cur
        self.cur = best
        self.last_q = q
        self.plan_ms.append((time.perf_counter() - t0) * 1000.)
        return best

    def decide(self, feat, ob, arena):
        agl = ob[2] * FT
        mask = np.ones(N_TACTICS, dtype=bool)
        if agl < 2500:
            mask[LOW_YOYO] = False
        if agl < 1800:
            mask[[BREAK_IN, BREAK_OUT, HIGH_YOYO, LOW_YOYO]] = False
        return self.plan(ob, mask)


class FixedTactic:
    name = 'fixed'

    def __init__(self, t=PURSUE):
        self.t = t

    def reset(self, cfg):
        pass

    def decide(self, feat, ob, arena):
        return self.t


# ----------------------------------------------------------------------------------------- tuned pursuit
PARAM_SPEC = {   # name: (default, low, high)  -- defaults reproduce the frozen PURSUE exactly
    'kp_head': (1.8, 1.0, 3.0),
    'bank_lim': (72., 60., 82.),
    'hold_m': (600., 250., 800.),
    'close_gain': (.07, .03, .15),
    'lead_blend': (.35, 0., .8),
    'near_m': (1100., 700., 1600.),
    'elev_rate_gain': (.5, 0., 1.2),
    'ff_gain': (1., 0., 1.5),
}
PARAM_DEFAULT = {k: v[0] for k, v in PARAM_SPEC.items()}


class ParamPilot(ShieldMixin, TacticalPilot):
    """Frozen PURSUE law with its main constants exposed (defaults == RepairController.act, bit-exact)."""
    def __init__(self, params=None, shield=None):
        super().__init__()
        self.p = dict(PARAM_DEFAULT, **(params or {}))
        if shield:
            self.enable_shield(shield if isinstance(shield, dict) else None)

    def act(self, observation, residual=None, started=True):
        if not started:
            return np.array([0., 0., 0., .8]), False
        P = self.p
        o = validate_observation(observation)
        geo = geometry_from_observation(o)
        d = geo['distance_m']
        near = d < P['near_m']
        self.mode = 'track' if near else 'intercept'
        bearing = geo['bearing_deg']
        heading_error = wrap_deg(bearing - o[5])
        if not near and abs(heading_error) < 35:
            lead_delta = wrap_deg(geo['lead_bearing_deg'] - bearing)
            bearing += float(np.clip(lead_delta, -20, 20)) * P['lead_blend']
            heading_error = wrap_deg(bearing - o[5])
        if self.previous_bearing is None:
            self.bearing_rate = 0.
        else:
            rate = np.clip(wrap_deg(bearing - self.previous_bearing) * 60, -15, 15)
            self.bearing_rate = .9 * self.bearing_rate + .1 * rate
        self.previous_bearing = bearing
        feedforward = P['ff_gain'] * math.degrees(math.atan(geo['own_tas_mps'] * math.radians(self.bearing_rate) / 9.80665))
        bank = float(np.clip(P['kp_head'] * heading_error + feedforward, -P['bank_lim'], P['bank_lim']))
        altitude, enemy_altitude = o[2] * FT, o[22] * FT
        downward = o[8] * FT
        if near and geo['blue_angle_deg'] < 45:
            lat = math.radians(o[0]); lat2 = math.radians(o[20])
            rel = np.array([(lat2 - lat) * 6378137, math.radians(o[21] - o[1]) * 6378137 * math.cos((lat + lat2) / 2), -(o[22] - o[2]) * .3048])
            velocity = (o[23:26] - o[6:9]) * .3048
            horizontal = max(float(np.linalg.norm(rel[:2])), 1.)
            horizontal_rate = float(np.dot(rel[:2], velocity[:2])) / horizontal
            elevation_rate = math.degrees((-horizontal * velocity[2] + rel[2] * horizontal_rate) / max(d * d, 1.))
            pitch = geo['elevation_deg'] + float(np.clip(P['elev_rate_gain'] * elevation_rate, -4, 4))
        else:
            gamma = np.clip((enemy_altitude - altitude) * .012 + downward * .16, -8, 12)
            pitch = o[18] + gamma
        desired_close = float(np.clip((d - P['hold_m']) * P['close_gain'], -30, 65))
        speed = geo['enemy_equivalent_cas_kts'] + desired_close * 1.9438444924 * geo['cas_ratio']
        if abs(heading_error) > P.get('turn_cap_deg', 45.):
            speed = min(speed, P.get('turn_cap', 290.))
        speed = float(np.clip(speed, 260, 450))
        return self.command(o, float(np.clip(bank, -72, 72)), float(np.clip(pitch, -18, 25)), speed, 0.)


# ----------------------------------------------------------------------------------------- tail-chase defence
DEF_DEFAULT = dict(mode='break', ba_deg=110., asp_deg=45., range_m=1800., enter_s=1.0, hold_s=2.0, cool_s=.5, min_agl_m=1500.)
_DEF_TACTIC = {'break': BREAK_IN, 'out': BREAK_OUT, 'extend': EXTEND, 'hy': HIGH_YOYO, 'ly': LOW_YOYO, 'none': None}


class DefPilot(ParamPilot):
    """ParamPilot pursuit + a rule-based defensive reversal.

    Threat = enemy behind us (our nose > ba_deg off him), his velocity points at us (aspect proxy < asp_deg) and
    he is within range_m, persisting for enter_s.  While defending (at least hold_s) the TacticalPilot response
    `mode` flies (break / out / extend / hy / ly); mode 'none' only keeps the pursuit law (use with turn_cap).
    Uses only legal OBS quantities."""
    def __init__(self, params=None, shield=None, defense=None):
        super().__init__(params, shield)
        self.dcfg = dict(DEF_DEFAULT, **(defense or {}))
        self.threat_ticks = 0
        self.def_until = -1
        self.cool_until = -1
        self.k = 0
        self.n_def_ticks = 0
        self.n_def_entries = 0

    def act(self, observation, residual=None, started=True):
        if not started:
            return np.array([0., 0., 0., .8]), False
        c = self.dcfg
        self.k += 1
        resp = _DEF_TACTIC.get(c['mode'])
        if resp is not None:
            o = validate_observation(observation)
            geo = geometry_from_observation(o)
            threat = (geo['blue_angle_deg'] > c['ba_deg'] and geo['aspect_proxy_deg'] < c['asp_deg']
                      and geo['distance_m'] < c['range_m'] and o[2] * FT > c['min_agl_m'])
            self.threat_ticks = self.threat_ticks + 1 if threat else 0
            if self.k > self.def_until and self.k > self.cool_until and self.threat_ticks >= c['enter_s'] * 60:
                self.def_until = self.k + int(c['hold_s'] * 60)
                self.n_def_entries += 1
            if self.k <= self.def_until:
                if self.k == self.def_until:
                    self.cool_until = self.k + int(c['cool_s'] * 60)
                self.n_def_ticks += 1
                TacticalPilot.set_tactic(self, resp)
                return TacticalPilot.act(self, observation)
        return super().act(observation)
