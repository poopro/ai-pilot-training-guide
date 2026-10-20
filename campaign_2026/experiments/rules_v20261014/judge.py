"""Publication/LINE-derived local judge, not certified official Host code.

Inputs belong to the private simulation judge, never the deployed policy.
Call once for each completed 60 Hz physics step after START. Frozen historical
judges and candidate sources are not imported or modified.
"""
from dataclasses import dataclass
import math

HZ = 60
ROUND_TICKS = 18000
KILL_TICKS = 180
FT_TO_M = .3048


@dataclass(frozen=True)
class RuleProfile:
    # Required choices expose disagreements/unstated details instead of hiding
    # them in a single supposedly official default.
    angle_source: str
    altitude_basis: str
    distance_edge_policy: str

    def __post_init__(self):
        if self.angle_source not in ('pdf_20261008_2deg', 'line_20261014_1deg'):
            raise ValueError('Choose the published2deg or later LINE1deg profile')
        if self.altitude_basis not in ('AGL', 'HSL'):
            raise ValueError('Altitude datum is not specified by the documents; choose explicitly')
        if self.distance_edge_policy not in ('left_bin', 'right_bin'):
            raise ValueError('Exact500m/1500m position-factor ties need an explicit choice')

    @property
    def attack_angle_deg(self):
        return 1. if self.angle_source == 'line_20261014_1deg' else 2.


@dataclass(frozen=True)
class Frame:
    distance_m: float
    blue_ta_deg: float
    red_ta_deg: float
    blue_g_z: float
    red_g_z: float
    blue_altitude_m: float
    red_altitude_m: float

    def validate(self):
        values = vars(self).values()
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError('Seven finite numeric judge inputs required')
        if self.distance_m < 0 or not 0 <= self.blue_ta_deg <= 180 or not 0 <= self.red_ta_deg <= 180:
            raise ValueError('Distance or body-axis angle outside physical range')


def attack_window(distance_m, angle_deg, profile):
    return 500 * FT_TO_M <= distance_m <= 3000 * FT_TO_M and 0 <= angle_deg <= profile.attack_angle_deg


def distance_factor(distance_m, profile):
    if distance_m < 150: return .1
    if distance_m < 500 or distance_m == 500 and profile.distance_edge_policy == 'left_bin': return 1.2
    if distance_m < 1500 or distance_m == 1500 and profile.distance_edge_policy == 'left_bin': return 1.
    if distance_m <= 3000: return .5
    return .1


def position_index(distance_m, own_ta_deg, other_ta_deg, profile):
    # Enemy tail aspect =180-enemy nose-to-own LOS. This uses judge-only
    # enemy attitude, never an enemy-velocity proxy offered to the policy.
    aa = 180. - other_ta_deg
    own = max(0., (90. - abs(own_ta_deg)) / 90.)
    tail = max(0., (90. - abs(aa)) / 90.)
    return (own + tail) * distance_factor(distance_m, profile)


def select_event(collision, blue_crash, red_crash, blue_kill, red_kill, timeout):
    if collision: return 'collision'
    if blue_crash and red_crash: return 'mutual_crash'
    if blue_crash: return 'blue_crash'
    if red_crash: return 'red_crash'
    if blue_kill and red_kill: return 'simultaneous_kill'
    if blue_kill: return 'blue_kill'
    if red_kill: return 'red_kill'
    if timeout: return 'timeout'
    return 'ongoing'


class Judge:
    def __init__(self, profile):
        if not isinstance(profile, RuleProfile): raise TypeError('Explicit RuleProfile required')
        self.profile = profile
        self.ticks = 0
        self.attack = [0, 0]
        self.over_g = [0, 0]
        self.position = [0., 0.]
        self.kill_ticks = [None, None]
        self.event = 'ongoing'
        self.winner = None
        self.rematch = False
        self.unresolved = []

    def advantages(self):
        return [10000. * self.attack[i] / HZ - 100. * self.over_g[i] / HZ + self.position[i] for i in (0, 1)]

    def _advantage_winner(self):
        a, b = self.advantages()
        # The publication says completely equal. No arbitrary isclose tolerance
        # is allowed to silently turn a small real difference into a draw.
        return 'blue' if a > b else ('red' if b > a else 'draw')

    def advance(self, frame, *, started):
        if self.event != 'ongoing': raise RuntimeError('Round already terminal; no later frame may accrue')
        if not isinstance(started, bool): raise TypeError('START state must be explicit boolean')
        frame.validate()
        if not started: return self.snapshot()
        self.ticks += 1
        d = frame.distance_m
        for i, (ta, other_ta, g) in enumerate(((frame.blue_ta_deg, frame.red_ta_deg, frame.blue_g_z),
                                              (frame.red_ta_deg, frame.blue_ta_deg, frame.red_g_z))):
            self.attack[i] += int(attack_window(d, ta, self.profile))
            self.over_g[i] += int(abs(g) > 9.)
            # Raw per-frame sum, not an integral multiplied by1/60.
            self.position[i] += position_index(d, ta, other_ta, self.profile)
            if self.attack[i] >= KILL_TICKS and self.kill_ticks[i] is None:
                self.kill_ticks[i] = self.ticks
        self.event = select_event(d < 15., frame.blue_altitude_m < 50., frame.red_altitude_m < 50.,
                                  self.attack[0] >= KILL_TICKS, self.attack[1] >= KILL_TICKS,
                                  self.ticks >= ROUND_TICKS)
        if self.event in ('red_crash', 'blue_kill'): self.winner = 'blue'
        elif self.event in ('blue_crash', 'red_kill'): self.winner = 'red'
        elif self.event in ('collision', 'simultaneous_kill', 'timeout'):
            self.winner = self._advantage_winner()
            self.rematch = self.winner == 'draw'
        elif self.event == 'mutual_crash':
            # Only single-aircraft crash and collision policies are explicit.
            # No invented winner for simultaneous independent ground impacts.
            self.unresolved.append('mutual_crash_winner_not_confirmed')
        return self.snapshot()

    def snapshot(self):
        advantage = self.advantages()
        bonuses = [0., 0.]
        if self.event in ('blue_kill', 'red_kill', 'simultaneous_kill'):
            for i in (0, 1):
                if self.kill_ticks[i] is not None:
                    kill_seconds = self.kill_ticks[i] / HZ
                    bonuses[i] = 30000. * (1. + (300. - kill_seconds) / 300.)
        ambiguous_bonus = self.event in ('collision', 'blue_crash', 'red_crash', 'mutual_crash') and any(t is not None for t in self.kill_ticks)
        return {
            'profile': vars(self.profile), 'ticks': self.ticks, 'seconds': self.ticks / HZ,
            'event': self.event, 'winner': self.winner, 'rematch': self.rematch,
            'attack_ticks': self.attack.copy(), 'over_g_ticks': self.over_g.copy(),
            'position_sum': self.position.copy(), 'advantage': advantage,
            'kill_score': None if ambiguous_bonus else bonuses,
            'total_score': None if ambiguous_bonus else [advantage[i] + bonuses[i] for i in (0, 1)],
            'unresolved': self.unresolved.copy() + (['canceled_kill_display_score_not_confirmed'] if ambiguous_bonus else []),
            'runtime_Host_conformance_verified': False,
        }
