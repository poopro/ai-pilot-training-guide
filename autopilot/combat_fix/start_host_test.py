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
import uuid
import psutil
from artifacts import ROOT,BASE,atomic_json,file_hash,contract_sources

HOST=BASE/'D.比賽用主辦方連線程式_驗證是否符合能正確連線'

if __name__=='__main__':
    folder=ROOT/'official_validation'/('host_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4])
    folder.mkdir(parents=True)
    for name in ('Setting.txt','readme_part1.txt','readme_part2.txt'):shutil.copy2(HOST/name,folder/name)
    for name in ('player.py','controller.py','udp_config.json'):shutil.copy2(ROOT/name,folder/name)
    runtime=Path(os.environ['LOCALAPPDATA'])/'JSBsimHost_1_0_0_0'
    sources=contract_sources()
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
        'host_validation_completed':False,'competition_certification':False}
    atomic_json(folder/'session.json',record);atomic_json(ROOT/'active_host_test.json',record)
    print(json.dumps(record,ensure_ascii=False),flush=True)
