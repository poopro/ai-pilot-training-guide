"""Bounded local overnight runner. No API calls; one learner; no official deployment."""
import argparse
import ctypes
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

import psutil

ROOT = Path(__file__).resolve().parent
AP = ROOT.parent
sys.path.insert(0, str(AP))
from common import atomic, read, identity, alive, terminate_owned, JobLock, digest

POINTER = ROOT / 'night_latest.json'
TAIPEI = timezone(timedelta(hours=8))
TERMINAL = {'completed', 'failed', 'stopped_by_user', 'time_limit', 'safety_stop'}


def valid_bundle(folder):
    folder = Path(folder)
    manifest = read(folder / 'manifest.json')
    if not manifest or manifest.get('format') != 'opponent_lab_sac_v1':
        raise ValueError('不是新對手完整存檔')
    for name, suffix in [('model', 'zip'), ('replay', 'pkl')]:
        if digest(folder / (name + '.' + suffix)) != manifest[name + '_sha256']:
            raise ValueError('存檔校驗失敗：' + name)
    return manifest


def newest_bundle(folder):
    paths = list(Path(folder).glob('*/manifest.json'))
    for candidate in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
        if not candidate.parent.name.startswith(('checkpoint_', 'final_')):
            continue
        try:
            valid_bundle(candidate.parent)
            return candidate.parent
        except (ValueError, OSError, KeyError):
            continue
    return None


def source_hashes():
    # Trainer's snapshots and fingerprint also cover the frozen v3 environment.
    return {name: digest(ROOT / name) for name in ['train_opponents.py', 'duel_lab.py', 'training_control.py', 'overnight.py', 'check_bundle.py']}


def publish(job):
    job['heartbeat_epoch'] = time.time()
    atomic(Path(job['job_dir']) / 'state.json', job)
    lines = ['# 夜間 AI 空戰訓練結果', '',
             f"作業：{job['job_id']}；狀態：**{job['status']}**；階段：{job['phase']}。",
             f"新增步數：{job['new_steps']:,}/{job['step_budget']:,}；期限：{job['deadline_taipei']}。", '',
             '沿用舊第三版策略，紅方為 75% 規則式＋25% 凍結 SAC；只用本機算力。',
             '學習成效：以下為本地開發比較，尚未完成的場次不算成績。',
             '官方驗證：未執行；本地 1° 診斷門檻、位置估計及無碰撞模型不能取代官方 Host。',
             '原官方部署維持原選定純引導器，這輪不自動替換。', '']
    if job.get('smoke'):
        lines.insert(2, '僅流程驗證：短程測試模型，不是主訓練成果。')
    for warning in job.get('warnings', []):
        lines.extend(['注意：' + warning, ''])
    if job.get('error'):
        lines.extend(['原因：' + job['error'], ''])
    if job.get('last_bundle'):
        path = Path(job['last_bundle']).as_posix()
        lines.extend([f'最後完整存檔：[模型、replay、manifest](<{path}>)。', ''])
    if job.get('checked_bundle'):
        lines.extend(['最後一次模型／replay 載入與有限數值檢查：通過。', ''])
    for evaluation in job['evaluations']:
        data = read(Path(evaluation['folder']) / 'report.json', {})
        lines.extend([f"評估：{evaluation['name']}；狀態 {data.get('status', evaluation.get('status', 'unknown'))}。",
                      '| P2 | 藍方 | 場數 | 擊落 | 存活 | 平均攻擊秒數 | 平均獎勵 |',
                      '| --- | --- | --- | --- | --- | --- | --- |'])
        for group in data.get('groups', []):
            cases = [c for c in data['cases'] if c['p2'] == group['p2'] and c['blue'] == group['blue']]
            reward = sum(c['local_reward'] for c in cases) / len(cases)
            lines.append(f"| {group['p2']} | {group['blue']} | {group['episodes']} | {group['kills']} | {group['survivals']} | {group['mean_attack_seconds']:.3f} | {reward:.3f} |")
        reasons = {}
        for case in data.get('cases', []):
            if case['blue'] == 'rl':
                reason = case['final'].get('failure_reason', case['final']['outcome'])
                reasons[reason] = reasons.get(reason, 0) + 1
        view = Path(evaluation['folder']) / '結果.md'
        if not view.exists():
            view = Path(evaluation['folder']) / 'report.json'
        lines.extend(['', '新模型終止／失敗原因：' + json.dumps(reasons, ensure_ascii=False),
                      f"[評估報告](<{view.as_posix()}>)", ''])
    lines.extend(['完整命令、退出碼、錯誤及每階段紀錄：[' + job['job_id'] + '](<' + Path(job['job_dir']).as_posix() + '>)。', '',
                  '醒來先看評估中的 rl（新模型）相對 guide（纯引導器）是否改善擊落與存活；loss 和訓練 rolling 指標不能取代這份比較。'.replace('纯', '純'),
                  '需要提前停止，雙擊「停止夜間訓練並保存.cmd」；不要直接關 Python。'])
    result_path = Path(job['job_dir']) / '結果.md'
    temp = result_path.with_suffix('.tmp')
    temp.write_text('\n'.join(lines), encoding='utf-8')
    os.replace(temp, result_path)
    if job['publish']:
        atomic(POINTER, job)
        atomic(AP / '夜間最新狀態.json', job)
        review_temp = AP / '最新結果.tmp'
        shutil.copy2(result_path, review_temp)
        os.replace(review_temp, AP / '最新結果.md')


def resources():
    return {'available_ram_gb': psutil.virtual_memory().available / 2**30,
            'free_disk_gb': shutil.disk_usage(ROOT).free / 2**30}


def run_stage(job, name, command, folder, *, timeout, training=False, start=0):
    folder = Path(folder)
    # Trainer requires a fresh run directory; logs live beside it.
    log_dir = Path(job['job_dir']) / 'logs' / name
    log_dir.mkdir(parents=True)
    record = {'name': name, 'command': list(map(str, command)), 'folder': str(folder),
              'log_dir': str(log_dir), 'start_step': start, 'counted_steps': 0,
              'started_epoch': time.time(), 'status': 'running'}
    job['stages'].append(record)
    job['phase'] = name
    publish(job)
    with (log_dir / 'stdout.log').open('w', encoding='utf-8') as out, (log_dir / 'stderr.log').open('w', encoding='utf-8') as err:
        child = subprocess.Popen(list(map(str, command)), cwd=str(ROOT), stdout=out, stderr=err,
                                 env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1', 'OMP_NUM_THREADS': '1'},
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        owned = identity(child.pid)
        job['child'] = owned
        record['process'] = owned
        started = last_change = time.monotonic()
        stop_at = None
        reason = None
        signature = None
        disk_pressure = False
        try:
            while child.poll() is None:
                progress = read(folder / 'progress.json', {}) if training else {}
                now = time.monotonic()
                if training:
                    steps = max(0, int(progress.get('timesteps', start)) - start)
                    delta = max(0, steps - record['counted_steps'])
                    job['new_steps'] += delta
                    record['counted_steps'] += delta
                    marker = (progress.get('timesteps'), progress.get('updates'))
                    if marker != signature:
                        signature, last_change = marker, now
                    job['training_progress'] = progress
                    if progress.get('status') == 'saving':
                        # Saving has a bounded grace too; it cannot mask a permanent hang.
                        pass
                    available = resources()
                    job['resources'] = available
                    disk_pressure = available['free_disk_gb'] < 5 or available['available_ram_gb'] < .3
                user_stop = (Path(job['job_dir']) / 'STOP').exists()
                deadline = time.time() >= job['training_deadline_epoch'] if training else time.time() >= job['deadline_epoch']
                stalled = training and now - last_change > job.get('stall_seconds', 600)
                if stop_at is None and (user_stop or deadline or stalled or now - started >= timeout or disk_pressure):
                    reason = ('stopped_by_user' if user_stop else 'resource_pressure' if disk_pressure else
                              'time_limit' if deadline else 'stalled' if stalled else 'stage_timeout')
                    stop_at = now
                    record['stop_reason'] = reason
                    if training:
                        folder.mkdir(parents=True, exist_ok=True)
                        (folder / 'STOP').write_text(reason, encoding='utf-8')
                    else:
                        # Stop only this owned evaluation tree; complete cases remain saved.
                        terminate_owned(owned)
                if stop_at is not None and now - stop_at >= job.get('save_grace_seconds', 180):
                    terminate_owned(owned)
                    record['forced_stop'] = True
                publish(job)
                time.sleep(job.get('poll_seconds', 30))
            child.wait(timeout=10)
        except BaseException:
            # Also prevent orphaned owned subprocesses if the supervisor fails.
            if child.poll() is None:
                if training:
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / 'STOP').write_text('supervisor_error', encoding='utf-8')
                    try:
                        child.wait(timeout=job.get('save_grace_seconds', 180))
                    except subprocess.TimeoutExpired:
                        terminate_owned(owned)
                else:
                    terminate_owned(owned)
            raise
    if training:
        result = read(folder / 'result.json', {})
        progress = read(folder / 'progress.json', {})
        final_step = max(int(result.get('timesteps', start)), int(progress.get('timesteps', start)))
        delta = max(0, final_step - start - record['counted_steps'])
        job['new_steps'] += delta
        record['counted_steps'] += delta
        record['learner_status'] = result.get('status', 'no_result')
        saved = newest_bundle(folder)
        if saved:
            job['last_bundle'] = str(saved)
    record.update(exit_code=child.returncode, status='finished', reason=reason, finished_epoch=time.time())
    atomic(log_dir / 'exit.json', record)
    job['child'] = None
    publish(job)
    return record


def evaluate(job, name, *, final=False):
    before = {str(p) for p in (ROOT / 'evaluations').glob('eval_*')}
    command = [sys.executable, '-X', 'utf8', ROOT / 'training_control.py', 'evaluate', '--bundle', job['last_bundle'],
               '--rounds', str(1 if job.get('smoke') else 5 if final else 3), '--max-minutes', str(3 if job.get('smoke') else 25 if final else 12),
               '--seed', str(20272000 if final else 20271000)]
    if not job['publish']:
        command.append('--no-publish')
    record = run_stage(job, name, command, Path(job['job_dir']) / name,
                       timeout=200 if job.get('smoke') else 1560 if final else 780)
    created = [p for p in (ROOT / 'evaluations').glob('eval_*') if str(p) not in before]
    if created:
        folder = max(created, key=lambda p: p.stat().st_mtime)
        data = read(folder / 'report.json', {})
        if record.get('reason') and data.get('status') == 'running':
            data['status'] = 'interrupted'
            data['supervisor_stop_reason'] = record['reason']
            atomic(folder / 'report.json', data)
        job['evaluations'].append({'name': name, 'folder': str(folder), 'status': read(folder / 'report.json', {}).get('status')})
    if record['exit_code'] != 0:
        job.setdefault('warnings', []).append('評估未完整完成：' + name + '；只列完整場次')
    publish(job)


def run(job):
    with JobLock(ROOT / 'overnight.lock'):
        job['supervisor'] = identity(os.getpid())
        job['status'] = 'running'
        # Keep the system awake only while this process runs, allowing screen-off.
        power_ok = bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
        job['keep_awake_enabled'] = power_ok
        publish(job)
        try:
            if not power_ok:
                raise RuntimeError('無法建立暫時防睡眠要求，未啟動訓練')
            while job['new_steps'] < job['step_budget']:
                if (Path(job['job_dir']) / 'STOP').exists():
                    job['status'] = 'stopped_by_user'; break
                if time.time() >= job['training_deadline_epoch']:
                    job['status'] = 'time_limit'; break
                if source_hashes() != job['source_sha256']:
                    raise RuntimeError('來源在夜間執行時改變，不繼續訓練')
                available = resources()
                job['resources'] = available
                if available['free_disk_gb'] < 5 or available['available_ram_gb'] < .5:
                    raise RuntimeError('記憶體或磁碟不足，保留既有完整存檔')
                index = len([s for s in job['stages'] if s['name'].startswith('train_')]) + 1
                name = f'train_{index:02d}'
                requested = min(job['segment_steps'], job['step_budget'] - job['new_steps'])
                folder = Path(job['job_dir']) / name if not job['publish'] else ROOT / 'training' / f"run_{job['job_id']}_{index:02d}"
                start = valid_bundle(job['last_bundle'])['timesteps'] if job.get('last_bundle') else 0
                command = [sys.executable, '-X', 'utf8', ROOT / 'train_opponents.py', '--steps', requested,
                           '--p2', 'mixed', '--device', 'cuda', '--max-minutes', max(.01, min(60, (job['training_deadline_epoch'] - time.time()) / 60)),
                           '--run-dir', folder, '--checkpoint-steps', 20000, '--checkpoint-seconds', 300]
                if job.get('last_bundle'):
                    command += ['--resume', job['last_bundle']]
                if job.get('smoke'):
                    command += ['--learning-starts', 32, '--buffer-size', 512, '--batch-size', 16, '--no-publish']
                record = run_stage(job, name, command, folder, timeout=3900, training=True, start=start)
                result = read(folder / 'result.json', {})
                if record['reason'] == 'stopped_by_user' or result.get('status') in ('stopped_by_user', 'interrupted') and not record['reason']:
                    job['status'] = 'stopped_by_user'; break
                if record['reason'] in ('time_limit', 'resource_pressure'):
                    job['status'] = 'time_limit' if record['reason'] == 'time_limit' else 'failed'
                    job['error'] = record['reason']; break
                if record['exit_code'] != 0 or result.get('status') not in ('completed', 'time_limit'):
                    text = (Path(record['log_dir']) / 'stderr.log').read_text(encoding='utf-8', errors='replace')
                    unsafe = any(token in text.lower() for token in ['cuda out of memory', 'non-finite', 'nan', 'invalid simulation', 'memoryerror'])
                    if not unsafe and job['retries'] < 1 and job.get('last_bundle') and record['counted_steps'] > 0:
                        job['retries'] += 1
                        job.setdefault('warnings', []).append('原設定從完整 checkpoint 恢復一次：' + name)
                        continue
                    raise RuntimeError('訓練失敗或疑似卡住：' + name + '；查看 stderr 與退出紀錄')
                check = run_stage(job, 'check_' + name, [sys.executable, '-X', 'utf8', ROOT / 'check_bundle.py', job['last_bundle']],
                                  Path(job['job_dir']) / ('check_' + name), timeout=90)
                if check['exit_code']:
                    raise RuntimeError('模型／replay 載入或有限數值檢查失敗')
                job['checked_bundle'] = job['last_bundle']
                episodes = [json.loads(line) for line in (folder / 'episodes.jsonl').read_text(encoding='utf-8').splitlines()] if (folder / 'episodes.jsonl').exists() else []
                recent = episodes[-20:]
                if len(recent) >= 10 and sum(e['own_crash'] for e in recent) / len(recent) > .5:
                    job['status'] = 'safety_stop'; job['error'] = '最近完整回合墜機超過一半，保存並停止追加訓練'; break
                # Sparse assessments use the same development seeds for comparisons.
                if not job.get('smoke') and job['new_steps'] >= job['next_evaluation'] and job['new_steps'] < job['step_budget']:
                    evaluate(job, f"development_{job['new_steps']:010d}")
                    job['next_evaluation'] += 500000
            else:
                job['status'] = 'completed'
            if job.get('last_bundle') and job['status'] in ('completed', 'time_limit', 'safety_stop') and not (Path(job['job_dir']) / 'STOP').exists() and time.time() < job['deadline_epoch']:
                if job.get('checked_bundle') != job['last_bundle']:
                    checked = run_stage(job, 'check_final', [sys.executable, '-X', 'utf8', ROOT / 'check_bundle.py', job['last_bundle']],
                                        Path(job['job_dir']) / 'check_final', timeout=90)
                    if checked['exit_code']:
                        raise RuntimeError('最終存檔載入／有限數值檢查失敗，不評估此模型')
                    job['checked_bundle'] = job['last_bundle']
                training_result = job['status']
                job['status'] = 'evaluating'
                evaluate(job, 'final_evaluation', final=True)
                job['status'] = 'stopped_by_user' if (Path(job['job_dir']) / 'STOP').exists() else training_result
        except BaseException as error:
            job['status'] = 'failed'
            job['error'] = repr(error)
        finally:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            job['phase'] = '已保存並收尾'
            job['finished_epoch'] = time.time()
            job['child'] = None
            publish(job)


def create_job(args):
    now = time.time()
    job_id = 'night_' + datetime.now(TAIPEI).strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4]
    folder = ROOT / ('overnight_verification' if args.smoke else 'overnight') / job_id
    folder.mkdir(parents=True)
    deadline = now + args.hours * 3600
    job = {'job_id': job_id, 'job_dir': str(folder), 'status': 'preparing', 'phase': '準備夜間作業',
           'started_epoch': now, 'deadline_epoch': deadline, 'training_deadline_epoch': deadline - (60 if args.smoke else 1800),
           'deadline_taipei': datetime.fromtimestamp(deadline, TAIPEI).isoformat(), 'step_budget': args.steps,
           'segment_steps': 128 if args.smoke else 250000, 'new_steps': 0, 'next_evaluation': 500000,
           'retries': 0, 'stages': [], 'evaluations': [], 'child': None, 'supervisor': None,
           'publish': not args.smoke, 'smoke': args.smoke, 'source_sha256': source_hashes(),
           'official_validation': False, 'poll_seconds': .5 if args.smoke else 30}
    if not args.smoke:
        previous = read(ROOT / 'latest_training.json', {})
        if previous.get('status') in ('initializing', 'training', 'saving', 'saving_final'):
            pid = previous.get('pid')
            if pid and psutil.pid_exists(pid):
                raise RuntimeError('已有手動新對手訓練，不重複啟動')
        saved = previous.get('final_bundle')
        if saved:
            valid_bundle(saved)
            job['last_bundle'] = saved
        historical = AP / '最新結果.md'
        if historical.exists():
            shutil.copy2(historical, folder / '前一輪結果.md')
    snapshots = folder / 'source'
    snapshots.mkdir()
    for name in job['source_sha256']:
        shutil.copy2(ROOT / name, snapshots / name)
    atomic(folder / 'config.json', job)
    publish(job)
    return job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'run', 'status', 'stop'])
    parser.add_argument('--job', type=Path)
    parser.add_argument('--hours', type=float, default=8)
    parser.add_argument('--steps', type=int, default=2000000)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.hours <= 0 or args.steps <= 0 or args.hours > 8 or args.steps > 2000000:
        parser.error('上限八小時、二百萬新增步；須為正數')
    if args.action == 'run':
        run(read(args.job)); return
    current = read(POINTER)
    if args.action in ('status', 'stop'):
        if not current:
            print('尚未啟動夜間訓練'); return
        if args.action == 'stop' and current['status'] not in TERMINAL:
            (Path(current['job_dir']) / 'STOP').write_text('stopped_by_user', encoding='utf-8')
            print('已要求保存並停止，請等報告顯示已收尾。')
        print(f"狀態：{current['status']}；階段：{current['phase']}")
        print(f"新增訓練：{current['new_steps']:,}/{current['step_budget']:,} 步；期限：{current['deadline_taipei']}")
        print('最後完整存檔：' + str(current.get('last_bundle', '尚未產生')))
        print('監督程序仍存在：' + str(alive(current.get('supervisor'))))
        print('結果：' + str(AP / '最新結果.md'))
        return
    with JobLock(ROOT / 'overnight_launch.lock'):
        if current and (alive(current.get('supervisor')) or alive(current.get('child'))):
            print('既有夜間作業仍在運行，不重複啟動：' + current['job_id']); return
        job = create_job(args)
        folder = Path(job['job_dir'])
        with (folder / 'supervisor_stdout.log').open('w', encoding='utf-8') as out, (folder / 'supervisor_stderr.log').open('w', encoding='utf-8') as err:
            proc = subprocess.Popen([sys.executable, '-X', 'utf8', str(Path(__file__)), 'run', '--job', str(folder / 'state.json')],
                                    cwd=str(ROOT), stdout=out, stderr=err,
                                    env={**os.environ, 'PYTHONUTF8': '1'}, creationflags=subprocess.CREATE_NO_WINDOW)
        # Hold launch lock until the persistent process acknowledges ownership.
        # This closes the start-up race without overwriting a running child's state.
        acknowledgement_deadline = time.monotonic() + 10
        while time.monotonic() < acknowledgement_deadline:
            state = read(folder / 'state.json', {})
            if alive(state.get('supervisor')):
                break
            if proc.poll() is not None:
                job['status'] = 'failed'; job['error'] = '監督程序啟動失敗，查看 supervisor_stderr.log'
                publish(job)
                raise SystemExit(1)
            time.sleep(.1)
        else:
            terminate_owned(identity(proc.pid))
            job['status'] = 'failed'; job['error'] = '監督程序未確認啟動，不留下孤兒程序'
            publish(job)
            raise SystemExit(1)
        print('已啟動本機夜間監督程序 PID ' + str(proc.pid) + '；作業：' + str(folder))


if __name__ == '__main__':
    main()
