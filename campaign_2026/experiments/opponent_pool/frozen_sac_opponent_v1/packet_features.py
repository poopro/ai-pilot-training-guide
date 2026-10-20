"""Pure OWN20+ENEMY6 features copied by AST from frozen source; no simulator access."""
import math
import numpy as np
FT_TO_M=.3048
BAND_LO_M,BAND_HI_M=500*.3048,3000*.3048
KILL_TICKS=180
def validate_observation(obs):
    o = np.asarray(obs, dtype=np.float64)
    if o.shape != (26,) or not np.isfinite(o).all():
        raise ValueError('OBS must contain 26 finite doubles')
    if not (-90 <= o[0] <= 90 and -90 <= o[20] <= 90 and (-180 <= o[1] <= 180) and (-180 <= o[21] <= 180)):
        raise ValueError('Invalid latitude/longitude')
    return o

def geometry_from_observation(o):
    o = validate_observation(o)
    lat = math.radians(o[0])
    lat2 = math.radians(o[20])
    rel = np.array([(lat2 - lat) * 6378137, math.radians(o[21] - o[1]) * 6378137 * math.cos((lat + lat2) / 2), -(o[22] - o[2]) * FT_TO_M])
    d = float(np.linalg.norm(rel))
    (phi, theta, psi) = np.radians(o[3:6])
    (cp, sp) = (math.cos(phi), math.sin(phi))
    (ct, st) = (math.cos(theta), math.sin(theta))
    (cy, sy) = (math.cos(psi), math.sin(psi))
    rotation = np.array([[ct * cy, ct * sy, -st], [sp * st * cy - cp * sy, sp * st * sy + cp * cy, sp * ct], [cp * st * cy + sp * sy, cp * st * sy - sp * cy, cp * ct]])
    (x, y, z) = rotation @ rel
    ev = o[23:26] * FT_TO_M
    rv = (o[23:26] - o[6:9]) * FT_TO_M
    aspect = 180.0 if np.linalg.norm(ev) < 1e-06 or d < 1e-06 else math.degrees(math.acos(float(np.clip(np.dot(ev, -rel) / (np.linalg.norm(ev) * d), -1, 1))))
    cas_ratio = float(np.clip(o[12] / max(o[13], 1.0), 0.4, 1.2))
    own_tas = max(float(o[13]) * FT_TO_M, 100.0)
    lead_seconds = min(10.0, d / max(own_tas, 150.0))
    lead = rel + ev * lead_seconds
    return {'distance_m': d, 'blue_angle_deg': math.degrees(math.acos(float(np.clip(x / max(d, 1e-09), -1, 1)))), 'blue_az_deg': math.degrees(math.atan2(y, x)), 'blue_el_deg': math.degrees(math.atan2(-z, math.hypot(x, y))), 'bearing_deg': math.degrees(math.atan2(rel[1], rel[0])) % 360, 'elevation_deg': math.degrees(math.atan2(-rel[2], math.hypot(rel[0], rel[1]))), 'aspect_proxy_deg': aspect, 'closing_mps': -float(np.dot(rel, rv)) / max(d, 1e-09), 'lead_bearing_deg': math.degrees(math.atan2(lead[1], lead[0])) % 360, 'lead_elevation_deg': math.degrees(math.atan2(-lead[2], math.hypot(lead[0], lead[1]))), 'own_tas_mps': own_tas, 'cas_ratio': cas_ratio, 'enemy_equivalent_cas_kts': float(np.linalg.norm(ev)) * 1.9438444924 * cas_ratio}

def enemy_heading_proxy_deg(o: np.ndarray) -> float:
    """Enemy nose direction estimated from its NED velocity. LEGAL: the official
    26-value packet carries enemy position + NED velocity, nothing else. The true
    enemy attitude is judge-only and must never reach the deployed policy."""
    (vn, ve) = (float(o[23]), float(o[24]))
    if math.hypot(vn, ve) < 0.001:
        return 0.0
    return math.degrees(math.atan2(ve, vn)) % 360.0

def tactical_obs(o: np.ndarray, geo: dict, ticks: int, guard: bool, elapsed_ticks: int=0) -> np.ndarray:
    d = geo['distance_m']
    in_band = 1.0 if BAND_LO_M <= d <= BAND_HI_M else 0.0
    eh = math.radians(enemy_heading_proxy_deg(o))
    rel = math.radians(geo['bearing_deg']) - eh
    return np.array([float(np.clip(d / 4000.0, 0.0, 1.0)), in_band, math.cos(math.radians(min(geo['blue_angle_deg'], 180.0))), math.sin(math.radians(geo['blue_angle_deg'])), math.cos(rel), math.sin(rel), math.tanh(geo['closing_mps'] / 200.0), math.sin(math.radians(o[3])), math.cos(math.radians(o[3])), math.tanh(o[14] / 9.0), ticks / KILL_TICKS, 1.0 if guard else 0.0, max(0.0, 1.0 - elapsed_ticks / 18000.0)], dtype=np.float32)
