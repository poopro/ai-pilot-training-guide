"""One 26-double ICD encoder for training and official UDP deployment.
No enemy attitude, health, intent, terrain, or simulator object is available here.
"""
import math
import struct
import numpy as np
FT_TO_M=.3048
FPS_TO_KTS=1/1.6878098571011957
OWN_KEYS=('position/lat-gc-deg','position/long-gc-deg','position/h-sl-ft',
 'attitude/phi-deg','attitude/theta-deg','attitude/psi-deg',
 'velocities/v-north-fps','velocities/v-east-fps','velocities/v-down-fps',
 'velocities/p-rad_sec','velocities/q-rad_sec','velocities/r-rad_sec',
 'velocities/vc-fps','velocities/vt-fps','accelerations/n-pilot-z-norm',
 'velocities/u-fps','velocities/v-fps','velocities/w-fps','aero/alpha-deg','aero/beta-deg')
ENEMY_KEYS=(OWN_KEYS[0],OWN_KEYS[1],OWN_KEYS[2],OWN_KEYS[6],OWN_KEYS[7],OWN_KEYS[8])
def simulator_observation(own,enemy):
    return np.array([own.fdm[k] for k in OWN_KEYS]+[enemy.fdm[k] for k in ENEMY_KEYS],dtype=np.float64)
def validate_observation(obs):
    o=np.asarray(obs,dtype=np.float64)
    if o.shape!=(26,) or not np.isfinite(o).all():raise ValueError('OBS must contain 26 finite doubles')
    if not (-90<=o[0]<=90 and -90<=o[20]<=90 and -180<=o[1]<=180 and -180<=o[21]<=180):
        raise ValueError('Invalid latitude/longitude')
    return o
def decode_packet(data):
    if len(data)!=208:raise ValueError('OBS packet must be 208 bytes')
    return validate_observation(struct.unpack('<26d',data))
def encode_command(action,state):
    a=np.asarray(action,dtype=float)
    if a.shape!=(4,) or not np.isfinite(a).all() or state not in (0,1,2):raise ValueError('Invalid command')
    a=np.clip(a,[-1,-1,-1,0],[1,1,1,1])
    return struct.pack('<fffff10s',*a,float(state),b'PLAYER_CMD')
def geometry_from_observation(o):
    o=validate_observation(o)
    lat=math.radians(o[0]);lat2=math.radians(o[20])
    rel=np.array([(lat2-lat)*6378137,math.radians(o[21]-o[1])*6378137*math.cos((lat+lat2)/2),
                  -(o[22]-o[2])*FT_TO_M])
    d=float(np.linalg.norm(rel));phi,theta,psi=np.radians(o[3:6])
    cp,sp=math.cos(phi),math.sin(phi);ct,st=math.cos(theta),math.sin(theta);cy,sy=math.cos(psi),math.sin(psi)
    rotation=np.array([[ct*cy,ct*sy,-st],[sp*st*cy-cp*sy,sp*st*sy+cp*cy,sp*ct],
                       [cp*st*cy+sp*sy,cp*st*sy-sp*cy,cp*ct]])
    x,y,z=rotation@rel
    ev=o[23:26]*FT_TO_M;rv=(o[23:26]-o[6:9])*FT_TO_M
    # Enemy nose is unavailable in the ICD: velocity-based aspect is a proxy only.
    aspect=180. if np.linalg.norm(ev)<1e-6 or d<1e-6 else math.degrees(math.acos(float(np.clip(np.dot(ev,-rel)/(np.linalg.norm(ev)*d),-1,1))))
    cas_ratio=float(np.clip(o[12]/max(o[13],1.),.4,1.2))
    own_tas=max(float(o[13])*FT_TO_M,100.)
    lead_seconds=min(10.,d/max(own_tas,150.))
    lead=rel+ev*lead_seconds
    return {'distance_m':d,'blue_angle_deg':math.degrees(math.acos(float(np.clip(x/max(d,1e-9),-1,1)))),
            'blue_az_deg':math.degrees(math.atan2(y,x)),
            'blue_el_deg':math.degrees(math.atan2(-z,math.hypot(x,y))),
            'bearing_deg':math.degrees(math.atan2(rel[1],rel[0]))%360,
            'elevation_deg':math.degrees(math.atan2(-rel[2],math.hypot(rel[0],rel[1]))),
            'aspect_proxy_deg':aspect,'closing_mps':-float(np.dot(rel,rv))/max(d,1e-9),
            'lead_bearing_deg':math.degrees(math.atan2(lead[1],lead[0]))%360,
            'lead_elevation_deg':math.degrees(math.atan2(-lead[2],math.hypot(lead[0],lead[1]))),
            'own_tas_mps':own_tas,'cas_ratio':cas_ratio,
            'enemy_equivalent_cas_kts':float(np.linalg.norm(ev))*1.9438444924*cas_ratio}
def policy_state(o):
    o=validate_observation(o);g=geometry_from_observation(o);p,t=np.radians(o[3:5])
    s=np.array([g['distance_m']/5000,(o[22]-o[2])*FT_TO_M/5000,g['blue_el_deg']/90,
      g['blue_az_deg']/180,g['aspect_proxy_deg']/180,math.sin(p),math.cos(p),math.sin(t),math.cos(t),
      o[18]/30,o[19]/30,o[2]*FT_TO_M/5000,o[13]*FT_TO_M/340,g['closing_mps']/340,
      *list(o[15:18]*FT_TO_M/340),*list(o[9:12])],dtype=np.float32)
    return np.clip(s,-500,500)
class OwnSnapshot:
    def __init__(self,o):
        self.fdm=dict(zip(OWN_KEYS,validate_observation(o)[:20]))
        self.fdm['velocities/vc-kts']=o[12]*FPS_TO_KTS
class PacketController:
    def __init__(self,config,safety=True):
        from combat_v3.controller import FlightController
        self.control=FlightController(config['safety_floor_m'],config)
        self.safety=safety
    def act(self,obs,residual,started=True):
        # During INIT no rate limiter, accumulator, or guidance state advances.
        if not started:return np.array([0,0,0,.8]),False
        o=validate_observation(obs)
        return self.control.pursue_observation(OwnSnapshot(o),geometry_from_observation(o),residual,self.safety)
