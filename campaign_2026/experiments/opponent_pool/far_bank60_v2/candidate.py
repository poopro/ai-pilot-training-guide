"""Only project the far roll target; unchanged inner command retains safety."""
import math

FAR_M=914.4
BANK_DEG=60.

def project_goal(distance_m,requested,*,enabled):
    if len(requested)!=4 or not math.isfinite(distance_m) or distance_m<0 or not all(math.isfinite(x) for x in requested):
        raise ValueError('Finite distance and four requested goals required')
    if type(enabled) is not bool:raise ValueError('Explicit candidate flag required')
    roll=requested[0]
    if enabled and distance_m>FAR_M:roll=max(-BANK_DEG,min(BANK_DEG,roll))
    return [roll,*requested[1:]]
