"""Bounded offline guidance projection over saved packets; no FDM/model call.

The frozen StationController.act and its bearing history are used unchanged.
command() is a recorder: it does not replay the inner actuator controller.
Actual sent-command equality is prior independently verified evidence.
"""
from pathlib import Path
import datetime,hashlib,inspect,json,math,os,subprocess,sys,time,types,uuid
import psutil

ROOT=Path(r'E:\ai_pilot\campaign_2026')
SOURCE=ROOT/'experiments/opponent_pool/frozen_sac_battle_v2'
RUN=SOURCE/'run_20261017_093943_16bee6'
sys.path.insert(0,str(SOURCE))
import battle as b
read,write,sha,identity,live=b.read,b.write,b.sha,b.identity,b.live
LIMIT=120

def worker(out):
    spec=read(out/'CONTRACT.json');t0=time.monotonic()
    if os.getppid()!=spec['guardian']['pid'] or not live(spec['guardian']):raise RuntimeError('Wrong direct parent identity')
    if sha(Path(__file__))!=spec['diagnostic_source_sha256']:raise RuntimeError('Diagnostic source changed')
    b.source_gate(read(RUN/'CONTRACT.json'))
    sys.path.insert(0,str(ROOT/'experiments/m4_tactical_v4'))
    import m4_tactical_rl as m
    import numpy as np
    m.torch.set_num_threads(1)
    results=[]
    for case in b.plan():
        folder=RUN/'cases'/case['id'];r=read(folder/'RESULT.json')
        if sha(folder/'telemetry.jsonl')!=r['artifacts']['telemetry.jsonl']:raise RuntimeError('Saved packets changed')
        # Same _build_blue import path as the actual frozen executor, without an environment.
        ctrl=m.TacticalDuel._build_blue(types.SimpleNamespace(settings={}))
        module_path=Path(inspect.getfile(type(ctrl))).resolve()
        if module_path!=ROOT/'experiments/m4_tactical_v4/m1_station.py':raise RuntimeError('Unexpected resolved StationController')
        held=[0.,0.,0.];goals=hashlib.sha256();rawbank=hashlib.sha256();counts=dict(frames=0,bank_binding=0,heading_speed_cap_binding=0,near=0,in_band=0,break_threshold=0)
        minmax=dict(bank_raw=[float('inf'),-float('inf')],speed_before_heading_cap=[float('inf'),-float('inf')],heading_abs=[float('inf'),-float('inf')])
        decisions={d['tick']:d['action'] for d in r['tactical_decisions']};samples=[];row=None
        def record_command(obs,bank,pitch,speed,rudder=0.,safety=True):
            f=sys._getframe(1)
            if f.f_code.co_filename!=str(module_path) or f.f_code.co_name!='act':raise RuntimeError('Wrong recorded guidance caller')
            v=f.f_locals
            before_bank=1.8*v['heading_error']+v['feedforward']
            if v['in_band']:
                before_bank+=v['nose_gain']*float(np.clip(v['nose_err'],-25,25))-(.35*(1+1.2*v['brk']))*v['rate']
            before_speed=v['geo']['enemy_equivalent_cas_kts']+v['desired_close']*1.9438444924*v['geo']['cas_ratio']
            expected_bank=float(np.clip(before_bank,-72,72))
            expected_speed=float(np.clip(min(before_speed,290.) if abs(v['heading_error'])>45 and not v['in_band'] else before_speed,260,450))
            if bank!=expected_bank or speed!=expected_speed:raise RuntimeError('Captured pre/post clipping reconstruction differs')
            if [ctrl.tac_aggression,ctrl.tac_break,ctrl.tac_range]!=held:raise RuntimeError('Tactical setter did not reach act')
            counts['frames']+=1;counts['bank_binding']+=int(abs(before_bank)>72);counts['heading_speed_cap_binding']+=int(abs(v['heading_error'])>45 and not v['in_band'] and before_speed>290)
            counts['near']+=int(v['near']);counts['in_band']+=int(v['in_band']);counts['break_threshold']+=int(v['brk']>.2)
            target=[bank,pitch,speed,rudder]
            goals.update(json.dumps(target,separators=(',',':')).encode())
            rawbank.update(json.dumps(before_bank).encode())
            for key,value in (('bank_raw',before_bank),('speed_before_heading_cap',before_speed),('heading_abs',abs(v['heading_error']))):
                minmax[key]=[min(minmax[key][0],value),max(minmax[key][1],value)]
            if row['tick'] in (1,6000,12000,18000):samples.append(dict(tick=row['tick'],tactical=held[:],bank_raw=before_bank,requested_goal=target,speed_before_heading_cap=before_speed,heading_error=v['heading_error']))
            # These are saved values, not newly generated or validated inner-loop commands.
            return np.asarray(row['blue_command']),row['blue_private_guard']
        ctrl.command=record_command
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                if counts['frames']%300==0 and (b.expired(spec) or (ROOT/'STOP').exists() or (out/'STOP').exists()):raise RuntimeError('Original diagnostic deadline/STOP')
                row=json.loads(line);tick=row['tick']-1
                if tick%20==0:held=decisions[tick]
                ctrl.set_tactical(*held)
                ctrl.act(row['blue_packet_pre'],np.zeros(4,dtype=np.float32),started=True)
        if counts['frames']!=r['final']['ticks']:raise RuntimeError('Missing saved frames')
        results.append(dict(case=case,counts=counts,minmax=minmax,samples=samples,requested_goal_sha256=goals.hexdigest(),preclip_bank_sha256=rawbank.hexdigest(),controller_module_path=str(module_path),controller_sha256=sha(module_path),tactical_values_delivered_exactly=True))
        write(out/'progress.json',dict(completed_cases=len(results),elapsed=time.monotonic()-t0));print(json.dumps(dict(case=case['id'],counts=counts,elapsed=time.monotonic()-t0)),flush=True)
    equivalence=[]
    for opening in (0,1):
        group=[r for r in results if r['case']['opening']==opening]
        equivalence.append(dict(opening=opening,identical_requested_goals=len({r['requested_goal_sha256'] for r in group})==1,different_preclip_bank=len({r['preclip_bank_sha256'] for r in group})>1))
    b.source_gate(read(RUN/'CONTRACT.json'))
    report=dict(status='completed_offline_goal_projection',results=results,equivalence=equivalence,
                source_run=str(RUN),prior_full_battle_comparison=str(ROOT/'diagnostics/saved_sac_battle_audit_20261017_094917_10fc24/COMPARISON.json'),
                no_new_FDM_ticks=True,no_new_model_inference=True,new_training_started=False,
                inner_command_replayed=False,stub_return_was_saved_command=True,
                runtime_identity_limit='Resolved frozen import path in this offline process; not a missing runtime module receipt retroactively added to old workers',
                conclusion='Recorded tactic setter reaches act. Guidance clipping counters and goal equivalence below describe saved trajectories only; no improved combat result or intervention claim.',
                deployment_allowed=False,wall_seconds=time.monotonic()-t0)
    write(out/'ANALYSIS.json',report)
    return 0

def launch():
    sys.path.insert(0,str(ROOT));from runner import JobLock
    with JobLock(ROOT/'launch.lock'):
        if b.base.inventory():raise RuntimeError('Other or unknown work active')
        resources=b.base.resources()
        if b.stop(RUN):raise RuntimeError('STOP')
        b.source_gate(read(RUN/'CONTRACT.json'))
        out=ROOT/'diagnostics'/('sac_goal_projection_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6]);out.mkdir()
        started=time.monotonic();spec=dict(guardian=identity(),deadline_epoch=time.time()+LIMIT,deadline_monotonic=started+LIMIT,seconds=LIMIT,diagnostic_source_sha256=sha(Path(__file__)),source_run=str(RUN),original_source_contract_sha256=sha(RUN/'CONTRACT.json'),resources=resources,usage_observation=read(Path(__file__).with_suffix('.usage.json')),new_FDM_ticks=0,seed_claims=[],training_started=False)
        write(out/'CONTRACT.json',spec)
        lp=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=read(lp);ledger['items'].append(dict(id=out.name,hours=LIMIT/3600,status='reserved_offline_goal_projection',output=str(out),warning_only=True));ledger['reserved_hours']=sum(i['hours'] for i in ledger['items']);write(lp,ledger)
        j=read(ROOT/'research_latest.json');j['active_workload']=dict(status='running_offline_goal_projection',run=str(out),supervisor=b.normalized(spec['guardian']),worker=None);j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[j['active_workload']]);write(ROOT/'research_latest.json',j)
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
            if item['id']==out.name:item.update(status='offline_projection_complete_pending_parent' if passed else 'failed_offline_projection',actual_worker_exit=code,actual_wall_seconds=time.monotonic()-started)
        write(lp,ledger)
        j=read(ROOT/'research_latest.json');j['active_workload']=None;j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[]);j['latest_goal_projection']=str(out);write(ROOT/'research_latest.json',j)
        print(json.dumps(dict(out=str(out),actual_worker_exit=code,reason=reason,absent=absent,wall_seconds=time.monotonic()-started)),flush=True)
        return 0 if passed else 2

if __name__=='__main__':
    raise SystemExit(worker(Path(sys.argv[2])) if len(sys.argv)==3 and sys.argv[1]=='--worker' else launch())
