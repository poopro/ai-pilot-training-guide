"""Interface/state/magnitude/physics checks, no environment constructed."""
import ast,importlib.util,sys,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('rear_latch_test_exact_candidate',HERE/'candidate.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
checks=[]
for sign in (-1,1):
    l=c.RearLatch();goals=[sign*60.,12.3,290.,.01]
    a,t=l.apply(goals,sign*179.,150.,enabled=True);assert a==goals and not t['active']
    opposite=[-sign*60.,*goals[1:]]
    a,t=l.apply(opposite,-sign*179.,150.,enabled=True);assert a==goals and t['triggered']
    for magnitude in (0.,17.,60.,72.):
        a,t=l.apply([-sign*magnitude,*goals[1:]],-sign*95.,110.,enabled=True)
        assert abs(a[0])==magnitude and a[0]*sign>=0 and a[1:]==goals[1:] and t['active']
    a,t=l.apply(opposite,-sign*80.,90.,enabled=True);assert a==opposite and t['released'] and not t['active']
    l.reset();a,t=l.apply(opposite,-sign*179.,150.,enabled=True);assert a==opposite and not t['active']
    checks.append('both signs trigger, hold, magnitude including zero, forward-inclusive release, reset '+str(sign))
for enabled in (True,False):
    l=c.RearLatch()
    for he,angle in ((1.,30.),(-1.,30.),(179.,89.),(-179.,89.)):
        g=[60. if he>0 else -60.,2.,290.,0.];a,t=l.apply(g,he,angle,enabled=enabled);assert a==g and not t['active']
checks.append('no zero-cross or forward-wrap trigger; disabled baseline unchanged')
for d in (152.4,914.4,914.4+1e-9,1100.):
    for roll in (-72.,0.,72.):
        g=[roll,12.,310.,.003];a=c.project_goal(d,g,enabled=True)
        assert a==[max(-60.,min(60.,roll)) if d>914.4 else roll,*g[1:]]
checks.append('same far60/near72 inclusive boundary, speed pitch rudder untouched')
for he,angle in ((float('nan'),120.),(180.,120.),(0.,181.)):
    try:c.RearLatch().apply([60.,0.,290.,0.],he,angle,enabled=True)
    except ValueError:pass
    else:raise AssertionError('invalid inputs not rejected')
checks.append('nonfinite/invalid angle failclosed')
def definition(p,name):
    nodes=[n for n in ast.walk(ast.parse(p.read_text(encoding='utf8'))) if isinstance(n,ast.FunctionDef) and n.name==name]
    assert len(nodes)==1;return ast.dump(nodes[0],include_attributes=False)
for name in ('initialize_side','expired','stop','terminate_known','blue_act','red_action','blue_send','red_send','physics','judge'):
    assert definition(HERE/'battle.py',name)==definition(HERE.parent/'far_bank60_v2/battle.py',name)
    checks.append(name+' unchanged AST')
tree=ast.parse((HERE/'battle.py').read_text(encoding='utf8'))
fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='logged_command')
calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call)]
assert sum(isinstance(n.func,ast.Name) and n.func.id=='original_command' for n in calls)==1
assert not any(isinstance(n.func,ast.Attribute) and n.func.attr in ('step','act','sendAction') for n in calls)
checks.append('one unchanged safety command; no additional act/physics/send')
import battle
assert battle.SEEDS==(2026310500,2026310501) and len(battle.plan())==4 and battle.TOTAL==600 and battle.CASE_SECONDS==90
poison=types.ModuleType('candidate');poison.RearLatch=None;sys.modules['candidate']=poison
sys.path.insert(0,str(HERE.parents[2]/'experiments/m4_tactical_v4'));import m4_tactical_rl
assert Path(battle.RearLatch.apply.__code__.co_filename).resolve()==HERE/'candidate.py'
assert sys.modules['candidate'] is poison
checks.append('exact cold module binding resists generic candidate cache collision')
print({'passed':len(checks),'checks':checks,'new_FDM_ticks':0,'training_started':False})
