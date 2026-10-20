import ast,importlib.util,json,math,sys,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('far_speed_static_exact_candidate',HERE/'candidate.py');c=importlib.util.module_from_spec(sp);sp.loader.exec_module(c)
checks=[]
for d in (0,152.4,914.4-1e-9,914.4,914.4+1e-9,3000.):
    for he in (-179.,-45.00001,-45.,0.,45.,45.00001,179.):
        for raw in (250.,290.,360.,500.):
            g=[-72.,13.,290.,.003]
            assert c.map_speed(d,he,raw,g,enabled=False)==g
            v=c.map_speed(d,he,raw,g,enabled=True)
            assert v[0]==g[0] and v[1]==g[1] and v[3]==g[3]
            assert v[2]==(max(260.,min(450.,raw)) if d>914.4 and abs(he)>45 else g[2])
checks.append('distance/heading inclusive boundaries, both directions, final speed bounds, other goals unchanged')
for bad in (float('nan'),float('inf'),-1.):
    try:c.map_speed(bad,90.,350.,[72.,0.,290.,0.],enabled=True)
    except ValueError:pass
    else:raise AssertionError('Invalid distance accepted')
checks.append('invalid inputs failclosed')
def definition(p,name):
    nodes=[n for n in ast.walk(ast.parse(p.read_text(encoding='utf8'))) if isinstance(n,ast.FunctionDef) and n.name==name];assert len(nodes)==1;return ast.dump(nodes[0],include_attributes=False)
for name in ('initialize_side','expired','stop','terminate_known','blue_act','red_action','blue_send','red_send','physics','judge'):
    assert definition(HERE/'battle.py',name)==definition(HERE.parent/'far_bank60_v2/battle.py',name);checks.append(name+' frozen AST')
tree=ast.parse((HERE/'battle.py').read_text(encoding='utf8'));f=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=='logged_command');calls=[x for x in ast.walk(f) if isinstance(x,ast.Call)]
assert sum(isinstance(x.func,ast.Name) and x.func.id=='original_command' for x in calls)==1
assert not any(isinstance(x.func,ast.Attribute) and x.func.attr in ('act','step','sendAction') for x in calls)
checks.append('one unchanged safety command, no extra act/send/step')
import battle
assert battle.SEEDS==(2026310700,2026310701) and len(battle.plan())==4 and battle.TOTAL==600 and battle.CASE_SECONDS==90
poison=types.ModuleType('candidate');poison.project_goal=None;sys.modules['candidate']=poison
sys.path.insert(0,str(HERE.parents[2]/'experiments/m4_tactical_v4'));import m4_tactical_rl
assert Path(battle.project_goal.__code__.co_filename).resolve()==HERE/'candidate.py' and sys.modules['candidate'] is poison
checks.append('exact cold module binding / four-case source plan')
import numpy as np
for d,he in ((np.float64(1000),np.float64(179)),(np.float64(914.4),np.float64(45))):json.dumps(c.map_speed(d,he,np.float64(350),[72.,0.,290.,0.],enabled=True),allow_nan=False)
checks.append('NumPy legal scalar serialization')
# Geodetic ACMI latitude cannot be equated to geocentric OWN latitude.
gd=math.radians(23.18620064256812);aa=20925646.32546*.3048;bb=20855486.5951*.3048;e=1-(bb/aa)**2;rn=aa/math.sqrt(1-e*math.sin(gd)**2);h=3160.1799968592436
gc=math.degrees(math.atan2((rn*(1-e)+h)*math.sin(gd),(rn+h)*math.cos(gd)))
assert abs(gc-23.04730770521738)<1e-8 and abs(math.degrees(gd)-23.04730770521738)>.1
ast.parse((HERE/'verify.py').read_text(encoding='utf8'));checks.append('geodetic/geocentric regression and strict verifier syntax')
print(dict(passed=len(checks),checks=checks,new_FDM_ticks=0,training_started=False))
