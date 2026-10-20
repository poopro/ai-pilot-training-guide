"""Persistent sequential subprocess supervisor with bounded recovery."""
import argparse, os, subprocess, sys, time
from pathlib import Path
from common import *

def run_stage(job,name,command,folder,timeout=3600,training=False,start_step=0):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    stop=folder/'STOP';stop.unlink(missing_ok=True)
    # A new subprocess must never inherit an earlier attempt's progress counter.
    (folder/'progress.json').unlink(missing_ok=True)
    record={'name':name,'folder':str(folder),'command':[str(x) for x in command],
            'started_utc':stamp(),'training':training,'start_step':start_step,'counted_steps':0}
    job['results'].append(record);job['stage']=name;job['status']='running'
    atomic(folder/'command.json',record)
    out=open(folder/'stdout.log','w',encoding='utf-8');err=open(folder/'stderr.log','w',encoding='utf-8')
    child=subprocess.Popen([str(x) for x in command],cwd=str(BASE),stdout=out,stderr=err,
        env={**os.environ,'PYTHONUTF8':'1','PYTHONUNBUFFERED':'1','OMP_NUM_THREADS':'1'},
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    job['process']=identity(child.pid);record['process']=job['process'];publish(job)
    started=time.monotonic();last_progress=started;last_signature=None;stop_at=None;reason=None;last_bundle_stamp=None
    while child.poll() is None:
        progress=read(folder/'progress.json',{})
        if training:
            current=int(progress.get('timesteps',start_step));added=max(0,current-start_step)
            if added>record['counted_steps']:
                job['new_steps']+=added-record['counted_steps'];record['counted_steps']=added
            manifests=list(folder.glob('**/manifest.json'))
            newest=max((p.stat().st_mtime for p in manifests),default=0)
            if newest!=last_bundle_stamp:
                checkpoint=latest_bundle(folder)
                if checkpoint:job['checkpoint']=checkpoint
                last_bundle_stamp=newest
        signature=(progress.get('timesteps'),progress.get('completed_episodes'),
                   progress.get('episodes_done'),progress.get('work_tick'),progress.get('phase'))
        if signature!=last_signature:last_signature=signature;last_progress=time.monotonic()
        now=time.monotonic()
        interrupted=(Path(job['job_dir'])/'STOP').exists()
        budget=time.time()>=job['deadline_epoch']-1800 or (training and job['new_steps']>=job['step_budget'])
        stalled=now-last_progress>job['config']['stall_seconds']
        expired=now-started>timeout
        if stop_at is None and (interrupted or budget or stalled or expired):
            reason='interrupted' if interrupted else ('budget_exhausted' if budget else ('stalled' if stalled else 'timeout'))
            stop.write_text(reason,encoding='utf-8');stop_at=now;record['stop_reason']=reason
        if stop_at and now-stop_at>job['config']['save_grace_seconds']:
            terminate_owned(job['process']);record['forced_stop']=True;break
        job['progress']=progress;publish(job)
        time.sleep(min(5,float(job['config'].get('poll_seconds',5))))
    child.wait(timeout=10);out.close();err.close()
    progress=read(folder/'progress.json',{})
    if training:
        current=int(progress.get('timesteps',start_step));added=max(0,current-start_step)
        job['new_steps']+=max(0,added-record['counted_steps']);record['counted_steps']=max(record['counted_steps'],added)
        checkpoint=latest_bundle(folder)
        if checkpoint:job['checkpoint']=checkpoint
    record.update(exit_code=child.returncode,finished_utc=stamp(),reason=reason)
    atomic(folder/'exit.json',record);job['process']=None;publish(job);report(job)
    return record

def resource_ready(job):
    import psutil
    m=psutil.virtual_memory();s=psutil.swap_memory()
    # Windows pagefile headroom plus free physical RAM, while avoiding multiple torch workers.
    free_commit=(m.available+s.free)/2**30
    free_physical=m.available/2**30
    job['resources']={'available_ram_gb':free_physical,'commit_headroom_lower_bound_gb':free_commit,
                      'disk_free_gb':psutil.disk_usage(str(ROOT)).free/2**30}
    return free_physical>=job['config']['min_available_ram_gb'] and free_commit>=job['config']['min_commit_free_gb'] and job['resources']['disk_free_gb']>=5

def acquire_resources(job):
    start=time.monotonic()
    while not resource_ready(job):
        job['stage']='等待記憶體／磁碟資源';publish(job);report(job)
        if time.monotonic()-start>job['config']['resource_wait_seconds'] or time.time()>job['deadline_epoch']-1800:return False
        if (Path(job['job_dir'])/'STOP').exists():return False
        time.sleep(15)
    return True

def execute(job,plan):
    job['supervisor']=identity(os.getpid());job['status']='running';publish(job)
    for task in plan:
        if any(r['name']==task['name'] and r.get('exit_code')==0 for r in job['results']):continue
        if (Path(job['job_dir'])/'STOP').exists():job['status']='interrupted';break
        if time.time()>=job['deadline_epoch']-1800:job['status']='budget_exhausted';break
        if task.get('requires_resources') and not acquire_resources(job):
            job['status']='failed';job['error']='資源不足，未啟動額外訓練';break
        record=run_stage(job,task['name'],task['command'],task['folder'],task.get('timeout',3600),
                         task.get('training',False),task.get('start_step',0))
        if record['reason'] in ('interrupted','budget_exhausted'):
            job['status']=record['reason'];break
        if record['exit_code']!=0:
            job['status']='failed';job['error']='階段失敗：'+task['name'];break
        if task.get('result'):
            result=read(task['result'],{})
            job[task.get('store_as','stage_result')]=result
            if task.get('gate') and not result.get(task['gate']):
                job['status']='failed';job['error']='未通過：'+task['gate'];break
    else:job['status']='completed'
    job['stage']='收尾與結果報告';job['process']=None;publish(job);report(job)

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path);p.add_argument('--plan',type=Path)
    p.add_argument('--status',action='store_true');p.add_argument('--stop',action='store_true')
    a=p.parse_args();job=read(a.job or ROOT/'最新狀態.json')
    if not job:raise SystemExit('尚無作業')
    if a.status:print(json.dumps(job,ensure_ascii=False,indent=2));return
    if a.stop:(Path(job['job_dir'])/'STOP').write_text('user_stop');print('已要求安全停止與保存。');return
    if job['status'] in TERMINAL and not a.plan:
        print('作業已收尾；不重複開始。請查看最新結果。');return
    with JobLock(ROOT/'runner.lock'):
        # Recover an orphan without ever launching a second learner.
        if alive(job.get('process')):raise SystemExit('既有子程序仍在運行，先查閱狀態；不重複啟動。')
        plan=read(a.plan or Path(job['job_dir'])/'plan.json',[])
        if not plan:raise SystemExit('尚未準備執行計畫')
        try:execute(job,plan)
        except BaseException as e:
            job['status']='failed';job['error']=repr(e);publish(job);report(job);raise

if __name__=='__main__':main()
