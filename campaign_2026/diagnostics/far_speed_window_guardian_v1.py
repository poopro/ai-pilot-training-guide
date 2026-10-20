"""Bounded window extraction only; no act, FDM or model inference."""
from pathlib import Path
import datetime,hashlib,inspect,json,math,os,subprocess,sys,time,types,uuid
import psutil

ROOT=Path(r'E:\ai_pilot\campaign_2026')
SOURCE=ROOT/'experiments/opponent_pool/far_speed_v1'
RUN=SOURCE/'run_20261018_033053_98bc0f'
sys.path.insert(0,str(SOURCE))
import battle as b
read,write,sha,identity,live=b.read,b.write,b.sha,b.identity,b.live
LIMIT=120

def worker(out):
    spec=read(out/'CONTRACT.json')
    if sha(Path(__file__))!=spec['diagnostic_source_sha256']:raise RuntimeError('Guardian source changed')
    if sha(ROOT/'diagnostics/far_speed_window_worker_v1.py')!=spec['analysis_worker_sha256']:raise RuntimeError('Window worker changed')
    import far_speed_window_worker_v1
    return far_speed_window_worker_v1.worker(out)

def launch():
    sys.path.insert(0,str(ROOT));from runner import JobLock
    with JobLock(ROOT/'launch.lock'):
        if b.base.inventory():raise RuntimeError('Other or unknown work active')
        resources=b.base.resources()
        if b.stop(RUN):raise RuntimeError('STOP')
        b.source_gate(read(RUN/'CONTRACT.json'))
        out=ROOT/'diagnostics'/('far_speed_window_v1_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6]);out.mkdir()
        started=time.monotonic();spec=dict(guardian=identity(),deadline_epoch=time.time()+LIMIT,deadline_monotonic=started+LIMIT,seconds=LIMIT,diagnostic_source_sha256=sha(Path(__file__)),source_run=str(RUN),original_source_contract_sha256=sha(RUN/'CONTRACT.json'),resources=resources,usage_observation=read(Path(__file__).with_suffix('.usage.json')),new_FDM_ticks=0,seed_claims=[],training_started=False)
        spec.update(comparison_path=str(RUN/'COMPARISON.json'),comparison_sha256=sha(RUN/'COMPARISON.json'),analysis_worker_sha256=sha(ROOT/'diagnostics/far_speed_window_worker_v1.py'),window_definitions='early0to10s/late240to260s/minimum-post-distance+-5s',hypothesis='Test whether enemy-equivalentCAS plus desired-close term repeatedly saturates450; distinguish target saturation from actual speed/turn response, no intervention',model_inference_calls=0,controller_calls=0)
        write(out/'CONTRACT.json',spec)
        write(Path(__file__).with_suffix('.latest.json'),dict(out=str(out),guardian=spec['guardian'],deadline_epoch=spec['deadline_epoch']))
        lp=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=read(lp);ledger['items'].append(dict(id=out.name,hours=LIMIT/3600,status='reserved_offline_far_speed_window',output=str(out),warning_only=True));ledger['reserved_hours']=sum(i['hours'] for i in ledger['items']);write(lp,ledger)
        j=read(ROOT/'research_latest.json');j['active_workload']=dict(status='running_offline_far_speed_window',run=str(out),supervisor=b.normalized(spec['guardian']),worker=None);j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[j['active_workload']]);write(ROOT/'research_latest.json',j)
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
            if item['id']==out.name:item.update(status='offline_far_speed_window_complete_pending_parent' if passed else 'failed_offline_far_speed_window',actual_worker_exit=code,actual_wall_seconds=time.monotonic()-started)
        write(lp,ledger)
        j=read(ROOT/'research_latest.json');j['active_workload']=None;j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[]);j['latest_far_speed_window']=str(out);write(ROOT/'research_latest.json',j)
        print(json.dumps(dict(out=str(out),actual_worker_exit=code,reason=reason,absent=absent,wall_seconds=time.monotonic()-started)),flush=True)
        return 0 if passed else 2

if __name__=='__main__':
    raise SystemExit(worker(Path(sys.argv[2])) if len(sys.argv)==3 and sys.argv[1]=='--worker' else launch())
