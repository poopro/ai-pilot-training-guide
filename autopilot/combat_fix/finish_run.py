"""Complete this bounded repair experiment locally even if the chat disconnects.

No training is launched here. Wait only for the named registered run, reload
its actual bundle, compare against guidance, then publish complete results.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from artifacts import ROOT,atomic_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    run=a.run.resolve();allowed=(ROOT/'training').resolve()
    if run.parent!=allowed:raise ValueError('Named repair training run only')
    state={'status':'waiting_for_training','run':str(run),'official_validation':False}
    state_path=ROOT/'postprocess.json';atomic_json(state_path,state)
    deadline=time.monotonic()+1200
    def execute(args,timeout):
        result=subprocess.run([sys.executable,'-X','utf8',*map(str,args)],capture_output=True,text=True,encoding='utf-8',timeout=timeout)
        with (ROOT/'postprocess.log').open('a',encoding='utf-8') as log:log.write(result.stdout+'\n'+result.stderr+'\n')
        if result.returncode:raise RuntimeError(f'{args[0]} exited {result.returncode}')
    try:
        while not (run/'result.json').exists():
            if time.monotonic()>deadline:raise TimeoutError('Training result not available within bounded wait')
            time.sleep(5)
        result=json.loads((run/'result.json').read_text(encoding='utf-8'))
        if result['status'] not in ('completed','time_limit','stopped_by_user','interrupted') or not result.get('final_bundle'):
            raise RuntimeError('No usable completed training bundle')
        bundle=Path(result['final_bundle'])
        if bundle.parent!=run:raise ValueError('Training bundle path mismatch')
        # start_train publishes latest only after its SHA validation finishes.
        while True:
            if (ROOT/'latest_train.json').exists():
                latest=json.loads((ROOT/'latest_train.json').read_text(encoding='utf-8'))
                if Path(latest['bundle']).resolve()==bundle.resolve():break
            if time.monotonic()>deadline:raise TimeoutError('Registered saved bundle was not validated')
            time.sleep(2)
        state.update(status='verify_reload',bundle=str(bundle));atomic_json(state_path,state)
        execute([ROOT/'verify_saved.py','--bundle',bundle,'--out',ROOT/'validation/final_reload.json'],120)
        state.update(status='model_comparison');atomic_json(state_path,state)
        execute([ROOT/'compare.py','--baseline','repair_guide','--candidate',bundle,
                 '--out',ROOT/'evaluations/model_vs_guide'],900)
        while True:
            report=json.loads((ROOT/'evaluations/guide_new20/report.json').read_text(encoding='utf-8'))
            if report['status']=='completed':break
            if report['status']=='failed':raise RuntimeError('20-case guidance evaluation failed')
            if time.monotonic()>deadline:raise TimeoutError('20-case evaluation did not finish')
            time.sleep(5)
        execute([ROOT/'write_results.py'],60)
        state.update(status='completed',latest_report=str(ROOT.parent/'最新結果.md'));atomic_json(state_path,state)
        print(json.dumps(state,ensure_ascii=False),flush=True)
    except BaseException as error:
        state.update(status='failed',error=repr(error));atomic_json(state_path,state)
        (ROOT.parent/'最新結果.md').write_text('# 修正版作業收尾失敗\n\n'+repr(error)+'\n\n訓練、模型與逐場報告均保留，未替換官方部署。詳見 E:/ai_pilot/autopilot/combat_fix/postprocess.json。官方Host未驗證。\n',encoding='utf-8')
        raise

if __name__=='__main__':main()
