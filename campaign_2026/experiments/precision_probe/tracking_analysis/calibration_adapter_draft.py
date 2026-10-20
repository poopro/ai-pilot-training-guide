"""Local adapter draft. Original FDM/controller; command-channel calibration only."""
import json, math
import numpy as np

def make_pair(runtime, altitude_ft=12000., speed_cas_kts=320.):
    settings=json.loads((runtime.env.BASE/'combat_v3'/'config.json').read_text(encoding='utf-8'))
    common=dict(fdm_aircraft='f16',fdm_ic_v=speed_cas_kts,fdm_ic_lat=23.055,
        fdm_ic_h=altitude_ft,fdm_ic_theta=0.,fdm_ic_phi=0.,fdm_freq=60,fdm_fgfs=False)
    own=runtime.JsbsimFdm(fdm_id=1,fdm_ic_long=121.941,fdm_ic_psi=0.,**common)
    enemy=runtime.JsbsimFdm(fdm_id=2,fdm_ic_long=121.961,fdm_ic_psi=180.,**common)
    for fdm in [own,enemy]:
        if not math.isclose(fdm.fdm.get_delta_t(),1/60,rel_tol=0,abs_tol=1e-12):
            raise ValueError('FDM physics rate differs from the fixed calibration protocol')
    control=runtime.RepairController(settings,'repair')
    reference_control=runtime.RepairController(settings,'repair')

    class Adapter:
        def __init__(self):
            self.own=own;self.reference=enemy;self.ticks=0
        def read_obs(self):
            return runtime.simulator_observation(self.own,self.reference)
        def advance(self,command):
            c=np.asarray(command,dtype=float)
            if c.shape!=(4,) or not np.isfinite(c).all() or np.any(c<[-1,-1,-1,0]) or np.any(c>[1,1,1,1]):
                raise ValueError('Invalid own command')
            # Both FDMs advance exactly once. Reference is a fixed bank0/path-hold
            # legal-observation controller; no judge or hidden enemy state is used.
            reference_obs=runtime.simulator_observation(self.reference,self.own)
            reference_control.mode='track'
            reference_cmd,_=reference_control.command(reference_obs,0.,float(reference_obs[18]),speed_cas_kts,
                rudder=0.,safety=True)
            self.own.sendAction(c);self.reference.sendAction(reference_cmd)
            self.own.step();self.reference.step();self.ticks+=1
        def close(self):
            # The wrapper has no close() API. Release our simulator references;
            # a dedicated worker process provides the final lifetime boundary.
            self.own=None;self.reference=None
    return Adapter(),control
