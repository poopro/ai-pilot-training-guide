"""Launch the unchanged official GUI from its own writable data directory."""
from datetime import datetime
import json
from pathlib import Path
import subprocess
import uuid
import psutil
from artifacts import BASE, ROOT, atomic_json, file_hash


def main():
    host = BASE / 'D.比賽用主辦方連線程式_驗證是否符合能正確連線'
    running = [p.pid for p in psutil.process_iter(['name'])
               if (p.info['name'] or '').lower() == 'jsb_host_gui_publish.exe']
    if running:
        raise RuntimeError(f'已有官方 Host 程序 {running}；請先在舊視窗 STOP 並關閉，避免通訊埠衝突。')
    folder = ROOT / 'official_validation' / ('host_launch_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4])
    folder.mkdir(parents=True)
    exe = host / 'JSB_host_GUI_publish.exe'
    with (folder / 'host_stdout.log').open('wb') as out, (folder / 'host_stderr.log').open('wb') as err:
        proc = subprocess.Popen([str(exe)], cwd=str(host), stdout=out, stderr=err)
    record = {'pid': proc.pid, 'create_time': psutil.Process(proc.pid).create_time(),
              'command': [str(exe)], 'cwd': str(host), 'host_sha256': file_hash(exe),
              'folder': str(folder), 'host_modified': False}
    atomic_json(folder / 'launch.json', record)
    atomic_json(ROOT / 'active_host_launch.json', record)
    print('已從官方資料夾啟動；請按 INIT，等待雙方 READY／GO，再按 START。')
    print('Host 診斷紀錄：' + str(folder))


if __name__ == '__main__':
    main()
