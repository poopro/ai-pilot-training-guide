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
    import runpy,importlib.util,inspect
    spec=read(out/'CONTRACT.json')
    if os.getppid()!=spec['guardian']['pid'] or not live(spec['guardian']):raise RuntimeError('Wrong parent identity')
    for path,h in spec['new_sources'].items():
        if sha(Path(path))!=h:raise RuntimeError('New source changed')
    new=ROOT/'experiments/opponent_pool/far_speed_v1';sys.path.insert(0,str(new))
    exact=importlib.util.spec_from_file_location('battle',new/'battle.py');module=importlib.util.module_from_spec(exact);exact.loader.exec_module(module);sys.modules['battle']=module
    runpy.run_path(str(new/'test_static.py'))
    import numpy as np
    import m4_tactical_rl as m
    import combat_v3.env as ce
    settings=read(Path(ce.__file__).parent/'config.json');records=[];total_changed=0
    for case in b.plan():
        if case['actor']!='station_zero':continue
        folder=RUN/'cases'/case['id'];r=read(folder/'RESULT.json');assert sha(folder/'telemetry.jsonl')==r['artifacts']['telemetry.jsonl']
        controllers=[m.TacticalDuel._build_blue(types.SimpleNamespace(settings=settings)) for _ in range(2)]
        assert all(Path(inspect.getfile(type(c))).resolve()==ROOT/'experiments/m4_tactical_v4/m1_station.py' for c in controllers)
        row=None;changes=0;calls=[0,0];emitted=[None,None]
        def make_hook(index,original):
            def hook(packet,roll,pitch,speed,rudder=0.,safety=True):
                nonlocal changes
                requested=[float(roll),float(pitch),float(speed),float(rudder)]
                assert requested==row['blue_guidance']['requested']
                applied,trace=module.project_goal(packet,requested,enabled=index==1)
                assert applied[0]==requested[0] and applied[1]==requested[1] and applied[3]==requested[3] and safety is True
                if index==0:assert applied==requested
                else:changes+=int(applied[2]!=requested[2]);json.dumps(trace,allow_nan=False)
                calls[index]+=1
                return original(packet,*applied,safety=safety)
            return hook
        for index,ctrl in enumerate(controllers):ctrl.command=make_hook(index,ctrl.command)
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                row=json.loads(line)
                if row['tick']>300:break
                if b.expired(spec) or b.stop(out):raise RuntimeError('Precheck deadline/STOP')
                outputs=[ctrl.act(row['blue_packet_pre'],np.zeros(4),started=True) for ctrl in controllers]
                np.testing.assert_array_equal(outputs[0][0],row['blue_command']);assert outputs[0][1]==row['blue_private_guard']
        assert calls==[300,300] and changes>0;total_changed+=changes
        records.append(dict(case=case['id'],saved_packet_frames=300,baseline_actual_inner_commands_exact=True,single_act_and_command_counts=calls,candidate_only_speed_goal_changed_frames=changes,fresh_controller_state_per_case=True))
    for path,h in spec['new_sources'].items():
        if sha(Path(path))!=h:raise RuntimeError('New source changed')
    b.source_gate(read(RUN/'CONTRACT.json'))
    write(out/'VERIFICATION.json',dict(verified_saved_packet_precheck=True,static_checks=16,results=records,saved_packet_frames=600,candidate_goal_changes=total_changed,new_FDM_ticks=0,new_model_inference=False,training_started=False,scope='Two new controller instances per saved prefix, original baseline exact command replay, candidate changes speed target only. No closed-loop strength result.'))
    print(json.dumps(dict(verified_saved_packet_precheck=True,results=records)),flush=True);return 0

def launch():
    sys.path.insert(0,str(ROOT));from runner import JobLock
    with JobLock(ROOT/'launch.lock'):
        if b.base.inventory():raise RuntimeError('Other or unknown work active')
        resources=b.base.resources()
        if b.stop(RUN):raise RuntimeError('STOP')
        b.source_gate(read(RUN/'CONTRACT.json'))
        out=ROOT/'diagnostics'/('far_speed_precheck_v1_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6]);out.mkdir()
        started=time.monotonic();spec=dict(guardian=identity(),deadline_epoch=time.time()+LIMIT,deadline_monotonic=started+LIMIT,seconds=LIMIT,diagnostic_source_sha256=sha(Path(__file__)),source_run=str(RUN),original_source_contract_sha256=sha(RUN/'CONTRACT.json'),resources=resources,usage_observation=read(Path(__file__).with_suffix('.usage.json')),new_FDM_ticks=0,seed_claims=[],training_started=False)
        spec['new_sources']={str(p):sha(p) for p in (ROOT/'experiments/opponent_pool/far_speed_v1').glob('*.py')}
        write(out/'CONTRACT.json',spec)
        lp=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=read(lp) if lp.exists() else dict(date_taipei=datetime.datetime.now().date().isoformat(),daily_limit_hours=6.,reserved_hours=0.,items=[],policy='warning_only_no_refund');ledger['items'].append(dict(id=out.name,hours=LIMIT/3600,status='reserved_offline_far_speed_precheck',output=str(out),warning_only=True));ledger['reserved_hours']=sum(i['hours'] for i in ledger['items']);write(lp,ledger)
        j=read(ROOT/'research_latest.json');j['active_workload']=dict(status='running_offline_far_speed_precheck',run=str(out),supervisor=b.normalized(spec['guardian']),worker=None);j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[j['active_workload']]);write(ROOT/'research_latest.json',j)
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
            if item['id']==out.name:item.update(status='offline_far_speed_precheck_complete_pending_parent' if passed else 'failed_offline_far_speed_precheck',actual_worker_exit=code,actual_wall_seconds=time.monotonic()-started)
        write(lp,ledger)
        j=read(ROOT/'research_latest.json');j['active_workload']=None;j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[]);j['latest_far_speed_precheck']=str(out);write(ROOT/'research_latest.json',j)
        print(json.dumps(dict(out=str(out),actual_worker_exit=code,reason=reason,absent=absent,wall_seconds=time.monotonic()-started)),flush=True)
        return 0 if passed else 2

if __name__=='__main__':
    raise SystemExit(worker(Path(sys.argv[2])) if len(sys.argv)==3 and sys.argv[1]=='--worker' else launch())
