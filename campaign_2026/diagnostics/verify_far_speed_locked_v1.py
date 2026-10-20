"""OS-locked verification phase, independently bounded by original600s and120s."""
from pathlib import Path
import sys,time,subprocess,psutil,datetime
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/far_speed_v1'
sys.path.insert(0,str(SOURCE));import battle as b
sys.path.insert(0,str(ROOT));from runner import JobLock
def main(out):
    with JobLock(ROOT/'launch.lock'):
        if b.base.inventory():raise RuntimeError('Other or unknown campaign work active')
        spec=b.read(out/'CONTRACT.json')
        if b.read(out/'PARENT_EXIT_OBSERVED.json')['actual_exit']!=0:raise RuntimeError('No observed parent0')
        if b.stop(out) or b.expired(spec):raise RuntimeError('STOP/original deadline')
        b.source_gate(spec);resources=b.base.resources();started=time.monotonic()
        limit=dict(deadline_monotonic=min(spec['deadline_monotonic'],started+120),deadline_epoch=min(spec['deadline_epoch'],time.time()+120))
        cmd=[sys.executable,'-B','-X','utf8',str(SOURCE/'verify.py'),'--guarded',str(out),'0'];descendants={};code=None;reason=None;actions=[];p=None;i=None
        wrapper=b.identity();b.write(out/'VERIFICATION_PHASE_CONTRACT.json',dict(wrapper=wrapper,source_sha256=b.sha(Path(__file__)),limits=limit,resources=resources,original_contract_sha256=b.sha(out/'CONTRACT.json'),OS_lock=True,worker_compute_pre_reserved_in_original_600s=True))
        try:
            with (out/'verifier_wrapper.log').open('w',encoding='utf8') as log:
                p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);i=b.identity(p.pid)
                j=b.read(ROOT/'research_latest.json');j.update(status='verifying_saved_full_games',active_workload=dict(status='running_original_deadline_verifier',run=str(out),supervisor=b.normalized(wrapper),worker=b.normalized(i)));j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[j['active_workload']]);b.write(ROOT/'research_latest.json',j)
                while p.poll() is None:
                    try:
                        for child in psutil.Process(i['pid']).children(recursive=True):
                            try:
                                d=b.identity(child.pid);chain=[];node=child
                                while node.pid!=i['pid']:
                                    chain.append(b.identity(node.pid));node=node.parent()
                                    if node is None:raise RuntimeError('Lost own verifier descendant chain')
                                if not b.live(i):raise RuntimeError('Verifier guard identity changed')
                                descendants[(d['pid'],d['create'])]=dict(identity=d,chain=chain,worker=i)
                            except psutil.NoSuchProcess:continue
                    except psutil.NoSuchProcess:
                        if p.poll() is None:raise
                    if b.expired(spec,limit) or b.stop(out):reason='STOP_or_original_deadline_or_phase120';code,actions=b.terminate_known(p,i,descendants);break
                    time.sleep(.1)
                if code is None:code=p.wait(timeout=3)
        finally:
            if p is not None and p.poll() is None:reason=reason or 'wrapper_exception';code,actions=b.terminate_known(p,i,descendants)
            for item in descendants.values():
                d=item['identity']
                if b.live(d):
                    try:psutil.Process(d['pid']).wait(timeout=1)
                    except psutil.TimeoutExpired:
                        if b.live(d):psutil.Process(d['pid']).terminate();actions.append(d)
            absent=i is not None and not b.live(i) and all(not b.live(item['identity']) for item in descendants.values())
            b.write(out/'LOCKED_VERIFIER_EXIT.json',dict(actual_guarded_wrapper_exit=code,reason=reason,identity=i,descendants=list(descendants.values()),absent=absent,cleanup_actions=actions,wall_seconds=time.monotonic()-started,OS_lock_held=True,original600_and120_limits=True))
            j=b.read(ROOT/'research_latest.json');j['active_workload']=None;j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[]);b.write(ROOT/'research_latest.json',j)
        print(dict(actual_guarded_wrapper_exit=code,reason=reason,absent=absent,wall_seconds=time.monotonic()-started),flush=True)
        return 0 if code==0 and reason is None and absent else 2
if __name__=='__main__':raise SystemExit(main(Path(sys.argv[1])))
