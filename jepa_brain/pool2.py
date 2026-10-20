"""Opponent pool v2 (held-out): maneuvering scripted reds, randomised-parameter pursuers,
an official-SAC checkpoint ladder and "controller as red" (league) opponents.

Importing this module chains one more patch on top of rollout_sac's, so every spawned worker that
imports rollout_bfm gets all of them.  rollout.py / opponents.py / sac_red.py are NOT modified.

Opponent kinds (use as --opponents names):
  weave      level turns, roll flips +-65 deg every 3-6 s
  jink       pursue 2-4 s, then 1-2.5 s random jink (roll +-40..78, flight-path -8..+10)
  vosc       wings level, +14 deg climb 5 s / -12 deg dive 5 s
  hturn      sustained level hard turn (70 deg bank) toward the enemy's initial side
  defender   pursues, but breaks into the attacker whenever his velocity points at it (<35 deg, <2000 m)
  pp0..pp5   ParamPilot pursuit with seeded random parameters (odd index also carries the collision shield)
  sac:<N>    official checkpoint model/jsbsim_sac_<N>_steps.zip   (e.g. sac:1600000, sac:25600000)
  sacc:<N>   competition-aligned checkpoint model_competition/competition_sac_<N>_steps.zip
  saccf      model_competition/competition_sac_final.zip
  ctl:<arm>  red flies one of our own blue arms (base, base_t3, tuned, user_nz_t, ...) -> head-to-head league
"""
import math
import numpy as np
import rollout
import rollout_sac                       # make sure its patch is installed first (sac314)
from common import BASE
from combat_v3.interface import validate_observation, geometry_from_observation
from combat_v3.controller import wrap_deg
from tactics import TacticalPilot, PURSUE, BREAK_IN
from bfm import ParamPilot, PARAM_SPEC, frame, FixedTactic

FT = .3048
TIGHT3 = dict(tcpa_s=2.0, miss_m=60., range_m=1000.)
MANEUVER = ('weave', 'jink', 'vosc', 'hturn', 'defender')
PARAMKINDS = tuple('pp%d' % i for i in range(6))
SAC_LADDER = ('sac:1600000', 'sac:10400000', 'sac:25600000', 'sac:50400000', 'sacc:1000000')
CTL = ('ctl:base', 'ctl:base_t3', 'ctl:tuned', 'ctl:user_nz_t')
POOL_V2 = MANEUVER + PARAMKINDS + SAC_LADDER          # held-out opponents for league evaluation

_SAC_CACHE = {}


def _sac_path(kind):
    if kind.startswith('sac:'):
        return BASE / 'model' / ('jsbsim_sac_%d_steps.zip' % int(kind[4:]))
    if kind.startswith('sacc:'):
        return BASE / 'model_competition' / ('competition_sac_%d_steps.zip' % int(kind[5:]))
    if kind == 'saccf':
        return BASE / 'model_competition' / 'competition_sac_final.zip'
    raise ValueError(kind)


def _load_sac(path):
    key = str(path)
    if key not in _SAC_CACHE:
        from stable_baselines3 import SAC
        import torch
        torch.set_num_threads(1)
        _SAC_CACHE[key] = SAC.load(key, device='cpu')
    return _SAC_CACHE[key]


class SacLadderRed:
    def __init__(self, kind):
        from sac_red import OfficialSacPlayer
        self.inner = OfficialSacPlayer(model=_load_sac(_sac_path(kind)))

    def act(self, obs, tick):
        return self.inner.act(obs, tick)


class ParamRed:
    """Pursuit with randomised (but fixed per index) constants -- same family, different tuning."""
    def __init__(self, idx):
        rng = np.random.default_rng(7000 + idx)
        params = {}
        for k, (d, lo, hi) in PARAM_SPEC.items():
            params[k] = float(lo + (hi - lo) * rng.uniform(.15, .85))
        self.params = params
        self.pilot = ParamPilot(params, shield=(TIGHT3 if idx % 2 == 1 else None))

    def act(self, obs, tick):
        return self.pilot.act(obs)[0]


class ManeuverRed:
    def __init__(self, kind, seed):
        self.kind = kind
        self.rng = np.random.default_rng(seed)
        self.pilot = TacticalPilot()
        self.hold_alt = None
        self.state = None
        self.until = 0
        self.cool_until = 0
        self.sign = 1. if self.rng.random() < .5 else -1.
        self.roll = 0.
        self.gam = 0.

    def _cmd(self, o, roll, pitch, speed):
        return self.pilot.command(o, float(np.clip(roll, -80, 80)), float(np.clip(pitch, -18, 25)), float(np.clip(speed, 260, 450)), 0.)[0]

    def act(self, obs, tick):
        o = validate_observation(obs)
        alt, down = o[2] * FT, o[8] * FT
        if self.hold_alt is None:
            self.hold_alt = alt
        hold = float(np.clip((self.hold_alt - alt) * .012 + down * .16, -8, 12))
        k = self.kind
        if alt < 2500. and k != 'vosc':                 # keep the opponent alive: plain pursuit near the ground
            self.pilot.set_tactic(PURSUE)
            return self.pilot.act(obs)[0]
        if k == 'weave':
            if tick >= self.until:
                self.sign = -self.sign
                self.until = tick + int(self.rng.uniform(3, 6) * 60)
            roll = 65. * self.sign
            ff = 3. * (1. / max(math.cos(math.radians(abs(roll))), .25) - 1.)
            return self._cmd(o, roll, o[18] + hold + ff, 340.)
        if k == 'jink':
            if tick >= self.until:
                if self.state == 'jink' or self.state is None:
                    self.state = 'pursue'
                    self.until = tick + int(self.rng.uniform(2, 4) * 60)
                else:
                    self.state = 'jink'
                    self.until = tick + int(self.rng.uniform(1, 2.5) * 60)
                    self.roll = float(self.rng.choice([-1., 1.]) * self.rng.uniform(40, 78))
                    self.gam = float(self.rng.uniform(-8, 10))
            if self.state == 'pursue':
                self.pilot.set_tactic(PURSUE)
                return self.pilot.act(obs)[0]
            return self._cmd(o, self.roll, o[18] + self.gam, 380.)
        if k == 'vosc':
            gam = 14. if (tick // 300) % 2 == 0 else -12.
            return self._cmd(o, 0., o[18] + gam, 340.)
        if k == 'hturn':
            if self.state is None:
                geo = geometry_from_observation(o)
                self.sign = 1. if wrap_deg(geo['bearing_deg'] - o[5]) >= 0 else -1.
                self.state = 'turn'
            roll = 70. * self.sign
            ff = 3. * (1. / max(math.cos(math.radians(abs(roll))), .25) - 1.)
            return self._cmd(o, roll, o[18] + hold + ff, 400.)
        if k == 'defender':
            if tick % 20 == 0 and tick >= self.cool_until and self.state != 'break':
                rel, ov, ev = frame(o)
                d = float(np.linalg.norm(rel))
                sp = float(np.linalg.norm(ev))
                if d < 2000. and sp > 1.:
                    ang = math.degrees(math.acos(float(np.clip(np.dot(ev, -rel) / (sp * max(d, 1.)), -1., 1.))))
                    if ang < 35.:
                        self.state = 'break'
                        self.until = tick + int(self.rng.uniform(1.5, 2.5) * 60)
            if self.state == 'break' and tick >= self.until:
                self.state = 'pursue'
                self.cool_until = tick + 60
            self.pilot.set_tactic(BREAK_IN if self.state == 'break' else PURSUE)
            return self.pilot.act(obs)[0]
        raise ValueError(k)


class CtlRed:
    """Red flies one of our own blue controllers (arms without a tactic planner)."""
    def __init__(self, arm):
        from rollout_bfm import make_arm            # lazy: rollout_bfm imports this module
        pilot, policy = make_arm(arm)
        if policy is not None and not isinstance(policy, FixedTactic):
            raise ValueError('ctl:%s needs a planner; only fixed-tactic / user arms can fly as red' % arm)
        if isinstance(policy, FixedTactic):
            pilot.set_tactic(policy.t)
        self.pilot = pilot

    def act(self, obs, tick):
        return self.pilot.act(obs)[0]


def build(kind, seed):
    if kind in MANEUVER:
        return ManeuverRed(kind, seed)
    if kind in PARAMKINDS:
        return ParamRed(int(kind[2:]))
    if kind.startswith('sac:') or kind.startswith('sacc:') or kind == 'saccf':
        return SacLadderRed(kind)
    if kind.startswith('ctl:'):
        return CtlRed(kind[4:])
    return None


_Prev = rollout.ScriptedRed


class _Wrap2:
    def __init__(self, kind, seed):
        self.kind = kind
        inner = build(kind, seed)
        self.inner = inner if inner is not None else _Prev(kind, seed)

    def act(self, obs, tick):
        return self.inner.act(obs, tick)


if rollout.ScriptedRed is not _Wrap2 and getattr(rollout.ScriptedRed, '__name__', '') != '_Wrap2':
    rollout.ScriptedRed = _Wrap2
