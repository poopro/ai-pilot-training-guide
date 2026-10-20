"""Only remove the far heading speed ceiling; original command owns safety."""
import math,importlib.util
from pathlib import Path
FEATURES=Path(r'E:\ai_pilot\campaign_2026\experiments\opponent_pool\frozen_sac_opponent_v2\packet_features.py')
_spec=importlib.util.spec_from_file_location('far_speed_exact_packet_geometry',FEATURES);_module=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_module)
geometry_from_observation=_module.geometry_from_observation
def map_speed(distance,he,raw,requested,*,enabled):
    if type(enabled) is not bool or len(requested)!=4 or not all(math.isfinite(float(x)) for x in [distance,he,raw,*requested]) or distance<0:raise ValueError('Finite legal goals and explicit flag required')
    eligible=bool(distance>914.4 and abs(he)>45.)
    result=[float(x) for x in requested]
    if enabled and eligible:result[2]=float(max(260.,min(450.,raw)))
    return result
def project_goal(packet,requested,*,enabled):
    geo=geometry_from_observation(packet);d=geo['distance_m'];band=152.4<=d<=914.4;wrap=lambda x:(x+180)%360-180
    bearing=geo['bearing_deg']
    if not band:bearing+=max(-20.,min(20.,wrap(geo['lead_bearing_deg']-bearing)))*.35
    he=float(wrap(bearing-packet[5]));close=max(-30.,min(65.,(d-600)*.07)) if not band else 0.
    raw=float(geo['enemy_equivalent_cas_kts']+close*1.9438444924*geo['cas_ratio'])
    old=float(max(260.,min(450.,min(raw,290.) if abs(he)>45 and not band else raw)))
    if abs(float(requested[2])-old)>1e-8:raise RuntimeError('Non-zero tactical or residual / wrong original StationController speed')
    applied=map_speed(d,he,raw,requested,enabled=enabled)
    return applied,dict(distance_m=float(d),heading_error_deg=he,raw_speed_kts=raw,original_speed_kts=old,eligible=bool(d>914.4 and abs(he)>45),enabled=enabled)
