"""Compact read-only campaign inspection; never restart or stop a process."""
import json
from pathlib import Path
import psutil

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def identity_state(record):
    if not record:
        return {'state': 'not_recorded'}
    expected_time = record.get('create_time', record.get('creation_epoch'))
    expected_command = record.get('cmdline', record.get('command'))
    try:
        process = psutil.Process(record['pid'])
        matches = (expected_time is not None and expected_command is not None
                   and abs(process.create_time()-expected_time) < .01
                   and process.cmdline() == expected_command)
        return {'pid': process.pid, 'state': 'identity_verified_live' if matches else 'identity_mismatch',
                'create_time': process.create_time(), 'parent_pid': process.ppid()}
    except psutil.NoSuchProcess:
        return {'pid': record['pid'], 'state': 'absent_exit_code_not_inferred'}
    except psutil.AccessDenied:
        return {'pid': record['pid'], 'state': 'unknown_access_denied'}

def inspect():
    research = read(ROOT/'research_latest.json')
    result = {k:research.get(k) for k in ('updated_utc','status','experiment','run','report',
              'comparison','gate','verified_comparison','retained_deployment','seed_role',
              'source_manifest','hard_deadline_epoch','next_action')}
    result['source_hashes_verified'] = False
    result['source_note'] = 'This compact reader checks process identity only; source/metadata require the experiment verifier.'
    run = Path(research['run'])
    state_path = run/'state.json'
    if state_path.is_file():
        state = read(state_path)
        result['run_status'] = state.get('status')
        result['case_id'] = state.get('case_id')
        result['supervisor'] = identity_state(state.get('supervisor'))
        result['worker'] = identity_state(state.get('worker'))
        result['error'] = state.get('error')
    result['guardian'] = identity_state(research.get('guardian'))
    cases = run/'cases'
    if cases.is_dir():
        receipts = [read(p) for p in cases.glob('*/exit.json')]
        result['worker_exit_receipts'] = len(receipts)
        result['worker_exit_zero'] = sum(r.get('exit_code') == 0 and r.get('wait_reason') == 'exited' for r in receipts)
    parent = run/'supervisor_exit.json'
    if parent.is_file():
        receipt = read(parent)
        result['parent_exit'] = {k:receipt.get(k) for k in ('actual_exit_code','wait_return_observed','wait_reason','error')}
    gate_path = ROOT/'diagnostics/host_gate_latest.json'
    if gate_path.is_file():
        gate = read(gate_path)
        result['official_host_gate'] = {k:gate.get(k) for k in ('eligible_rounds','required_rounds','fixed_profile_hash','competition_certification')}
    result['resources'] = {'stop':(ROOT/'STOP').exists(),
                           'available_ram_gib':round(psutil.virtual_memory().available/2**30,2),
                           'free_disk_gib':round(psutil.disk_usage(str(ROOT)).free/2**30,2)}
    return result

if __name__ == '__main__':
    print(json.dumps(inspect(),ensure_ascii=False,indent=2))
