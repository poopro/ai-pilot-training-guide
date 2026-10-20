"""Known-development counterfactual: latch80 near-bank ceiling 80 -> 75 only.
Exact baseline latch command, safety floor, trim, gains and slew are inherited.
No learned policy, replay or training state. Inputs remain OWN20+ENEMY6.
"""
from controller import validate_observation, geometry_from_observation, wrap_deg, np, math
from bank80_latch import GGuardLatchBank80

class Bank75LatchController(GGuardLatchBank80):
    def act(self, observation, residual=None, started=True):
        if not started:
            return np.array([0.,0.,0.,.8]), False
        o = validate_observation(observation)
        geo = geometry_from_observation(o)
        d = geo['distance_m']
        near = d < 1100
        bank_limit = 75. if near else 72.
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
        bank = float(np.clip(1.8*heading_error + feedforward, -bank_limit, bank_limit))
        altitude, enemy_altitude = o[2]*.3048, o[22]*.3048
        downward = o[8]*.3048
        # Intercept at comparable height; near the target, point the actual nose
        # at LOS. Euler damping now preserves this pitch while banking.
        if near and geo['blue_angle_deg'] < 45:
            lat=math.radians(o[0]); lat2=math.radians(o[20])
            rel=np.array([(lat2-lat)*6378137,math.radians(o[21]-o[1])*6378137*math.cos((lat+lat2)/2),-(o[22]-o[2])*.3048])
            velocity=(o[23:26]-o[6:9])*.3048
            horizontal=max(float(np.linalg.norm(rel[:2])),1.)
            horizontal_rate=float(np.dot(rel[:2],velocity[:2]))/horizontal
            elevation_rate=math.degrees((-horizontal*velocity[2]+rel[2]*horizontal_rate)/max(d*d,1.))
            pitch = geo['elevation_deg'] + float(np.clip(.5*elevation_rate,-4,4))
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
        return self.command(o, float(np.clip(bank,-bank_limit,bank_limit)), float(np.clip(pitch,-18,25)),
                            float(np.clip(speed,260,450)), rudder)

