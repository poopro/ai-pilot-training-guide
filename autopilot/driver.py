"""Self-contained training -> checkpoints -> paired evaluation -> holdout -> report."""
import argparse, shutil, sys, time, os
from pathlib import Path
from common import *
from supervisor import run_stage, acquire_resources

def stage(job,name,command,folder,timeout=1800,training=False,start=0):
    name=stage_label(job,name)
    existing=next((r for r in reversed(job['results']) if r['name']==name and r.get('exit_code')==0),None)
    if existing:return existing
    if time.time()>=job['deadline_epoch']-1800:raise TimeoutError('保留最後 30 分鐘，停止新工作')
    if (Path(job['job_dir'])/'STOP').exists():raise InterruptedError('使用者停止')
    r=run_stage(job,name,command,folder,timeout,training,start)
    if r.get('reason') in ('budget_exhausted','interrupted'):
        if r['reason']=='interrupted':raise InterruptedError(r['reason'])
        raise TimeoutError(r['reason'])
    if r['exit_code']!=0:raise RuntimeError(f"{name} failed ({r['exit_code']}); see {folder}")
    return r

def eval_stage(job,name,bundle=None,episodes=5,seed=20261200):
    folder=experiment_dir(job)/name
    cmd=[PYTHON,ROOT/'experiment.py','eval','--out',folder,'--episodes',str(episodes),'--seed',str(seed)]
    if bundle:cmd+=['--bundle',bundle,'--paired']
    stage(job,name,cmd,folder,3600)
    result=read(folder/'report.json')
    if not result:raise RuntimeError('Evaluation incomplete')
    return result

def train_stage(job,name,steps,bundle=None,warmup=10000,buffer=50000):
    folder=experiment_dir(job)/name
    recovery=folder.with_name(name+'_recovery')
    # Re-entry attaches to a completed segment, or resumes an interrupted one
    # in a new directory. Never restart its counter from a stale progress.json.
    for candidate_name,candidate_folder in ((name,folder),(name+'_recovery',recovery)):
        if any(r['name']==stage_label(job,candidate_name) and r.get('exit_code')==0 for r in job['results']):
            complete=latest_bundle(candidate_folder)
            if complete and valid_bundle(complete)['config']['run_status']=='completed':return complete
    previous_config=read(folder/'config.json')
    if previous_config:
        checkpoint=latest_bundle(folder)
        if not checkpoint or job['attempts'].get('learner_recovery',0)>=1:
            raise RuntimeError('中斷階段沒有可恢復存檔，或已用完一次恢復；請看結果')
        old=valid_bundle(checkpoint)
        intended=old['config'].get('start_timesteps',0)+old['config']['requested_steps']
        delta=min(intended-old['timesteps'],job['step_budget']-job['new_steps'])
        if delta<2:
            job['checkpoint']=checkpoint;publish(job);return checkpoint
        job['attempts']['learner_recovery']=1;publish(job)
        return train_stage(job,name+'_recovery',delta,checkpoint,warmup,buffer)
    if not acquire_resources(job):raise RuntimeError('Insufficient available memory or disk')
    remaining=job['step_budget']-job['new_steps'];steps=min(int(steps),remaining)
    steps=(steps//2)*2
    if steps<2:raise TimeoutError('訓練步數預算耗盡')
    start=valid_bundle(bundle)['timesteps'] if bundle else 0
    cmd=[PYTHON,BASE/'combat_v3/train.py','--steps',str(steps),'--envs','2','--vec-mode','dummy',
         '--device','cuda','--learning-starts',str(warmup),'--buffer-size',str(buffer),
         '--checkpoint-steps','10000','--checkpoint-seconds','300','--run-dir',folder,
         '--stop-file',folder/'STOP','--deadline-epoch',str(job['deadline_epoch']-1800)]
    if bundle:cmd+=['--resume',bundle]
    try:stage(job,name,cmd,folder,10800,True,start)
    except RuntimeError:
        # Resume only one time from an intact, source-compatible checkpoint.
        retry_key='learner_recovery'
        checkpoint=latest_bundle(folder)
        if job['attempts'].get(retry_key,0)>=1 or not checkpoint:raise
        error_text=(folder/'stderr.log').read_text(encoding='utf-8',errors='replace')
        if 'CUDA out of memory' in error_text or 'NaN' in error_text or 'Invalid simulation' in error_text:raise
        done=max(0,valid_bundle(checkpoint)['timesteps']-start)
        if done>=steps:raise
        job['attempts'][retry_key]=1;publish(job)
        return train_stage(job,name+'_recovery',steps-done,checkpoint,warmup,buffer)
    result=latest_bundle(folder)
    if not result:raise RuntimeError('沒有完整模型與 replay')
    manifest=valid_bundle(result)
    if manifest['config']['run_status'] not in ('completed',):raise RuntimeError('訓練未正常完成：'+manifest['config']['run_status'])
    job['checkpoint']=result;publish(job);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--guide-report',type=Path)
    p.add_argument('--candidate2',action='store_true')
    a=p.parse_args();job=read(ROOT/'最新狀態.json');folder=Path(job['job_dir'])
    with JobLock(ROOT/'runner.lock'):
        if alive(job.get('process')):raise SystemExit('既有作業仍在運行，不建立第二 learner')
        if job.get('pipeline_finished'):
            print('作業已收尾，請查看最新結果；新任務請明確使用 --new。');return
        if a.candidate2 and job.get('candidate_count')!=2:
            if job.get('candidate_count')!=1:raise RuntimeError('第二候選必須以第一候選的具體失敗證據為依據')
            job.setdefault('retired_candidates',[]).append({'candidate':1,'reason':'actual initial CAS differed from requested 340 knots',
                'bundle':job.get('checkpoint'),'artifact':str(folder/'initialization_fix_probe.json')})
            job['candidate_count']=2;job['active_experiment_dir']=str(folder/'candidate2')
            job['guide_revisions']=2;job['error']=None;job['selection']={};job.pop('final_evaluation',None)
            job.pop('guide_evaluation',None);job['learning']='重新驗證初始化修正版本'
        folder=experiment_dir(job);folder.mkdir(parents=True,exist_ok=True)
        job['supervisor']=identity(os.getpid());job['status']='running'
        guide_path=a.guide_report or folder/'guide_preflight/report.json'
        guide=read(guide_path)
        job.setdefault('artifacts',{})['引導器開發評估']=str(guide_path)
        publish(job);report(job)
        try:
            if not guide:guide=eval_stage(job,'guide_preflight')
            job['guide_evaluation']=guide
            if not guide or not guide.get('guide_gate_passed'):raise RuntimeError('引導器未通過攻擊能力門檻')
            runtime=folder/'frozen_source';hashes=read(runtime/'hashes.json')
            if hashes is None:
                hashes={}
                for src in list((BASE/'combat_v3').glob('*.py'))+list((BASE/'combat_v3').glob('*.json')):
                    target=runtime/src.name;target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(src,target);hashes[src.name]=digest(src)
                atomic(runtime/'hashes.json',hashes)
            job['artifacts']['訓練來源快照']=str(runtime)
            def unchanged():
                for name,expected in hashes.items():
                    if digest(BASE/'combat_v3'/name)!=expected:raise RuntimeError('來源在執行中改變：'+name)
            unchanged()
            stage(job,'compliance_tests',[PYTHON,BASE/'combat_v3/test_v3.py'],folder/'compliance_tests',180)
            stage(job,'udp_loopback',[PYTHON,BASE/'combat_v3/verify_udp.py'],folder/'udp_loopback',180)
            job['verification']='監督測試、規則測試及 UDP loopback 通過；等待模型驗證';publish(job)
            smoke=train_stage(job,'smoke_train',512,warmup=64,buffer=2000)
            stage(job,'smoke_load',[PYTHON,ROOT/'experiment.py','modelcheck','--out',folder/'smoke_load','--bundle',smoke],folder/'smoke_load',180)
            # Cooperative stop/resume test is a real learner, not a dummy checksum fixture.
            stop_folder=folder/'smoke_stop'
            stop_folder.mkdir(exist_ok=True)
            r=next((r for r in reversed(job['results']) if r['name']==stage_label(job,'smoke_stop') and r.get('exit_code')==0),None)
            if r is None:
                stopper=[PYTHON,ROOT/'stop_fixture.py','--folder',stop_folder]
                helper=__import__('subprocess').Popen([str(x) for x in stopper],creationflags=__import__('subprocess').CREATE_NO_WINDOW if os.name=='nt' else 0)
                cmd=[PYTHON,BASE/'combat_v3/train.py','--steps','256','--envs','2','--vec-mode','dummy','--resume',smoke,
                     '--run-dir',stop_folder,'--stop-file',stop_folder/'STOP','--device','cuda','--checkpoint-steps','10000']
                try:
                    r=run_stage(job,stage_label(job,'smoke_stop'),cmd,stop_folder,180,True,512)
                    helper.wait(timeout=20)
                finally:
                    if helper.poll() is None:helper.terminate();helper.wait(timeout=10)
            stopped=latest_bundle(stop_folder)
            if r['exit_code']!=0 or not stopped:raise RuntimeError('合作停止未完整保存')
            stopped_m=valid_bundle(stopped)
            if stopped_m['config']['run_status']!='interrupted':raise RuntimeError('停止流程未驗證')
            resumed=train_stage(job,'smoke_resume',128,stopped,warmup=64,buffer=2000)
            if valid_bundle(resumed)['timesteps']!=stopped_m['timesteps']+128:raise RuntimeError('續訓步數不正確')
            unchanged()
            job['verification']='監督八項、環境測試、UDP loopback、CUDA optimizer、模型載入、合作停止及續訓均通過'
            job['candidate_count']=job.get('candidate_count') or 1;publish(job)
            bundle=None;regressions=0;last=None
            for target in (20000,50000,100000,199000):
                unchanged();done=valid_bundle(bundle)['timesteps'] if bundle else 0
                available=job['step_budget']-job['new_steps']
                delta=min(target-done,max(0,available-2))
                if delta<2:break
                bundle=train_stage(job,f'candidate1_to_{target}',delta,bundle)
                result=eval_stage(job,f'dev_{target}',bundle)
                job['final_evaluation']=result;job['selection']={'decision':result['decision'],'bundle':bundle}
                job['artifacts']['最近配對評估']=str(folder/f'dev_{target}/report.json')
                policy=[g for g in result['groups'] if g['policy']=='policy'];base=[g for g in result['groups'] if g['policy']=='guide']
                bad=sum(g['crashes']+g['hits'] for g in policy)>sum(g['crashes']+g['hits'] for g in base) or sum(g['kills'] for g in policy)<sum(g['kills'] for g in base)
                regressions=regressions+1 if bad else 0
                publish(job);report(job)
                if regressions>=2:job['error']='連續兩次開發評估退步，停止延長候選';break
                last=result
            selected=job.get('selection',{}).get('decision','retain_guide')
            # Freeze choice before untouched holdout; never tune against this report.
            atomic(folder/'selection.json',{'decision':selected,'bundle':bundle if selected=='policy_candidate' else None,'utc':stamp()})
            holdout=eval_stage(job,'holdout',bundle if selected=='policy_candidate' else None,20,20262000)
            job['final_evaluation']=holdout;job['artifacts']['保留測試']=str(folder/'holdout/report.json')
            job['learning']='已完成固定評估；SAC 有改善候選' if selected=='policy_candidate' else '未證明 SAC 優於引導器；保留引導器'
            if bundle:
                stage(job,'deployment_latency',[PYTHON,ROOT/'experiment.py','modelcheck','--out',folder/'deployment_latency','--bundle',bundle],folder/'deployment_latency',180)
                job['artifacts']['模型與控制延遲']=str(folder/'deployment_latency/model_check.json')
            job['status']='completed';job['next_action']='查看保留測試與 ACMI；官方 Host／Tacview 視覺確認另列待人工驗證。'
        except InterruptedError as e:job['status']='interrupted';job['error']=str(e)
        except TimeoutError as e:job['status']='budget_exhausted';job['error']=str(e)
        except BaseException as e:job['status']='failed';job['error']=repr(e)
        finally:
            if alive(job.get('process')):terminate_owned(job['process'])
            job['process']=None;job['stage']='收尾與結果報告';job['pipeline_finished']=job['status'] in ('completed','failed','budget_exhausted')
            publish(job);report(job)
            try:
                from summarize import build
                build(job)
            except Exception as e:
                job['report_error']=repr(e);publish(job)
                print('詳細報告整理失敗，基本結果已保留：'+repr(e),flush=True)

if __name__=='__main__':main()
