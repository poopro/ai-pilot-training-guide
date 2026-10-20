"""Isolated repair: Euler-rate damping, full bank trim, bounded pursuit/track.

Inputs remain official OWN20+ENEMY6; no hidden opponent attitude or judge state.
"""
from pathlib import Path
import math
import sys
import numpy as np

BASE = Path(r'E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test')
sys.path.insert(0, str(BASE))
from combat_v3.interface import validate_observation, OwnSnapshot, geometry_from_observation
from combat_v3.controller import wrap_deg


class RepairController:
    def __init__(self, settings, variant='repair'):
        self.settings = settings
        self.variant = variant
        self.last = np.array([0., 0., 0., .8])
        self.recovering = False
        self.mode = 'intercept'
        self.previous_bearing = None
        self.bearing_rate = 0.
        self.bank_target = 0.
        self.pitch_target = 0.
        self.speed_target = 340.
        self.telemetry = {}
        self.pitch_integral = 0.
        self.speed_integral = 0.

    def command(self, obs, roll_target, pitch_target, speed_target, rudder=0., safety=True):
        o = validate_observation(obs)
        altitude, downward = o[2]*.3048, o[8]*.3048
        cas = o[12] / 1.6878098571011957
        roll, pitch, alpha = o[3], o[4], o[18]
        guard = False
        floor = self.settings['safety_floor_m']
        if safety and (altitude < floor or downward > 10 and altitude/downward < 15):
            self.recovering = True
        if self.recovering and altitude > floor+400 and downward <= 0 and cas > 220:
            self.recovering = False
        if safety and self.recovering:
            roll_target, pitch_target, speed_target, rudder = 0., 12., 400., 0.
            self.mode, guard = 'recover', True
        if safety and (cas < 180 or alpha > 22):
            roll_target, pitch_target, speed_target, rudder = 0., min(pitch, 2.), 420., 0.
            self.mode, guard = 'energy_recover', True
        phi, theta = np.radians([roll, pitch])
        p, q, r = o[9:12]
        # Body q includes coordinated yaw at bank. Dampen Euler theta_dot instead.
        pitch_rate = math.degrees(q*math.cos(phi)-r*math.sin(phi))
        roll_rate = math.degrees(p+math.tan(float(np.clip(theta, -.7, .7)))*(q*math.sin(phi)+r*math.cos(phi)))
        bank = min(abs(roll), 75.)
        trim = .035/max(math.cos(math.radians(bank)), .25)
        aileron = .025*wrap_deg(roll_target-roll) - .008*roll_rate
        pitch_error = float(pitch_target-pitch)
        self.pitch_integral = float(np.clip(self.pitch_integral + .004*pitch_error/60, -.25, .25))
        self.speed_integral = float(np.clip(self.speed_integral + .0004*(speed_target-cas)/60, -.5, .3))
        elevator = -.035*pitch_error + .009*pitch_rate - trim - self.pitch_integral
        throttle = .65+.008*(speed_target-cas)+self.speed_integral
        if guard:
            throttle = 1.
            self.speed_integral = 0.
        if safety and abs(o[14]) > 8.5:
            elevator = max(elevator, -.08)
        target = np.clip([aileron, elevator, rudder, throttle], [-1,-1,-1,0], [1,1,1,1])
        self.last += np.clip(target-self.last, [-.12,-.08,-.06,-.025], [.12,.08,.06,.025])
        self.bank_target, self.pitch_target, self.speed_target = roll_target, pitch_target, speed_target
        self.telemetry = {'mode':self.mode, 'bank_target':roll_target, 'pitch_target':pitch_target,
                          'pitch_rate_euler_deg_s':pitch_rate, 'trim':trim, 'speed_target':speed_target,
                          'guard':guard}
        return self.last.copy(), guard

    def act(self, observation, residual=None, started=True):
        if not started:
            return np.array([0.,0.,0.,.8]), False
        o = validate_observation(observation)
        geo = geometry_from_observation(o)
        d = geo['distance_m']
        near = d < 1100
        self.mode = 'track' if near else 'intercept'
        bearing = geo['bearing_deg']
        # Use direct LOS when far off target; long lead on opposing headings made
        # the old controller chase a moving point while both aircraft circled.
        heading_error = wrap_deg(bearing-o[5])
        if not near and abs(heading_error) < 35:
            lead_delta = wrap_deg(geo['lead_bearing_deg']-bearing)
            bearing += float(np.clip(lead_delta, -20, 20))*.35
            heading_error = wrap_deg(bearing-o[5])
        if self.previous_bearing is None:
            self.bearing_rate = 0.
        else:
            rate = np.clip(wrap_deg(bearing-self.previous_bearing)*60, -15, 15)
            self.bearing_rate = .9*self.bearing_rate+.1*rate
        self.previous_bearing = bearing
        feedforward = math.degrees(math.atan(geo['own_tas_mps']*math.radians(self.bearing_rate)/9.80665))
        bank = float(np.clip(1.8*heading_error + feedforward, -72, 72))
        altitude, enemy_altitude = o[2]*.3048, o[22]*.3048
        downward = o[8]*.3048
        # Intercept at comparable height; near the target, point the actual nose
        # at LOS. Euler damping now preserves this pitch while banking.
        if near and geo['blue_angle_deg'] < 45:
            pitch = geo['elevation_deg']
        else:
            gamma = np.clip((enemy_altitude-altitude)*.012+downward*.16, -8, 12)
            pitch = o[18] + gamma
        desired_close = float(np.clip((d-600)*.07, -30, 65))
        speed = geo['enemy_equivalent_cas_kts'] + desired_close*1.9438444924*geo['cas_ratio']
        if abs(heading_error) > 45:
            speed = min(speed, 290.)
        speed = float(np.clip(speed, 260, 450))
        rudder = 0.
        if residual is not None:
            a = np.clip(np.asarray(residual, dtype=float), -1, 1)
            limits = [2.5,.8,.005,8.] if near and geo['blue_angle_deg'] < 10 else [8.,2.,.015,15.]
            bank += a[0]*limits[0]; pitch += a[1]*limits[1]
            rudder = a[2]*limits[2]; speed += a[3]*limits[3]
        return self.command(o, float(np.clip(bank,-72,72)), float(np.clip(pitch,-18,25)),
                            float(np.clip(speed,260,450)), rudder)
