#!/usr/bin/env python3
"""Reliable local AI Pilot training dashboard."""
from __future__ import annotations
import http.server
import json
import os
import re
import socket
import socketserver
import subprocess
import sys
import time
import threading
import uuid
from datetime import datetime
from training_store import candidates, read_json, write_json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(os.environ.get("AI_PILOT_ROOT", r"E:\ai_pilot"))
CONFIGURED_WORK = Path(os.environ.get("AI_PILOT_WORK", str(ROOT / "work")))
FALLBACK_WORK = Path(os.environ.get("AI_PILOT_FALLBACK_WORK", str(Path.home() / "ai-pilot-runtime")))


def _path_writable(path):
    probe = path / ".ai_pilot_startup_probe"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="ascii")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        return False


WORK = CONFIGURED_WORK if _path_writable(CONFIGURED_WORK) else FALLBACK_WORK
SOURCE_WORK = CONFIGURED_WORK
TRAIN = SOURCE_WORK / os.environ.get("AI_PILOT_TRAIN_SCRIPT", "train_local.py")
MODEL = WORK / "model"
LOGS = WORK / "logs"
LOG = WORK / "train.log"
PID = WORK / "train.pid"
LIVE_METRICS = WORK / "live_metrics.json"
LAG_ROOT = Path(os.environ.get("AI_PILOT_LAG_ROOT", str(ROOT / "lag")))
LAG_SMOKE = LAG_ROOT / "lag_smoke.py"
LAG_LOG = WORK / "logs" / "lag_smoke.log"
PORT = int(os.environ.get("AI_PILOT_PORT", "8765"))
TB_PORT = int(os.environ.get("AI_PILOT_TB_PORT", "6006"))
STEPS = int(os.environ.get("AI_PILOT_STEPS", "2000000"))
ENVS = int(os.environ.get("AI_PILOT_ENVS", "2"))
CHECKPOINT_STEPS = int(os.environ.get("AI_PILOT_CHECKPOINT_STEPS", "100000"))
_cache = (0.0, {})
_log_handle = None
_last_lag_smoke_output = ""
_action_lock = threading.Lock()
_lag_cache = (0.0, {})


def active_run():
    value = read_json(WORK / "active_run.json").get("run")
    return Path(value) if value else WORK


def choose_python():
    choices = [
        r"C:\Users\USER\AppData\Local\ai-pilot\venv\Scripts\python.exe",
        os.environ.get("AI_PILOT_PYTHON"),
        r"C:\Users\USER\anaconda3\envs\F16_ai\python.exe",
        sys.executable,
    ]
    for value in choices:
        if value and Path(value).is_file():
            return Path(value)
    return None


def probe(python):
    if python is None:
        return {"ok": False, "message": "找不到 Python"}
    try:
        result = subprocess.run(
            [str(python), "-c", "import torch,gymnasium,jsbsim,stable_baselines3;print(torch.__version__);print(torch.cuda.is_available());print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        lines = result.stdout.strip().splitlines()
        return {"ok": result.returncode == 0 and len(lines) >= 3, "python": str(python), "torch": lines[0] if lines else "", "cuda": lines[1] if len(lines) > 1 else "", "gpu": lines[2] if len(lines) > 2 else "", "message": result.stderr[-500:]}
    except Exception as exc:
        return {"ok": False, "python": str(python), "message": str(exc)}


def work_writable():
    probe_path = WORK / ".ai_pilot_write_probe"
    try:
        WORK.mkdir(exist_ok=True)
        probe_path.write_text("ok", encoding="ascii")
        probe_path.unlink(missing_ok=True)
        return True, ""
    except OSError as exc:
        try:
            probe_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False, f"{type(exc).__name__}: {exc}"


def preflight(force=False):
    global _cache
    if not force and _cache[1] and (_cache[1].get("ready") or time.monotonic() - _cache[0] < 15):
        return _cache[1]
    py = probe(choose_python())
    writable, write_error = work_writable()
    result = {"root": str(ROOT), "configured_work": str(SOURCE_WORK), "work": str(WORK), "using_fallback": WORK != SOURCE_WORK, "python": py, "work_exists": WORK.is_dir(), "work_writable": writable, "write_error": write_error, "train_exists": TRAIN.is_file(), "model_exists": MODEL.is_dir(), "config": {"steps": STEPS, "envs": ENVS, "checkpoint_steps": CHECKPOINT_STEPS}}
    result["ready"] = bool(result["work_exists"] and result["work_writable"] and result["train_exists"] and py.get("ok"))
    if not writable:
        result["message"] = "訓練輸出資料夾無法寫入，請修正資料夾權限或改用可寫入的 AI_PILOT_WORK"
    elif not py.get("ok"):
        result["message"] = "Python 套件檢查失敗：" + py.get("message", "未知錯誤")
    _cache = (time.monotonic(), result)
    return result


def lag_preflight():
    global _lag_cache
    if _lag_cache[1]:
        return _lag_cache[1]
    py = choose_python()
    result = {
        "root": str(LAG_ROOT),
        "python": str(py) if py else "",
        "lag_exists": LAG_ROOT.is_dir(),
        "jsbsim_data_exists": (LAG_ROOT / "envs" / "JSBSim" / "data" / "aircraft").is_dir(),
        "smoke_exists": LAG_SMOKE.is_file(),
    }
    if py is None:
        result["ready"] = False
        result["message"] = "找不到 Python"
        return result
    try:
        probe = subprocess.run(
            [str(py), "-c", "import yaml,pymap3d,jsbsim,gymnasium;print(jsbsim.__version__)"],
            cwd=str(LAG_ROOT) if LAG_ROOT.is_dir() else None,
            capture_output=True, text=True, timeout=20, check=False,
        )
        result["dependency_probe"] = probe.stdout.strip()
        result["dependency_error"] = probe.stderr[-500:]
        result["ready"] = bool(
            result["lag_exists"] and result["jsbsim_data_exists"] and result["smoke_exists"]
            and probe.returncode == 0
        )
    except Exception as exc:
        result["ready"] = False
        result["message"] = str(exc)
    _lag_cache = (time.monotonic(), result)
    return result


def lag_smoke():
    global _last_lag_smoke_output
    info = lag_preflight()
    if not info.get("ready"):
        return {"ok": False, "message": "LAG 預檢查未通過", "preflight": info}
    py = Path(info["python"])
    try:
        LAG_LOG.parent.mkdir(exist_ok=True)
    except OSError:
        pass
    try:
        result = subprocess.run(
            [str(py), "-u", str(LAG_SMOKE)],
            cwd=str(LAG_ROOT), capture_output=True, text=True, timeout=120, check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        _last_lag_smoke_output = output[-4000:]
        try:
            LAG_LOG.write_text(output, encoding="utf-8")
        except OSError:
            # The simulator result remains useful even if a synced folder is
            # temporarily read-only; the response still carries the output.
            pass
        try:
            payload = json.loads((result.stdout or "").strip().splitlines()[-1])
        except (ValueError, IndexError):
            payload = {"ok": False, "error": output[-2000:]}
        payload.update({"returncode": result.returncode, "log": output[-4000:], "preflight": info})
        return payload
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        _last_lag_smoke_output = output[-4000:]
        try:
            LAG_LOG.write_text(output + "\nLAG smoke test timeout\n", encoding="utf-8")
        except OSError:
            pass
        return {"ok": False, "message": "LAG smoke test 超時", "log": output[-4000:], "preflight": info}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "preflight": info}


def process_ok(pid):
    try:
        import psutil
        process = psutil.Process(pid)
        return process.is_running() and TRAIN.name.lower() in " ".join(process.cmdline()).lower()
    except Exception:
        return False


def running_pid():
    try:
        value = int(PID.read_text(encoding="ascii").strip())
        if process_ok(value):
            return value
    except (OSError, ValueError):
        pass
    PID.unlink(missing_ok=True)
    return None


def checkpoints():
    return candidates([WORK, SOURCE_WORK])


def log_tail():
    try:
        with (active_run() / "train.log").open("rb") as stream:
            stream.seek(max(0, stream.seek(0, 2) - 24000))
            return "\n".join(stream.read().decode("utf-8", errors="replace").splitlines()[-60:])
    except OSError:
        return "(尚未建立 train.log)"


def tb_running():
    sock = socket.socket(); sock.settimeout(.25)
    try:
        sock.connect(("127.0.0.1", TB_PORT)); return True
    except OSError:
        return False
    finally:
        sock.close()


def scalars():
    try:
        from tensorboard.backend.event_processing import event_accumulator
        events = sorted((active_run() / "logs").rglob("events.out.tfevents*"), key=lambda p: p.stat().st_mtime)
        if not events:
            return {}
        acc = event_accumulator.EventAccumulator(str(events[-1].parent)); acc.Reload()
        data = {}
        for tag in acc.Tags().get("scalars", []):
            values = acc.Scalars(tag)
            if values:
                data[tag] = {"last": values[-1].value, "count": len(values)}
        return data
    except Exception:
        return {}


def live_metrics():
    try:
        payload = json.loads((active_run() / "live_metrics.json").read_text(encoding="utf-8"))
        payload["age_seconds"] = max(0.0, time.time() - float(payload.get("updated_epoch", time.time())))
        return payload
    except (OSError, ValueError, TypeError):
        return {}


def gpu_stats():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        line = result.stdout.strip().splitlines()[0]
        values = [item.strip() for item in line.split(",")]
        if len(values) != 4:
            return {}
        return {"utilization_percent": float(values[0]), "memory_used_mb": float(values[1],),
                "memory_total_mb": float(values[2]), "temperature_c": float(values[3])}
    except (FileNotFoundError, IndexError, ValueError, subprocess.SubprocessError):
        return {}


def status():
    global _last_lag_smoke_output
    pid = running_pid(); info = preflight()
    lag = lag_preflight()
    lag_log = _last_lag_smoke_output
    try:
        lag_log = LAG_LOG.read_text(encoding="utf-8", errors="replace")[-4000:]
    except OSError:
        pass
    metrics = live_metrics()
    pid = running_pid()
    if pid is None and metrics.get("state") in ("running", "saving", "starting"):
        metrics["state"] = "interrupted"
    error = read_json(active_run() / "error.json")
    if error:
        metrics.update(state="error", error=error.get("error"))
    saved = checkpoints()
    return {"running": pid is not None, "stopping": pid is not None and (active_run()/"stop.request").exists(), "pid": pid, "preflight": info, "ready": info.get("ready", False), "lag": lag, "lag_log": lag_log, "metrics": metrics, "gpu": gpu_stats(), "checkpoints": saved, "resume_candidate": saved[-1] if saved else None, "run_dir": str(active_run()), "tensorboard": tb_running(), "scalars": scalars(), "log": log_tail()}


def start(new=False):
    with _action_lock:
        return _start(new)


def _start(new=False):
    global _log_handle
    info = preflight(True)
    if not info["ready"]:
        return {"ok": False, "message": "預檢查未通過", "preflight": info}
    if running_pid() is not None:
        return {"ok": False, "message": "訓練已在執行中"}
    saved = checkpoints()
    source = saved[-1] if saved and not new else None
    if source and source["steps"] >= STEPS:
        return {"ok": False, "message": f"最新模型已達 {source['steps']:,} 步，已完成目前 {STEPS:,} 步目標。若要獨立實驗，請按『另開全新訓練』。"}
    run = WORK / "runs" / (datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8])
    command = [info["python"]["python"], "-u", str(TRAIN), "--envs", str(ENVS), "--steps", str(STEPS), "--checkpoint-steps", str(CHECKPOINT_STEPS)]
    command += ["--run-dir", str(run)]
    command += ["--resume", source["path"]] if source else ["--new"]
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", AI_PILOT_WORK=str(WORK), AI_PILOT_OUTPUT_ROOT=str(WORK))
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
    proc = None
    try:
        run.mkdir(parents=True, exist_ok=False)
        if _log_handle:
            _log_handle.close()
        _log_handle = (run / "train.log").open("ab")
        write_json(run / "live_metrics.json", {"state":"starting", "step":source["steps"] if source else 0, "total_steps":STEPS, "updated_epoch":time.time()})
        proc = subprocess.Popen(command, cwd=str(WORK), stdout=_log_handle, stderr=subprocess.STDOUT, env=env, creationflags=flags)
        write_json(WORK / "active_run.json", {"run":str(run)})
        PID.write_text(str(proc.pid), encoding="ascii")
        message = f"接續 {source['steps']:,} 步 → {STEPS:,} 步" if source else "已建立獨立的新訓練"
        if source and source["legacy"]:
            message += "；舊檔沒有經驗資料，先重新收集 20,000 步，再恢復模型更新"
        return {"ok": True, "message": message, "run_dir":str(run)}
    except Exception as exc:
        if proc is not None:
            try:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10, check=False)
            except Exception:
                pass
        PID.unlink(missing_ok=True)
        if _log_handle: _log_handle.close()
        _log_handle = None
        return {"ok": False, "message": f"無法啟動訓練：{type(exc).__name__}: {exc}", "path": str(WORK)}


def stop():
    with _action_lock:
        pid = running_pid()
        if pid is None:
            return {"ok": False, "message": "目前沒有執行中的訓練"}
        run = active_run()
        if run == WORK:
            return {"ok": False, "message": "這是舊版訓練程序，沒有安全存檔停止功能；請讓它跑完。"}
        (run / "stop.request").touch()
        return {"ok": True, "message": "已請求停止，正在保存模型與經驗資料；請等待『已保存並停止』。"}

def tensorboard():
    if tb_running(): return {"ok": True, "message": f"已在 http://localhost:{TB_PORT}"}
    py = choose_python()
    if py is None: return {"ok": False, "message": "找不到 Python"}
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        subprocess.Popen([str(py), "-m", "tensorboard.main", "--logdir", str(WORK), "--port", str(TB_PORT)], cwd=str(WORK), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        return {"ok": True, "message": f"TensorBoard 啟動中：http://localhost:{TB_PORT}"}
    except Exception as exc: return {"ok": False, "message": str(exc)}


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def reply(self, value, code=200):
        data = json.dumps(value, ensure_ascii=False).encode(); self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/":
            page = (Path(__file__).with_name("dashboard.html")).read_bytes(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(page))); self.end_headers(); self.wfile.write(page)
        elif route == "/api/status": self.reply(status())
        elif route == "/api/preflight": self.reply(preflight(True))
        else: self.send_error(404)
    def do_POST(self):
        actions = {"start": start, "new": lambda: start(new=True), "stop": stop, "tensorboard": tensorboard, "lag-smoke": lag_smoke}; action = actions.get(urlparse(self.path).path.removeprefix("/api/"))
        if action is None: self.send_error(404)
        else: self.reply(action())


if __name__ == "__main__":
    if "--check" in sys.argv or "--preflight" in sys.argv:
        print(json.dumps({"official": preflight(True), "lag": lag_preflight()}, ensure_ascii=False, indent=2))
    else:
        with Server(("127.0.0.1", PORT), Handler) as server:
            print(f"AI Pilot dashboard: http://localhost:{PORT}", flush=True); server.serve_forever()

