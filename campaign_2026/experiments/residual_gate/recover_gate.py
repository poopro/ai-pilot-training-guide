"""One immutable, full-horizon timeout retry. Never changes the original report."""
from pathlib import Path
import copy, hashlib, json, subprocess, sys, time
import psutil

ROOT=Path(r'E:\ai_pilot\campaign_2026')
EXP=ROOT/'experiments'/'residual_gate'
RUN=EXP/'run_20261012_191703_f102'
sys.path.insert(0,str(EXP))
import benchmark_gate as bench
from compare_gate import compare

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v): bench.atomic_json(p,v)

def main():
    old_path=RUN/'report.json'; old=read(old_path); old_hash=sha(old_path)
    invalid=[r for r in old['cases'] if not r['score_eligible']]
    assert len(invalid)==1 and invalid[0]['stop_reason']=='wall_timeout'
    assert old['planned_cases']==24 and len(old['cases'])==24
    assert sha(Path(bench.__file__))==old['benchmark_sha256']
    assert bench.capture_sources(old['repair_root'])==old['source_sha256']
    assert bench.bundle_hashes(old['candidate_bundle'])==old['candidate_bundle_sha256']
    assert bench.bundle_hashes(old['red_bundle'])==old['red_bundle_sha256']
    recovery=RUN/'recovery_01'; recovery.mkdir(exist_ok=False)
    record={'status':'waiting_for_original_evaluation','original_report_sha256':old_hash,
        'max_retries':1,'case_seconds':150,'reserved_total_compute_hours':4.75,
        'daily_compute_limit_hours':6,'official_validation':False}
    write(recovery/'state.json',record)
    # Avoid simultaneous CPU evaluation. Host identity checks distinguish denial from death.
    deadline=time.monotonic()+600
    while True:
        state=read(ROOT/'jobs'/'job_20261012_184123_68be'/'state.json')
        active=False
        for stage in state.get('stages',[]):
            identity=stage.get('process',{})
            if stage.get('name')!='dev_02' or not identity: continue
            try:
                process=psutil.Process(identity['pid'])
                active=(abs(process.create_time()-identity['creation_epoch'])<.01
                    and process.cmdline()==identity['cmdline'])
            except psutil.NoSuchProcess: active=False
        if not active: break
        if time.monotonic()>=deadline or bench.stopped(RUN):
            record['status']='deferred_no_retry_started'; write(recovery/'state.json',record); return 2
        time.sleep(5)
    row=invalid[0]; folder=recovery/'cases'/row['case_id']; folder.mkdir(parents=True)
    original_input=RUN/'cases'/row['case_id']/'input.json'
    spec=read(original_input)
    assert spec['max_steps']==18000 and spec['case_seconds']==150
    assert spec['source_sha256']==old['source_sha256']
    spec['out']=str(recovery)
    write(folder/'input.json',spec)
    record.update(status='running',case_id=row['case_id'],original_input_sha256=sha(original_input))
    with (folder/'worker.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen([sys.executable,'-B','-X','utf8',str(EXP/'benchmark_gate.py'),
            '--_worker',str(folder/'input.json')],stdout=log,stderr=subprocess.STDOUT,
            cwd=EXP,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        process=psutil.Process(proc.pid)
        record['process']={'pid':proc.pid,'creation_epoch':process.create_time(),'cmdline':process.cmdline()}
        write(recovery/'state.json',record)
        reason=bench.wait_process(proc,timeout_s=150,stop_check=lambda:bench.stopped(recovery) or bench.stopped(RUN))
    record.update(observed_exit_code=proc.returncode,wait_reason=reason)
    assert sha(old_path)==old_hash, 'Original report changed'
    assert bench.capture_sources(old['repair_root'])==old['source_sha256']
    if proc.returncode!=0 or not (folder/'result.json').exists():
        record['status']='retry_failed';write(recovery/'state.json',record);return 2
    new=read(folder/'result.json')
    assert new['score_eligible'] and new['full_round_completed'] and new['case_id']==row['case_id']
    assert new['initial_sha256']==row['initial_sha256']
    merged=copy.deepcopy(old)
    merged['cases']=[new if r['case_id']==new['case_id'] else r for r in old['cases']]
    for r in old['cases']:
        if r['score_eligible']:
            saved=read(RUN/'cases'/r['case_id']/'result.json')
            assert saved['score_eligible'] and saved['metrics']==r['metrics'] and saved['initial_sha256']==r['initial_sha256']
    planned=[bench.Case(**r['case']) for r in merged['cases']]
    merged['summary']=bench.summarize(merged['cases'],planned,True)
    assert merged['summary']['complete'] and merged['summary']['paired_completed']==12
    merged.update(status='completed',benchmark_complete=True,gate='review_pending',
        recovery={'original_report':str(old_path),'original_report_sha256':old_hash,
            'replacement_case':new['case_id'],'replacement_result':str(folder/'result.json'),
            'replacement_result_sha256':sha(folder/'result.json'),'replacement_exit_code':proc.returncode,
            'original_attempt_retained':True,'maximum_attempts_per_case':2})
    write(recovery/'report.json',merged)
    raw=read(ROOT/'jobs'/'job_20261012_184123_68be'/'dev_01'/'report.json')
    comparison=compare(raw,merged); write(recovery/'COMPARISON.json',comparison)
    assert comparison['verified_comparison']
    record.update(status='completed',merged_report_sha256=sha(recovery/'report.json'),
        candidate_gate=comparison['candidate_gate'])
    write(recovery/'state.json',record)
    latest=read(EXP/'latest.json'); latest.update(status='completed_after_one_timeout_retry',
        original_status=old['status'],comparison_report=str(recovery/'report.json'),
        comparison=str(recovery/'COMPARISON.json'),benchmark_complete=True,
        promotion=comparison['candidate_gate'],recovery_state=str(recovery/'state.json'),
        compute_reserved_hours=4.75,eligible_cases=24)
    write(EXP/'latest.json',latest)
    print(json.dumps({'status':record['status'],'comparison':comparison},ensure_ascii=False),flush=True)
    return 0

if __name__=='__main__': raise SystemExit(main())
