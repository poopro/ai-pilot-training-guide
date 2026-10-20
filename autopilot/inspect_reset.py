"""Measure actual simulator initialization, rather than trusting the requested label."""
import sys,numpy as np
from common import *
sys.path.insert(0,str(BASE))
from combat_v3.env import CombatEnvV3
from combat_v3.interface import simulator_observation,geometry_from_observation,FPS_TO_KTS
job=read(ROOT/'最新狀態.json');rows=[]
for distance in (3000,6000,9000):
    for seed in (20261200,20261201,20261202):
        e=CombatEnvV3(opponent='maneuver',scenario='official',max_steps=1)
        try:
            _,info=e.reset(seed=seed,options={'distance_ft':distance})
            o=simulator_observation(e.fdm1,e.fdm2);g=geometry_from_observation(o)
            rows.append({'seed':seed,'requested_distance_ft':distance,'actual_distance_ft':g['distance_m']/.3048,
                         'relative_error_percent':100*(g['distance_m']/(distance*.3048)-1),
                         'own_altitude_ft':float(o[2]),'own_calibrated_speed_kts':float(o[12]*FPS_TO_KTS),
                         'info_speed_kts':info['speed_kts'],'true_speed_kts':float(o[13]*FPS_TO_KTS),
                         'ic_vc_kts':float(e.fdm1.fdm['ic/vc-kts']),
                         'ground_speed_kts':float(np.linalg.norm(o[6:9])*FPS_TO_KTS)})
        finally:e.close()
result={'rows':rows,'max_distance_error_percent':max(abs(r['relative_error_percent']) for r in rows),'utc':stamp()}
atomic(Path(job['job_dir'])/'initialization_audit.json',result)
print(json.dumps(result))
