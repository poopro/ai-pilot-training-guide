"""Start the selected local controller; only its own recorded PID may be stopped."""
import argparse,subprocess,os,time
from common import *
p=argparse.ArgumentParser();p.add_argument('--status',action='store_true');p.add_argument('--stop',action='store_true')
p.add_argument('--dry-run',action='store_true',help='Validate selection and print command without starting a Player')
p.add_argument('--network',type=Path);a=p.parse_args();pid_file=ROOT/'player_process.json';old=read(pid_file)
if a.status:print(json.dumps({'running':alive(old),'process':old},ensure_ascii=False,indent=2));raise SystemExit(0)
if a.stop:
    terminate_owned(old);print('本入口啟動的 Player 已停止；Host 與其他程序不受影響。');raise SystemExit(0)
with JobLock(ROOT/'player_launch.lock'):
    if alive(old):print('Player 已運行，不重複啟動。');raise SystemExit(0)
    job=read(ROOT/'最新狀態.json')
    if not job or not job.get('pipeline_finished'):raise SystemExit('本輪尚未收尾，請先查看結果。')
    folder=experiment_dir(job);selection=read(folder/'deployment_selection.json') or read(folder/'selection.json')
    if not selection:raise SystemExit('尚未選出本地部署版本，請看結果。')
    frozen=read(folder/'frozen_source/hashes.json',{})
    if not frozen or any(digest(BASE/'combat_v3'/n)!=v for n,v in frozen.items()):raise SystemExit('來源與本輪版本不符，請重新驗證。')
    cmd=[str(PYTHON),'-u',str(BASE/'combat_v3/player.py')]
    if selection['decision']=='policy_candidate':valid_bundle(selection['bundle']);cmd+=['--bundle',selection['bundle']]
    else:cmd+=['--guide']
    if a.network:cmd+=['--network',str(a.network)]
    if a.dry_run:
        print(json.dumps({'selection':selection,'command':cmd,'source_matches':True,'player_started':False},ensure_ascii=False,indent=2))
        raise SystemExit(0)
    out=open(folder/'selected_player_stdout.log','a',encoding='utf-8');err=open(folder/'selected_player_stderr.log','a',encoding='utf-8')
    process=subprocess.Popen(cmd,cwd=str(BASE),stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW,
                            env={**os.environ,'PYTHONUTF8':'1','PYTHONUNBUFFERED':'1'})
    record=identity(process.pid);record.update(job_id=job['job_id'],selection=selection);atomic(pid_file,record)
    print('已啟動本地版本；PID '+str(process.pid)+'。每場比賽之前需停止再重新啟動 Player。')
    print('正式 Host 尚待驗證；請依官方指引進行 INIT、READY、START 並保存裁判結果。')
