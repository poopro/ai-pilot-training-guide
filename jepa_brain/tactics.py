"""Tactic-conditioned wrapper around the frozen RepairController.

Tactic PURSUE reproduces RepairController.act exactly (verified by test_equiv.py).
The other tactics only change the three targets (bank, pitch, speed) that the
frozen low-level command() loop (rate limits, G guard, ground recovery) executes.
"""
import math
import numpy as np
from common import repair, SETTINGS
from combat_v3.interface import validate_observation, geometry_from_observation
from combat_v3.controller import wrap_deg

PURSUE, LEAD, LAG, BREAK_IN, BREAK_OUT, HIGH_YOYO, LOW_YOYO, EXTEND, STRAIGHT = range(9)
N_TACTICS = 8          # tactics the brain may choose (STRAIGHT is for scripted opponents only)
NAMES = ['pursue', 'lead', 'lag', 'break_in', 'break_out', 'high_yoyo', 'low_yoyo', 'extend', 'straight']


class TacticalPilot(repair.RepairController):
    def __init__(self, settings=None, variant='tactical'):
        super().__init__(settings or SETTINGS, variant)
        self.tactic = PURSUE
        self.hold_altitude_m = None

    def set_tactic(self, tactic):
        self.tactic = int(tactic)

    def act(self, observation, residual=None, started=True):
        if not started:
            return np.array([0., 0., 0., .8]), False
        o = validate_observation(observation)
        tac = self.tactic
        geo = geometry_from_observation(o)
        d = geo['distance_m']
        near = d < 1100
        self.mode = 'track' if near else 'intercept'
        bearing = geo['bearing_deg']
        heading_error = wrap_deg(bearing - o[5])
        if tac == LEAD:
            lead_delta = wrap_deg(geo['lead_bearing_deg'] - bearing)
            bearing += float(np.clip(lead_delta, -30, 30)) * .8
            heading_error = wrap_deg(bearing - o[5])
        elif tac == LAG:
            if abs(heading_error) < 60:
                lead_delta = wrap_deg(geo['lead_bearing_deg'] - bearing)
                bearing -= float(np.clip(lead_delta, -25, 25)) * .6
                heading_error = wrap_deg(bearing - o[5])
        elif not near and abs(heading_error) < 35:
            lead_delta = wrap_deg(geo['lead_bearing_deg'] - bearing)
            bearing += float(np.clip(lead_delta, -20, 20)) * .35
            heading_error = wrap_deg(bearing - o[5])
        if self.previous_bearing is None:
            self.bearing_rate = 0.
        else:
            rate = np.clip(wrap_deg(bearing - self.previous_bearing) * 60, -15, 15)
            self.bearing_rate = .9 * self.bearing_rate + .1 * rate
        self.previous_bearing = bearing
        feedforward = math.degrees(math.atan(geo['own_tas_mps'] * math.radians(self.bearing_rate) / 9.80665))
        bank = float(np.clip(1.8 * heading_error + feedforward, -72, 72))
        altitude, enemy_altitude = o[2] * .3048, o[22] * .3048
        downward = o[8] * .3048
        if near and geo['blue_angle_deg'] < 45:
            lat = math.radians(o[0]); lat2 = math.radians(o[20])
            rel = np.array([(lat2 - lat) * 6378137, math.radians(o[21] - o[1]) * 6378137 * math.cos((lat + lat2) / 2), -(o[22] - o[2]) * .3048])
            velocity = (o[23:26] - o[6:9]) * .3048
            horizontal = max(float(np.linalg.norm(rel[:2])), 1.)
            horizontal_rate = float(np.dot(rel[:2], velocity[:2])) / horizontal
            elevation_rate = math.degrees((-horizontal * velocity[2] + rel[2] * horizontal_rate) / max(d * d, 1.))
            pitch = geo['elevation_deg'] + float(np.clip(.5 * elevation_rate, -4, 4))
        else:
            gamma = np.clip((enemy_altitude - altitude) * .012 + downward * .16, -8, 12)
            pitch = o[18] + gamma
        desired_close = float(np.clip((d - 600) * .07, -30, 65))
        speed = geo['enemy_equivalent_cas_kts'] + desired_close * 1.9438444924 * geo['cas_ratio']
        if abs(heading_error) > 45:
            speed = min(speed, 290.)
        speed = float(np.clip(speed, 260, 450))
        rudder = 0.
        # ---- tactic-specific target changes (PURSUE leaves everything untouched) ----
        bank_limit = 72.
        if tac == LEAD:
            bank = float(np.clip(1.8 * heading_error + feedforward, -80, 80)); bank_limit = 80.
        elif tac in (BREAK_IN, BREAK_OUT):
            sign = 1. if heading_error >= 0 else -1.
            if tac == BREAK_OUT:
                sign = -sign
            bank = 78. * sign; bank_limit = 80.
            pitch = o[4] + 3.
            speed = 420.
        elif tac == HIGH_YOYO:
            bank *= .6
            pitch += 10.
            speed = min(speed, 300.)
        elif tac == LOW_YOYO:
            pitch -= 8.
            speed = 450.
        elif tac == EXTEND:
            bank = 0.
            pitch = o[18]
            speed = 450.
        elif tac == STRAIGHT:
            if self.hold_altitude_m is None:
                self.hold_altitude_m = altitude
            bank = 0.
            pitch = o[18] + float(np.clip((self.hold_altitude_m - altitude) * .012 + downward * .16, -8, 12))
            speed = 340.
        return self.command(o, float(np.clip(bank, -bank_limit, bank_limit)), float(np.clip(pitch, -18, 25)),
                            float(np.clip(speed, 260, 450)), rudder)
