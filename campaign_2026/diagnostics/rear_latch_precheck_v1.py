"""Bounded offline guidance projection over saved packets; no FDM/model call.

The frozen StationController.act and its bearing history are used unchanged.
command() is a recorder: it does not replay the inner actuator controller.
Actual sent-command equality is prior independently verified evidence.
"""
from pathlib import Path
import datetime,hashlib,inspect,json,math,os,subprocess,sys,time,types,uuid
import psutil

ROOT=Path(r'E:\ai_pilot\campaign_2026')
SOURCE=ROOT/'experiments/opponent_pool/far_bank60_v2'
RUN=SOURCE/'run_20261017_153047_104619'
sys.path.insert(0,str(SOURCE))
import battle as b
read,write,sha,identity,live=b.read,b.write,b.sha,b.identity,b.live
LIMIT=120

def worker(out):
    import runpy,inspect
    spec=read(out/'CONTRACT.json')
    if os.getppid()!=spec['guardian']['pid'] or not live(spec['guardian']):raise RuntimeError('Wrong direct parent')
    for path,h in spec['new_sources'].items():
        if sha(Path(path))!=h:raise RuntimeError('Precheck source changed')
    new=ROOT/'experiments/opponent_pool/rear_latch60_v1'
    sys.path.insert(0,str(new))
    import importlib.util
    exact=importlib.util.spec_from_file_location('battle',new/'battle.py');module=importlib.util.module_from_spec(exact);exact.loader.exec_module(module);sys.modules['battle']=module
    runpy.run_path(str(new/'test_static.py'))
    helper=sys.modules['battle'];c=helper._goal_module
    import numpy as np
    import m4_tactical_rl as m
    from combat_v3.interface import geometry_from_observation
    import combat_v3.env as ce
    settings=read(Path(ce.__file__).parent/'config.json')
    results=[]
    for case in b.plan():
        if case['actor']!='far_bank60':continue
        folder=RUN/'cases'/case['id'];result=read(folder/'RESULT.json')
        if sha(folder/'telemetry.jsonl')!=result['artifacts']['telemetry.jsonl']:raise RuntimeError('Saved packets changed')
        controls=[m.TacticalDuel._build_blue(types.SimpleNamespace(settings=settings)) for _ in range(2)]
        original=[ctrl.command for ctrl in controls];latch=c.RearLatch();row=None;first=None;precommands=0
        def originalcap(packet,roll,pitch,speed,rudder=0.,safety=True):
            geo=geometry_from_observation(packet);g=[roll,pitch,speed,rudder]
            if g!=row['blue_guidance']['requested']:raise RuntimeError('Original act goals changed')
            applied=c.project_goal(geo['distance_m'],g,enabled=True)
            return original[0](packet,*applied,safety=safety)
        def latchedcap(packet,roll,pitch,speed,rudder=0.,safety=True):
            nonlocal first
            geo=geometry_from_observation(packet);g=[roll,pitch,speed,rudder]
            capped=c.project_goal(geo['distance_m'],g,enabled=True)
            he=c.heading_error(packet,geo)
            caller=sys._getframe(1)
            if abs(he-caller.f_locals['heading_error'])>1e-9:raise RuntimeError('Legal heading projection differs from original act')
            applied,t=latch.apply(capped,he,geo['blue_angle_deg'],enabled=True)
            if t['triggered'] and first is None:first=row['tick']
            if first is None and applied!=row['blue_guidance']['applied']:raise RuntimeError('Pretrigger goals changed')
            return original[1](packet,*applied,safety=safety)
        controls[0].command=originalcap;controls[1].command=latchedcap
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                if b.expired(spec) or b.stop(out):raise RuntimeError('Precheck original deadline/STOP')
                row=json.loads(line)
                commands=[ctrl.act(row['blue_packet_pre'],np.zeros(4),started=True) for ctrl in controls]
                np.testing.assert_array_equal(commands[0][0],row['blue_command'])
                if first is not None:break
                np.testing.assert_array_equal(commands[0][0],commands[1][0]);assert commands[0][1]==commands[1][1]==row['blue_private_guard'];precommands+=1
        expected=3591 if case['side']=='normal' else 3974
        if first!=expected or precommands!=first-1:raise RuntimeError('Unexpected saved first rear wrap')
        results.append(dict(case=case['id'],first_saved_packet_trigger_tick=first,pretrigger_actual_inner_commands_exact=precommands,baseline_replayed_against_recorded_actual_command=True,settings_sha256=sha(Path(__import__('combat_v3.env',fromlist=['x']).__file__).parent/'config.json')))
    for path,h in spec['new_sources'].items():
        if sha(Path(path))!=h:raise RuntimeError('Precheck source changed')
    b.source_gate(read(RUN/'CONTRACT.json'))
    write(out/'VERIFICATION.json',dict(verified_pretrigger_actual_command_replay=True,results=results,new_FDM_ticks=0,new_model_inference=False,training_started=False,closed_loop_advantage_verified=False))
    print(json.dumps(dict(verified_pretrigger_actual_command_replay=True,results=results)),flush=True)
    return 0

def launch():
    sys.path.insert(0,str(ROOT));from runner import JobLock
    with JobLock(ROOT/'launch.lock'):
        if b.base.inventory():raise RuntimeError('Other or unknown work active')
        resources=b.base.resources()
        if b.stop(RUN):raise RuntimeError('STOP')
        b.source_gate(read(RUN/'CONTRACT.json'))
        out=ROOT/'diagnostics'/('rear_latch_precheck_v1_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6]);out.mkdir()
        started=time.monotonic();spec=dict(guardian=identity(),deadline_epoch=time.time()+LIMIT,deadline_monotonic=started+LIMIT,seconds=LIMIT,diagnostic_source_sha256=sha(Path(__file__)),source_run=str(RUN),original_source_contract_sha256=sha(RUN/'CONTRACT.json'),resources=resources,usage_observation=read(Path(__file__).with_suffix('.usage.json')),new_FDM_ticks=0,seed_claims=[],training_started=False)
        spec['new_sources']={str(p):sha(p) for p in (ROOT/'experiments/opponent_pool/rear_latch60_v1').glob('*.py')}
        write(out/'CONTRACT.json',spec)
        lp=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=read(lp);ledger['items'].append(dict(id=out.name,hours=LIMIT/3600,status='reserved_offline_rear_latch_precheck',output=str(out),warning_only=True));ledger['reserved_hours']=sum(i['hours'] for i in ledger['items']);write(lp,ledger)
        j=read(ROOT/'research_latest.json');j['active_workload']=dict(status='running_offline_rear_latch_precheck',run=str(out),supervisor=b.normalized(spec['guardian']),worker=None);j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[j['active_workload']]);write(ROOT/'research_latest.json',j)
        with (out/'worker.log').open('w',encoding='utf8') as log:
            p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(Path(__file__)),'--worker',str(out)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);i=identity(p.pid);descendants={};reason=None
            write(out/'worker_identity.json',i)
            while p.poll() is None:
                try:
                    for child in psutil.Process(i['pid']).children(recursive=True):
                        try:
                            d=identity(child.pid);chain=[];node=child
                            while node.pid!=i['pid']:
                                chain.append(identity(node.pid));node=node.parent()
                                if node is None:raise RuntimeError('Lost own chain')
                            if not live(i):raise RuntimeError('Worker identity changed')
                            descendants[(d['pid'],d['create'])]=dict(identity=d,chain=chain,worker=i)
                        except psutil.NoSuchProcess:continue
                except psutil.NoSuchProcess:
                    if p.poll() is None:raise
                if b.expired(spec) or b.stop(out):reason='original_diagnostic_deadline_or_STOP';code,actions=b.terminate_known(p,i,descendants);break
                time.sleep(.1)
            else:code=p.wait(timeout=3);actions=[]
            for d in descendants.values():
                if live(d['identity']):
                    try:psutil.Process(d['identity']['pid']).wait(timeout=1)
                    except psutil.TimeoutExpired:
                        if live(d['identity']):psutil.Process(d['identity']['pid']).terminate()
            absent=not live(i) and all(not live(d['identity']) for d in descendants.values())
        passed=code==0 and reason is None and absent
        write(out/'WORKER_EXIT.json',dict(actual_worker_exit=code,reason=reason,identity=i,descendants=list(descendants.values()),absent=absent,cleanup_actions=actions,wall_seconds=time.monotonic()-started,guardian_return_intended=0 if passed else 2))
        ledger=read(lp)
        for item in ledger['items']:
            if item['id']==out.name:item.update(status='offline_rear_latch_precheck_complete_pending_parent' if passed else 'failed_offline_rear_latch_precheck',actual_worker_exit=code,actual_wall_seconds=time.monotonic()-started)
        write(lp,ledger)
        j=read(ROOT/'research_latest.json');j['active_workload']=None;j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[]);j['latest_rear_latch_precheck']=str(out);write(ROOT/'research_latest.json',j)
        print(json.dumps(dict(out=str(out),actual_worker_exit=code,reason=reason,absent=absent,wall_seconds=time.monotonic()-started)),flush=True)
        return 0 if passed else 2

if __name__=='__main__':
    raise SystemExit(worker(Path(sys.argv[2])) if len(sys.argv)==3 and sys.argv[1]=='--worker' else launch())
