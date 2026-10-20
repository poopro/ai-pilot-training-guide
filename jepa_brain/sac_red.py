"""Official 314.4M-step SAC model as a red opponent.

Faithful port of the organizer's player1_Loadmodel.py (get_state, process_joystick_action,
float32 observation, deterministic predict every 60 Hz frame). Per-instance state, so
each game starts clean exactly like a freshly started player program.
"""
import math
import numpy as np
from common import BASE

MODEL_PATH = BASE / 'model' / 'jsbsim_sac_314400000_steps.zip'
_MODEL = {}


def load_model():
    if 'm' not in _MODEL:
        from stable_baselines3 import SAC
        import torch
        torch.set_num_threads(1)
        _MODEL['m'] = SAC.load(str(MODEL_PATH), device='cpu')
    return _MODEL['m']


def _enemy_3d_angle_deg(pos1, pos2, vel2):
    v_los = pos1 - pos2
    n2, nl = np.linalg.norm(vel2), np.linalg.norm(v_los)
    if n2 < 1e-5 or nl < 1e-5:
        return 180.0
    return float(np.degrees(np.arccos(np.clip(np.dot(vel2, v_los) / (n2 * nl), -1.0, 1.0))))


class OfficialSacPlayer:
    def __init__(self, model=None):
        self.model = model
        self.prev_distance_m = None
        self.last_actual = np.array([0, 0, 0, 0.8])

    def get_state(self, obs):
        R = 6378137.0
        lat1, lon1, alt1 = obs[0], obs[1], obs[2] * 0.3048
        lat2, lon2, alt2 = obs[20], obs[21], obs[22] * 0.3048
        la1, la2 = math.radians(lat1), math.radians(lat2)
        lo1, lo2 = math.radians(lon1), math.radians(lon2)
        dn = (la2 - la1) * R
        de = (lo2 - lo1) * R * math.cos(la1)
        dd = -(alt2 - alt1)
        rel = np.array([dn, de, dd], dtype=np.float64)
        ev = np.array([obs[23], obs[24], obs[25]], dtype=np.float64) * 0.3048
        dist = np.linalg.norm(rel)
        if self.prev_distance_m is None:
            self.prev_distance_m = dist
        vc = (self.prev_distance_m - dist) / (1 / 60)
        self.prev_distance_m = dist
        e3d = _enemy_3d_angle_deg(np.zeros(3), rel, ev)
        phi, theta, psi = math.radians(obs[3]), math.radians(obs[4]), math.radians(obs[5])
        rx = np.array([[1, 0, 0], [0, np.cos(phi), np.sin(phi)], [0, -np.sin(phi), np.cos(phi)]])
        ry = np.array([[np.cos(theta), 0, -np.sin(theta)], [0, 1, 0], [np.sin(theta), 0, np.cos(theta)]])
        rz = np.array([[np.cos(psi), np.sin(psi), 0], [-np.sin(psi), np.cos(psi), 0], [0, 0, 1]])
        xb, yb, zb = (rx @ ry @ rz) @ rel
        az = np.degrees(np.arctan2(yb, xb))
        el = np.degrees(np.arctan2(-zb, np.sqrt(xb ** 2 + yb ** 2)))
        s = np.zeros(20, dtype=np.float32)
        s[0] = dist / 5000.0
        s[1] = (alt2 - alt1) / 5000.0
        s[2] = el / 90.0
        s[3] = az / 180.0
        s[4] = e3d / 180.0
        s[5], s[6] = np.sin(phi), np.cos(phi)
        s[7], s[8] = np.sin(theta), np.cos(theta)
        s[9] = obs[18] / 30.0
        s[10] = obs[19] / 30.0
        s[11] = alt1 / 5000.0
        s[12] = obs[13] * 0.3048 / 340.0
        s[13] = vc / 340.0
        s[14] = obs[15] * 0.3048 / 340.0
        s[15] = obs[16] * 0.3048 / 340.0
        s[16] = obs[17] * 0.3048 / 340.0
        s[17], s[18], s[19] = obs[9], obs[10], obs[11]
        return s

    def process_joystick_action(self, rl_action, obs):
        out = np.zeros(4)
        deadbands = np.array([0.01, 0.03, 0.06])
        exponents = np.array([1.0, 3.0, 3.0])
        max_change = np.array([0.050, 0.026, 0.013])
        mach = obs[13] * 0.3048 / 340
        elevator_limit = 0.4 if mach > 0.8 else 1.0
        limits = np.array([1.0, elevator_limit, 0.2])
        for i in range(3):
            act = rl_action[i]
            if abs(act) < deadbands[i]:
                act = 0.0
            act = np.sign(act) * (abs(act) ** exponents[i])
            act = np.clip(act, -limits[i], limits[i])
            last = self.last_actual[i]
            out[i] = last + np.clip(act - last, -max_change[i], max_change[i])
        target_throttle = np.clip(rl_action[3], 0.0, 1.0)
        last_t = self.last_actual[3]
        out[3] = last_t + np.clip(target_throttle - last_t, -0.004, 0.004)
        self.last_actual = out
        return out

    def act(self, obs26, tick=0):
        obs = np.asarray(obs26, dtype=np.float32)   # the official receiver unpacks into float32
        state = self.get_state(obs)
        if self.model is None:
            self.model = load_model()
        action, _ = self.model.predict(state, deterministic=True)
        return self.process_joystick_action(action, obs)
