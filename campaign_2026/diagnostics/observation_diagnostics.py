"""Local OWN20+ENEMY6 adapter for the reviewed public math module."""
import math
import numpy as np
from precision_math import analyze

def analyze_observation(observation):
    o=np.asarray(observation,dtype=float)
    if o.shape!=(26,) or not np.isfinite(o).all():
        raise ValueError('Observation must contain 26 finite doubles')
    if not (-90 <= o[0] <=90 and -90 <= o[20] <=90 and -180 <= o[1] <=180 and -180 <= o[21] <=180):
        raise ValueError('Invalid latitude/longitude')
    lat, enemy_lat=math.radians(o[0]),math.radians(o[20])
    relative=np.array([(enemy_lat-lat)*6378137,
        math.radians((o[21]-o[1]+180)%360-180)*6378137*math.cos((lat+enemy_lat)/2),
        -(o[22]-o[2])*.3048])
    velocity=(o[23:26]-o[6:9])*.3048
    return analyze(relative,velocity,o[3],o[4],o[5])
