"""A new bounded saved-data audit. Never launches physics or training.

Preserves the original 60-second verifier failure; runs its unchanged strict
checks under a separate 180-second offline review contract and reservation.
"""
import datetime
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psutil

ROOT=Path(r'E:\ai_pilot\campaign_2026')
SOURCE=ROOT/'experiments/opponent_pool/frozen_sac_battle_v2'
RUN=SOURCE/'run_20261017_093943_16bee6'
LIMIT=180

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def identity(pid):
    p=psutil.Process(pid)
    return dict(pid=p.pid,create=p.create_time(),cmd=p.cmdline(),exe=p.exe(),parent=p.ppid())
def live(i):
    try:return identity(i['pid'])==i
    except psutil.NoSuchProcess:return False

def worker(audit):
    contract=read(audit/'CONTRACT.json')
    if {p:sha(Path(p)) for p in contract['sources']}!=contract['sources']:raise RuntimeError('Review source changed')
    if read(RUN/'PARENT_EXIT_OBSERVED.json')['actual_exit']!=0:raise RuntimeError('Actual game parent exit missing')
    sys.path.insert(0,str(SOURCE))
    import verify
    original_read=verify.read
    def observed_read(p):
        if p.name=='RESULT.json':print(json.dumps(dict(stage='strict_case_replay',case=p.parent.name,elapsed=time.time()-contract['started_epoch'])),flush=True)
        return original_read(p)
    verify.read=observed_read
    print(json.dumps(dict(stage='unchanged_strict_verifier_start')),flush=True)
    code=verify.verify(RUN,0)
    result=read(RUN/'COMPARISON.json')
    result.update(independent_saved_data_reaudit=str(audit),original_60s_verifier_success=False,
                  original_verifier_failure_preserved=str(RUN/'VERIFIER_EXIT.json'))
    write(audit/'COMPARISON.json',result)
    return code

def launch():
    sys.path.insert(0,str(ROOT));from runner import JobLock
    with JobLock(ROOT/'launch.lock'):
        sys.path.insert(0,str(SOURCE));import battle
        if battle.base.inventory():raise RuntimeError('Other/unknown live campaign work')
        battle.base.resources()
        if (ROOT/'STOP').exists() or (RUN/'STOP').exists():raise RuntimeError('STOP')
        if read(RUN/'VERIFIER_EXIT.json')['reason']!='original_deadline_or_60s_verifier_cap':raise RuntimeError('Not the documented failed audit')
        receipt=read(RUN/'VERIFIER_EXIT.json')
        if live(receipt['identity']):raise RuntimeError('Original verifier still live')
        audit=ROOT/'diagnostics'/('saved_sac_battle_audit_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6])
        audit.mkdir()
        started=time.monotonic()
        contract=dict(started_epoch=time.time(),deadline_epoch=time.time()+LIMIT,deadline_monotonic=started+LIMIT,
                      seconds=LIMIT,source_run=str(RUN),guardian=identity(__import__('os').getpid()),
                      sources={str(p):sha(p) for p in (Path(__file__),SOURCE/'battle.py',SOURCE/'verify.py')},
                      prior_failure=receipt,new_FDM_ticks=0,training_started=False,
                      hypothesis='Original complete saved games can pass unchanged strict verification; first auditor exceeded its 60s wall cap',
                      limitations='Separate offline review contract; does not change or repair the original timeout receipt, repeat games, or claim original auditor exit0')
        write(audit/'CONTRACT.json',contract)
        ledger_path=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json'
        ledger=read(ledger_path);ledger['items'].append(dict(id=audit.name,hours=LIMIT/3600,status='reserved_saved_data_audit',output=str(audit),warning_only=True));ledger['reserved_hours']=sum(i['hours'] for i in ledger['items']);write(ledger_path,ledger)
        write(RUN/'OFFLINE_REAUDIT_POINTER.json',dict(audit=str(audit),status='running',original_verifier_failed=True))
        with (audit/'audit.log').open('w',encoding='utf8') as log:
            p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(Path(__file__)),'--worker',str(audit)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            ident=identity(p.pid);children={};reason='normal_exit'
            write(audit/'worker_identity.json',ident)
            while p.poll() is None:
                if live(ident):
                    for child in psutil.Process(p.pid).children(recursive=True):
                        try:
                            ci=identity(child.pid);node=child;chain=[]
                            while node.pid!=p.pid:
                                chain.append(identity(node.pid));node=node.parent()
                                if node is None:raise RuntimeError('Lost owned ancestry')
                            if not live(ident):raise RuntimeError('Worker identity changed')
                            children[(ci['pid'],ci['create'])]=dict(identity=ci,chain=chain)
                        except psutil.NoSuchProcess:continue
                if time.monotonic()>=contract['deadline_monotonic'] or time.time()>=contract['deadline_epoch'] or any(x.exists() for x in (ROOT/'STOP',RUN/'STOP',audit/'STOP')):
                    reason='new_offline_review_deadline_or_STOP'
                    for item in reversed(list(children.values())):
                        if live(item['identity']):psutil.Process(item['identity']['pid']).terminate()
                    if live(ident):p.terminate()
                    break
                time.sleep(.1)
            try:code=p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if not live(ident):raise RuntimeError('Worker identity unknown')
                p.kill();code=p.wait(timeout=2)
            for item in children.values():
                ci=item['identity']
                if live(ci):
                    try:psutil.Process(ci['pid']).wait(timeout=1)
                    except psutil.TimeoutExpired:
                        if live(ci):psutil.Process(ci['pid']).terminate()
            absent=not live(ident) and all(not live(c['identity']) for c in children.values())
        passed=code==0 and reason=='normal_exit' and absent
        exit_record=dict(actual_worker_exit=code,guardian_return_intended=0 if passed else 2,reason=reason,identity=ident,owned_descendants=list(children.values()),original_identities_absent=absent,wall_seconds=time.monotonic()-started,source_run=str(RUN),original_failure_preserved=True,new_FDM_ticks=0)
        write(audit/'AUDIT_EXIT.json',exit_record)
        write(RUN/'OFFLINE_REAUDIT_POINTER.json',dict(audit=str(audit),status='passed_pending_actual_guardian_exit' if passed else 'failed',original_verifier_failed=True))
        ledger=read(ledger_path)
        for item in ledger['items']:
            if item['id']==audit.name:item.update(status='audit_passed_pending_actual_guardian_exit' if passed else 'failed_saved_data_audit',actual_worker_exit=code,actual_wall_seconds=exit_record['wall_seconds'])
        write(ledger_path,ledger)
        print(json.dumps(dict(audit=str(audit),**exit_record)),flush=True)
        return 0 if passed else 2

if __name__=='__main__':
    raise SystemExit(worker(Path(sys.argv[2])) if len(sys.argv)==3 and sys.argv[1]=='--worker' else launch())
