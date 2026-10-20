"""Start only a fresh repair-guide Player for a named official GUI test.

No Host UI automation here. Preserve identities, inputs and preexisting files.
The user/Computer Use performs INIT/START and the actual Host adjudicates.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import argparse
sys.path.insert(0,r"E:\ai_pilot\autopilot\combat_fix")
import uuid
import psutil
from artifacts import ROOT,BASE,atomic_json,file_hash,contract_sources,source_paths

HOST=BASE/'D.比賽用主辦方連線程式_驗證是否符合能正確連線'
WATCHDOG=Path(r"E:\ai_pilot\campaign_2026\diagnostics\active_host_watchdog.json")


def verified_launch(record):
    if record.get('evidence_capture_version')!=2 or record.get('host_started') is not True:
        raise RuntimeError('必須先使用有設定快照的新Host啟動入口；舊session不能補當新回合。')
    if record.get('setting_unchanged_immediately_after_launch') is not True or record.get('exe_unchanged_immediately_after_launch') is not True:
        raise RuntimeError('Host啟動時輸入有變動，不能驗證。')
    folder=Path(record['folder']).resolve();snapshot=Path(record['setting_snapshot']).resolve()
    if not folder.is_relative_to((ROOT/'official_validation').resolve()) or not snapshot.is_relative_to(folder):
        raise RuntimeError('設定快照不在該Host紀錄資料夾。')
    if file_hash(snapshot)!=record['host_setting_sha256'] or file_hash(HOST/'Setting.txt')!=record['host_setting_sha256']:
        raise RuntimeError('Host設定與啟動前快照不一致。')
    if file_hash(HOST/'JSB_host_GUI_publish.exe')!=record['host_exe_sha256']:
        raise RuntimeError('Host執行檔已改變。')
    return record

def verified_watchdog(token):
    if not token or not WATCHDOG.is_file():
        raise RuntimeError('缺少已啟動的獨立watchdog。')
    record=json.loads(WATCHDOG.read_text(encoding='utf-8-sig'))
    if record.get('token')!=token or record.get('status')!='armed':
        raise RuntimeError('watchdog token或狀態不吻合。')
    process=psutil.Process(record['pid'])
    if abs(process.create_time()-record['create_time'])>=1 or process.cmdline()!=record['command']:
        raise RuntimeError('watchdog程序身分不吻合。')
    return record

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    launch_path=ROOT/'active_host_launch.json'
    if not launch_path.is_file():raise RuntimeError('必須先使用有設定快照的新Host啟動入口；目前沒有啟動紀錄。')
    launch=verified_launch(json.loads(launch_path.read_text(encoding='utf-8-sig')))
    watchdog=verified_watchdog(launch.get('watchdog_token'))
    if args.check_only:
        print('新Host設定快照核對完成；未啟動Player。');sys.exit(0)
    live_hosts=[]
    for process in psutil.process_iter(['name']):
        if (process.info['name'] or '').lower()=='jsb_host_gui_publish.exe':
            if process.cmdline()!=launch['command'] or process.create_time()<launch['create_time']-1:
                raise RuntimeError('有不屬於新啟動身分的Host；不得混用。')
            live_hosts.append(process.pid)
        elif (process.info['name'] or '').lower() in ('python.exe','pythonw.exe'):
            if str(ROOT/'player.py') in process.cmdline():
                raise RuntimeError('原Player仍存在；請先依身分確認並保存結束。')
    if not live_hosts:raise RuntimeError('沒有可核對的新Host程序。')
    folder=ROOT/'official_validation'/('host_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4])
    folder.mkdir(parents=True)
    for name in ('Setting.txt','readme_part1.txt','readme_part2.txt'):shutil.copy2(HOST/name,folder/name)
    for name in ('player.py','controller.py','udp_config.json'):shutil.copy2(ROOT/name,folder/name)
    runtime=Path(os.environ['LOCALAPPDATA'])/'JSBsimHost_1_0_0_0'
    sources=contract_sources()
    snapshots={}
    for label,path in source_paths().items():
        target=folder/'source_snapshot'/label;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        if file_hash(target)!=sources[label]:raise RuntimeError('來源在封存中改變')
        snapshots[label]=str(target)
    before={str(p):{'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns}
        for directory in (HOST,runtime) if directory.exists() for p in directory.glob('*.csv')}
    cmd=[sys.executable,'-X','utf8','-u',str(ROOT/'player.py'),'--guide','--network',str(ROOT/'udp_config.json')]
    with (folder/'player_stdout.log').open('w',encoding='utf-8') as out,(folder/'player_stderr.log').open('w',encoding='utf-8') as err:
        proc=subprocess.Popen(cmd,cwd=str(BASE),stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    identity={'pid':proc.pid,'create_time':psutil.Process(proc.pid).create_time(),'command':cmd}
    host_procs=[{'pid':p.pid,'create_time':p.create_time(),'exe':p.exe(),'command':p.cmdline()}
        for p in psutil.process_iter() if p.name()=='JSB_host_GUI_publish.exe']
    record={'status':'waiting_init','controller':'repair_guide','model':None,'player':identity,
        'host_processes':host_procs,'host_dir':str(HOST),'runtime_dir':str(runtime),'folder':str(folder),
        'source_sha256':sources,'player_sha256':file_hash(ROOT/'player.py'),
        'host_exe_sha256':file_hash(HOST/'JSB_host_GUI_publish.exe'),'preexisting_csv':before,
        'network':json.loads((ROOT/'udp_config.json').read_text(encoding='utf-8')),
        'host_validation_completed':False,'competition_certification':False,
        'watchdog_token':launch['watchdog_token'],'watchdog':watchdog}
    verified_launch(launch)
    shutil.copy2(Path(launch['folder'])/'launch.json',folder/'host_launch_snapshot.json')
    shutil.copy2(launch['host_exe_snapshot'],folder/'Host_executable.bin')
    record.update(evidence_capture_version=2,host_exe_snapshot=str(folder/'Host_executable.bin'),host_setting_sha256=launch['host_setting_sha256'],
        host_launch_record=str(folder/'host_launch_snapshot.json'),host_log_dir=launch['folder'],
        source_snapshots=snapshots,setting_capture_phase='before_host_Popen',
        capture_bridge_sha256=file_hash(Path(__file__)),validation_exit_code=None)
    record.update(terminal_capture_version=launch.get('terminal_capture_version'),
                  p2_logs_before_launch=launch.get('p2_logs_before_launch',{}),
                  host_launch_identity={key:launch[key] for key in ('pid','create_time','command')})
    atomic_json(folder/'session.json',record);atomic_json(ROOT/'active_host_test.json',record)
    print(json.dumps(record,ensure_ascii=False),flush=True)
