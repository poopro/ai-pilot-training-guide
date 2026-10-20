"""Launch the unchanged official GUI from its own writable data directory."""
from datetime import datetime
import json
import argparse
import hashlib
import os
import sys
sys.path.insert(0, r"E:\ai_pilot\autopilot\combat_fix")
from pathlib import Path
import subprocess
import uuid
import psutil
from artifacts import BASE, ROOT, atomic_json, file_hash
from p2_terminal_evidence import VERSION as TERMINAL_CAPTURE_VERSION, before_logs


def setting_receipt(data):
    return {"host_setting_sha256":hashlib.sha256(data).hexdigest(),"host_setting_bytes":len(data)}

def main(check_only=False, watchdog_token=None):
    host = BASE / 'D.比賽用主辦方連線程式_驗證是否符合能正確連線'
    running = [p.pid for p in psutil.process_iter(['name'])
               if (p.info['name'] or '').lower() == 'jsb_host_gui_publish.exe']
    if running:
        raise RuntimeError(f'已有官方 Host 程序 {running}；請先在舊視窗 STOP 並關閉，避免通訊埠衝突。')
    exe = host / 'JSB_host_GUI_publish.exe'
    setting_data = (host / 'Setting.txt').read_bytes()
    capture = setting_receipt(setting_data)
    capture.update(evidence_capture_version=2, setting_capture_phase='before_host_Popen',
                   captured_utc=datetime.now().astimezone().isoformat(), host_exe_sha256=file_hash(exe))
    runtime = Path(os.environ['LOCALAPPDATA'])/'JSBsimHost_1_0_0_0'
    capture.update(terminal_capture_version=TERMINAL_CAPTURE_VERSION,
                   p2_logs_before_launch=before_logs([host/'player2_runtime.log',runtime/'player2_runtime.log']))
    if check_only:
        print(json.dumps(dict(capture, check_only=True, host_started=False,
                              scope='Current readable inputs only; no captured Host session'),ensure_ascii=False))
        return 0
    if not watchdog_token:
        raise RuntimeError('實際Host啟動前必須先啟動獨立watchdog；請使用 arm_host_watchdog.py。')
    folder = ROOT / 'official_validation' / ('host_launch_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4])
    folder.mkdir(parents=True)
    (folder / 'Setting.txt').write_bytes(setting_data)
    capture['setting_snapshot'] = str(folder / 'Setting.txt')
    exe_snapshot=folder/'Host_executable.bin'
    exe_snapshot.write_bytes(exe.read_bytes())
    if file_hash(exe_snapshot)!=capture['host_exe_sha256']:raise RuntimeError('Host執行檔在保存中改變')
    capture['host_exe_snapshot']=str(exe_snapshot)
    atomic_json(folder / 'inputs_before_launch.json', capture)
    with (folder / 'host_stdout.log').open('wb') as out, (folder / 'host_stderr.log').open('wb') as err:
        proc = subprocess.Popen([str(exe)], cwd=str(host), stdout=out, stderr=err)
    record = {'pid': proc.pid, 'create_time': psutil.Process(proc.pid).create_time(),
              'command': [str(exe)], 'cwd': str(host), 'host_sha256': file_hash(exe),
              'folder': str(folder), 'host_modified': False,
              'watchdog_token': watchdog_token}
    record.update(capture)
    record['setting_unchanged_immediately_after_launch'] = file_hash(host / 'Setting.txt') == capture['host_setting_sha256']
    record['exe_unchanged_immediately_after_launch'] = file_hash(exe) == capture['host_exe_sha256']
    record['host_started'] = True
    atomic_json(folder / 'launch.json', record)
    atomic_json(ROOT / 'active_host_launch.json', record)
    print('已從官方資料夾啟動；請按 INIT，等待雙方 READY／GO，再按 START。')
    print('Host 診斷紀錄：' + str(folder))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='Capture original Host settings before launch; does not control INIT/START')
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--watchdog-token')
    args=parser.parse_args()
    main(args.check_only,args.watchdog_token)
