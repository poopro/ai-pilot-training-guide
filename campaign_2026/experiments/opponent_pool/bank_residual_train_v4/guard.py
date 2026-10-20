"""Independent900s fresh pilot, no extensions or implicit reruns."""
from pathlib import Path
import datetime,json,subprocess,sys,time,uuid,psutil,traceback
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
                                if node is None:raise RuntimeError('Owned ancestor chain lost')
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
        if c.b.base.inventory():raise RuntimeError('Other/unknown campaign work active')
        resources=c.b.base.resources()
        if c.stop(c.HERE):raise RuntimeError('STOP')
        prep=c.read(c.HERE/'PREPARATION.json')
        if prep.get('consumed',False):raise RuntimeError('Consumed branch: no automatic relaunch')
        _,seen=seen_seeds()
        if set(c.SEEDS)&seen:raise RuntimeError('New learner/episode seed used/reserved')
        interface=c.ROOT/'experiments/opponent_pool/bank_residual_fdm_v1/run_20261018_153511_6fb16a'
        if not c.read(interface/'VERIFICATION.json')['verified_bank_residual_60Hz_interface'] or c.read(interface/'PARENT_EXIT_OBSERVED.json')['actual_exit']!=0:raise RuntimeError('No actual interface pass')
        source=c.sources()
        if c.read(c.HERE/'BRANCH_FREEZE.json')['sources']!=source:raise RuntimeError('Prepared branch source drift')
        out=c.HERE/('run_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6]);out.mkdir()
        mono=time.monotonic();spec=dict(profile='fresh_bank_residual_17x1_CPU_pilot_v1',hypothesis='Existing bank residual has effective authority; test fresh learning mechanics before a separate matched strength comparison',sources=source,guardian=c.identity(),deadline_epoch=time.time()+900,deadline_monotonic=mono+900,
            phase_seconds=dict(PRECHECK=30,WORKER=780,VERIFIER=90),resources=resources,usage_observation=c.read(c.HERE/'USAGE_OBSERVATION.json'),episodes=c.plan(),learner_seed=c.LEARNER_SEED,
            observation='17 legal OWN26-derived features/private own counters and clock',action='1bank -> original4residual[bank,0,0,0],20ticks per decision; original safety unchanged',
            reward='published90 LINE1deg AGL right_bin blue-red advantage increment/(10000/60), true terminal blue+180/red-180/draw0; unresolved winner failclosed; cutoff truncation only',
            hyperparameters=dict(learning_rate=.0003,buffer_size=10000,learning_starts=300,batch_size=128,train_freq=8,gradient_steps=1,tau=.005,gamma=.9995,ent_coef='auto',device='cpu',net_arch=[128,128]),
            max_decisions=3000,max_blue_FDM_ticks=60000,fresh_actor_critic_optimizer_replay=True,formal_deployment='repair_guide',deployment_allowed=False)
        c.write(out/'CONTRACT.json',spec);c.write(c.HERE/'LATEST.json',dict(out=str(out),guardian=spec['guardian'],deadline_epoch=spec['deadline_epoch']))
        day=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat();lp=c.ROOT/'compute_budgets'/f'{day}.json';ledger=c.read(lp) if lp.exists() else dict(date_taipei=day,daily_limit_hours=6.,reserved_hours=0.,items=[],policy='warning_only_no_refund')
        ledger['items'].append(dict(id=out.name,hours=.25,status='reserved_fresh_bank_training',output=str(out),warning_only=True));ledger['reserved_hours']=sum(i['hours'] for i in ledger['items']);c.write(lp,ledger)
        j=c.read(c.ROOT/'research_latest.json');j['active_workload']=dict(status='running_fresh_bank_pilot',run=str(out),supervisor=c.b.normalized(spec['guardian']));j['current_live_workloads']=dict(learners=[j['active_workload']],loops=[],evaluations=[]);c.write(c.ROOT/'research_latest.json',j)
        receipts={};code=2;error=None;claimed=False
        prep.update(consumed=True,status='precheck_under_original900s',run=str(out),training_launch_allowed=False);c.write(c.HERE/'PREPARATION.json',prep)
        try:
            receipts['PRECHECK']=phase(out,spec,'PRECHECK','test_contract.py',30)
            if not c.read(out/'PRECHECK.json')['verified_training_contract']:raise RuntimeError('Precheck not verified')
            c.gate(spec);c.b.base.resources();reg,seen=seen_seeds()
            if set(c.SEEDS)&seen:raise RuntimeError('Seed claimed during precheck')
            reg.setdefault('trials',{})[out.name]=dict(seeds=list(c.SEEDS),status='attempted',seed_role='fresh_training_new_development_not_holdout',output=str(out),reusable=False);c.write(c.ROOT/'seed_registry.json',reg);claimed=True
            prep.update(status='precheck_actual0_seedpool_claimed_running',precheck=str(out/'PRECHECK.json'),precheck_actual_exit=0,reason='Only existing supervised handle may proceed under original900s');c.write(c.HERE/'PREPARATION.json',prep)
            receipts['WORKER']=phase(out,spec,'WORKER','train.py',780)
            receipts['VERIFIER']=phase(out,spec,'VERIFIER','verify.py',90)
            c.gate(spec)
            if not c.read(out/'VERIFICATION.json')['verified_fresh_bank_residual_pilot']:raise RuntimeError('No verification')
            code=0
        except Exception as exc:traceback.print_exc();error=repr(exc)
        finally:
            actual={name:c.read(out/(name+'_EXIT.json'))['actual_exit'] for name in ('PRECHECK','WORKER','VERIFIER') if (out/(name+'_EXIT.json')).exists()}
            c.write(out/'GUARD_EXIT.json',dict(phase_exits=actual,error=error,seeds_claimed=claimed,source_fixed=(c.sources()==source),wall_seconds=time.monotonic()-mono,guardian=spec['guardian'],guardian_return_intended=code))
            ledger=c.read(lp)
            for item in ledger['items']:
                if item['id']==out.name:item.update(status='verified_pilot_pending_observed_parent' if code==0 else 'failed_pilot',actual_phase_exits=actual,actual_wall_seconds=time.monotonic()-mono,seeds_claimed=claimed)
            c.write(lp,ledger);j=c.read(c.ROOT/'research_latest.json');j['active_workload']=None;j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[]);j['latest_fresh_bank_training_run']=str(out);c.write(c.ROOT/'research_latest.json',j)
        print(json.dumps(dict(out=str(out),phase_exits=actual,seeds_claimed=claimed,error=error,wall_seconds=time.monotonic()-mono)),flush=True);return code
if __name__=='__main__':raise SystemExit(launch())
