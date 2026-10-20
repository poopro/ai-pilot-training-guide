"""Single locked900s paired evaluation, original90s cases/180s audit."""
from pathlib import Path
import datetime,json,subprocess,sys,time,uuid,psutil,traceback
import common as c
def phase(out,spec,name,script,seconds,argument=None):
    began=time.monotonic();limits=dict(deadline_epoch=min(spec['deadline_epoch'],time.time()+seconds),deadline_monotonic=min(spec['deadline_monotonic'],began+seconds));c.write(out/(name+'_LIMITS.json'),limits)
    child=None;ident=None;tracked={};actions=[];code=None;reason=None
    try:
        with (out/(name+'.log')).open('w',encoding='utf8') as log:
            child=subprocess.Popen([sys.executable,'-B','-X','utf8',str(c.HERE/script),str(argument or out)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);ident=c.identity(child.pid);c.write(out/(name+'_identity.json'),ident)
            j=c.read(c.ROOT/'research_latest.json');j['active_workload'].update(phase=name,worker=c.b.normalized(ident));c.write(c.ROOT/'research_latest.json',j)
            while child.poll() is None:
                try:
                    for node in psutil.Process(ident['pid']).children(recursive=True):
                        try:
                            item=c.identity(node.pid);chain=[];cursor=node
                            while cursor.pid!=ident['pid']:
                                chain.append(c.identity(cursor.pid));cursor=cursor.parent()
                                if cursor is None:raise RuntimeError('Owned ancestor chain lost')
                            if not c.live(ident):raise RuntimeError('Phase root changed')
                            tracked[(item['pid'],item['create'])]=dict(identity=item,chain=chain,worker=ident)
                        except psutil.NoSuchProcess:continue
                except psutil.NoSuchProcess:
                    if child.poll() is None:raise
                if c.stop(out) or c.b.expired(spec,limits):reason='STOP_or_original_phase_deadline';code,actions=c.b.terminate_known(child,ident,tracked);break
                time.sleep(.1)
            if code is None:code=child.wait(timeout=3)
    finally:
        if child is not None and child.poll() is None:reason=reason or 'guardian_phase_exception';code,actions=c.b.terminate_known(child,ident,tracked)
        for item in tracked.values():
            original=item['identity']
            if c.live(original):
                try:psutil.Process(original['pid']).wait(timeout=1)
                except psutil.TimeoutExpired:
                    if c.live(original):psutil.Process(original['pid']).terminate();actions.append(original)
        absent=ident is not None and not c.live(ident) and all(not c.live(item['identity']) for item in tracked.values())
        result=Path(argument or out)/'RESULT.json'
        receipt=dict(actual_exit=code,reason=reason,identity=ident,descendants=list(tracked.values()),absent=absent,cleanup_actions=actions,wall_seconds=time.monotonic()-began,limits=limits)
        if name.startswith('CASE') and result.exists():receipt['result_sha256']=c.sha(result)
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
        if c.b.base.inventory():raise RuntimeError('Other/unknown campaign workload')
        resources=c.b.base.resources();prep=c.read(c.HERE/'PREPARATION.json')
        if c.stop(c.HERE) or prep['consumed']:raise RuntimeError('STOP/consumed branch')
        _,seen=seen_seeds()
        if set(c.SEEDS)&seen:raise RuntimeError('Opening seeds used/reserved')
        source=c.sources()
        if source!=c.read(c.HERE/'BRANCH_FREEZE.json')['sources']:raise RuntimeError('Prepared source drift')
        out=c.HERE/('run_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6]);(out/'cases').mkdir(parents=True);began=time.monotonic()
        spec=dict(profile='bank17_frozen_model_neutral_three_opponents_development_v1',hypothesis='Does frozen17x1 learned bank timing beat original neutral guidance under identical full-game starts?',cases=c.plan(),sources=source,guardian=c.identity(),deadline_epoch=time.time()+900,deadline_monotonic=began+900,total_seconds=900,precheck_seconds=30,case_seconds=90,verifier_seconds=180,resources=resources,usage_observation=c.read(c.HERE/'USAGE_OBSERVATION.json'),candidate_model=str(c.MODEL),candidate_model_sha256=c.MODEL_SHA,seed_role='new_paired_development_not_holdout',training_started=False,formal_deployment='repair_guide',deployment_allowed=False)
        c.write(out/'CONTRACT.json',spec);c.write(c.HERE/'LATEST.json',dict(out=str(out),guardian=spec['guardian'],deadline_epoch=spec['deadline_epoch']))
        day=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat();lp=c.ROOT/'compute_budgets'/f'{day}.json';ledger=c.read(lp);ledger['items'].append(dict(id=out.name,hours=.25,status='reserved_bank17_matched_evaluation',output=str(out),warning_only=True));ledger['reserved_hours']=sum(x['hours'] for x in ledger['items']);c.write(lp,ledger)
        j=c.read(c.ROOT/'research_latest.json');j['active_workload']=dict(status='running_bank17_paired_evaluation',run=str(out),supervisor=c.b.normalized(spec['guardian']));j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[j['active_workload']]);c.write(c.ROOT/'research_latest.json',j)
        prep.update(consumed=True,status='guarded_precheck_with_original900s',run=str(out),FDM_launch_allowed=False);c.write(c.HERE/'PREPARATION.json',prep)
        code=2;error=None;claimed=False;receipts={}
        try:
            receipts['PRECHECK']=phase(out,spec,'PRECHECK','test_contract.py',30)
            if not c.read(out/'PRECHECK.json')['verified_prelaunch_evaluation']:raise RuntimeError('No actual precheck pass')
            c.gate(spec);c.b.base.resources();reg,seen=seen_seeds()
            if set(c.SEEDS)&seen:raise RuntimeError('Seed claimed during precheck')
            reg.setdefault('trials',{})[out.name]=dict(seeds=list(c.SEEDS),status='attempted',seed_role='new_paired_development_not_holdout',output=str(out),reusable=False);c.write(c.ROOT/'seed_registry.json',reg);claimed=True
            prep.update(status='precheck_actual0_seed_claimed_live',precheck=str(out/'PRECHECK.json'),reason='Only same existing guardian handle may proceed; no relaunch');c.write(c.HERE/'PREPARATION.json',prep)
            for i,case in enumerate(spec['cases']):
                c.gate(spec);c.b.base.resources();folder=out/'cases'/case['id'];folder.mkdir();name=f'CASE{i}';c.write(folder/'INPUT.json',dict(out=str(out),case=case,phase=name));receipts[name]=phase(out,spec,name,'worker.py',90,folder)
            receipts['VERIFIER']=phase(out,spec,'VERIFIER','verify.py',180)
            if not c.read(out/'COMPARISON.json')['verified_comparison']:raise RuntimeError('No strict verified comparison')
            c.gate(spec);code=0
        except Exception as exc:traceback.print_exc();error=repr(exc)
        finally:
            names=['PRECHECK',*[f'CASE{i}' for i in range(6)],'VERIFIER'];actual={n:c.read(out/(n+'_EXIT.json'))['actual_exit'] for n in names if (out/(n+'_EXIT.json')).exists()}
            c.write(out/'GUARD_EXIT.json',dict(phase_exits=actual,error=error,seeds_claimed=claimed,source_fixed=c.sources()==source,wall_seconds=time.monotonic()-began,guardian=spec['guardian'],guardian_return_intended=code))
            ledger=c.read(lp)
            for item in ledger['items']:
                if item['id']==out.name:item.update(status='verified_games_pending_observed_parent' if code==0 else 'failed_partial_evaluation',actual_phase_exits=actual,actual_wall_seconds=time.monotonic()-began,seeds_claimed=claimed)
            c.write(lp,ledger);j=c.read(c.ROOT/'research_latest.json');j['active_workload']=None;j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[]);j['latest_bank17_evaluation_attempt']=str(out);c.write(c.ROOT/'research_latest.json',j)
        print(json.dumps(dict(out=str(out),phase_exits=actual,error=error,seeds_claimed=claimed,wall_seconds=time.monotonic()-began)),flush=True);return code
if __name__=='__main__':raise SystemExit(launch())
