"""10Hz actor using only the legal 26-double packet and its own history."""
from .bootstrap import HERE
import math
import numpy as np
from kr_red import NumpyPolicy, _obs_state_class

MODEL = 'gylee_69k'
FT = .3048

def rotation(angles):
    p, t, y = np.radians(angles)
    cp, sp, ct, st, cy, sy = math.cos(p), math.sin(p), math.cos(t), math.sin(t), math.cos(y), math.sin(y)
    return np.array([[ct*cy, sp*st*cy-cp*sy, cp*st*cy+sp*sy],
                     [ct*sy, sp*st*sy+cp*cy, cp*st*sy-sp*cy],
                     [-st, sp*ct, cp*ct]])

class ObservationAdapter:
    def __init__(self): self.reset()

    def reset(self):
        self.origin = None
        self.previous_velocity = None
        self.previous_time = None
        self.acceleration = np.zeros(3)

    def states(self, packet, seconds):
        o = np.asarray(packet, dtype=np.float64)
        if o.shape != (26,) or not np.isfinite(o).all() or not math.isfinite(seconds):
            raise ValueError('Expected 26 finite values and finite time')
        if self.previous_time is not None and seconds <= self.previous_time:
            raise ValueError('Time must advance at each 10Hz policy update')
        if self.origin is None: self.origin = o[:2].copy()
        def position(lat, lon, h):
            return [math.radians(lat-self.origin[0])*6378137.,
                    math.radians(lon-self.origin[1])*6378137.*math.cos(math.radians(self.origin[0])), -h*FT]
        own = np.r_[position(*o[:3]), o[3:6], o[15:18]*FT]
        velocity = o[23:26]*FT
        speed = float(np.linalg.norm(velocity))
        if self.previous_time is not None:
            raw = (velocity-self.previous_velocity)/(seconds-self.previous_time)
            self.acceleration = .5*self.acceleration + .5*np.clip(raw, -150., 150.)
        forward = velocity/max(speed, 1e-9) if speed > 1. else np.array([1., 0., 0.])
        # Coordinated-flight proxy: no access to target attitude, AoA or sideslip.
        down = np.array([0.,0.,9.80665])-self.acceleration
        down -= forward*np.dot(down,forward)
        if np.linalg.norm(down) < 1e-5:
            down = np.array([0.,1.,0.])-forward*forward[1]
        down /= max(np.linalg.norm(down), 1e-9)
        right = np.cross(down, forward)
        right /= max(np.linalg.norm(right), 1e-9)
        down = np.cross(forward, right)
        matrix = np.column_stack((forward, right, down))
        attitude = np.degrees([math.atan2(matrix[2,1],matrix[2,2]),
                               math.asin(float(np.clip(-matrix[2,0],-1,1))),
                               math.atan2(matrix[1,0],matrix[0,0])])
        target = np.r_[position(*o[20:23]), attitude, matrix.T@velocity]
        self.previous_time, self.previous_velocity = float(seconds), velocity.copy()
        return own, target

class KoreanV1:
    def __init__(self, model=MODEL):
        folder = HERE / 'upstream/final_team_models' / model
        self.actor = NumpyPolicy(folder)
        # Float32 matrix operations match the upstream actor precision.
        for field in ('Wl', 'bl', 'mean', 'var'):
            value = getattr(self.actor, field)
            if value is not None: setattr(self.actor, field, value.astype(np.float32))
        self.actor.W = [w.astype(np.float32) for w in self.actor.W]
        self.actor.b = [b.astype(np.float32) for b in self.actor.b]
        self.observation = _obs_state_class(folder)()
        self.adapter = ObservationAdapter()

    def reset(self):
        self.adapter.reset()
        self.observation.reset()

    def command(self, packet, seconds):
        own, target = self.adapter.states(packet, seconds)
        return self.command_states(own, target)

    def command_states(self, own, target):
        # Public only for diagnostic truth-state comparison; deployed path uses command().
        obs = self.observation.observation(own, target)
        x = np.asarray(obs, dtype=np.float32)
        p = self.actor
        if p.mean is not None: x = np.clip((x-p.mean)/np.sqrt(p.var+1e-8), -10, 10)
        for w,b in zip(p.W,p.b): x = np.tanh(x@w+b)
        indices = (x@p.Wl+p.bl).reshape(4,p.nb).argmax(-1)
        action = np.linspace(-1,1,p.nb,dtype=np.float32)[indices]
        action[3] = .5*action[3]+.5
        self.observation.record_command(action)
        return action
