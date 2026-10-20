"""Arm an independent guard before launching the recorded Host and Player."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

import psutil

DIAGNOSTICS = Path(__file__).resolve().parent
ACTIVE = DIAGNOSTICS / "active_host_watchdog.json"
PYTHON = Path(r"C:\Users\USER\anaconda3\envs\F16_ai\python.exe")
LAUNCH = DIAGNOSTICS / "launch_host_recorded.py"
START = DIAGNOSTICS / "start_host_player_recorded.py"
WATCHDOG = DIAGNOSTICS / "host_watchdog.py"


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def exact_live(record):
    try:
        process = psutil.Process(record["pid"])
        return abs(process.create_time() - record["create_time"]) < 1 and process.cmdline() == record["command"]
    except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
        return False


def main(deadline_seconds, check_only):
    if ACTIVE.is_file():
        previous = load(ACTIVE)
        if previous.get("status") == "armed" and exact_live(previous):
            raise RuntimeError(f"已有watchdog PID {previous['pid']}；不得重複啟動。")
    if check_only:
        print(json.dumps({"check_only": True, "watchdog": str(WATCHDOG),
                          "launcher": str(LAUNCH), "player_launcher": str(START),
                          "deadline_seconds": deadline_seconds}, ensure_ascii=False))
        return 0
    token = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    deadline_epoch = time.time() + deadline_seconds
    out_path = DIAGNOSTICS / f"host_watchdog_{token}.stdout.log"
    err_path = DIAGNOSTICS / f"host_watchdog_{token}.stderr.log"
    command = [str(PYTHON), "-B", "-X", "utf8", str(WATCHDOG),
               "--token", token, "--deadline-epoch", str(deadline_epoch)]
    with out_path.open("wb") as stdout, err_path.open("wb") as stderr:
        process = subprocess.Popen(command, cwd=str(DIAGNOSTICS), stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    limit = time.time() + 5
    while time.time() < limit:
        if ACTIVE.is_file():
            record = load(ACTIVE)
            if record.get("token") == token and record.get("status") == "armed" and exact_live(record):
                break
        time.sleep(.1)
    else:
        raise RuntimeError("watchdog未在5秒內留下可核對身分；不得啟動Host。")
    try:
        subprocess.run([str(PYTHON), "-B", "-X", "utf8", str(LAUNCH),
                        "--watchdog-token", token], check=True)
        subprocess.run([str(PYTHON), "-B", "-X", "utf8", str(START)], check=True)
    except BaseException as exc:
        abort_path = DIAGNOSTICS / f"host_watchdog_abort_{token}.json"
        abort_path.write_text(json.dumps({"token": token, "aborted_utc": datetime.now(timezone.utc).isoformat(),
                                          "reason": f"{type(exc).__name__}: {exc}"},
                                         ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        raise
    print(json.dumps({"watchdog_token": token, "watchdog_pid": process.pid,
                      "deadline_epoch": deadline_epoch, "active_record": str(ACTIVE),
                      "instruction": "用Computer Use按INIT；雙方READY/GO後mark-start再按START。"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--deadline-seconds", type=int, default=3600)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not 60 <= args.deadline_seconds <= 7200:
        parser.error("deadline-seconds must be 60..7200")
    raise SystemExit(main(args.deadline_seconds, args.check_only))
