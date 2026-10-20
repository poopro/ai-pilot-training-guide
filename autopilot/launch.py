"""One click starts or attaches; explicit --new is required for a fresh budget."""
import argparse,subprocess,os,shutil,time
from common import *
p=argparse.ArgumentParser();p.add_argument('--new',action='store_true');p.add_argument('--resume',action='store_true')
p.add_argument('--status',action='store_true');p.add_argument('--stop',action='store_true');a=p.parse_args()
job=read(ROOT/'最新狀態.json')
if a.status:
    print(json.dumps(job,ensure_ascii=False,indent=2));raise SystemExit(0)
if a.stop:
    if job:(Path(job['job_dir'])/'STOP').write_text('interrupted',encoding='utf-8');print('已要求停止並保存。')
    raise SystemExit(0)
with JobLock(ROOT/'launch.lock'):
    if job and (alive(job.get('supervisor')) or alive(job.get('process'))):
        print('已有作業運行，不重複啟動：'+job['job_id']);raise SystemExit(0)
    if a.new or not job:
        job=new_job()
        snap=Path(job['job_dir'])/'baseline_source';hashes={}
        for src in list((BASE/'combat_v3').glob('*.py'))+list((BASE/'combat_v3').glob('*.json')):
            dest=snap/src.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);hashes[src.name]=digest(src)
        atomic(snap/'hashes.json',hashes)
    elif job.get('pipeline_finished') or job['status'] in TERMINAL and not a.resume:
        print('這個作業已收尾。請查看最新結果；要新任務需加 --new。');raise SystemExit(0)
    if time.time()>=job['deadline_epoch']-1800:print('原作業期限已到，不重置預算。');raise SystemExit(1)
    (Path(job['job_dir'])/'STOP').unlink(missing_ok=True)
    out=open(Path(job['job_dir'])/'driver_stdout.log','a',encoding='utf-8')
    err=open(Path(job['job_dir'])/'driver_stderr.log','a',encoding='utf-8')
    process=subprocess.Popen([str(PYTHON),'-u',str(ROOT/'driver.py')],cwd=str(ROOT),stdout=out,stderr=err,
      creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,
      env={**os.environ,'PYTHONUTF8':'1','PYTHONUNBUFFERED':'1'})
    job['supervisor']=identity(process.pid);job['status']='running';job['stage']='管線啟動中';publish(job)
    print('已啟動作業：'+job['job_id']+'；PID '+str(process.pid))
