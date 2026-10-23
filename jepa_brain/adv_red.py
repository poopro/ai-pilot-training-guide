"""Adversarial opponent family F (2026-10-23): a parametric tactical red with a WIDER turn envelope.

Why: every scripted red so far flies the same frozen RepairController law as our own pilots, and
ParamPilot.act clips the bank target at +-72 deg no matter what bank_lim says, so no opponent ever
turned hard. AdvRed lets the bank target go up to bank_cap (60-88 deg; the frozen low-level command()
still caps pull at ~8.5 G) and adds three rule-based tactical layers whose thresholds are searched:

  opening   : for the first open_s seconds fly open_tac
  defensive : enemy behind us (our nose > def_ata off the LOS), his velocity pointing at us (< 45 deg),
              range < def_range  ->  def_tac for def_hold seconds (then 1 s cool-down)
  offensive : range < off_range and our nose < off_ata off the LOS  ->  off_tac
  otherwise : pursuit with the searched constants

All parameters live in [0, 1] (CMA-ES space) and are decoded by decode(). Use as opponent kind
'adv:<json-file-stem>' (see pool3.py) or build AdvRed(params) directly.
"""
import math
import numpy as np
import common  # noqa: F401  (puts the official AirCombat_Train_Test folder on sys.path)
from combat_v3.interface import validate_observation, geometry_from_observation
from combat_v3.controller import wrap_deg
from tactics import TacticalPilot, PURSUE, LEAD, LAG, BREAK_IN, BREAK_OUT, HIGH_YOYO, LOW_YOYO, EXTEND
from bfm import frame

FT = .3048
OPEN_TACS = (PURSUE, BREAK_OUT, LAG, EXTEND, HIGH_YOYO, LEAD)
DEF_TACS = (BREAK_IN, BREAK_OUT, HIGH_YOYO, LOW_YOYO, EXTEND)
OFF_TACS = (PURSUE, LEAD, LAG, HIGH_YOYO)
TAC_NAMES = {PURSUE: 'pursue', LEAD: 'lead', LAG: 'lag', BREAK_IN: 'break_in', BREAK_OUT: 'break_out',
             HIGH_YOYO: 'high_yoyo', LOW_YOYO: 'low_yoyo', EXTEND: 'extend'}

# name: (low, high) for continuous, or tuple of choices for categorical
SPEC = [
    ('kp_head', (1.0, 3.0)), ('hold_m', (250., 1200.)), ('close_gain', (.03, .15)), ('lead_blend', (0., .8)),
    ('near_m', (700., 1600.)), ('elev_rate_gain', (0., 1.2)), ('ff_gain', (0., 1.5)), ('turn_cap_deg', (30., 70.)),
    ('turn_cap', (240., 380.)), ('bank_cap', (60., 88.)),
    ('open_s', (0., 20.)), ('open_tac', OPEN_TACS),
    ('def_range', (800., 3000.)), ('def_ata', (90., 150.)), ('def_tac', DEF_TACS), ('def_hold', (1., 5.)),
    ('off_range', (500., 2500.)), ('off_ata', (5., 45.)), ('off_tac', OFF_TACS),
]
DIM = len(SPEC)


def decode(x):
    x = np.clip(np.asarray(x, dtype=float), 0., 1.)
    p = {}
    for (name, rng), v in zip(SPEC, x):
        if name.endswith('_tac'):
            p[name] = int(rng[min(int(v * len(rng)), len(rng) - 1)])
        else:
            p[name] = float(rng[0] + (rng[1] - rng[0]) * v)
    return p


def describe(p):
    q = dict(p)
    for k in ('open_tac', 'def_tac', 'off_tac'):
        q[k] = TAC_NAMES[p[k]]
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in q.items()}


class AdvPilot(TacticalPilot):
    def __init__(self, params):
        super().__init__()
        self.p = dict(params)

    def act(self, observation, residual=None, started=True):
        if self.tactic != PURSUE:
            return self._other(observation)
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
        ff = P['ff_gain'] * math.degrees(math.atan(geo['own_tas_mps'] * math.radians(self.bearing_rate) / 9.80665))
        cap = P['bank_cap']
        bank = float(np.clip(P['kp_head'] * heading_error + ff, -cap, cap))
        altitude, enemy_altitude = o[2] * FT, o[22] * FT
        downward = o[8] * FT
        if near and geo['blue_angle_deg'] < 45:
            lat = math.radians(o[0]); lat2 = math.radians(o[20])
            rel = np.array([(lat2 - lat) * 6378137, math.radians(o[21] - o[1]) * 6378137 * math.cos((lat + lat2) / 2), -(o[22] - o[2]) * FT])
            velocity = (o[23:26] - o[6:9]) * FT
            horizontal = max(float(np.linalg.norm(rel[:2])), 1.)
            horizontal_rate = float(np.dot(rel[:2], velocity[:2])) / horizontal
            elevation_rate = math.degrees((-horizontal * velocity[2] + rel[2] * horizontal_rate) / max(d * d, 1.))
            pitch = geo['elevation_deg'] + float(np.clip(P['elev_rate_gain'] * elevation_rate, -4, 4))
        else:
            gamma = np.clip((enemy_altitude - altitude) * .012 + downward * .16, -8, 12)
            pitch = o[18] + gamma
        desired_close = float(np.clip((d - P['hold_m']) * P['close_gain'], -30, 65))
        speed = geo['enemy_equivalent_cas_kts'] + desired_close * 1.9438444924 * geo['cas_ratio']
        if abs(heading_error) > P['turn_cap_deg']:
            speed = min(speed, P['turn_cap'])
        speed = float(np.clip(speed, 260, 450))
        return self.command(o, bank, float(np.clip(pitch, -18, 25)), speed, 0.)

    def _other(self, observation):
        # non-pursuit tactics use the frozen TacticalPilot targets unchanged (break / lead up to 80 deg bank)
        cmd, guard = TacticalPilot.act(self, observation)
        return cmd, guard


class AdvRed:
    """Opponent object for rollout.ScriptedRed-style use: act(obs, tick) -> 4-dim command."""
    def __init__(self, params, seed=0):
        self.p = dict(params)
        self.pilot = AdvPilot(self.p)
        self.state, self.until, self.cool = None, 0, 0

    def _decide(self, o, tick):
        P = self.p
        t = tick / 60.
        if t < P['open_s']:
            return P['open_tac']
        if self.state == 'def' and tick < self.until:
            return P['def_tac']
        if self.state == 'def':
            self.state, self.cool = None, tick + 60
        rel, ov, ev = frame(o)
        d = float(np.linalg.norm(rel))
        so, se = float(np.linalg.norm(ov)), float(np.linalg.norm(ev))
        if so < 1. or se < 1. or d < 1.:
            return PURSUE
        ata = math.degrees(math.acos(float(np.clip(np.dot(ov, rel) / (so * d), -1., 1.))))      # our nose off the LOS
        threat = math.degrees(math.acos(float(np.clip(np.dot(ev, -rel) / (se * d), -1., 1.))))  # his velocity vs LOS to us
        agl_ok = o[2] * FT > 2500.
        if tick >= self.cool and agl_ok and d < P['def_range'] and ata > P['def_ata'] and threat < 45.:
            self.state, self.until = 'def', tick + int(P['def_hold'] * 60)
            return P['def_tac']
        if d < P['off_range'] and ata < P['off_ata']:
            return P['off_tac'] if (agl_ok or P['off_tac'] != HIGH_YOYO) else PURSUE
        return PURSUE

    def act(self, obs, tick):
        o = validate_observation(obs)
        if tick % 20 == 0:
            self.pilot.set_tactic(self._decide(o, tick))
        return self.pilot.act(obs)[0]
