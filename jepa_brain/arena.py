"""Competition-faithful 1v1 arena.

Geometry (organizer answers 10/14): same altitude, parallel opposite headings,
red directly abeam on the left or right, lateral 3000/6000/9000 ft, 340 KCAS,
altitude 10-20k ft. Rules from the frozen local judge (1 deg cone, collision
<15 m, crash <50 m AGL, kill after 180 cumulative ticks).
Optional host_fidelity mimics the 10/08 Host: gear up and tanks locked full.
"""
import math
import numpy as np
from common import PROFILE, judge_mod
from combat_v3.fdm import JsbsimFdm
from combat_v3.controller import relative_geometry
from combat_v3.interface import simulator_observation

R_EARTH = 6378137.0
LAT0, LON0 = 23.060552, 121.948555
FT = .3048


class Arena:
    def __init__(self, seed, distance_ft, side, altitude_ft, host_fidelity=True):
        rng = np.random.default_rng(seed)
        psi = float(rng.uniform(0, 360))
        bearing = psi + (90. if side > 0 else -90.)
        dm = distance_ft * FT
        lat0 = math.radians(LAT0)
        rlat = LAT0 + math.degrees(math.cos(math.radians(bearing)) * dm / R_EARTH)
        rlon = LON0 + math.degrees(math.sin(math.radians(bearing)) * dm / (R_EARTH * math.cos(lat0)))
        common = dict(fdm_ic_h=float(altitude_ft), fdm_ic_v=340)
        self.fdm1 = JsbsimFdm(fdm_id=1, fdm_ic_lat=LAT0, fdm_ic_long=LON0, fdm_ic_psi=psi % 360, **common)
        self.fdm2 = JsbsimFdm(fdm_id=2, fdm_ic_lat=rlat, fdm_ic_long=rlon, fdm_ic_psi=(psi + 180) % 360, **common)
        self.judge = judge_mod.Judge(PROFILE)
        self.tick = 0
        self.host_fidelity = bool(host_fidelity)
        self.tanks = []
        self.fidelity_applied = {'gear': False, 'tanks': 0}
        if self.host_fidelity:
            self._fidelity_init()
        self.geo = relative_geometry(self.fdm1, self.fdm2)

    def _fidelity_init(self):
        for idx, fdm in enumerate((self.fdm1, self.fdm2)):
            try:
                fdm.fdm['gear/gear-cmd-norm'] = 0
                self.fidelity_applied['gear'] = True
            except Exception:
                pass
            tanks = []
            for i in range(8):
                key = 'propulsion/tank[%d]/contents-lbs' % i
                try:
                    value = float(fdm.fdm[key])
                except Exception:
                    break
                if value > 0:
                    tanks.append((key, value))
            self.tanks.append(tanks)
            self.fidelity_applied['tanks'] += len(tanks)

    def _lock_fuel(self):
        for fdm, tanks in zip((self.fdm1, self.fdm2), self.tanks):
            for key, value in tanks:
                try:
                    fdm.fdm[key] = value
                except Exception:
                    pass

    def obs_blue(self):
        return simulator_observation(self.fdm1, self.fdm2)

    def obs_red(self):
        return simulator_observation(self.fdm2, self.fdm1)

    def agl_blue_m(self):
        return float(self.fdm1.fdm['position/h-agl-ft']) * FT

    def step(self, blue_cmd, red_cmd):
        """Advance one 60 Hz physics tick. Returns True when the round is over."""
        self.fdm1.sendAction(blue_cmd)
        self.fdm2.sendAction(red_cmd)
        self.fdm1.step()
        self.fdm2.step()
        if self.host_fidelity:
            self._lock_fuel()
        self.tick += 1
        geo = relative_geometry(self.fdm1, self.fdm2)
        self.geo = geo
        frame = judge_mod.Frame(
            float(geo['distance_m']), float(geo['blue_angle_deg']), float(geo['red_angle_deg']),
            float(self.fdm1.fdm['accelerations/n-pilot-z-norm']), float(self.fdm2.fdm['accelerations/n-pilot-z-norm']),
            float(self.fdm1.fdm['position/h-agl-ft']) * FT, float(self.fdm2.fdm['position/h-agl-ft']) * FT)
        self.judge.advance(frame, started=True)
        return self.judge.event != 'ongoing'

    def counters(self):
        j = self.judge
        return [j.attack[0], j.attack[1], j.position[0], j.position[1], j.over_g[0], j.over_g[1]]
