"""Durable local job state; no ML imports."""
import hashlib, json, os, time, uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
import psutil

ROOT = Path(__file__).resolve().parent
BASE = Path(r'E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test')
PYTHON = Path(r'C:\Users\USER\anaconda3\envs\F16_ai\python.exe')
TERMINAL = {'completed','failed','budget_exhausted','interrupted'}

def read(path, default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):return default

def atomic(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp_'+uuid.uuid4().hex)
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    for n in range(6):
        try:os.replace(temp,path);return
        except PermissionError:
            if n==5:raise
            time.sleep(.1)

def stamp():return datetime.now(timezone.utc).isoformat()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def experiment_dir(job):return Path(job.get('active_experiment_dir',job['job_dir']))
def stage_label(job,name):return ('c2_' if job.get('candidate_count',0)==2 else '')+name

def identity(pid):
    p=psutil.Process(int(pid))
    return {'pid':p.pid,'create_time':p.create_time(),'command':p.cmdline()}

def alive(record):
    if not record:return False
    try:
        p=psutil.Process(int(record['pid']))
        return abs(p.create_time()-record['create_time'])<.02 and p.is_running()
    except (psutil.Error,KeyError,ValueError):return False

class JobLock:
    def __init__(self,path):self.path=Path(path);self.owned=False
    def __enter__(self):
        for attempt in range(3):
            try:
                fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
                with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(identity(os.getpid()),f)
                self.owned=True;return self
            except FileExistsError:
                record=read(self.path)
                # A newly created lock may not yet have its JSON flushed.
                if record is None and time.time()-self.path.stat().st_mtime<10:raise RuntimeError('作業鎖建立中')
                if alive(record):raise RuntimeError('已有監督程序運行：'+str(record['pid']))
                self.path.unlink(missing_ok=True)
        raise RuntimeError('無法取得作業鎖')
    def __exit__(self,*args):
        if self.owned and read(self.path,{}).get('pid')==os.getpid():self.path.unlink(missing_ok=True)

def publish(job):
    job['heartbeat_utc']=stamp()
    job['remaining_steps']=max(0,job['step_budget']-job['new_steps'])
    atomic(Path(job['job_dir'])/'state.json',job)
    atomic(ROOT/'最新狀態.json',job)

def new_job(first_started=None):
    now=time.time();started=first_started or now
    ident='job_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4]
    folder=ROOT/'jobs'/ident;folder.mkdir(parents=True)
    job={'job_id':ident,'job_dir':str(folder),'status':'preparing','stage':'盤點與監督程序測試',
         'first_started_epoch':started,'deadline_epoch':started+8*3600,
         'deadline_utc':datetime.fromtimestamp(started+8*3600,timezone.utc).isoformat(),
         'deadline_taipei':datetime.fromtimestamp(started+8*3600,timezone(timedelta(hours=8))).isoformat(),
         'step_budget':200000,'new_steps':0,'candidate_count':0,'attempts':{},'results':[],
         'official_host':'pending_manual','learning':'not_evaluated','process':None,
         'checkpoint':None,'error':None,'config':{'envs':2,'vec_mode':'dummy','max_candidates':2,
            'checkpoint_steps':10000,'checkpoint_seconds':300,'stall_seconds':600,'save_grace_seconds':180,
            'min_commit_free_gb':3,'min_available_ram_gb':.35,'resource_wait_seconds':1800}}
    publish(job);return job

def valid_bundle(path, verify_replay=True):
    path=Path(path);m=read(path/'manifest.json')
    if not m or m.get('format')!='guided_combat_v3':raise ValueError('無效 manifest')
    for key,suffix in [('model','zip'),('replay','pkl')]:
        if key=='replay' and not verify_replay:continue
        if digest(path/(key+'.'+suffix))!=m[key+'_sha256']:raise ValueError('校驗失敗：'+key)
    return m

def latest_bundle(folder):
    paths=[p for p in Path(folder).glob('**/manifest.json') if p.parent.name.startswith(('checkpoint_','final_'))]
    paths.sort(key=lambda p:p.stat().st_mtime,reverse=True)
    for p in paths:
        try:valid_bundle(p.parent);return str(p.parent)
        except (OSError,ValueError,KeyError):pass
    return None

def terminate_owned(record,timeout=5):
    if not alive(record):return
    root=psutil.Process(record['pid']);children=root.children(recursive=True)
    owned=[(p,p.create_time()) for p in children]+[(root,root.create_time())]
    for p,created in reversed(owned):
        try:
            if abs(p.create_time()-created)<.02:p.terminate()
        except psutil.Error:pass
    gone,pending=psutil.wait_procs([p for p,_ in owned],timeout=timeout)
    for p in pending:
        try:p.kill()
        except psutil.Error:pass

def report(job):
    elapsed=(time.time()-job['first_started_epoch'])/60
    lines=['# AI 空戰無人值守結果','',f"作業：`{job['job_id']}`；狀態：**{job['status']}**；階段：{job['stage']}",
       f"已經過 {elapsed:.1f} 分鐘；新增訓練 {job['new_steps']:,} / {job['step_budget']:,} 步。",
       '',f"程式驗證：{job.get('verification','尚未完成')}。",
       f"學習成效：{job.get('learning','尚未評估')}。",
       f"官方 Host：{job.get('official_host','pending_manual')}（本機模擬／loopback 不等於官方通過）。",'']
    if job.get('error'):lines+=['原因：'+str(job['error']),'']
    selection=job.get('selection',{})
    if selection:lines+=['目前選擇：'+selection.get('decision','尚未選定'),'']
    if job.get('checkpoint'):lines+=['最後完整存檔：['+Path(job['checkpoint']).name+'](<'+job['checkpoint'].replace('\\','/')+'>)','']
    for label,path in job.get('artifacts',{}).items():lines+=['- ['+label+'](<'+str(path).replace('\\','/')+'>)']
    lines+=['','| 階段 | 退出碼 | 結果位置 |','| --- | --- | --- |']
    for result in job['results']:
        lines.append('| '+result['name']+' | '+str(result.get('exit_code','執行中'))+' | ['+result['name']+'](<'+result['folder'].replace('\\','/')+'>) |')
    evaluation=job.get('final_evaluation') or job.get('guide_evaluation')
    if evaluation:
        lines+=['','| 版本／對手 | 場數 | 擊殺 | 存活 | 平均攻擊秒數 | 平均獎勵 |','| --- | --- | --- | --- | --- | --- |']
        for group in evaluation.get('groups',[]):
            lines.append(f"| {group['policy']}／{group['opponent']} | {group['episodes']} | {group['kills']}/{group['episodes']} | {group['survivals']}/{group['episodes']} | {group['attack_seconds']:.3f} | {group['mean_reward']:.3f} |")
        lines+=['','失敗／終止原因：`'+json.dumps(evaluation.get('end_reasons',{}),ensure_ascii=False)+'`。']
    lines+=['','後續：'+job.get('next_action','等待本機監督程序完成；先查看最新狀態與心跳。'),
      '','本地藍色＝我方，紅色＝對手。正式 Host 顏色與裁判結果仍需核對。']
    content='\n'.join(lines)+'\n'
    (Path(job['job_dir'])/'結果.md').write_text(content,encoding='utf-8')
    temp=ROOT/'最新結果.tmp';temp.write_text(content,encoding='utf-8');os.replace(temp,ROOT/'最新結果.md')
