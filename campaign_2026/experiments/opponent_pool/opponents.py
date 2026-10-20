"""Fixed P2 adapters using OWN20+ENEMY6 only; no hidden judge state."""
import numpy as np
from duel_lab import (math, geometry_from_observation, wrap_deg, FT_TO_M,
                      PacketController, OwnSnapshot)
from controller import RepairController
OPPONENT_IDS=('rule','rl','repair_guide','rule_bank60')
class RuleBank60:
    """Pursuit/tracking and threat-triggered break turn, using OWN20+ENEMY6 only."""
    def __init__(self, settings, initial_altitude_m, rng):
        self.controller = PacketController(settings)
        self.altitude_m = initial_altitude_m
        self.rng = rng
        self.break_until = -1.0
        self.next_break_allowed = 0.0
        self.break_bank = 0.0
        self.mode = "intercept"
        self.guard = False

    def act(self, observation, elapsed_s):
        geo = geometry_from_observation(observation)
        # Enemy velocity direction is an estimate of threat, never its hidden nose.
        threatened = (geo["distance_m"] < 1300 and geo["aspect_proxy_deg"] < 18
                      and geo["blue_angle_deg"] > 65)
        if threatened and elapsed_s >= self.next_break_allowed:
            self.break_bank = float(self.rng.choice([-1, 1])) * 65
            self.break_until = elapsed_s + 2.5
            self.next_break_allowed = elapsed_s + 6.0
        if elapsed_s < self.break_until:
            self.mode = "defensive_break"
            command, self.guard = self.controller.control.level(
                OwnSnapshot(observation), self.altitude_m, self.break_bank, 410)
        else:
            if geo["distance_m"] > 1200:
                # A different, altitude-controlled pure-pursuit entry avoids both
                # planes following identical lead-intercept circles indefinitely.
                heading_error = wrap_deg(geo["bearing_deg"] - observation[5])
                bank = float(np.clip(1.8 * heading_error, -60, 60))
                own_altitude = observation[2] * FT_TO_M
                target_altitude = float(np.clip(observation[22] * FT_TO_M,
                                               max(1200, own_altitude - 600),
                                               max(1200, own_altitude + 600)))
                speed = 340 if abs(heading_error) > 45 else 400
                command, self.guard = self.controller.control.level(
                    OwnSnapshot(observation), target_altitude, bank, speed)
                self.mode = "altitude_controlled_pursuit"
            else:
                residual = np.zeros(4, dtype=np.float32)
                command, self.guard = self.controller.act(observation, residual)
                self.mode = "precision_track"
        if self.guard:
            self.mode = "recover"
        return command

class RepairGuideFighter:
    def __init__(self,settings):
        self.controller=RepairController(settings,'repair');self.guard=False;self.mode='initializing'
    def act(self,observation,elapsed_s):
        observation=np.asarray(observation,dtype=float)
        if observation.shape!=(26,) or not np.isfinite(observation).all():raise ValueError('P2 legal observation must be OWN20+ENEMY6')
        command,self.guard=self.controller.act(observation,residual=None)
        self.mode=self.controller.mode
        return command

def configure_red(environment,name):
    if name not in OPPONENT_IDS:raise ValueError('Unknown frozen opponent')
    if name=='rule_bank60':
        environment.red_fighter=RuleBank60(environment.settings,float(environment.fdm2.getProperty('pose')[2]),environment.np_random)
    elif name=='repair_guide':environment.red_fighter=RepairGuideFighter(environment.settings)
    if name in ('repair_guide','rule_bank60'):environment.p2_type='rule'
    return {'opponent_id':name,'policy_observation':'OWN20+ENEMY6','rng_state':environment.np_random.bit_generator.state}
