"""One safety factor: retain the existing G limiter until abs(G) < 8.0.

Frozen Bank80 act(), trim, gains, recovery, legal controls and slew are retained.
command() matches frozen RepairController.command except its limiter condition.
"""
from candidate import Bank80Controller
from controller import validate_observation, wrap_deg, np, math


class GGuardLatchBank80(Bank80Controller):
    def __init__(self, settings, variant='repair'):
        super().__init__(settings, variant)
        self.g_guard_latched = False

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
        pitch_gain = .07 if self.mode == 'track' else .035
        elevator = -pitch_gain*pitch_error + .009*pitch_rate - trim - self.pitch_integral
        throttle = .65+.008*(speed_target-cas)+self.speed_integral
        if guard:
            throttle = 1.
            self.speed_integral = 0.
        if safety:
            if abs(o[14]) > 8.5:
                self.g_guard_latched = True
            elif abs(o[14]) < 8.0:
                self.g_guard_latched = False
        if safety and self.g_guard_latched:
            elevator = max(elevator, -.08)
        target = np.clip([aileron, elevator, rudder, throttle], [-1,-1,-1,0], [1,1,1,1])
        self.last += np.clip(target-self.last, [-.12,-.08,-.06,-.025], [.12,.08,.06,.025])
        self.bank_target, self.pitch_target, self.speed_target = roll_target, pitch_target, speed_target
        self.telemetry = {'mode':self.mode, 'bank_target':roll_target, 'pitch_target':pitch_target,
                          'pitch_rate_euler_deg_s':pitch_rate, 'trim':trim, 'speed_target':speed_target,
                          'guard':guard}
        return self.last.copy(), guard
