"""Pure and fake-parent gates before any training seed/FDM is consumed."""
from pathlib import Path
import ast,copy,io,json,math,sys,types
import numpy as np
import common as c
from policy_features import observation,reward,tactical_obs,geometry_from_observation
def run(out):
    spec=c.check(out,'PRECHECK');c.gate(spec);checks=[]
    source=c.ROOT/'experiments/opponent_pool/bank_residual_fdm_v1/run_20261018_153511_6fb16a/RESULT.json';packet=c.read(source)['episodes'][0]['initial'][0]
    values=observation(packet,0,False,0);assert values.shape==(17,) and values.dtype==np.float32 and np.isfinite(values).all()
    np.testing.assert_array_equal(values[:13],tactical_obs(np.asarray(packet),geometry_from_observation(packet),0,False,elapsed_ticks=0))
    angle=math.radians((geometry_from_observation(packet)['bearing_deg']-packet[5]+180)%360-180)
    np.testing.assert_allclose(values[13:],[math.tanh(packet[12]/1.6878098571011957/400),math.tanh(packet[13]*.3048/250),math.sin(angle),math.cos(angle)],rtol=0,atol=1e-7)
    assert np.array_equal(values,observation(packet,0,False,0));checks.append('17 exact frozen legal13 plus explicit own speeds and signed LOS')
    for a in (-1,0,1):np.testing.assert_array_equal(c.bridge.residual(np.array([a],dtype=np.float32)),[a,0,0,0])
    for bad in ([0,0,0],float('nan'),1.1):
        try:c.bridge.residual(bad)
        except ValueError:pass
        else:raise AssertionError('Illegal bank action')
    checks.append('1D action existing4residual mapping and bounds')
    tree=ast.parse((c.HERE/'policy_features.py').read_text(encoding='utf8'));obs=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=='observation')
    assert not any(isinstance(x,ast.Attribute) and x.attr in ('judge','fdm','winner','score','advantage') for x in ast.walk(obs));checks.append('observation has only packet owncounter guard clock arguments')
    for after,bonus in [(dict(advantage=[12.,7.],event='ongoing',winner=None),0),(dict(advantage=[12.,7.],event='blue_kill',winner='blue'),180),(dict(advantage=[12.,7.],event='red_kill',winner='red'),-180),(dict(advantage=[12.,7.],event='collision',winner='draw'),0)]:
        before=dict(advantage=[9.,6.],event='ongoing',winner=None);actual,terminal=reward(before,after);assert actual==2/(10000/60)+bonus and terminal==(after['event']!='ongoing')
    try:reward(dict(advantage=[0,0],event='ongoing'),dict(advantage=[0,0],event='mutual_crash',winner=None))
    except RuntimeError:pass
    else:raise AssertionError('Invented winner')
    checks.append('independent scalar advantage reward/winner/truncation/unresolved gate')
    schedule=c.plan();assert len(schedule)==32 and len({x['seed'] for x in schedule})==32
    assert len({(x['opponent'],x['distance_ft'],x['side']) for x in schedule[:18]})==18;assert [x['opponent'] for x in schedule[:3]]==['sac5000','rule','mirror']
    checks.append('preregistered18 distinct cells in32 private episode seeds')
    import environment as e
    sys.path.insert(0,str(c.ROOT/'experiments/rules_v20261014'));from judge import Judge,RuleProfile,Frame
    fake=object.__new__(e.BankGym);fake.physics=types.SimpleNamespace(current_step=0,fdm1=None,fdm2=None,judge=types.SimpleNamespace(core=Judge(RuleProfile('line_20261014_1deg','AGL','right_bin'))));fake.case=dict(episode=0);fake.private_attack=0;fake.guard=False;fake.decisions=0;fake.samples=io.StringIO();fake.completed=[];fake.runtime=lambda:None
    fake.features=lambda:observation(packet,0,False,fake.physics.current_step)
    original_step=e.m.RepairDuel.step;original_packet=e.m.simulator_observation;received=[]
    def parent(env,action):
        received.append(action.copy())
        if env.current_step%20==0:fake.first=dict(blue_pre=packet,blue_state={},red_guard_pre=False)
        env.current_step+=1;env.judge.core.advance(Frame(2000,90,90,1,1,4000,4000),started=True)
        return None,99999.,False,False,{} # legacy reward must be ignored
    try:
        e.m.RepairDuel.step=parent;e.m.simulator_observation=lambda a,b:np.asarray(packet)
        obs,r,term,trunc,info=e.BankGym.step(fake,np.asarray([.5],dtype=np.float32));assert len(received)==20 and all(np.array_equal(x,[.5,0,0,0]) for x in received)
        record=json.loads(fake.samples.getvalue());assert record['completed_tick']==0 and record['physical_ticks']==20 and record['decision']==1 and r!=99999 and not term and not trunc
        np.testing.assert_array_equal(obs,observation(packet,0,False,20))
    finally:e.m.RepairDuel.step=original_step;e.m.simulator_observation=original_packet
    checks.append('actual new step method fake-parent20ticks/privateclock/no legacy reward leakage')
    import combat_v3.interface as interface
    settings=c.read(Path(interface.__file__).parent/'config.json');first=c.bridge.controller(settings);second=c.bridge.controller(settings)
    assert first is not second and first.settings is not second.settings;np.testing.assert_array_equal(first.act(packet,residual=None)[0],second.act(packet,residual=c.bridge.residual(0))[0]);checks.append('fresh private controller/state/settings neutral reset parity')
    loaded_red=e.build_frozen_opponent('sac5000',settings);receipt=e.runtime_receipt(loaded_red.controller);assert Path(receipt['path'])==c.ROOT/'experiments/m4_tactical_v4/m1_station.py';assert receipt['sha256']==c.sha(Path(receipt['path']));checks.append('true frozen model/controller dynamic-module method-source receipt, no FDM or learner')
    from duel_lab import RuleFighter
    rule=RuleFighter(copy.deepcopy(settings),float(packet[2])*.3048,np.random.default_rng(123))
    mirror_module=c.load('bank17_precheck_mirror',c.ROOT/'experiments/m4_tactical_v4/m3_mirror_league.py');mirror=mirror_module.MirrorP2Controller(copy.deepcopy(settings),.72,6.,9.)
    for kind,obj in (('sac5000',loaded_red),('rule',rule),('mirror',mirror)):
        for n in range(3):
            value,guard,mode=e.opponent_command(obj,kind,np.asarray(packet,dtype=float),n);assert value.shape==(4,) and type(guard) is bool and 'fallback' not in mode
    checks.append('actual shared production opponent_command three real CPU opponent APIs/guard/cadence no physics')
    reset=next(x for x in ast.walk(ast.parse((c.HERE/'environment.py').read_text(encoding='utf8'))) if isinstance(x,ast.FunctionDef) and x.name=='red_action')
    assert not any(isinstance(x,ast.Try) for x in ast.walk(reset));checks.append('opponent exceptions failclosed no silent mirror fallback')
    for path in c.HERE.glob('*.py'):ast.parse(path.read_text(encoding='utf8'))
    c.gate(spec);c.write(out/'PRECHECK.json',dict(verified_training_contract=True,checks=checks,groups=len(checks),fake_parent_physics_calls=20,new_FDM_ticks=0,learner_started=False))
    print(json.dumps(dict(precheck=True,groups=len(checks),new_FDM_ticks=0)),flush=True);return 0
if __name__=='__main__':raise SystemExit(run(Path(sys.argv[1])))
