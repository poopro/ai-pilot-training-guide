"""Bounded local campaign: immutable training, paired review, no deployment.

All generated files remain below this script's ROOT. Existing E: bundles and
simulator dependencies are read only. This process makes no network/API calls.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

import psutil

ROOT = Path(__file__).resolve().parent
REPAIR = ROOT / 'repair_v1'
PYTHON = Path(r'C:\Users\USER\anaconda3\envs\F16_ai\python.exe')
DEFAULT_RESUME = Path(r'E:\ai_pilot\autopilot\combat_fix\training\run_20261006_192453_c95b\final_0000024000')
POINTER = ROOT / 'pipeline_latest.json'
TAIPEI = timezone(timedelta(hours=8))
TERMINAL = {'completed', 'failed', 'time_limit', 'stopped_by_user', 'resource_pressure', 'futility_stop'}
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp_' + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


class JobLock:
    """OS lock is released when the owning process exits, including a crash."""
    def __init__(self, path):
        self.path = Path(path)
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open('a+b')
        if self.stream.tell() == 0:
            self.stream.write(b'0'); self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.stream.close(); self.stream = None
            raise RuntimeError('已有同一作業的啟動或監督程序；不重複執行。') from error
        return self

    def __exit__(self, *_):
        if self.stream is not None:
            self.stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_UN)
            self.stream.close(); self.stream = None


def identity(pid):
    proc = psutil.Process(pid)
    return {'pid': pid, 'creation_epoch': proc.create_time(), 'cmdline': proc.cmdline()}


def owned_alive(record):
    """A reused PID or altered command is never accepted as our child."""
    if not record or not record.get('cmdline'):
        return False
    try:
        proc = psutil.Process(record['pid'])
        return (proc.is_running() and abs(proc.create_time() - record['creation_epoch']) < .01
                and proc.cmdline() == record['cmdline'])
    except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
        return False


def terminate_owned(record):
    if not owned_alive(record):
        return False
    parent = psutil.Process(record['pid'])
    # Capture identities before any termination, then recheck each identity.
    try:
        records = [identity(p.pid) for p in parent.children(recursive=True)]
    except psutil.NoSuchProcess:
        return False
    records.append(record)
    for item in reversed(records):
        if owned_alive(item):
            try:
                psutil.Process(item['pid']).terminate()
            except psutil.NoSuchProcess:
                pass
    survivors = []
    for item in records:
        if owned_alive(item):
            survivors.append(psutil.Process(item['pid']))
    _, remaining = psutil.wait_procs(survivors, timeout=5)
    for proc in remaining:
        item = next((r for r in records if r['pid'] == proc.pid), None)
        if owned_alive(item):
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                pass
    return True


def is_trainer_command(command):
    for token in command or []:
        path = str(token).replace('\\', '/').lower()
        if path.endswith('/train_opponents.py') or re.search(r'/(?:combat_fix|repair_v[^/]+)/train\.py$', path):
            return True
    return False


def blocking_trainers(exclude=()):
    blocked = []
    for proc in psutil.process_iter(['name', 'cmdline', 'create_time']):
        try:
            if proc.pid in exclude or 'python' not in (proc.info['name'] or '').lower():
                continue
            if is_trainer_command(proc.info['cmdline']):
                blocked.append({'pid': proc.pid, 'creation_epoch': proc.info['create_time'],
                                'cmdline': proc.info['cmdline']})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return blocked


def artifacts_module():
    spec = importlib.util.spec_from_file_location('campaign_repair_artifacts', REPAIR / 'artifacts.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_bundle(folder):
    return artifacts_module().read_manifest(Path(folder), verify_replay=True)


def newest_bundle(folder):
    for path in sorted(Path(folder).glob('*/manifest.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.parent.name.startswith(('checkpoint_', 'final_')):
            try:
                valid_bundle(path.parent)
                return path.parent
            except (OSError, ValueError, KeyError):
                continue
    return None


def source_hashes():
    paths = {'runner': ROOT / 'runner.py', 'benchmark': ROOT / 'benchmark.py'}
    paths.update({'repair/' + p.name: p for p in REPAIR.glob('*.py')})
    paths.update({'dependency/' + name: path for name, path in artifacts_module().source_paths().items()})
    return {name: {'path': str(path), 'sha256': digest(path)} for name, path in paths.items()}


def check_sources(job):
    if source_hashes() != job['source_sha256']:
        raise RuntimeError('訓練或評估來源已改變；停止追加，保留完整存檔。')


def resources():
    return {'available_ram_gb': psutil.virtual_memory().available / 2**30,
            'free_disk_gb': shutil.disk_usage(ROOT).free / 2**30}


def pressure(value):
    return value['available_ram_gb'] < .5 or value['free_disk_gb'] < 10


def publish(job):
    job['heartbeat_epoch'] = time.time()
    folder = Path(job['job_dir'])
    atomic_json(folder / 'state.json', job)
    keys = ('job_id', 'job_dir', 'status', 'phase', 'new_decisions', 'decision_budget', 'deadline_taipei',
            'last_bundle', 'candidate_gate', 'supervisor', 'child', 'heartbeat_epoch', 'error')
    atomic_json(POINTER, {key: job.get(key) for key in keys})
    lines = ['# AI 飛行員本機訓練進度', '',
             f"狀態：{job['status']}；階段：{job['phase']}。",
             f"本輪已執行決策：{job['new_decisions']:,}/{job['decision_budget']:,}；期限：{job['deadline_taipei']}。", '',
             f"候選狀態：{job.get('candidate_gate', 'review_pending')}。",
             'completed 只表示作業完成。模型仍須審查；本程序不自動替換部署。',
             '評估屬本地開發比較，沒有據此估算奪冠機率。', '']
    if job.get('last_bundle'):
        lines.extend([f"最後完整存檔：[bundle](<{Path(job['last_bundle']).as_posix()}>)。", ''])
    for evaluation in job['evaluations']:
        summary = evaluation.get('summary', {})
        lines.extend([f"評估 {evaluation['name']}：{evaluation.get('status', 'unknown')}。",
                      '| 控制器 | 完整場數 | 擊落 | 平均攻擊秒數 |', '| --- | ---: | ---: | ---: |'])
        for label in ('guide', 'candidate'):
            value = summary.get(label, {})
            lines.append(f"| {label} | {value.get('completed_cases', '?')} | {value.get('kills', '?')} | {value.get('mean_attack_seconds', '?')} |")
        lines.extend([f"[配對評估報告](<{(Path(evaluation['folder']) / 'report.json').as_posix()}>)", ''])
    if job.get('error'):
        lines.extend(['原因：' + job['error'], ''])
    lines.extend(['停止入口：runner.py stop；請等待完整保存與收尾。',
                  f"[完整作業紀錄](<{(folder / 'state.json').as_posix()}>)"])
    temporary = ROOT / ('latest_result.tmp_' + uuid.uuid4().hex)
    temporary.write_text('\n'.join(lines), encoding='utf-8')
    os.replace(temporary, ROOT / 'latest_result.md')
    (folder / '結果.md').write_text('\n'.join(lines), encoding='utf-8')


def should_stop(job, record, progress, now, last_change, started, timeout):
    if (Path(job['job_dir']) / 'STOP').exists():
        return 'stopped_by_user'
    deadline = job['training_deadline_epoch'] if record['training'] else job['deadline_epoch']
    if time.time() >= deadline:
        return 'time_limit'
    if pressure(resources()):
        return 'resource_pressure'
    if record['training'] and now - last_change >= job['stall_seconds']:
        return 'stalled'
    if now - started >= timeout:
        return 'stage_timeout'
    return None


def add_observed_steps(job, record, steps):
    observed = min(record['requested_decisions'], max(0, int(steps) - record['start_decisions']))
    delta = max(0, observed - record['counted_decisions'])
    record['counted_decisions'] += delta
    job['new_decisions'] += delta


def cooperative_cleanup(child, owned, training_folder=None, grace=180):
    if child.poll() is not None:
        return
    if training_folder is not None:
        training_folder = Path(training_folder)
        training_folder.mkdir(parents=True, exist_ok=True)
        (training_folder / 'STOP').write_text('supervisor_cleanup', encoding='utf-8')
        until = time.monotonic() + grace
        while child.poll() is None and time.monotonic() < until:
            time.sleep(min(5, max(.01, until - time.monotonic())))
    if child.poll() is None:
        terminate_owned(owned)


def run_stage(job, name, command, folder, *, timeout, training=False, start=0, requested=0):
    folder = Path(folder)
    logs = Path(job['job_dir']) / 'logs' / name
    logs.mkdir(parents=True, exist_ok=False)
    record = {'name': name, 'command': list(map(str, command)), 'folder': str(folder),
              'training': training, 'start_decisions': start, 'requested_decisions': requested,
              'counted_decisions': 0, 'started_epoch': time.time(), 'status': 'running'}
    job['stages'].append(record)
    job['phase'] = name
    publish(job)
    child = owned = None
    try:
        with (logs / 'stdout.log').open('w', encoding='utf-8') as out, (logs / 'stderr.log').open('w', encoding='utf-8') as err:
            child = subprocess.Popen(list(map(str, command)), cwd=str(ROOT), stdout=out, stderr=err,
                creationflags=NO_WINDOW, env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                                            'PYTHONUNBUFFERED': '1', 'OMP_NUM_THREADS': '1'})
            owned = identity(child.pid)
            record['process'] = owned
            job['child'] = owned
            started = last_change = time.monotonic()
            marker = None
            stop_at = None
            while child.poll() is None:
                now = time.monotonic()
                progress = read_json(folder / 'progress.json', {}) if training else {}
                if training:
                    add_observed_steps(job, record, progress.get('decision_steps', start))
                    signature = (progress.get('decision_steps'), progress.get('critic_updates'))
                    if signature != marker:
                        marker, last_change = signature, now
                    job['training_progress'] = progress
                job['resources'] = resources()
                if stop_at is None:
                    reason = should_stop(job, record, progress, now, last_change, started, timeout)
                    if reason:
                        record['stop_reason'] = reason
                        stop_at = now
                        if training:
                            folder.mkdir(parents=True, exist_ok=True)
                            (folder / 'STOP').write_text(reason, encoding='utf-8')
                        else:
                            terminate_owned(owned)
                if stop_at is not None and now - stop_at >= job['save_grace_seconds'] and child.poll() is None:
                    terminate_owned(owned)
                    record['forced_stop'] = True
                publish(job)
                time.sleep(job['poll_seconds'])
            record['exit_code'] = child.wait(timeout=10)
    finally:
        if child is not None and child.poll() is None:
            cooperative_cleanup(child, owned, folder if training else None, job['save_grace_seconds'])
        if training:
            result = read_json(folder / 'result.json', {})
            progress = read_json(folder / 'progress.json', {})
            saved = newest_bundle(folder)
            saved_steps = valid_bundle(saved)['decision_steps'] if saved else start
            add_observed_steps(job, record, max(int(result.get('decision_steps', start)),
                int(progress.get('decision_steps', start)), saved_steps))
            record['learner_status'] = result.get('status', 'no_result')
            if saved:
                job['last_bundle'] = str(saved)
                record['saved_bundle'] = str(saved)
        record.update(status='finished', finished_epoch=time.time())
        if child is not None:
            record.setdefault('exit_code', child.poll())
        job['child'] = None
        atomic_json(logs / 'exit.json', record)
        publish(job)
    return record


def futile(evaluations):
    if len(evaluations) < 2:
        return False
    for evaluation in evaluations[-2:]:
        if evaluation.get('status') != 'completed':
            return False
        summary = evaluation.get('summary', {})
        candidate, guide = summary.get('candidate', {}), summary.get('guide', {})
        try:
            ca, ga = float(candidate['mean_attack_seconds']), float(guide['mean_attack_seconds'])
            if not all(map(math.isfinite, (ca, ga))) or not (
                    guide['kills'] > candidate['kills'] and ga > .25 and ca < ga * .5):
                return False
        except (KeyError, TypeError, ValueError):
            return False
    return True


def recoverable(job, record):
    error_file = Path(job['job_dir']) / 'logs' / record['name'] / 'stderr.log'
    message = error_file.read_text(encoding='utf-8', errors='replace').lower() if error_file.exists() else ''
    unsafe = any(value in message for value in ('out of memory', 'memoryerror', 'non-finite',
                 'nonfinite', 'invalid simulation', 'nan', 'inf detected'))
    return (not unsafe and job['retries'] < 1 and record.get('saved_bundle')
            and record['counted_decisions'] > 0 and record.get('stop_reason') not in
            ('stopped_by_user', 'time_limit', 'resource_pressure'))


def train_command(job, folder, requested, index):
    remaining = max(.01, (job['training_deadline_epoch'] - time.time()) / 60)
    return [PYTHON, '-B', '-X', 'utf8', REPAIR / 'train.py', '--resume', job['last_bundle'],
            '--run-dir', folder, '--decisions', requested, '--max-minutes', min(60, remaining),
            '--checkpoint-decisions', 10000, '--checkpoint-seconds', 300, '--device', 'cuda',
            '--seed', 2026110100 + index]


def run(job):
    with JobLock(ROOT / 'learner.lock'):
        if blocking_trainers(exclude=(os.getpid(),)):
            raise RuntimeError('偵測到其他訓練程序；不啟動第二個 learner。')
        job['supervisor'] = identity(os.getpid())
        job.update(status='running', ready_epoch=time.time())
        power_enabled = False
        try:
            if os.name == 'nt':
                power_enabled = bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
                if not power_enabled:
                    raise RuntimeError('無法設定暫時防睡眠要求。')
            job['keep_awake_enabled'] = power_enabled
            publish(job)
            check_sources(job)
            while job['new_decisions'] < job['decision_budget']:
                if (Path(job['job_dir']) / 'STOP').exists():
                    job['status'] = 'stopped_by_user'; break
                if time.time() >= job['training_deadline_epoch']:
                    job['status'] = 'time_limit'; break
                if pressure(resources()):
                    job['status'] = 'resource_pressure'; break
                check_sources(job)
                index = 1 + sum(s['training'] for s in job['stages'])
                name = f'train_{index:02d}'
                folder = Path(job['job_dir']) / name
                requested = min(job['segment_decisions'], job['decision_budget'] - job['new_decisions'])
                start = valid_bundle(job['last_bundle'])['decision_steps']
                record = run_stage(job, name, train_command(job, folder, requested, index), folder,
                                   timeout=min(3900, max(1, job['training_deadline_epoch'] - time.time())),
                                   training=True, start=start, requested=requested)
                if record.get('stop_reason') in ('stopped_by_user', 'time_limit', 'resource_pressure'):
                    job['status'] = record['stop_reason']; break
                if record.get('learner_status') in ('stopped_by_user', 'interrupted'):
                    job['status'] = 'stopped_by_user'; break
                good = (record['exit_code'] == 0 and record['learner_status'] in ('completed', 'time_limit')
                        and record.get('saved_bundle') and record['counted_decisions'] > 0)
                if not good:
                    check_sources(job)
                    if recoverable(job, record):
                        valid_bundle(record['saved_bundle'])
                        job['retries'] += 1
                        job.setdefault('warnings', []).append('從合法完整存檔恢復一次；已消耗決策仍計入預算。')
                        continue
                    raise RuntimeError('訓練失敗或沒有新增有效存檔；查看該階段 stderr 與退出紀錄。')
                check_sources(job)
                verified = Path(job['job_dir']) / f'verified_{index:02d}.json'
                checked = run_stage(job, f'check_{index:02d}',
                    [PYTHON, '-B', '-X', 'utf8', REPAIR / 'verify_saved.py', '--bundle', job['last_bundle'], '--out', verified],
                    Path(job['job_dir']) / f'check_{index:02d}', timeout=300)
                if checked['exit_code'] != 0 or not read_json(verified, {}).get('passed'):
                    raise RuntimeError('完整模型／replay 實際重載或有限數值檢查失敗。')
                job['checked_bundle'] = job['last_bundle']
                check_sources(job)
                evaluation_folder = Path(job['job_dir']) / f'dev_{index:02d}'
                evaluated = run_stage(job, f'dev_{index:02d}',
                    [PYTHON, '-B', '-X', 'utf8', ROOT / 'benchmark.py', '--repair-root', REPAIR,
                     '--bundle', job['last_bundle'], '--out', evaluation_folder, '--rounds', 1,
                     '--seed', 2026101100, '--mirror', 'both', '--max-minutes', 40],
                    evaluation_folder, timeout=2460)
                report = read_json(evaluation_folder / 'report.json', {})
                job['evaluations'].append({'name': f'dev_{index:02d}', 'folder': str(evaluation_folder),
                    'status': report.get('status', 'missing_report'), 'summary': report.get('summary', {}),
                    'gate': report.get('gate', 'incomplete'), 'bundle': job['last_bundle']})
                publish(job)
                if evaluated.get('stop_reason'):
                    job['status'] = evaluated['stop_reason']; break
                if evaluated['exit_code'] != 0 or report.get('status') != 'completed':
                    raise RuntimeError('配對評估未完整完成；不能把部分結果當作晉級證據。')
                if len(job['evaluations']) >= 2 and futile(job['evaluations']):
                    job['status'] = 'futility_stop'
                    job['error'] = '連續兩次配對評估擊落較少且攻擊時間低於純引導器一半；停止追加並檢討。'
                    break
            else:
                job['status'] = 'completed'
        except KeyboardInterrupt:
            job['status'] = 'stopped_by_user'
        except BaseException as error:
            job.update(status='failed', error=repr(error))
        finally:
            if owned_alive(job.get('child')):
                terminate_owned(job['child'])
            if os.name == 'nt' and power_enabled:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            job.update(child=None, candidate_gate='review_pending', phase='已保存並收尾', finished_epoch=time.time())
            publish(job)
    return job


def create_job(args):
    now = time.time()
    job_id = 'job_' + datetime.now(TAIPEI).strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4]
    folder = ROOT / 'jobs' / job_id
    valid_bundle(args.resume)
    frozen = source_hashes()
    folder.mkdir(parents=True, exist_ok=False)
    deadline = now + args.hours * 3600
    job = {'job_id': job_id, 'job_dir': str(folder), 'status': 'preparing', 'phase': '準備啟動',
           'started_epoch': now, 'deadline_epoch': deadline, 'training_deadline_epoch': deadline - 1800,
           'deadline_taipei': datetime.fromtimestamp(deadline, TAIPEI).isoformat(),
           'decision_budget': args.decisions, 'segment_decisions': args.segment, 'new_decisions': 0,
           'initial_bundle': str(args.resume), 'last_bundle': str(args.resume), 'source_sha256': frozen,
           'poll_seconds': 20, 'stall_seconds': 600, 'save_grace_seconds': 180,
           'stages': [], 'evaluations': [], 'retries': 0, 'supervisor': None, 'child': None,
           'candidate_gate': 'review_pending', 'official_validation': False}
    atomic_json(folder / 'config.json', job)
    publish(job)
    return job


def start(args):
    with JobLock(ROOT / 'launch.lock'):
        current = read_json(POINTER, {})
        if owned_alive(current.get('supervisor')) or owned_alive(current.get('child')):
            raise RuntimeError('既有作業仍在執行；使用 status 或 stop。')
        blocked = blocking_trainers(exclude=(os.getpid(),))
        if blocked:
            raise RuntimeError('已有 GPU 訓練程序，不重複啟動：' + ', '.join(str(p['pid']) for p in blocked))
        if not PYTHON.is_file():
            raise RuntimeError('找不到已驗證的 F16_ai Python runtime。')
        job = create_job(args)
        folder = Path(job['job_dir'])
        with (folder / 'supervisor_stdout.log').open('w', encoding='utf-8') as out, (folder / 'supervisor_stderr.log').open('w', encoding='utf-8') as err:
            child = subprocess.Popen([str(PYTHON), '-B', '-X', 'utf8', str(ROOT / 'runner.py'), 'run', '--job', str(folder / 'state.json')],
                cwd=str(ROOT), stdout=out, stderr=err, creationflags=NO_WINDOW,
                env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '1'})
        owned = identity(child.pid)
        until = time.monotonic() + 20
        while time.monotonic() < until:
            state = read_json(folder / 'state.json', {})
            if state.get('ready_epoch') and owned_alive(state.get('supervisor')):
                print('已啟動本機訓練作業：' + job['job_id'])
                print('完整進度：' + str(folder / 'state.json'))
                return state
            if child.poll() is not None:
                if state.get('status') != 'failed':
                    job.update(status='failed', phase='啟動失敗', error='監督程序未啟動；查看 supervisor_stderr.log。')
                    publish(job)
                raise RuntimeError('監督程序啟動失敗；查看作業紀錄。')
            time.sleep(.1)
        terminate_owned(owned)
        job.update(status='failed', phase='啟動失敗', error='監督程序未確認啟動；已收尾。')
        publish(job)
        raise RuntimeError(job['error'])


def status_or_stop(action):
    current = read_json(POINTER)
    if not current:
        print('尚未啟動本輪訓練。'); return
    job = read_json(Path(current['job_dir']) / 'state.json', current)
    live = owned_alive(job.get('supervisor')) or owned_alive(job.get('child'))
    if action == 'stop' and live:
        (Path(job['job_dir']) / 'STOP').write_text('stopped_by_user', encoding='utf-8')
        print('已要求保存並停止；等待「已保存並收尾」。')
    print(f"狀態：{job['status']}；階段：{job['phase']}；程序存在：{live}")
    print(f"本輪決策：{job['new_decisions']:,}/{job['decision_budget']:,}；候選：review_pending")
    print('結果：' + str(ROOT / 'latest_result.md'))


def main():
    parser = argparse.ArgumentParser(description='本機訓練與配對檢討；不自動部署')
    parser.add_argument('action', choices=['start', 'run', 'status', 'stop'])
    parser.add_argument('--resume', type=Path, default=DEFAULT_RESUME)
    parser.add_argument('--decisions', type=int, default=150000)
    parser.add_argument('--segment', type=int, default=50000)
    parser.add_argument('--hours', type=float, default=4)
    parser.add_argument('--job', type=Path)
    args = parser.parse_args()
    if not (0 < args.decisions <= 300000 and args.segment > 0 and .75 <= args.hours <= 6):
        parser.error('上限300,000新增決策、6小時；至少45分鐘；segment須為正數。')
    if args.action == 'run':
        if not args.job:
            parser.error('run 需要 --job <state.json>')
        job = read_json(args.job)
        if not job:
            parser.error('找不到合法的作業狀態檔。')
        result = run(job)
        if result['status'] == 'failed':
            raise SystemExit(1)
    elif args.action == 'start':
        start(args)
    else:
        status_or_stop(args.action)


if __name__ == '__main__':
    main()
