"""Existing rule families, one real act and command per live frame.

This module never imports a simulator, actor, judge, telemetry or training.
The controller receives only the legal packet. No learned residual/tactic.
"""
from pathlib import Path
import copy,hashlib,importlib.util,inspect,json,sys
import numpy as np
ROOT=Path(r'E:\ai_pilot\campaign_2026')
REPAIR=ROOT/'repair_v1/controller.py'
STATION=ROOT/'experiments/m4_tactical_v4/m1_station.py'
FAMILIES=('station_zero','pure_guide')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def exact_module(name,path):
    if name in sys.modules:
        module=sys.modules[name]
        if Path(module.__file__).resolve()!=path:raise RuntimeError('Wrong cached module')
        return module
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module
def build_controller(family,settings):
    if family not in FAMILIES:raise ValueError('Unknown rule family')
    if family=='pure_guide':
        module=exact_module('rule_family_v1_exact_repair',REPAIR)
        controller=module.RepairController(copy.deepcopy(settings),'repair')
    else:
        # Canonical parent import is checked rather than trusted by name.
        module=exact_module('rule_family_v1_exact_station',STATION)
        controller=module.StationController(copy.deepcopy(settings),'station')
        controller.set_tactical(0.,0.,0.)
    receipt=controller_receipt(controller)
    expected=REPAIR if family=='pure_guide' else STATION
    if receipt['class_path']!=str(expected) or receipt['act_path']!=str(expected) or receipt['command_path']!=str(REPAIR):raise RuntimeError('Mixed controller wiring')
    if family=='pure_guide' and hasattr(controller,'set_tactical'):raise RuntimeError('Pure guide gained tactical injection')
    return controller
def controller_receipt(controller):
    path=Path(inspect.getfile(type(controller))).resolve()
    act=Path(controller.act.__func__.__code__.co_filename).resolve()
    command=Path(controller.command.__func__.__code__.co_filename).resolve()
    return dict(class_name=type(controller).__name__,class_path=str(path),class_sha256=sha(path),act_path=str(act),act_sha256=sha(act),command_path=str(command),command_sha256=sha(command),
        MRO=[dict(name=c.__name__,path=str(Path(inspect.getfile(c)).resolve())) for c in type(controller).__mro__ if c is not object])

class RulePolicy:
    """Adapter for direct RepairDuel.step(zero4), not TacticalDuel.step(zero3).

    Parent passes a zero4 compatibility argument; it is checked, then real act
    receives residual=None. An attempted nonzero residual fails before act.
    Reset creates an entirely new controller and deep-copied settings.
    """
    def __init__(self,family,settings):
        self.family=family;self.settings=copy.deepcopy(settings);self.reset()
    def reset(self):
        self.controller=build_controller(self.family,self.settings)
        self.receipt=controller_receipt(self.controller)
        self.act_calls=0;self.command_calls=0;self.last=None
        original=self.controller.command
        def command(packet,roll,pitch,speed,rudder=0.,safety=True):
            if safety is not True:raise RuntimeError('Safety must remain enabled')
            self.command_calls+=1
            goals=[float(roll),float(pitch),float(speed),float(rudder)]
            value=original(packet,*goals,safety=True)
            self.last=dict(requested=goals,applied=list(goals),safety=True,family=self.family,residual=None,
                act_calls=self.act_calls,command_calls=self.command_calls)
            json.dumps(self.last,allow_nan=False)
            return value
        self.controller.command=command
        return self.receipt.copy()
    def act(self,packet,residual=None,started=True):
        if type(started) is not bool:raise ValueError('Explicit START boolean required')
        if residual is not None:
            values=np.asarray(residual,dtype=float)
            if values.shape!=(4,) or not np.isfinite(values).all() or np.any(values!=0):raise ValueError('No nonzero or tactical residual allowed')
        obs=np.asarray(packet,dtype=float)
        if obs.shape!=(26,) or not np.isfinite(obs).all():raise ValueError('Only finite OWN20+ENEMY6 packet')
        if self.family=='station_zero' and any(getattr(self.controller,k)!=0 for k in ('tac_aggression','tac_break','tac_range')):raise RuntimeError('Unexpected tactical injection')
        before=self.command_calls;self.act_calls+=1
        result=self.controller.act(obs,residual=None,started=started)
        if self.command_calls-before!=int(started):raise RuntimeError('Not exactly one command per started act')
        return result
    @property
    def mode(self):return self.controller.mode
    @property
    def telemetry(self):return self.controller.telemetry
