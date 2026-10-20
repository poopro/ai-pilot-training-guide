"""Test last-write IC speed and no hidden first tick without changing runtime files."""
import sys
from common import *
sys.path.insert(0,str(BASE))
from combat_v3.fdm import JsbsimFdm
rows=[]
for altitude in (10000,15000,20000):
    plane=JsbsimFdm(fdm_ic_v=340,fdm_ic_h=altitude,fdm_ic_lat=23.060552,fdm_ic_long=121.948555,fdm_ic_psi=75)
    before=float(plane.fdm['velocities/vc-kts'])
    for key,value in [('ic/lat-gc-deg',23.060552),('ic/long-gc-deg',121.948555),('ic/h-sl-ft',altitude),
                      ('ic/psi-true-deg',75),('ic/theta-deg',0),('ic/phi-deg',0),('ic/vc-kts',340)]:plane.fdm[key]=value
    plane.fdm.run_ic();plane.fdm['propulsion/starter_cmd']=1;plane.fdm['propulsion/active_engine']=True
    plane.fdm['propulsion/set-running']=-1
    rows.append({'height':altitude,'before_cas_kts':before,'after_cas_kts':float(plane.fdm['velocities/vc-kts']),
                 'lat':float(plane.fdm['position/lat-gc-deg']),'altitude':float(plane.fdm['position/h-sl-ft'])})
print(json.dumps(rows))
atomic(Path(read(ROOT/'最新狀態.json')['job_dir'])/'initialization_fix_probe.json',rows)
