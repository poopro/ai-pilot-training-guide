"""Versioned17 legal own-packet features and explicit judge reward contract."""
import math,sys
import numpy as np
import common as c
sys.path.insert(0,str(c.b.base.ADAPTER))
from packet_features import validate_observation,geometry_from_observation,tactical_obs
def observation(packet,own_attack,own_guard,elapsed_ticks):
    if type(own_attack) is not int or own_attack<0 or type(elapsed_ticks) is not int or not 0<=elapsed_ticks<=18000:raise ValueError('Own private counter/clock')
    if type(own_guard) is not bool:raise ValueError('Own guard')
    o=validate_observation(packet);g=geometry_from_observation(o)
    heading=math.radians((g['bearing_deg']-o[5]+180)%360-180)
    extra=[math.tanh((float(o[12])/1.6878098571011957)/400.),math.tanh((float(o[13])*.3048)/250.),math.sin(heading),math.cos(heading)]
    value=np.concatenate((tactical_obs(o,g,own_attack,own_guard,elapsed_ticks=elapsed_ticks),np.asarray(extra,dtype=np.float32))).astype(np.float32)
    if value.shape!=(17,) or not np.isfinite(value).all() or np.any(np.abs(value)>2):raise RuntimeError('Illegal17-feature packet observation')
    return value
def reward(before,after):
    if before['event']!='ongoing':raise ValueError('Cannot advance resolved game')
    delta=((after['advantage'][0]-after['advantage'][1])-(before['advantage'][0]-before['advantage'][1]))/(10000./60.)
    terminal=after['event']!='ongoing'
    if terminal:
        if after['winner'] not in ('blue','red','draw'):raise RuntimeError('Unresolved official assumption; stop, no invented target')
        delta += {'blue':180.,'red':-180.,'draw':0.}[after['winner']]
    return float(delta),bool(terminal)
