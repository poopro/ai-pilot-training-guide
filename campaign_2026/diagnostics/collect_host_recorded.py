"""Observe the real legacy collector exit and audit a newly captured Host session."""
from pathlib import Path
from datetime import datetime, timezone
import argparse,json,sys,subprocess,time,psutil
sys.path.insert(0,r"E:\ai_pilot\autopilot\combat_fix")
from artifacts import ROOT,atomic_json,file_hash,source_paths
CAMPAIGN=Path(r"E:\ai_pilot\campaign_2026")
sys.path.insert(0,str(CAMPAIGN/'diagnostics'))
from audit_host_evidence import audit
from p2_terminal_evidence import capture as capture_p2_terminal


def checked_session():
    s=json.loads((ROOT/'active_host_test.json').read_text(encoding='utf-8-sig'))
    if s.get('evidence_capture_version')!=2 or s.get('validation_exit_code') is not None:
        raise RuntimeError('僅收集新的完整capture session，不改歷史或已收集的回合。')
    folder=Path(s['folder']).resolve()
    if not folder.is_relative_to((ROOT/'official_validation').resolve()):raise RuntimeError('session資料夾不在授權範圍')
    saved=json.loads((folder/'session.json').read_text(encoding='utf-8-sig'))
    if saved!=s:raise RuntimeError('session與active pointer不一致')
    for label,path in source_paths().items():
        snapshot=Path(s['source_snapshots'][label]).resolve()
        if not snapshot.is_relative_to(folder) or file_hash(snapshot)!=s['source_sha256'][label] or file_hash(path)!=s['source_sha256'][label]:
            raise RuntimeError('來源或來源快照已改變')
    if file_hash(ROOT/'player.py')!=s['player_sha256']:raise RuntimeError('Player來源已改變')
    if file_hash(folder/'Setting.txt')!=s['host_setting_sha256'] or file_hash(Path(s['host_dir'])/'Setting.txt')!=s['host_setting_sha256']:
        raise RuntimeError('設定與事前快照不一致')
    if file_hash(Path(s['host_dir'])/'JSB_host_GUI_publish.exe')!=s['host_exe_sha256']:raise RuntimeError('Host來源已改變')
    return s,folder


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['check','mark-start','collect']);args=parser.parse_args()
    s,folder=checked_session()
    if args.action=='check':print('來源、設定及新session核對通過；尚未收集。');return 0
    if args.action=='mark-start':
        if 'start_clicked_epoch' in s:raise RuntimeError('起始界線已記錄，不能重置')
        p=psutil.Process(s['player']['pid'])
        if abs(p.create_time()-s['player']['create_time'])>=1 or p.cmdline()!=s['player']['command']:
            raise RuntimeError('Player程序身分不吻合')
        s.update(start_clicked_epoch=time.time(),start_marker_scope='Operator boundary immediately BEFORE pressing START; not direct UI observation',status='start_boundary_marked')
        atomic_json(folder/'session.json',s);atomic_json(ROOT/'active_host_test.json',s)
        print('已記錄起始界線；現在於Host視窗按START。');return 0
    if 'start_clicked_epoch' not in s:raise RuntimeError('缺少START前的界線紀錄，不能收集')
    live=CAMPAIGN/'diagnostics'/f"host_watchdog_live_{s['watchdog_token']}.json"
    if live.is_file() and s.get('terminal_capture_version')==1:
        receipt_path=capture_p2_terminal(s,folder,json.loads(live.read_text(encoding='utf-8-sig')))
        if receipt_path:
            s['p2_terminal_receipt']=receipt_path
            atomic_json(folder/'session.json',s);atomic_json(ROOT/'active_host_test.json',s)
    command=[sys.executable,'-B','-X','utf8',str(ROOT/'collect_host_test.py')]
    (folder/'collector_input_session.json').write_bytes((folder/'session.json').read_bytes())
    (folder/'collector_snapshot.py').write_bytes((ROOT/'collect_host_test.py').read_bytes())
    receipt={'command':command,'folder':str(folder),'input_session_sha256':file_hash(folder/'collector_input_session.json'),
        'collector_sha256':file_hash(folder/'collector_snapshot.py'),'started_utc':datetime.now(timezone.utc).isoformat()}
    if file_hash(ROOT/'collect_host_test.py')!=receipt['collector_sha256']:raise RuntimeError('收集來源在保存中改變')
    with (folder/'collector_stdout.log').open('wb') as out,(folder/'collector_stderr.log').open('wb') as err:
        proc=subprocess.Popen(command,cwd=str(ROOT),stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        receipt['pid']=proc.pid
        try:receipt['create_time']=psutil.Process(proc.pid).create_time()
        except psutil.NoSuchProcess:receipt['create_time']=None
        atomic_json(folder/'collector_process.json',receipt)
        try:code=proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process=psutil.Process(proc.pid)
            if process.cmdline()==command and abs(process.create_time()-receipt['create_time'])<1:
                process.terminate()
            try:code=proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process=psutil.Process(proc.pid)
                if process.cmdline()==command and abs(process.create_time()-receipt['create_time'])<1:process.kill()
                code=proc.wait(timeout=5)
    # Never infer an exit from CSV completion or a disappeared PID.
    receipt.update(actual_exit_code=code,exited_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(folder/'collector_exit.json',receipt)
    s,folder=checked_session()
    if file_hash(ROOT/'collect_host_test.py')!=receipt['collector_sha256']:raise RuntimeError('收集程式在執行中改變')
    s.update(validation_exit_code=code,validation_exit_receipt=str(folder/'collector_exit.json'),validation_capture_sources_unchanged=True)
    atomic_json(folder/'session.json',s);atomic_json(ROOT/'active_host_test.json',s)
    if code!=0:print('收集程式失敗；保存原退出碼，不能通過驗證。');return code
    result=audit(folder/'host_result.json');atomic_json(folder/'HOST_AUDIT.json',result)
    if not result['eligible_for_six_round_fixed_source_gate']:
        print('收集已退出，但Host證據未通過完整稽核。');return 2
    print('新Host回合證據核對通過；不是正式參賽認證。');return 0


if __name__=='__main__':raise SystemExit(main())
