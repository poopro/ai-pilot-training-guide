"""Independent deadline guard for processes created by one recorded Host attempt."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import uuid

import psutil
import subprocess
from p2_terminal_evidence import probe as probe_p2_terminal

CAMPAIGN = Path(r"E:\ai_pilot\campaign_2026")
DIAGNOSTICS = CAMPAIGN / "diagnostics"
LEGACY = Path(r"E:\ai_pilot\autopilot\combat_fix")
ACTIVE = DIAGNOSTICS / "active_host_watchdog.json"
STOP = CAMPAIGN / "STOP"
HOST_NAME = "jsb_host_gui_publish.exe"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_json(path: Path, value):
    temporary = path.with_name(path.name + ".tmp_" + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def process_identity(process: psutil.Process):
    return {
        "pid": process.pid,
        "parent_pid": process.ppid(),
        "create_time": process.create_time(),
        "command": process.cmdline(),
        "exe": process.exe(),
    }


def live_identity(identity):
    try:
        process = psutil.Process(identity["pid"])
        if abs(process.create_time() - identity["create_time"]) >= 1:
            return None, "pid_reused"
        if process.cmdline() != identity["command"]:
            return None, "command_changed"
        if identity.get("exe") and process.exe().lower() != identity["exe"].lower():
            return None, "executable_changed"
        return process, "same_process"
    except psutil.NoSuchProcess:
        return None, "absent"
    except psutil.AccessDenied:
        return None, "unknown_access_denied"


def host_descendant_allowed(process: psutil.Process):
    try:
        return process.name().lower() == HOST_NAME and Path(process.exe()).name.lower() == HOST_NAME
    except psutil.AccessDenied:
        return False


def add_descendants(tracked, events):
    for key, entry in list(tracked.items()):
        process, state = live_identity(entry["identity"])
        entry["last_state"] = state
        if process is None:
            continue
        try:
            children = process.children(recursive=True)
        except psutil.AccessDenied:
            events.append({"type": "descendants_unknown_access_denied", "pid": process.pid})
            continue
        for child in children:
            if not host_descendant_allowed(child):
                continue
            child_key = f"{child.pid}:{child.create_time():.6f}"
            if child_key not in tracked:
                tracked[child_key] = {
                    "role": "owned_host_descendant",
                    "identity": process_identity(child),
                    "discovered_from": key,
                    "discovered_utc": datetime.now(timezone.utc).isoformat(),
                }
                events.append({"type": "tracked_descendant", "pid": child.pid, "parent_pid": child.ppid()})


def add_recorded_roots(token, tracked, events):
    launch_path = LEGACY / "active_host_launch.json"
    if launch_path.is_file():
        launch = read_json(launch_path)
        if launch.get("watchdog_token") == token:
            identity = {
                "pid": launch["pid"], "create_time": launch["create_time"],
                "command": launch["command"], "exe": launch["command"][0],
            }
            key = f"{identity['pid']}:{identity['create_time']:.6f}"
            if key not in tracked:
                tracked[key] = {"role": "host_root", "identity": identity}
                events.append({"type": "tracked_host_root", "pid": identity["pid"]})
    session_path = LEGACY / "active_host_test.json"
    if session_path.is_file():
        session = read_json(session_path)
        if session.get("watchdog_token") == token and session.get("player"):
            player = session["player"]
            identity = {
                "pid": player["pid"], "create_time": player["create_time"],
                "command": player["command"], "exe": player["command"][0],
            }
            key = f"{identity['pid']}:{identity['create_time']:.6f}"
            if key not in tracked:
                tracked[key] = {"role": "player_root", "identity": identity}
                events.append({"type": "tracked_player_root", "pid": identity["pid"]})
        return session if session.get('watchdog_token') == token else None
    return None


def depth(key, tracked):
    result, seen = 0, set()
    while key in tracked and key not in seen and tracked[key].get("discovered_from"):
        seen.add(key)
        result += 1
        key = tracked[key]["discovered_from"]
    return result


def cleanup(tracked, reason):
    results = []
    for key in sorted(tracked, key=lambda item: depth(item, tracked), reverse=True):
        entry = tracked[key]
        process, state = live_identity(entry["identity"])
        result = {"role": entry["role"], "identity": entry["identity"], "before": state}
        if process is None:
            result["action"] = "none"
            results.append(result)
            continue
        try:
            process.terminate()
            gone, alive = psutil.wait_procs([process], timeout=5)
            if alive:
                current, current_state = live_identity(entry["identity"])
                if current is None:
                    result.update(action="terminated", after=current_state)
                else:
                    current.kill()
                    gone, alive = psutil.wait_procs([current], timeout=5)
                    result.update(action="killed_after_terminate_timeout", after="absent" if gone else "still_alive")
            else:
                result.update(action="terminated", after="absent")
        except psutil.AccessDenied:
            result.update(action="none", after="unknown_access_denied")
        results.append(result)
    return {"reason": reason, "results": results}


def collect_automatically(session, deadline_epoch):
    """Observe a real bounded collector wrapper exit before killing the Host."""
    folder=Path(session['folder']).resolve()
    if not folder.is_relative_to((LEGACY/'official_validation').resolve()):
        raise RuntimeError('Automatic collection folder outside recorded Host evidence')
    command=[sys.executable,'-B','-X','utf8',str(DIAGNOSTICS/'collect_host_recorded.py'),'collect']
    receipt={'command':command,'token':session['watchdog_token'],
             'started_utc':datetime.now(timezone.utc).isoformat(),
             'trigger':'fresh owned P2 STOPPED + new terminal CSV + converted stable ACMI'}
    with (folder/'auto_collector_stdout.log').open('wb') as out,(folder/'auto_collector_stderr.log').open('wb') as err:
        process=subprocess.Popen(command,cwd=str(DIAGNOSTICS),stdout=out,stderr=err,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        identity=process_identity(psutil.Process(process.pid))
        receipt['identity']=identity
        atomic_json(folder/'auto_collector_process.json',receipt)
        limit=min(time.time()+90,deadline_epoch)
        timed_out=False
        while process.poll() is None:
            if STOP.exists() or time.time() >= limit:
                timed_out=True
                owned={'collector':{'role':'collector_root','identity':identity}}
                live,_=live_identity(identity)
                if live:
                    for child in live.children(recursive=True):
                        child_id=process_identity(child)
                        if child_id['command'][-1:]==[str(LEGACY/'collect_host_test.py')]:
                            owned[str(child.pid)]={'role':'collector_child','identity':child_id,'discovered_from':'collector'}
                receipt['timeout_cleanup']=cleanup(owned,'collector_timeout_or_STOP')
                break
            time.sleep(.1)
        try:code=process.wait(timeout=5)
        except subprocess.TimeoutExpired:code=None
    receipt.update(actual_exit_code=code,timed_out=timed_out,
                   exited_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(folder/'auto_collector_exit.json',receipt)
    return receipt


def monitor(token, deadline_epoch, poll_seconds):
    current = psutil.Process()
    record = {
        "token": token, "status": "armed", "pid": current.pid,
        "create_time": current.create_time(), "command": current.cmdline(),
        "armed_utc": datetime.now(timezone.utc).isoformat(),
        "deadline_epoch": deadline_epoch, "poll_seconds": poll_seconds,
    }
    atomic_json(ACTIVE, record)
    tracked, events, terminal_reason = {}, [], None
    last_published_count=-1
    last_published_epoch=0
    abort_path = DIAGNOSTICS / f"host_watchdog_abort_{token}.json"
    while terminal_reason is None:
        session = add_recorded_roots(token, tracked, events)
        add_descendants(tracked, events)
        if len(tracked)!=last_published_count or time.time()-last_published_epoch>=1:
            atomic_json(DIAGNOSTICS/f'host_watchdog_live_{token}.json',
                        {**record,'observed_utc':datetime.now(timezone.utc).isoformat(),
                         'tracked':tracked,'events':events})
            last_published_count=len(tracked)
            last_published_epoch=time.time()
        now = time.time()
        if STOP.exists():
            terminal_reason = "campaign_STOP"
        elif abort_path.exists():
            terminal_reason = "launcher_abort"
        elif now >= deadline_epoch:
            terminal_reason = "deadline"
        elif session and session.get("validation_exit_code") is not None:
            terminal_reason = "collection_terminal"
        elif (session and session.get('watchdog_token')==token and
              probe_p2_terminal(session,{'token':token,'tracked':tracked}) is not None):
            atomic_json(DIAGNOSTICS/f'host_watchdog_live_{token}.json',
                        {**record,'observed_utc':datetime.now(timezone.utc).isoformat(),
                         'tracked':tracked,'events':events})
            events.append({'type':'auto_collection_started','utc':datetime.now(timezone.utc).isoformat()})
            try:
                outcome=collect_automatically(session,deadline_epoch)
                events.append({'type':'auto_collection_exited','actual_exit_code':outcome['actual_exit_code'],
                               'timed_out':outcome['timed_out']})
                terminal_reason='auto_collection_terminal'
            except Exception as error:
                events.append({'type':'auto_collection_failed','error':repr(error)})
                terminal_reason='auto_collection_failed'
        else:
            time.sleep(poll_seconds)
    add_recorded_roots(token, tracked, events)
    add_descendants(tracked, events)
    cleanup_result = cleanup(tracked, terminal_reason)
    receipt = {
        **record, "status": "finished", "finished_utc": datetime.now(timezone.utc).isoformat(),
        "terminal_reason": terminal_reason, "tracked": tracked, "events": events,
        "cleanup": cleanup_result,
        "all_known_live_processes_stopped": all(
            item.get("after") in ("absent", None) and item.get("after") != "unknown_access_denied"
            for item in cleanup_result["results"]
        ),
    }
    receipt_path = DIAGNOSTICS / f"host_watchdog_{token}.json"
    atomic_json(receipt_path, receipt)
    atomic_json(ACTIVE, {**record, "status": "finished", "receipt": str(receipt_path),
                         "terminal_reason": terminal_reason})
    return 0 if receipt["all_known_live_processes_stopped"] else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--deadline-epoch", type=float, required=True)
    parser.add_argument("--poll-seconds", type=float, default=.25)
    parser.add_argument('--check-only',action='store_true')
    args = parser.parse_args()
    if args.deadline_epoch <= time.time():
        raise SystemExit("deadline must be in the future")
    if args.check_only:
        print(json.dumps({'check_only':True,'host_started':False,'collector_started':False,
                          'auto_terminal_collection':True,'collector_timeout_seconds':90}))
        raise SystemExit(0)
    raise SystemExit(monitor(args.token, args.deadline_epoch, args.poll_seconds))
