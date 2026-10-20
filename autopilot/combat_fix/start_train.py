"""One registered training run, with a usable STOP path and exit evidence."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import uuid
import psutil
from artifacts import ROOT,atomic_json,read_manifest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--decisions',type=int,default=100000)
    parser.add_argument('--max-minutes',type=float,default=60)
    parser.add_argument('--resume-latest',action='store_true');args=parser.parse_args()
    registry=ROOT/'active_run.json'
    if registry.exists():
        old=json.loads(registry.read_text(encoding='utf-8'))
        try:
            proc=psutil.Process(old['pid'])
            if abs(proc.create_time()-old['creation_epoch'])<.01 and proc.is_running():
                raise RuntimeError('已有修正版訓練運行中，請等待或使用停止並保存入口。')
        except psutil.NoSuchProcess:pass
    run=ROOT/'training'/('run_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4])
    run.parent.mkdir(parents=True,exist_ok=True)
    cmd=[sys.executable,'-X','utf8',str(ROOT/'train.py'),'--run-dir',str(run),
         '--decisions',str(args.decisions),'--max-minutes',str(args.max_minutes)]
    if args.resume_latest:
        latest=json.loads((ROOT/'latest_train.json').read_text(encoding='utf-8'))
        read_manifest(Path(latest['bundle']),verify_replay=True)
        cmd+=['--resume',latest['bundle']]
    log=run.parent/(run.name+'.log')
    print('修正版訓練；最多'+str(args.max_minutes)+'分鐘。停止請用「停止修正版訓練並保存.cmd」。',flush=True)
    with log.open('w',encoding='utf-8') as output:
        child=subprocess.Popen(cmd,stdout=output,stderr=subprocess.STDOUT)
        process=psutil.Process(child.pid)
        active={'status':'running','pid':child.pid,'creation_epoch':process.create_time(),
            'command':cmd,'run_dir':str(run),'log':str(log),'stop_file':str(run/'STOP')}
        atomic_json(registry,active)
        try:code=child.wait()
        except KeyboardInterrupt:
            run.mkdir(parents=True,exist_ok=True);(run/'STOP').write_text('User requested stop',encoding='utf-8')
            code=child.wait(timeout=120)
    active.update(status='exited',exit_code=code);atomic_json(registry,active)
    if (run/'result.json').exists():
        result=json.loads((run/'result.json').read_text(encoding='utf-8'))
        if code==0 and result.get('final_bundle'):
            read_manifest(Path(result['final_bundle']),verify_replay=True)
            atomic_json(ROOT/'latest_train.json',{'bundle':result['final_bundle'],'run_dir':str(run),
                'status':result['status'],'official_validation':False,'evaluation':'not automatically promoted'})
        print(json.dumps(result,ensure_ascii=False),flush=True)
    print('詳細紀錄：'+str(log),flush=True)
    if code:raise SystemExit(code)

if __name__=='__main__':main()
