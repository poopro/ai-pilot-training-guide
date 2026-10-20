"""Single-factor rear-wrap direction latch over the unchanged zero-tactical law.

No judge, enemy attitude, clock, actor, inner actuator or physics dependency.
Each episode owns a new RearLatch. The original command retains all safety.
"""
import math
FAR_M=914.4
BANK_DEG=60.

def project_goal(distance_m,requested,*,enabled):
    if len(requested)!=4 or not math.isfinite(distance_m) or distance_m<0 or not all(math.isfinite(x) for x in requested):raise ValueError('Finite legal goals required')
    if type(enabled) is not bool:raise ValueError('Explicit flag')
    roll=requested[0]
    if enabled and distance_m>FAR_M:roll=max(-BANK_DEG,min(BANK_DEG,roll))
    return [roll,*requested[1:]]

def heading_error(packet,geo):
    """Exact original StationController zero-tactical adjusted LOS heading."""
    wrap=lambda x:(x+180)%360-180
    bearing=geo['bearing_deg']
    if not 152.4<=geo['distance_m']<=914.4:
        bearing+=max(-20.,min(20.,wrap(geo['lead_bearing_deg']-bearing)))*.35
    return wrap(bearing-packet[5])

class RearLatch:
    def __init__(self):self.reset()
    def reset(self):self.previous_he=None;self.previous_nonzero_sign=0;self.held_sign=0
    def apply(self,capped,he,body_angle,*,enabled):
        if type(enabled) is not bool or len(capped)!=4 or not all(math.isfinite(x) for x in [*capped,he,body_angle]) or not -180<=he<180 or not 0<=body_angle<=180:raise ValueError('Finite legal heading/angle/goals required')
        he=float(he);body_angle=float(body_angle)  # Normalize NumPy scalar types only.
        wrapped=self.previous_he is not None and he*self.previous_he<0 and abs(he-self.previous_he)>180
        released=self.held_sign!=0 and body_angle<=90
        triggered=False
        if not enabled or body_angle<=90:self.held_sign=0
        elif self.held_sign==0 and wrapped and self.previous_nonzero_sign!=0:
            self.held_sign=self.previous_nonzero_sign;triggered=True
        roll=capped[0]
        if self.held_sign and roll!=0:roll=math.copysign(abs(roll),self.held_sign)
        if roll!=0:self.previous_nonzero_sign=1 if roll>0 else -1
        self.previous_he=he
        return [roll,*capped[1:]],dict(enabled=enabled,wrapped=wrapped,triggered=triggered,released=released,active=self.held_sign!=0,held_sign=self.held_sign)
