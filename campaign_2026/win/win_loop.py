"""win_loop — the always-on orchestrator for the win campaign.

Contract with the user (2026-10-14):
  * No compute budget, no quota gate, no time limit. The loop runs until the
    queue drains. Budget/quota policy was removed on user instruction.
  * The only thing the loop still guards is RAM, because that is a physical
    property of this 16 GB machine, not a policy: 4 FDM workers were silently
    OOM-killed on this box. If RAM is low it waits; it never kills anything.
  * A single job running longer than BACKSTOP_HOURS becomes a paged notice, so
    a wedged FDM cannot run forever unnoticed.
  * Every step appends to win/TRACE.jsonl.

Usage:
    python win_loop.py status | run | loop | set
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notify

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "queue.json"
STATUS = ROOT / "status.json"
TRACE = ROOT / "TRACE.jsonl"
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
SAFE_RAM_GB = 3.5          # physical floor for starting FDM work on 16 GB
BACKSTOP_HOURS = 24.0      # age of one job before it becomes a p0 notice


def _ram_free_gb() -> float:
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    ms = MS()
    ms.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    return ms.ullAvailPhys / (1024 ** 3)


def now():
    return datetime.now(timezone.utc).isoformat()


def trace(kind: str, **kw):
    row = {"utc": now(), "kind": kind, **kw}
    with TRACE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load_queue():
    if not QUEUE.exists():
        return []
    d = json.loads(QUEUE.read_text(encoding="utf-8"))
    return d.get("steps", [])


def save_queue(steps):
    QUEUE.write_text(json.dumps({"steps": steps}, ensure_ascii=False, indent=2),
                     encoding="utf-8")


def write_status(**kw):
    s = {"updated": now(), **kw}
    STATUS.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return s


def wait_for_ram(limit_s: int = 3600):
    """Block until RAM is workable. Warns once. Never kills anything."""
    deadline = time.time() + limit_s
    warned = False
    while time.time() < deadline:
        free = _ram_free_gb()
        if free >= SAFE_RAM_GB:
            return True
        if not warned:
            notify.emit(
                "ram_low_wait", "waiting", "ram_low",
                f"RAM 只剩 {free:.2f} GB，低於啟動門檻 {SAFE_RAM_GB} GB。"
                f"等待中（最多 {limit_s // 60} 分鐘）。",
                cls="user_action",
                eli5=["關閉所有 Chrome 視窗與分頁（最耗記憶體）。",
                      "關閉遊戲啟動器、Discord、任何視訊編輯程式。",
                      "RAM 回到 4 GB 以上會自動繼續。"])
            warned = True
        trace("ram_wait", free_gb=round(free, 2))
        time.sleep(60)
    return False


def run_step(step: dict) -> dict:
    sid = step.get("id") or uuid.uuid4().hex[:8]
    cmd = step["cmd"]
    cwd = step.get("cwd") or str(ROOT)

    if not wait_for_ram():
        return {"id": sid, "status": "skipped_ram", "note": "RAM never recovered"}

    log_path = LOGS / f"{sid}.log"
    started = time.time()
    trace("step_start", id=sid, cmd=cmd, cwd=cwd)
    env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")

    with log_path.open("wb") as out:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=out,
                                stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        trace("step_popen", id=sid, pid=proc.pid)
        try:
            rc = proc.wait(timeout=None)      # deliberately no timeout
        except KeyboardInterrupt:
            proc.terminate()
            rc = -1
    wall = (time.time() - started) / 3600.0

    res = {"id": sid, "status": "completed" if rc == 0 else "failed",
           "exit_code": rc, "wall_hours": round(wall, 4), "log": str(log_path)}

    age_h = wall
    if age_h >= BACKSTOP_HOURS:
        res["backstop_tripped"] = True
        notify.emit(f"backstop_{sid}", "warning", "backstop",
                    f"工作 {sid} 跑了 {age_h:.1f} 小時仍未結束（>24h）。"
                    f"極可能是 FDM 卡死而非在算。", cls="backstop",
                    eli5=["開啟工作管理員，看那個 python.exe 的 CPU 使用率。",
                          "如果 CPU 是 0%，它就是卡死了，可以直接結束該程式。",
                          "如果 CPU 有在動，它還在算，等它跑完。"])
    trace("step_end", **res)
    return res


def drain() -> list:
    steps = load_queue()
    results = []
    while steps:
        step = steps[0]
        r = run_step(step)
        results.append(r)
        steps = steps[1:]
        save_queue(steps)
        write_status(running=False, last=r, done=[x["id"] for x in results])
        if r["status"] == "failed":
            notify.emit(f"step_failed_{r['id']}", "failed", "step_failed",
                        f"步驟 {r['id']} exit={r['exit_code']}，log: {r['log']}",
                        cls="blocker", report=str(r["log"]),
                        eli5=["開啟上面的 log 檔，看最後 30 行。",
                              "如果是 OOM，把 Chrome 關掉後重新執行這一步。"])
            break                      # stop this pass, keep the rest queued
    return results


def status():
    write_status(running=False, queue=len(load_queue()))
    print(json.dumps({"queue_remaining": len(load_queue()),
                      "ram_free_gb": round(_ram_free_gb(), 2),
                      "needs_you": notify.open_items(),
                      "status_file": str(STATUS)}, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "run", "loop", "set"])
    ap.add_argument("--gap", type=int, default=600)
    ap.add_argument("--key")
    ap.add_argument("--value")
    a = ap.parse_args()

    if a.cmd == "status":
        status()
    elif a.cmd == "run":
        write_status(running=True, started=now())
        drain()
    elif a.cmd == "loop":
        while True:
            try:
                if load_queue():
                    drain()
            except Exception as e:                      # noqa: BLE001
                trace("loop_exception", error=f"{type(e).__name__}: {e}")
                notify.emit(f"loop_exception_{int(time.time())}", "warning", "loop_exception",
                            f"編排器遇到例外但仍在運行：{type(e).__name__}: {e}",
                            cls="info")
            time.sleep(a.gap)
    elif a.cmd == "set":
        d = json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else {"steps": []}
        d.setdefault("config", {})[a.key] = json.loads(a.value)
        QUEUE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
