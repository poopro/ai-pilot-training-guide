"""One-factor inference ablation: residual only within the existing 1100m track zone."""
import numpy as np

TRACK_RANGE_M = 1100.0

def make_gated_controller(base, geometry_from_observation):
    class RangeGatedController(base):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.gate_ticks=0
            self.blocked_ticks=0
            self.last_gate={}

        def act(self,observation,residual=None,started=True):
            blocked=False
            raw=np.zeros(4,dtype=float) if residual is None else np.asarray(residual,dtype=float)
            if raw.shape!=(4,) or not np.isfinite(raw).all():
                raise ValueError('Residual must have four finite values')
            applied=residual
            if started and residual is not None:
                geometry=geometry_from_observation(observation)
                blocked=geometry['distance_m']>=TRACK_RANGE_M
                if blocked: applied=None
                self.gate_ticks+=1
                self.blocked_ticks+=int(blocked)
                self.last_gate={'range_before_tick_m':float(geometry['distance_m']),
                    'nose_error_before_tick_deg':float(geometry['blue_angle_deg']),
                    'blocked':blocked,'raw':raw.tolist(),
                    'applied':np.zeros(4).tolist() if blocked else raw.tolist()}
            else:
                self.last_gate={'blocked':False,'raw':raw.tolist(),
                    'applied':raw.tolist()}
            command,guard=super().act(observation,applied,started=started)
            self.telemetry.update(gate_blocked=blocked,
                gate_fraction_blocked=self.blocked_ticks/max(self.gate_ticks,1))
            return command,guard
    return RangeGatedController
