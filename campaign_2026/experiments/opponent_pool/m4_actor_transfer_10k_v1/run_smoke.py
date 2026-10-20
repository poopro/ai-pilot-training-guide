"""Private supervisor/worker. A recorded launcher and independent guard are mandatory."""
import argparse,csv,subprocess,time,copy,traceback
from common import *

def await_guard(out,launch):
    end=time.monotonic()+10
    while time.monotonic()<end:
        if (out/'guard.json').exists():
            try:guard=read(out/'guard.json')
            except (OSError,ValueError):
                time.sleep(.1);continue
            if guard['status']=='armed' and guard['target']==launch['supervisor'] and matching(guard['guard']):return guard
        if stop(out):raise RuntimeError('STOP before guard armed')
        time.sleep(.1)
    raise RuntimeError('Independent guard not armed')

def write_frame_with_offset(stream,env,offset):
    stream.write(f"#{(offset+env.current_step)/60.:.3f}\n")
    for oid,plane in ((1,env.fdm1),(2,env.fdm2)):
        pose=plane.getProperty('pose')
        stream.write(f"{oid},T={pose[1]}|{pose[7]}|{pose[2]}|{pose[5]}|{pose[4]}|{pose[3]}\n")

def worker(input_path):
    from train_worker import run
    return run(input_path)


def supervisor(out):
    out=Path(out);began=time.monotonic()
    end=time.monotonic()+10
    while not (out/'launch.json').exists() and time.monotonic()<end:time.sleep(.1)
    launch=read(out/'launch.json')
    if identity()!=launch['supervisor'] or psutil.Process().ppid()!=launch['launcher']['pid'] or not matching(launch['launcher']):raise RuntimeError('Supervisor ownership mismatch')
    execution_mode_gate(launch)
    await_guard(out,launch)
    report={'status':'running','cases':[],'score_eligible':False,'official_validation':False,'plan_sha256':jsha(launch['cases'])}
    code=0
    for case in launch['cases']:
        if stop(out) or time.monotonic()>=launch['deadline_monotonic']:code=2;break
        resource_gate();source_gate(launch['source_freeze'])
        folder=out/'cases'/case['case_id'];folder.mkdir(parents=True)
        write(folder/'input.json',{'out':str(out),'case':case,'source_freeze':launch['source_freeze'],'tools_sha256':launch['tools_sha256']})
        with (folder/'worker.log').open('w',encoding='utf8') as log:
            worker_start_monotonic=time.monotonic();worker_start_epoch=time.time()
            p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(HERE/'run_smoke.py'),'--worker',str(folder/'input.json')],stdout=log,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
            ident=identity(p.pid);worker_deadline=min(launch['deadline_monotonic'],worker_start_monotonic+840)
            write(out/'active_worker.json',{'identity':ident,'deadline_epoch':worker_start_epoch+840,'deadline_monotonic':worker_deadline,'case_id':case['case_id']})
            try:wcode=p.wait(timeout=max(0,worker_deadline-time.monotonic())+3)
            except subprocess.TimeoutExpired:
                # Independent guard owns termination; never restart timed-out cases.
                write(out/'abort.json',{'reason':'worker_guard_did_not_finish'});wcode=p.wait(timeout=5)
            receipt={'identity':ident,'actual_worker_exit_code':wcode,'case_id':case['case_id'],'input_sha256':sha(folder/'input.json'),'result_sha256':sha(folder/'result.json') if (folder/'result.json').exists() else None}
            write(folder/'worker_exit.json',receipt)
        report['cases'].append(receipt);write(out/'report.json',report)
        if wcode!=0:code=2;break
    report.update(status='completed' if len(report['cases'])==len(launch['cases']) and code==0 else 'partial',wall_seconds=time.monotonic()-began)
    write(out/'report.json',report)
    return code if len(report['cases'])==len(launch['cases']) else 2

def guarded_worker(input_path):
    # Ownership/guard failures occur before the FDM try/finally. Preserve them too.
    try:return worker(input_path)
    except BaseException as error:
        traceback.print_exc()
        spec=read(input_path);folder=Path(input_path).parent
        write(folder/'result.json',{'case':spec['case'],'worker_identity':identity(),'status':'failed','steps':0,'score_eligible':False,'official_validation':False,'failure_phase':'pre_fdm_gate','error':repr(error)})
        return 2

if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--out',type=Path);g.add_argument('--worker',type=Path);a=p.parse_args()
    raise SystemExit(guarded_worker(a.worker) if a.worker else supervisor(a.out))
