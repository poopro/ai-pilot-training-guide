"""Independent240s original wall across precheck30/physics90/verify60 phases."""
from pathlib import Path
import datetime,json,subprocess,sys,time,uuid,psutil
import common as c
def phase(out,spec,name,script,seconds):
    started=time.monotonic();limits=dict(deadline_epoch=min(spec['deadline_epoch'],time.time()+seconds),deadline_monotonic=min(spec['deadline_monotonic'],started+seconds))
    c.write(out/(name+'_LIMITS.json'),limits);p=None;i=None;tracked={};actions=[];code=None;reason=None
    try:
        with (out/(name+'.log')).open('w',encoding='utf8') as log:
            p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(c.HERE/script),str(out)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            i=c.identity(p.pid);c.write(out/(name+'_identity.json'),i)
            while p.poll() is None:
                try:
                    for child in psutil.Process(i['pid']).children(recursive=True):
                        try:
                            ident=c.identity(child.pid);chain=[];node=child
                            while node.pid!=i['pid']:
                                chain.append(c.identity(node.pid));node=node.parent()
                                if node is None:raise RuntimeError('Owned chain lost')
                            if not c.live(i):raise RuntimeError('Phase root changed')
                            tracked[(ident['pid'],ident['create'])]=dict(identity=ident,chain=chain,worker=i)
                        except psutil.NoSuchProcess:continue
                except psutil.NoSuchProcess:
                    if p.poll() is None:raise
                if c.stop(out) or c.b.expired(spec,limits):reason='STOP_or_original_phase_deadline';code,actions=c.b.terminate_known(p,i,tracked);break
                time.sleep(.1)
            if code is None:code=p.wait(timeout=3)
    finally:
        if p is not None and p.poll() is None:reason=reason or 'guardian_phase_exception';code,actions=c.b.terminate_known(p,i,tracked)
        for item in tracked.values():
            ident=item['identity']
            if c.live(ident):
                try:psutil.Process(ident['pid']).wait(timeout=1)
                except psutil.TimeoutExpired:
                    if c.live(ident):psutil.Process(ident['pid']).terminate();actions.append(ident)
        absent=i is not None and not c.live(i) and all(not c.live(d['identity']) for d in tracked.values())
        receipt=dict(actual_exit=code,reason=reason,identity=i,descendants=list(tracked.values()),absent=absent,cleanup_actions=actions,wall_seconds=time.monotonic()-started,limits=limits)
        if name=='WORKER' and (out/'RESULT.json').exists():receipt['result_sha256']=c.sha(out/'RESULT.json')
        c.write(out/(name+'_EXIT.json'),receipt)
    if code!=0 or reason is not None or not absent:raise RuntimeError('Phase failed '+name)
    return receipt
def seen_seeds():
    reg=c.read(c.ROOT/'seed_registry.json');seen={int(s) for s in reg.get('observed_seeds',{})}
    for trial in reg.get('trials',{}).values():seen.update(trial['seeds'])
    seen.update(reg.get('reserved_holdout_seeds',[]));return reg,seen
def launch():
    sys.path.insert(0,str(c.ROOT));from runner import JobLock
    with JobLock(c.ROOT/'launch.lock'):
        if c.b.base.inventory():raise RuntimeError('Other/unknown work active')
        resources=c.b.base.resources()
        if c.stop(c.HERE):raise RuntimeError('STOP')
        _,seen=seen_seeds()
        if c.SEED in seen:raise RuntimeError('Seed used/reserved; never retry')
        authority=c.ROOT/'diagnostics/bank_authority_v1_20261018_123907_985ac0'
        if not c.read(authority/'VERIFICATION.json')['verified_existing_bank_residual_authority'] or c.read(authority/'PARENT_EXIT_OBSERVED.json')['actual_exit']!=0:raise RuntimeError('No actual authority pass')
        source=c.sources()
        if c.read(c.HERE/'BRANCH_FREEZE.json')['sources']!=source:raise RuntimeError('Prepared branch source drift')
        out=c.HERE/('run_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6]);out.mkdir()
        mono=time.monotonic();spec=dict(profile='bank_only_60Hz_interface_v1',hypothesis='Actual original bank residual propagates once through unchanged parent physics/judge',seed=c.SEED,seed_role='new_short_interface_development_not_holdout',sources=source,guardian=c.identity(),deadline_epoch=time.time()+240,deadline_monotonic=mono+240,phase_seconds=dict(PRECHECK=30,WORKER=90,VERIFIER=60),resources=resources,usage_observation=c.read(c.HERE/'USAGE_OBSERVATION.json'),training_started=False,formal_deployment='repair_guide',deployment_allowed=False)
        c.write(out/'CONTRACT.json',spec);c.write(c.HERE/'LATEST.json',dict(out=str(out),guardian=spec['guardian'],deadline_epoch=spec['deadline_epoch']))
        lp=c.ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=c.read(lp);ledger['items'].append(dict(id=out.name,hours=240/3600,status='reserved_bank_FDM_interface',output=str(out),warning_only=True));ledger['reserved_hours']=sum(i['hours'] for i in ledger['items']);c.write(lp,ledger)
        j=c.read(c.ROOT/'research_latest.json');j['active_workload']=dict(status='running_bank_FDM_interface',run=str(out),supervisor=c.b.normalized(spec['guardian']));j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[j['active_workload']]);c.write(c.ROOT/'research_latest.json',j)
        receipts={};code=2;error=None;claimed=False
        try:
            receipts['PRECHECK']=phase(out,spec,'PRECHECK','test_bridge.py',30)
            if not c.read(out/'PRECHECK.json')['verified_prelaunch_bridge']:raise RuntimeError('Precheck not verified')
            c.gate(spec);c.b.base.resources();reg,seen=seen_seeds()
            if c.SEED in seen:raise RuntimeError('Seed claimed during precheck')
            reg.setdefault('trials',{})[out.name]=dict(seeds=[c.SEED],status='attempted',seed_role='development_short_bank_interface_not_holdout',output=str(out),reusable=False);c.write(c.ROOT/'seed_registry.json',reg);claimed=True
            prep=c.read(c.HERE/'PREPARATION.json');prep.update(status='precheck_actual0_seed_attempted_running',precheck=str(out/'PRECHECK.json'),precheck_actual_exit=0,run=str(out),FDM_launch_allowed=False,reason='Trial consumed; supervisor runs only this existing handle under original deadline, no relaunch');c.write(c.HERE/'PREPARATION.json',prep)
            receipts['WORKER']=phase(out,spec,'WORKER','probe.py',90)
            receipts['VERIFIER']=phase(out,spec,'VERIFIER','verify.py',60)
            c.gate(spec)
            if not c.read(out/'VERIFICATION.json')['verified_bank_residual_60Hz_interface']:raise RuntimeError('No verification')
            code=0
        except Exception as exc:
            import traceback;traceback.print_exc();error=repr(exc)
        finally:
            c.write(out/'GUARD_EXIT.json',dict(phase_exits={k:v['actual_exit'] for k,v in receipts.items()},error=error,seed_claimed=claimed,source_fixed=(c.sources()==source),wall_seconds=time.monotonic()-mono,guardian=spec['guardian'],guardian_return_intended=code))
            ledger=c.read(lp)
            for item in ledger['items']:
                if item['id']==out.name:item.update(status='verified_short_interface_pending_observed_parent' if code==0 else 'failed_short_interface',actual_phase_exits={k:v['actual_exit'] for k,v in receipts.items()},actual_wall_seconds=time.monotonic()-mono,seed_claimed=claimed)
            c.write(lp,ledger);j=c.read(c.ROOT/'research_latest.json');j['active_workload']=None;j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[]);j['latest_bank_FDM_interface']=str(out);c.write(c.ROOT/'research_latest.json',j)
        print(json.dumps(dict(out=str(out),phase_exits={k:v['actual_exit'] for k,v in receipts.items()},seed_claimed=claimed,error=error,wall_seconds=time.monotonic()-mono)),flush=True);return code
if __name__=='__main__':raise SystemExit(launch())
