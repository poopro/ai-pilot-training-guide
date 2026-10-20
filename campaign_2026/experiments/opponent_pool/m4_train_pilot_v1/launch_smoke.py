"""Only public FDM entry. Holds campaign lock and records real supervisor exit."""
import argparse,subprocess,time,uuid
from common import *

def main(args):
    if args.check_only:
        result=check(args.seed,diagnostic_case_index=args.diagnostic_case_index)
        print(json.dumps({k:v for k,v in result.items() if k not in ('source_freeze','cases','tools_sha256')},ensure_ascii=False))
        return 0
    if args.remaining_percent is None or args.usage_epoch is None:raise ValueError('Live quota observation required')
    with JobLock(ROOT/'launch.lock'):
        out=HERE/('run_'+datetime.now(TAIPEI).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]);out.mkdir()
        spec=reserve(args.seed,out,args.remaining_percent,args.usage_epoch,args.diagnostic_case_index)
        write(out/'reservation.json',spec)
        with (out/'supervisor.log').open('w',encoding='utf8') as log:
            supervisor=subprocess.Popen([sys.executable,'-B','-X','utf8',str(HERE/'run_smoke.py'),'--out',str(out)],stdout=log,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
            spec.update(supervisor=identity(supervisor.pid));write(out/'launch.json',spec)
            pointer=read(ROOT/'research_latest.json')
            pointer.update(updated_utc=datetime.now(timezone.utc).isoformat(),experiment='m4_train_pilot_v1',run=str(out),status='running',supervisor=spec['supervisor'],report=str(out/'report.json'),gate='fresh_pilot_running_not_promotable',new_run_permitted=False,new_run_block_reason='One fresh learner active; monitor same identity, never duplicate.')
            pointer['active_workload']={'status':'running','run':str(out),'supervisor':spec['supervisor'],'deadline_epoch':spec['deadline_epoch']}
            pointer['current_live_workloads']={'learners':[spec['supervisor']],'loops':[],'observed_utc':datetime.now(timezone.utc).isoformat()}
            write(ROOT/'research_latest.json',pointer)
            with (out/'guard.log').open('w',encoding='utf8') as glog:
                guard=subprocess.Popen([sys.executable,'-B','-X','utf8',str(HERE/'guard.py'),'--out',str(out)],stdout=glog,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
                write(out/'guard_identity.json',identity(guard.pid))
                try:
                    code=supervisor.wait(timeout=max(0,spec['deadline_monotonic']-time.monotonic())+10)
                except subprocess.TimeoutExpired:
                    write(out/'abort.json',{'reason':'launcher_wait_timeout'})
                    try:code=supervisor.wait(timeout=10)
                    except subprocess.TimeoutExpired:code=None
                write(out/'supervisor_exit.json',{'identity':spec['supervisor'],'actual_parent_exit_code':code,'observed_by':identity(),'observed_epoch':time.time()})
                try:gcode=guard.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    write(out/'abort.json',{'reason':'guard_receipt_timeout'})
                    try:gcode=guard.wait(timeout=10)
                    except subprocess.TimeoutExpired:gcode=None
                if code is None:
                    code=supervisor.poll()
                    write(out/'supervisor_exit.json',{'identity':spec['supervisor'],'actual_parent_exit_code':code,'exit_observation_unknown':code is None,'observed_by':identity(),'observed_epoch':time.time()})
                write(out/'launcher_receipt.json',{'actual_parent_exit_code':code,'actual_guard_exit_code':gcode,'reservation_sha256':sha(out/'reservation.json'),'launch_sha256':sha(out/'launch.json'),'report_sha256':sha(out/'report.json') if (out/'report.json').exists() else None,'guard_sha256':sha(out/'guard.json') if (out/'guard.json').exists() else None})
        registry=read(ROOT/'seed_registry.json');registry['trials'][spec['trial_id']].update(status='attempted_terminal',parent_exit_code=code)
        write(ROOT/'seed_registry.json',registry)
        ledger=read(spec['ledger']);item=next(x for x in ledger['items'] if x['id']==spec['trial_id']);item.update(status='attempted_terminal',parent_exit_code=code)
        if (out/'report.json').exists():item['actual_wall_seconds']=read(out/'report.json').get('wall_seconds')
        write(spec['ledger'],ledger)
        pointer=read(ROOT/'research_latest.json')
        pointer.update(updated_utc=datetime.now(timezone.utc).isoformat(),status='terminal_pending_verification',actual_parent_exit_code=code,gate='fresh_pilot_terminal_pending_audit')
        pointer['active_workload']={'status':'terminal_pending_verification','run':str(out),'actual_parent_exit_code':code}
        pointer['current_live_workloads']={'learners':[],'loops':[],'observed_utc':datetime.now(timezone.utc).isoformat()}
        write(ROOT/'research_latest.json',pointer)
        print(json.dumps({'out':str(out),'actual_parent_exit_code':code,'score_eligible':False},ensure_ascii=False))
        return code if code is not None else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check-only',action='store_true');p.add_argument('--seed',type=int,default=2026101650);p.add_argument('--diagnostic-case-index',type=int);p.add_argument('--remaining-percent',type=float);p.add_argument('--usage-epoch',type=float)
    raise SystemExit(main(p.parse_args()))
