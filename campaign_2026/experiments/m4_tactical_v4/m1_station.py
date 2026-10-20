"""M1 — station-keeping doctrine for the accumulated-attack game.

DIAGNOSIS (measured, 3000 telemetry samples per case)
    vs rl     median range 823 m, inside 152-914 m band 56% of the time,
              yet nose<=1 deg while in band: ZERO samples, min angle 1.5 deg.
    vs mirror median range 1401 m, in band 5%, but 32 samples reached 0.1 deg.

So we are already inside the envelope against the RL opponent and simply
cannot hold the pipper on it. This is a tracking-latency problem, not a
range-management problem.

ROOT CAUSE
    The frozen controller estimates bearing rate with a 0.9/0.1 EMA:
        self.bearing_rate = .9*self.bearing_rate + .1*rate
    That is a ~10 frame (167 ms) time constant. A target manoeuvring at
    20 deg/s moves ~3.3 deg inside that lag, which is exactly the residual
    we measured. The attack cone is 1 deg.

FIX (doctrine layer only; command() and every safety/slew/trim term inherited)
    1. Two-tap derivative for bearing rate: no long EMA, lag ~1 frame.
    2. Nose-error feedback added to the bank command inside the attack band,
       so the inner loop is driven by the quantity the judge actually scores.
    3. Higher near-field pitch gain, since track mode runs at ~820 m here.
    4. Lead is blended out when already inside the band: inside 500-3000 ft
       you want the pipper on him, not a lead solution.

Only act() is overridden. command(), the G limiter, trim, slew limits and the
safety layer are the frozen ones, byte-for-byte.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

REPAIR = Path(r"E:\ai_pilot\campaign_2026\repair_v1")
sys.path.insert(0, str(REPAIR))
from controller import RepairController  # noqa: E402
from combat_v3.interface import validate_observation, geometry_from_observation  # noqa: E402

BAND_LO_M = 500 * 0.3048          # 152.4
BAND_HI_M = 3000 * 0.3048         # 914.4


def wrap_deg(x: float) -> float:
    return (x + 180.0) % 360.0 - 180.0


class StationController(RepairController):
    """Frozen guidance + low-latency accumulation doctrine."""

    def __init__(self, settings, variant="station"):
        super().__init__(settings, variant)
        self.bearing_prev2 = None
        self.bearing_prev1 = None
        self.bearing_rate = 0.0
        # Slow tactical layer inputs. Defaults reproduce the pure M1 controller,
        # so with no policy attached the behaviour is bit-identical to M1.
        self.tac_aggression = 0.0
        self.tac_break = 0.0
        self.tac_range = 0.0

    def set_tactical(self, aggression: float, break_bias: float, range_bias: float):
        """Called once per 3 Hz decision by the RL layer."""
        self.tac_aggression = float(np.clip(aggression, -1, 1))
        self.tac_break = float(np.clip(break_bias, -1, 1))
        self.tac_range = float(np.clip(range_bias, -1, 1))

    # ---- fast, low-latency bearing-rate estimate --------------------------
    def _rate(self, bearing: float) -> float:
        if self.bearing_prev1 is None:
            self.bearing_prev1 = bearing
            self.bearing_prev2 = bearing
            self.bearing_rate = 0.0
            return 0.0
        # central difference over two frames, clamped against a bogus jump
        rate = 0.5 * wrap_deg(bearing - self.bearing_prev2) * 60.0
        self.bearing_prev2 = self.bearing_prev1
        self.bearing_prev1 = bearing
        if not math.isfinite(rate) or abs(rate) > 90.0:
            return self.bearing_rate
        # light smoothing only: kills sensor noise, keeps lag at ~2 frames
        self.bearing_rate = 0.65 * self.bearing_rate + 0.35 * rate
        return self.bearing_rate

    def act(self, observation, residual=None, started=True):
        if not started:
            return np.array([0., 0., 0., .8]), False

        o = validate_observation(observation)
        geo = geometry_from_observation(o)
        d = geo["distance_m"]
        in_band = BAND_LO_M <= d <= BAND_HI_M
        near = d < 1100.0
        self.mode = "track" if near else "intercept"

        bearing = geo["bearing_deg"]
        aggr, brk = self.tac_aggression, self.tac_break
        # Inside the envelope a lead solution is wrong: put the nose on him.
        # Outside, the lead is what closes the range. aggression widens the lead
        # pursuit that closes range; break_bias suppresses nose tracking.
        if not in_band:
            lead_delta = wrap_deg(geo["lead_bearing_deg"] - bearing)
            bearing += float(np.clip(lead_delta, -20, 20)) * (0.35 * (1.0 + 0.6 * aggr))
            heading_error = wrap_deg(bearing - o[5])
            if brk > 0.2:
                # forced wide reposition: stop chasing, break the turn
                heading_error += 35.0 * brk
        else:
            heading_error = wrap_deg(bearing - o[5])

        rate = self._rate(bearing)

        # lead turn to cancel the target's across-track motion
        feedforward = math.degrees(
            math.atan(geo["own_tas_mps"] * math.radians(rate) / 9.80665))
        bank = 1.8 * heading_error + feedforward

        if in_band:
            # Direct LOS-rate damping: the judge scores nose angle, so drive it.
            nose_err = heading_error
            nose_gain = (2.6 + 2.2 * aggr) * (1.0 - 0.6 * max(0.0, brk))
            bank += nose_gain * float(np.clip(nose_err, -25, 25))
            # and cancel the residual across-track motion hard
            bank -= (0.35 * (1.0 + 1.2 * brk)) * rate
            bank = float(np.clip(bank, -72, 72))
        else:
            bank = float(np.clip(bank, -72, 72))

        altitude, enemy_altitude = o[2] * .3048, o[22] * .3048
        downward = o[8] * .3048
        if near and geo["blue_angle_deg"] < 45:
            pitch = geo["elevation_deg"]
        else:
            pitch = o[18] + float(np.clip(
                (enemy_altitude - altitude) * .012 + downward * .16, -8, 12))

        # Do not add closure speed once inside the band: overshooting under
        # 500 ft forfeits accumulated progress and restarts nothing.
        target_range_m = 600.0 + 250.0 * self.tac_range
        desired_close = (float(np.clip((d - target_range_m) * .07, -30, 65))
                         if not in_band else 0.0)
        speed = geo["enemy_equivalent_cas_kts"] + desired_close * 1.9438444924 * geo["cas_ratio"]
        if abs(heading_error) > 45 and not in_band:
            speed = min(speed, 290.)
        speed = float(np.clip(speed, 260, 450))

        rudder = 0.0
        if residual is not None:
            a = np.clip(np.asarray(residual, dtype=float), -1, 1)
            limits = ([2.5, .8, .005, 8.] if near and geo["blue_angle_deg"] < 10
                      else [8., 2., .015, 15.])
            bank += a[0] * limits[0]
            pitch += a[1] * limits[1]
            rudder = a[2] * limits[2]
            speed += a[3] * limits[3]

        # Frozen command() reads self.mode for the pitch gain:
        #   pitch_gain = .07 if self.mode == 'track' else .035
        # Staying on 'track' inside the band is what gets the higher gain,
        # which is what lets the loop actually close the last degree.
        self.mode = "track" if near else "intercept"
        return self.command(o, float(np.clip(bank, -72, 72)),
                            float(np.clip(pitch, -18, 25)), speed, rudder)