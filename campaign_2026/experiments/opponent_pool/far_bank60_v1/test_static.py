"""Meaningful boundary and frozen physics checks; no FDM or model learning."""
import ast,hashlib,math
from pathlib import Path
import candidate
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'frozen_sac_battle_v2'
def definition(path,name):
    tree=ast.parse(path.read_text(encoding='utf8'))
    matches=[x for x in ast.walk(tree) if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name==name]
    if len(matches)!=1:raise AssertionError(name)
    return ast.dump(matches[0],include_attributes=False)

checks=[]
for distance in (0.,152.4,914.4-1e-9,914.4,914.4+1e-9,1200.,5000.):
    for roll in (-72.,-60.,-59.,0.,59.,60.,72.):
        goals=[roll,13.125,287.75,-.002]
        assert candidate.project_goal(distance,goals,enabled=False)==goals
        actual=candidate.project_goal(distance,goals,enabled=True)
        assert actual[1:]==goals[1:]
        assert actual[0]==(max(-60.,min(60.,roll)) if distance>914.4 else roll)
        assert goals==[roll,13.125,287.75,-.002]
checks.append('strict range boundary, both bank signs, unchanged other goals and baseline')
for bad in (float('nan'),float('inf'),-1.):
    try:candidate.project_goal(bad,[72,0,300,0],enabled=True)
    except ValueError:pass
    else:raise AssertionError('invalid distance')
checks.append('invalid input fail closed')
for name in ('initialize_side','expired','stop','terminate_known','blue_act','red_action','blue_send','red_send'):
    assert definition(HERE/'battle.py',name)==definition(OLD/'battle.py',name)
    checks.append(name+' original AST unchanged')
for f in ('battle.py','verify.py','candidate.py'):ast.parse((HERE/f).read_text(encoding='utf8'))
import battle
assert len(battle.plan())==4 and battle.SEEDS==(2026310300,2026310301) and battle.TOTAL==600 and battle.CASE_SECONDS==90
assert all(c['actor'] in ('station_zero','far_bank60') and c['red']=='sac5000' for c in battle.plan())
checks.append('four games; two unclaimed development seeds; original worker/global limits')
worker=ast.parse((HERE/'battle.py').read_text(encoding='utf8'))
mapped=next(x for x in ast.walk(worker) if isinstance(x,ast.FunctionDef) and x.name=='logged_command')
calls=[x for x in ast.walk(mapped) if isinstance(x,ast.Call)]
assert sum(isinstance(c.func,ast.Name) and c.func.id=='original_command' for c in calls)==1
assert not any(isinstance(c.func,ast.Attribute) and c.func.attr in ('act','step','sendAction') for c in calls)
checks.append('goal projection calls unchanged inner command once; no extra act/send/physics')
print({'passed':len(checks),'checks':checks,'new_FDM_ticks':0,'training_started':False})
