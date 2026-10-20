"""Read-only isolated preflight timing. Parent owns a real45s child wait handle."""
from pathlib import Path
import sys,json,time,subprocess,datetime,uuid

ROOT=Path(r'E:\ai_pilot\campaign_2026')
BRANCH=ROOT/'diagnostics/portable_host_v2'

def child(out):
    import faulthandler
    faulthandler.dump_traceback_later(5,repeat=True)
    sys.path.insert(0,str(BRANCH))
    import portable_host as m
    original=m.sha;calls=[];began=time.monotonic()
    def timed_sha(path):
        start=time.monotonic();value=original(path);elapsed=time.monotonic()-start
        calls.append({'path':str(path),'seconds':elapsed})
        if elapsed>.25 or len(calls)%100==0:print(json.dumps({'hash_count':len(calls),'last_path':str(path),'last_seconds':elapsed,'total_seconds':time.monotonic()-began}),flush=True)
        return value
    m.sha=timed_sha
    for name in ('frozen_profile','workload_conflicts','commands'):
        function=getattr(m,name)
        def measured(*args,_name=name,_fn=function,**kwargs):
            start=time.monotonic();print('ENTER '+_name,flush=True)
            result=_fn(*args,**kwargs);print('EXIT '+_name+' '+str(time.monotonic()-start),flush=True);return result
        setattr(m,name,measured)
    def forbidden(*args,**kwargs):raise RuntimeError('Profile forbids spawning Host/Player/FDM')
    m.subprocess.Popen=forbidden
    result=m.preflight(remaining_percent=8)
    m.atomic(out/'preflight.json',result)
    m.atomic(out/'hash_timings.json',{'calls':calls,'elapsed_seconds':time.monotonic()-began})
    print('PROFILE_FINISHED',flush=True)

def parent():
    import psutil
    sys.path.insert(0,str(ROOT))
    from runner import JobLock
    from datetime import timezone,timedelta
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S');out=ROOT/'diagnostics'/('preflight_profile_'+stamp+'_'+uuid.uuid4().hex[:4]);out.mkdir()
    def write(name,value): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    with JobLock(ROOT/'launch.lock'):
        if (ROOT/'STOP').exists() or (BRANCH/'STOP').exists():raise RuntimeError('STOP')
        day=datetime.datetime.now(timezone(timedelta(hours=8))).date().isoformat();ledger_path=ROOT/'compute_budgets'/(day+'.json')
        ledger=json.loads(ledger_path.read_text(encoding='utf-8-sig'));assert abs(sum(x['hours'] for x in ledger['items'])-ledger['reserved_hours'])<1e-8
        trial=out.name;ledger['items'].append({'id':trial,'hours':1/60,'status':'reserved_readonly_profile','output':str(out),'no_FDM':True});ledger['reserved_hours']=sum(x['hours'] for x in ledger['items']);ledger_path.write_text(json.dumps(ledger,indent=2),encoding='utf8')
        command=[str(ROOT/'deployment/repair_guide_portable_20261012/runtime/python.exe'),'-I','-S','-B','-X','utf8','-u',str(Path(__file__).resolve()),'--child',str(out)]
        began=time.monotonic()
        with (out/'profile.log').open('w',encoding='utf8') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            actual=psutil.Process(process.pid);identity={'pid':actual.pid,'creation_epoch':actual.create_time(),'cmdline':actual.cmdline(),'exe':actual.exe(),'parent_pid':actual.ppid()};write('identity.json',identity)
            timeout=False
            try:code=process.wait(timeout=45)
            except subprocess.TimeoutExpired:
                timeout=True;p=psutil.Process(identity['pid'])
                if p.create_time()!=identity['creation_epoch'] or p.cmdline()!=identity['cmdline'] or p.exe()!=identity['exe'] or p.ppid()!=__import__('os').getpid():raise RuntimeError('Cannot verify own timed-out child')
                p.terminate();code=process.wait(timeout=5)
        receipt={'actual_exit_code':code,'deadline45_expired':timeout,'wall_seconds':time.monotonic()-began,'identity':identity,'new_Host_rounds':0,'new_FDM_ticks':0,'source_files_modified':False,'out':str(out)};write('exit.json',receipt)
        ledger=json.loads(ledger_path.read_text(encoding='utf8'));item=next(x for x in ledger['items'] if x['id']==trial);item.update(status='terminal',actual_exit_code=code,actual_wall_seconds=receipt['wall_seconds']);ledger_path.write_text(json.dumps(ledger,indent=2),encoding='utf8')
        print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':
    child(Path(sys.argv[2])) if len(sys.argv)>1 and sys.argv[1]=='--child' else parent()
