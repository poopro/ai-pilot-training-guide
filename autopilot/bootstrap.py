import shutil,time
from common import *
if __name__=='__main__':
    existing=read(ROOT/'最新狀態.json')
    if existing:print(existing['job_dir'])
    else:
        job=new_job(1791129095)
        snapshot=Path(job['job_dir'])/'baseline_source'
        hashes={}
        paths=list((BASE/'combat_v3').glob('*.py'))+list((BASE/'combat_v3').glob('*.json'))
        paths+=[BASE/x for x in ('combat_v2/env.py','combat_v2/controller.py','envs/jsbsimEnv/jsbsimEnv.py','envs/jsbsimEnv/jsbsimFdm.py')]
        for source in paths:
            rel=source.relative_to(BASE);target=snapshot/rel;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target);hashes[str(rel)]=digest(source)
        atomic(snapshot/'hashes.json',hashes)
        job['artifacts']={'基準來源快照':str(snapshot)};publish(job);report(job)
        print(job['job_dir'])
