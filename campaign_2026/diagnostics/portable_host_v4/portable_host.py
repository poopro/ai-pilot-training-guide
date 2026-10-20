"""Independent portable-package Host rehearsal; never extends the legacy six.

Run with the package runtime -I -S. psutil is vendored beside this observer;
the unchanged Player and its self-check import only the original package.
Only arm/watchdog launch processes. check/aggregate do not launch Host or FDM.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "vendor"))
import psutil
import p2_terminal_evidence as terminal

ROOT = HERE.parents[1]
PREP = ROOT / "deployment" / "portable_guide_verification_20261012" / "PREPARATION.json"
PROTOCOL = PREP.with_name("HOST_PROTOCOL.json")
PROFILE = "portable_repair_guide_rehearsal_v4"
ACTIVE = HERE / "active.json"
TAIPEI = timezone(timedelta(hours=8))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic(path, value):
    """Bound transient Windows sharing violations; callers still clean in finally."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp_" + uuid.uuid4().hex)
    try:
        for attempt in range(6):
            try:
                temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                                allow_nan=False), encoding="utf-8")
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(.05 * (attempt + 1))
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def publish_best_effort(path, value, errors):
    try:
        atomic(path, value)
        return True
    except OSError as error:
        errors.append({"path": str(path), "error": repr(error), "utc": now()})
        print("Receipt write failed: " + repr(error), file=sys.stderr, flush=True)
        return False


def identity(process):
    return {"pid": process.pid, "create_time": process.create_time(),
            "command": process.cmdline(), "exe": process.exe(), "parent_pid": process.ppid()}


def exact_live(record):
    try:
        process = psutil.Process(record["pid"])
        if abs(process.create_time() - record["create_time"]) > .001:
            return None, "pid_reused"
        if process.cmdline() != record["command"]:
            return None, "command_changed"
        if os.path.normcase(process.exe()) != os.path.normcase(record["exe"]):
            return None, "executable_changed"
        return process, "same_process"
    except psutil.NoSuchProcess:
        return None, "absent"
    except psutil.AccessDenied:
        return None, "unknown_access_denied"


class CampaignLock:
    def __enter__(self):
        import msvcrt
        self.stream = (ROOT / "launch.lock").open("a+b")
        if self.stream.tell() == 0:
            self.stream.write(b"0"); self.stream.flush()
        self.stream.seek(0)
        try:
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.stream.close()
            raise RuntimeError("Another campaign supervisor holds the compute lock")
        return self

    def __exit__(self, *_):
        import msvcrt
        self.stream.seek(0)
        msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        self.stream.close()


def sanitized_env():
    result = {key: value for key, value in os.environ.items()
              if not key.upper().startswith("PYTHON") and not key.upper().startswith("CONDA")}
    result["PATH"] = str(Path(result.get("SystemRoot", r"C:\Windows")) / "System32")
    return result


def branch_sources():
    paths = [HERE / "portable_host.py", HERE / "p2_terminal_evidence.py"]
    paths.extend(sorted((HERE / "vendor").rglob("*")))
    return {path.relative_to(HERE).as_posix(): sha(path) for path in paths
            if path.is_file() and "__pycache__" not in path.parts}


def frozen_profile():
    preparation, protocol = read(PREP), read(PROTOCOL)
    package, archive = Path(preparation["package"]), Path(preparation["archive"])
    manifest = package / "manifest.json"
    if sha(manifest) != preparation["manifest_sha256"] or sha(archive) != preparation["archive_sha256"]:
        raise RuntimeError("Frozen portable manifest or ZIP changed")
    files = read(manifest)["files_sha256"]
    if len(files) != 2115:
        raise RuntimeError("Expected the original 2115-file package manifest")
    for relative, expected in files.items():
        path = (package / relative).resolve()
        if not path.is_relative_to(package.resolve()) or sha(path) != expected:
            raise RuntimeError("Portable package changed: " + relative)
    host = Path(protocol["host_dir"])
    for name, expected in protocol["host_sources_sha256"].items():
        if sha(host / name) != expected:
            raise RuntimeError("Original published Host input changed: " + name)
    cached = Path(os.environ["LOCALAPPDATA"]) / "JSBsimHost_1_0_0_0" / "JSB_host_GUI_publish.exe"
    if not cached.is_file():
        raise RuntimeError("Published cached Host executable missing; cannot freeze its prelaunch bytes")
    frozen = read(HERE / "BRANCH_FREEZE.json")
    if frozen["files_sha256"] != branch_sources():
        raise RuntimeError("Isolated observer branch changed after freeze")
    network = read(package / "network.json")
    if network != {"listen_ip": "127.0.0.1", "listen_port": 8199,
                   "host_ip": "127.0.0.1", "host_port": 8099, "max_hz": 60}:
        raise RuntimeError("This rehearsal requires the original local Host network profile")
    values = {"profile": PROFILE, "package": str(package), "archive": str(archive),
              "package_manifest_sha256": sha(manifest), "archive_sha256": sha(archive),
              "runtime_sha256": sha(package / "runtime" / "python.exe"),
              "player_sha256": sha(package / "tools" / "player.py"),
              "network_sha256": sha(package / "network.json"),
              "host_dir": str(host), "host_inputs_sha256": protocol["host_sources_sha256"],
              "cached_host_executable": str(cached), "cached_host_sha256": sha(cached),
              "cached_hash_is_not_assumed_equal_to_original": True,
              "observer_sources_sha256": frozen["files_sha256"], "checked_package_files": len(files),
              "console_helper_executable": str(Path(os.environ["SystemRoot"])/"System32"/"conhost.exe"),
              "console_helper_sha256": sha(Path(os.environ["SystemRoot"])/"System32"/"conhost.exe"),
              "terminal_cleanup_executable":str(Path(os.environ["SystemRoot"])/"System32"/"taskkill.exe"),
              "terminal_cleanup_sha256":sha(Path(os.environ["SystemRoot"])/"System32"/"taskkill.exe")}
    values["fixed_profile_hash"] = canonical(values)
    return values


def commands(profile, seconds):
    package = Path(profile["package"])
    python = package / "runtime" / "python.exe"
    prefix = [str(python), "-I", "-S", "-B", "-X", "utf8", "-u"]
    return {"python": str(python), "prefix": prefix,
            "host": [str(Path(profile["host_dir"]) / "JSB_host_GUI_publish.exe")],
            "self_check": prefix + [str(package / "tools" / "self_check.py")],
            "player": prefix + [str(package / "tools" / "player.py"), "--guide", "--network",
                                str(package / "network.json"), "--max-seconds", str(seconds)]}


def workload_conflicts(exclude=()):
    conflicts = []
    for process in psutil.process_iter(["name"]):
        if process.pid in set(exclude) | {os.getpid()}:
            continue
        name = (process.info["name"] or "").lower()
        if name != "jsb_host_gui_publish.exe" and name not in ("python.exe", "pythonw.exe"):
            continue
        try:
            cmd = process.cmdline()
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            conflicts.append({"pid": process.pid, "state": "unknown_access_denied"})
            continue
        if name == "jsb_host_gui_publish.exe" or any(
                "e:/ai_pilot/" in arg.replace("\\", "/").lower() and
                (arg.lower().endswith(".py") or "--internal-player2" in arg) for arg in cmd):
            conflicts.append({"pid": process.pid, "command": cmd})
    try:
        for connection in psutil.net_connections(kind="udp"):
            if connection.laddr and connection.laddr.port in (8199, 8099):
                conflicts.append({"pid": connection.pid, "udp_port": connection.laddr.port})
    except psutil.AccessDenied:
        conflicts.append({"state": "udp_owner_unknown_access_denied"})
    return conflicts


def preflight(seconds=720, remaining_percent=None, exclude=()):
    profile = frozen_profile()
    command = commands(profile, seconds)
    available_ram, disk_free = psutil.virtual_memory().available, psutil.disk_usage(str(ROOT)).free
    conflicts = workload_conflicts(exclude)
    blocked = []
    if conflicts: blocked.append("active_or_unknown_compute_or_UDP_owner")
    if (ROOT / "STOP").exists() or (HERE / "STOP").exists(): blocked.append("STOP_exists")
    if available_ram < 2 * 1024**3: blocked.append("RAM_below_2GiB")
    if disk_free < 5 * 1024**3: blocked.append("disk_below_5GiB")
    if ACTIVE.is_file() and read(ACTIVE).get("status") == "armed":
        live, state = exact_live(read(ACTIVE)["identity"])
        if live is not None or state == "unknown_access_denied": blocked.append("portable_guard_active_or_unknown")
    warnings = []
    if remaining_percent is None: warnings.append("Codex quota not freshly observed; warning only")
    elif remaining_percent <= 10: warnings.append("Codex quota <=10 percent; warning only")
    day = datetime.now(TAIPEI).date().isoformat()
    ledger_path = ROOT / "compute_budgets" / (day + ".json")
    ledger = read(ledger_path) if ledger_path.is_file() else {"reserved_hours": 0., "items": []}
    if float(ledger["reserved_hours"]) + seconds / 3600 > 6:
        warnings.append("Daily six-hour advisory exceeded; reserve and retain the actual history")
    return {"check_only": True, "profile": profile, "commands": command,
            "deadline_seconds": seconds, "deadline_uses_monotonic_and_epoch": True,
            "resource_checks": {"available_ram": available_ram, "disk_free": disk_free},
            "conflicts": conflicts, "blocked": blocked, "warnings": warnings,
            "operational_ready": not blocked, "portable_package_host_completed": False,
            "new_host_rounds": 0, "eligible_for_old_six_round_gate": False,
            "separate_packaged_requirement": 6, "package_files_modified": False,
            "host_started": False, "new_fdm_ticks": 0,
            "psutil_module": str(Path(psutil.__file__).resolve()),
            "supervisor_runtime": str(Path(sys.executable).resolve()),
            "supervisor_is_package_runtime": Path(sys.executable).resolve() == Path(command["python"]).resolve(),
            "budget_date_taipei": day, "ledger_path": str(ledger_path),
            "prior_reserved_hours": ledger["reserved_hours"], "reserve_hours": seconds / 3600}


def verify_supervisor_runtime(profile):
    if Path(sys.executable).resolve() != Path(profile["package"]) / "runtime" / "python.exe":
        raise RuntimeError("Actual launch must use the frozen package Python, not Conda")
    if not sys.flags.isolated or not sys.flags.no_site or not Path(psutil.__file__).resolve().is_relative_to(HERE / "vendor"):
        raise RuntimeError("Supervisor must use -I -S and local vendored process support")


def reserve_budget(check, token):
    path = Path(check["ledger_path"])
    data = read(path) if path.is_file() else {
        "date_taipei": check["budget_date_taipei"], "daily_limit_hours": 6., "reserved_hours": 0., "items": []}
    data["items"].append({"id": token, "hours": check["reserve_hours"], "status": "reserved",
                          "profile": PROFILE, "warning_only": True, "reserved_utc": now()})
    data["reserved_hours"] = sum(float(item["hours"]) for item in data["items"])
    atomic(path, data)
    return str(path)


def observed_cleanup_target(ident,parent_entry,tracked):
    """Observe the frozen Host's own P2 cleanup, never invoke taskkill.

    Only exact /PID own-direct-P2 /T /F is recognized. This is not permission
    to manage arbitrary Windows processes or to trust a basename alone.
    """
    command=ident.get("command",[])
    if len(command)!=5 or Path(command[0]).name.lower()!="taskkill.exe" or command[1].lower()!="/pid" or [c.lower() for c in command[3:]]!=["/t","/f"]:return None
    if parent_entry.get("role")!="owned_cached_gui":return None
    try:pid=int(command[2])
    except ValueError:return None
    targets=[e for e in tracked.values() if e["identity"]["pid"]==pid and e.get("role") in ("owned_host_descendant","owned_cached_internal_p2") and "--internal-player2" in e["identity"]["command"] and e["identity"]["parent_pid"]==parent_entry["identity"]["pid"] and e["identity"]["create_time"]<ident["create_time"]]
    return targets[0]["identity"] if len(targets)==1 else None


def discover(tracked, allowed_exe):
    """Capture direct-child links down from exact owned roots; never read ancestors.

allowed_exe is a path -> prelaunch SHA/snapshot map, not global permission to
capture a same-name cache process. Unknown owned children reject completeness.
"""
    queue = list(tracked)
    visited = set()
    while queue:
        key = queue.pop(0)
        if key in visited: continue
        visited.add(key)
        entry = tracked[key]
        process, state = exact_live(entry["identity"])
        entry["last_state"] = state
        if process is None: continue
        try:
            children = process.children(recursive=False)
        except psutil.NoSuchProcess:
            entry["last_state"] = "absent"
            continue
        except psutil.AccessDenied:
            entry["descendants_unknown"] = True
            continue
        for child in children:
            try:
                ident = identity(child)
            except psutil.NoSuchProcess: continue
            except psutil.AccessDenied:
                entry["descendants_unknown"] = True
                continue
            if ident["parent_pid"] != entry["identity"]["pid"]:
                entry["descendants_unknown"] = True
                continue
            descriptor = allowed_exe.get(os.path.normcase(ident["exe"]))
            if descriptor is None:
                entry["descendants_unknown"] = True
                entry.setdefault("unrecognized_owned_children", []).append(ident)
                continue
            child_key = f"{ident['pid']}:{ident['create_time']:.6f}"
            if child_key not in tracked:
                # Validate both endpoints while the direct link can still be
                # observed. PID/create/cmd/exe are never inferred after exit.
                parent, parent_state = exact_live(entry["identity"])
                child, child_state = exact_live(ident)
                if parent is None or child is None or child.ppid() != parent.pid:
                    entry["descendants_unknown"] = True
                    continue
                snapshot = Path(descriptor["snapshot"])
                if descriptor["phase"] != "before_host_Popen" or not snapshot.is_file() or \
                        sha(snapshot) != descriptor["sha256"] or sha(ident["exe"]) != descriptor["sha256"]:
                    entry["descendants_unknown"] = True
                    continue
                if ident["create_time"] < entry["identity"]["create_time"]:
                    entry["descendants_unknown"] = True
                    continue
                cached = descriptor.get("kind") == "cached_host"
                internal = "--internal-player2" in ident["command"]
                cleanup_target=observed_cleanup_target(ident,entry,tracked) if descriptor.get("kind")=="terminal_cleanup" else None
                if descriptor.get("kind")=="terminal_cleanup" and cleanup_target is None:
                    entry["descendants_unknown"]=True;continue
                role = "owned_terminal_cleanup_helper" if cleanup_target else ("owned_console_helper" if descriptor.get("kind")=="console_helper" else (("owned_cached_internal_p2" if internal else "owned_cached_gui") if cached else "owned_host_descendant"))
                tracked[child_key] = {"role": role, "identity": ident, "discovered_from": key,
                    "observed_utc": now(), "parent_identity_at_observation": entry["identity"],
                    "direct_link_observed": True, "executable_snapshot": str(snapshot),
                    "executable_sha256": descriptor["sha256"], "snapshot_phase": descriptor["phase"],"cleanup_target_identity":cleanup_target}
            queue.append(child_key)


def child_inventory_checks(session, ledger, folder):
    """Reject cached execution omitted from the observation ledger, even if root exited."""
    checks = {"session_token_matches": ledger.get("token") == session.get("watchdog_token"),
              "prelaunch_cache_receipt_matches": False, "all_owned_children_captured": False,
              "cached_gui_captured": False, "cached_internal_p2_captured": False,
              "all_direct_parent_chains_verified": False, "all_executable_snapshots_match": False}
    try:
        pre = read(session["host_launch_record"])
        cache = session["cached_executable_receipt"]
        checks["prelaunch_cache_receipt_matches"] = (pre["cached_executable_receipt"] == cache and
            cache["phase"] == "before_host_Popen" and
            sha(cache["snapshot"]) == cache["sha256"] == session["fixed_profile"]["cached_host_sha256"] and
            cache["path"] == session["fixed_profile"]["cached_host_executable"])
        tracked = ledger["tracked"]
        roots = [key for key, entry in tracked.items() if entry.get("role") == "host_root"]
        if len(roots) != 1: return checks
        root_key = roots[0]
        root = tracked[root_key]["identity"]
        if {key: root[key] for key in ("pid", "create_time", "command")} != session["host_launch_identity"]:
            return checks
        chains, snapshots = [], []
        for key, entry in tracked.items():
            if key == root_key or entry.get("role") in ("player_root", "collector_root"): continue
            chain_key, seen, valid = key, set(), True
            if entry.get("role")=="owned_terminal_cleanup_helper":
                parent=tracked.get(entry.get("discovered_from"),{})
                valid=(observed_cleanup_target(entry["identity"],parent,tracked)==entry.get("cleanup_target_identity") and entry.get("cleanup_target_identity") is not None and os.path.normcase(entry["identity"]["exe"])==os.path.normcase(session["fixed_profile"]["terminal_cleanup_executable"]) and entry["executable_sha256"]==session["fixed_profile"]["terminal_cleanup_sha256"])
            # Console helpers may belong to the exact package Player/collector;
            # cached Host/P2 must still terminate only at the exact Host root.
            target_root=root_key
            if entry.get("role")=="owned_console_helper":
                valid=(os.path.normcase(entry["identity"]["exe"])==os.path.normcase(session["fixed_profile"]["console_helper_executable"]) and entry["executable_sha256"]==session["fixed_profile"]["console_helper_sha256"])
                cursor=key; visited=set()
                while cursor in tracked and cursor not in visited:
                    visited.add(cursor);node=tracked[cursor]
                    if node.get("role") in ("host_root","player_root","collector_root"):
                        target_root=cursor;break
                    cursor=node.get("discovered_from")
                else: valid=False
                target=tracked.get(target_root,{})
                ident=target.get("identity",{})
                if target.get("role")=="player_root":
                    valid=valid and ident==session.get("player")
                elif target.get("role")=="collector_root":
                    valid=valid and ident.get("parent_pid")==session.get("watchdog_identity",{}).get("pid")
                elif target.get("role")!="host_root":valid=False
            while chain_key != target_root:
                if chain_key in seen or chain_key not in tracked:
                    valid = False; break
                seen.add(chain_key)
                node = tracked[chain_key]
                parent_key = node.get("discovered_from")
                if parent_key not in tracked:
                    valid = False; break
                parent = tracked[parent_key]["identity"]
                if not node.get("direct_link_observed") or node["identity"]["parent_pid"] != parent["pid"] or \
                        node.get("parent_identity_at_observation") != parent:
                    valid = False; break
                chain_key = parent_key
            chains.append(valid)
            snapshot = Path(entry["executable_snapshot"]).resolve()
            snapshots.append(snapshot.is_relative_to(Path(folder).resolve()) and
                entry["snapshot_phase"] == "before_host_Popen" and sha(snapshot) == entry["executable_sha256"])
            if entry.get("role") == "owned_cached_gui": checks["cached_gui_captured"] = True
            if entry.get("role") == "owned_cached_internal_p2": checks["cached_internal_p2_captured"] = True
        checks["all_direct_parent_chains_verified"] = bool(chains) and all(chains)
        checks["all_executable_snapshots_match"] = bool(snapshots) and all(snapshots)
        checks["all_owned_children_captured"] = bool(tracked) and all(
            not entry.get("descendants_unknown") and not entry.get("unrecognized_owned_children") for entry in tracked.values())
    except (OSError, KeyError, ValueError, TypeError):
        pass
    return checks


def cleanup(tracked, popens):
    results = []
    # Descendants are inserted after roots; stop them first, then each owned root.
    for key, entry in reversed(list(tracked.items())):
        process, state = exact_live(entry["identity"])
        result = {"role": entry["role"], "identity": entry["identity"], "before": state,
                  "descendants_unknown": entry.get("descendants_unknown", False)}
        if process is None:
            result.update(action="none", after=state)
        else:
            try:
                process.terminate()
                _, alive = psutil.wait_procs([process], timeout=3)
                if alive:
                    exact, state = exact_live(entry["identity"])
                    if exact is not None:
                        exact.kill(); _, alive = psutil.wait_procs([exact], timeout=3)
                        state = "still_alive" if alive else "absent"
                else: state = "absent"
                result.update(action="terminated_or_killed", after=state)
            except psutil.NoSuchProcess: result.update(action="already_exited", after="absent")
            except psutil.AccessDenied: result.update(action="none", after="unknown_access_denied")
        handle = popens.get(entry["identity"]["pid"])
        if handle is not None:
            try: result["actual_exit_code"] = handle.wait(timeout=3)
            except subprocess.TimeoutExpired: result["actual_exit_code"] = None
        results.append(result)
    return {"results": results, "all_known_processes_stopped": all(
        row["after"] == "absent" and not row["descendants_unknown"] for row in results)}


def snapshot_inputs(folder, profile):
    package, host = Path(profile["package"]), Path(profile["host_dir"])
    sources = {}
    selected = ["manifest.json", "network.json", "tools/player.py", "policy/bootstrap.py",
                "policy/controller.py", "policy/combat_v3/controller.py", "policy/combat_v3/interface.py",
                "policy/combat_v3/config.json", "runtime/python.exe", "runtime/python310._pth"]
    for relative in selected:
        target = folder / "package_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(package / relative, target)
        sources[relative] = {"snapshot": str(target), "sha256": sha(target)}
    for name in profile["host_inputs_sha256"]:
        shutil.copy2(host / name, folder / name)
    shutil.copy2(Path(profile["cached_host_executable"]), folder / "cachedHost_executable.bin")
    if sha(folder / "cachedHost_executable.bin") != profile["cached_host_sha256"]:
        raise RuntimeError("Cached Host changed while taking its prelaunch snapshot")
    shutil.copy2(Path(profile["console_helper_executable"]),folder/"console_helper.bin")
    if sha(folder/"console_helper.bin")!=profile["console_helper_sha256"]:
        raise RuntimeError("Console helper changed while taking prelaunch snapshot")
    shutil.copy2(Path(profile["terminal_cleanup_executable"]),folder/"terminal_cleanup.bin")
    if sha(folder/"terminal_cleanup.bin")!=profile["terminal_cleanup_sha256"]:raise RuntimeError("Terminal cleanup bytes changed before launch")
    return sources


def mark_start(folder):
    folder = checked_folder(folder)
    session = read(folder / "session.json")
    if "start_clicked_epoch" in session: raise RuntimeError("START boundary cannot be reset")
    for key in ("player", "watchdog_identity"):
        process, state = exact_live(session[key])
        if process is None: raise RuntimeError("Required process missing or changed: " + key + " " + state)
    # A PyInstaller bootloader root can exit while its recorded GUI descendant
    # remains alive. Accept only an exactly tracked owned non-P2 Host process.
    ledger = read(folder / "live.json")
    inventory = child_inventory_checks(session, ledger, folder)
    if not all(inventory.values()):
        raise RuntimeError("Owned cached Host/P2 capture incomplete before START: " + repr(inventory))
    host_live = any(exact_live(entry["identity"])[0] is not None and
                    Path(entry["identity"]["exe"]).name.lower() == "jsb_host_gui_publish.exe" and
                    "--internal-player2" not in entry["identity"]["command"]
                    for entry in ledger["tracked"].values())
    if not host_live: raise RuntimeError("No exactly recorded owned GUI Host is alive")
    session.update(start_clicked_epoch=time.time(), start_clicked_monotonic=time.monotonic(),
                   start_marker_scope="Operator boundary immediately BEFORE pressing Host START; not UI observation")
    atomic(folder / "session.json", session)
    print("已記錄portable START前界線，現在於該Host視窗按START。", flush=True)


def checked_folder(folder):
    folder = Path(folder).resolve()
    if not folder.is_relative_to((HERE / "runs").resolve()): raise RuntimeError("Run outside portable evidence branch")
    if read(folder / "intent.json")["profile"] != PROFILE: raise RuntimeError("Wrong rehearsal profile")
    return folder


def collect(folder):
    folder = checked_folder(folder)
    session = read(folder / "session.json")
    if session["profile"] != PROFILE or "start_clicked_epoch" not in session:
        raise RuntimeError("Portable session or START receipt missing")
    if frozen_profile() != session["fixed_profile"]: raise RuntimeError("Frozen rehearsal profile changed")
    for record in session["package_snapshots"].values():
        if sha(record["snapshot"]) != record["sha256"]: raise RuntimeError("Package snapshot changed")
    candidate = terminal.probe(session, read(folder / "live.json"))
    if candidate is None: raise RuntimeError("Unique fresh owned P2 terminal CSV/ACMI not ready")
    source = Path(candidate["csv"])
    shutil.copy2(source, folder / source.name)
    acmi = source.parent / "output_acmi" / (source.stem + ".acmi")
    shutil.copy2(acmi, folder / acmi.name)
    for path in ("host_stdout.log", "host_stderr.log"):
        if not (folder / path).is_file(): raise RuntimeError("Missing original Host log")
    with (folder / source.name).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    times = [float(row["time"]) for row in rows]
    last = rows[-1]
    early = float(last["system_Final_whoiswinner"]) in (1., 2.) and min(
        float(last["player1_Score_RemainingHP"]), float(last["player2_Score_RemainingHP"])) <= 0
    acmi_times = [float(line[1:]) for line in (folder / acmi.name).read_text(encoding="utf-8-sig").splitlines() if line.startswith("#")]
    terminal_checks = terminal.verify(folder, session, rows, sha(folder / source.name))
    inventory = child_inventory_checks(session, read(folder / "live.json"), folder)
    checks = {"finite_csv": all(math.isfinite(float(value)) for row in rows for value in row.values()),
              "strictly_increasing_time": all(b > a for a, b in zip(times, times[1:])),
              "full_or_early_adjudication": (times[-1] >= 299.9 and len(rows) >= 17900) or early,
              "player1_ready": any(float(row["player1_state"]) == 2 for row in rows),
              "player1_moved": any(abs(float(row["player1_lat_deg"]) - float(rows[0]["player1_lat_deg"])) > 1e-7 or
                  abs(float(row["player1_lon_deg"]) - float(rows[0]["player1_lon_deg"])) > 1e-7 for row in rows),
              "csv_matches_terminal_capture": sha(folder / source.name) == candidate["csv_sha256"],
              "acmi_terminal_time": bool(acmi_times) and all(math.isfinite(value) for value in acmi_times) and
                  all(b >= a for a, b in zip(acmi_times, acmi_times[1:])) and abs(acmi_times[-1] - times[-1]) <= .1,
              "fresh_owned_p2_terminal": all(terminal_checks.values()),
              "all_owned_cached_children_captured": all(inventory.values()),
              "package_runtime_self_check": session["package_self_check"]["actual_exit_code"] == 0 and
                  session["package_self_check"]["result"]["external_python_modules"] is False,
              "profile_hash_unchanged": session["fixed_profile"]["fixed_profile_hash"] == frozen_profile()["fixed_profile_hash"]}
    result = {"profile": PROFILE, "round_identity": canonical(session["host_launch_identity"]),
              "fixed_profile_hash": session["fixed_profile"]["fixed_profile_hash"],
              "source_csv": str(source), "csv_sha256": sha(folder / source.name),
              "acmi_sha256": sha(folder / acmi.name), "rows": len(rows), "sim_seconds": times[-1],
              "host_winner_raw": last["system_Final_whoiswinner"], "checks": checks,
              "portable_rehearsal_artifacts_complete": all(checks.values()),
              "eligible_for_old_six_round_gate": False, "packaged_six_round_gate_complete": False,
              "actual_collector_exit_code": None, "competition_certification": False,
              "terminal_receipt_checks": terminal_checks, "owned_child_inventory_checks": inventory,
              "scope": "Separate portable package vs unchanged published local GUI Host; not legacy six or competition certification."}
    atomic(folder / "portable_result.json", result)
    return 0 if all(checks.values()) else 2


def deadline_expired(intent):
    return time.monotonic() >= intent["deadline_monotonic"] or time.time() >= intent["deadline_epoch"]


class VerifiedWindowsWaitHandle:
    """A process handle remains bound to its original process after PID reuse."""
    def __init__(self, expected):
        import ctypes
        from ctypes import wintypes
        process, state = exact_live(expected)
        if process is None:
            raise RuntimeError("Cannot attach a wait handle to an absent/unknown identity: " + state)
        self.ctypes = ctypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.handle = self.kernel.OpenProcess(0x00100000 | 0x1000, False, expected["pid"])
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "OpenProcess wait handle failed; no inferred exit")
        try:
            creation, exited, kernel_time, user_time = [wintypes.FILETIME() for _ in range(4)]
            if not self.kernel.GetProcessTimes(self.handle, ctypes.byref(creation), ctypes.byref(exited),
                                              ctypes.byref(kernel_time), ctypes.byref(user_time)):
                raise OSError(ctypes.get_last_error(), "GetProcessTimes failed")
            epoch = (((creation.dwHighDateTime << 32) | creation.dwLowDateTime) - 116444736000000000) / 10000000
            if abs(epoch - expected["create_time"]) > .001:
                raise RuntimeError("Wait handle belongs to reused PID")
            self.creation_epoch_from_handle = epoch
        except BaseException:
            self.close()
            raise

    def wait(self, timeout_ms):
        value = self.kernel.WaitForSingleObject(self.handle, timeout_ms)
        if value == 0: return True
        if value == 258: return False
        raise OSError(self.ctypes.get_last_error(), "WaitForSingleObject failed")

    def exit_code(self):
        from ctypes import wintypes
        code = wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(self.handle, self.ctypes.byref(code)):
            raise OSError(self.ctypes.get_last_error(), "GetExitCodeProcess failed")
        return int(code.value)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def wait_verified_process(expected, deadline_monotonic, attached=lambda details: None):
    handle = VerifiedWindowsWaitHandle(expected)
    try:
        details = {"identity": expected, "process_creation_epoch_from_handle": handle.creation_epoch_from_handle,
                   "wait_handle_acquired": True, "attached_utc": now(),
                   "method": "verified Windows handle + WaitForSingleObject + GetExitCodeProcess"}
        attached(details)
        while time.monotonic() < deadline_monotonic:
            if handle.wait(1000):
                return {**details, "actual_exit_code": handle.exit_code(), "exited_utc": now(), "timed_out": False}
        return {**details, "actual_exit_code": None, "timed_out": True, "observed_utc": now()}
    finally:
        handle.close()


def observe_watchdog(folder):
    folder = checked_folder(folder)
    intent = read(folder / "intent.json")
    spawn = read(folder / "guard_spawn.json")
    receipt = {"profile": PROFILE, "guard_spawn_sha256": sha(folder / "guard_spawn.json"),
               "guard_source_sha256": intent["fixed_profile"]["observer_sources_sha256"]["portable_host.py"],
               "actual_exit_code": None, "identity": spawn["identity"]}
    try:
        verify_supervisor_runtime(intent["fixed_profile"])
        if sha(__file__) != receipt["guard_source_sha256"]:
            raise RuntimeError("Observer source differs from frozen guardian")
        if (folder / "watchdog_exit_observed.json").exists():
            raise RuntimeError("Do not replace an existing actual watchdog exit observation")
        observed = wait_verified_process(spawn["identity"], intent["deadline_monotonic"] + 90,
            attached=lambda details: atomic(folder / "watchdog_wait_attached.json", {**receipt, **details}))
        receipt.update(observed)
    except Exception as error:
        receipt.update(error=repr(error), observed_utc=now())
    atomic(folder / "watchdog_exit_observed.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    return 0 if type(receipt.get("actual_exit_code")) is int and receipt["actual_exit_code"] == 0 else 2


def watchdog_observation_valid(folder, profile_hash):
    try:
        receipt = read(folder / "watchdog_exit_observed.json")
        spawn = read(folder / "guard_spawn.json")
        intent = read(folder / "intent.json")
        return (receipt.get("profile") == PROFILE and receipt.get("wait_handle_acquired") is True and
            type(receipt.get("actual_exit_code")) is int and receipt["actual_exit_code"] == 0 and
            receipt.get("identity") == spawn["identity"] and receipt["guard_spawn_sha256"] == sha(folder / "guard_spawn.json") and
            receipt["guard_source_sha256"] == intent["fixed_profile"]["observer_sources_sha256"]["portable_host.py"] and
            profile_hash == intent["fixed_profile"]["fixed_profile_hash"])
    except (OSError, KeyError, TypeError):
        return False


def monitor(folder):
    folder = checked_folder(folder)
    intent = read(folder / "intent.json")
    profile = intent["fixed_profile"]
    verify_supervisor_runtime(profile)
    tracked, popens, errors = {}, {}, []
    reason, collector_code = "not_started", None
    active = {"status": "armed", "token": intent["token"], "profile": PROFILE,
              "identity": identity(psutil.Process()), "folder": str(folder),
              "deadline_epoch": intent["deadline_epoch"], "deadline_monotonic": intent["deadline_monotonic"]}
    allowed = {
        os.path.normcase(commands(profile, 720)["host"][0]): {"sha256": profile["host_inputs_sha256"]["JSB_host_GUI_publish.exe"],
            "snapshot": str(folder / "JSB_host_GUI_publish.exe"), "phase": "before_host_Popen", "kind": "original_host"},
        os.path.normcase(commands(profile, 720)["python"]): {"sha256": profile["runtime_sha256"],
            "snapshot": str(folder / "package_snapshot" / "runtime" / "python.exe"), "phase": "before_host_Popen", "kind": "package_python"},
        os.path.normcase(profile["cached_host_executable"]): {"sha256": profile["cached_host_sha256"],
            "snapshot": str(folder / "cachedHost_executable.bin"), "phase": "before_host_Popen", "kind": "cached_host"},
        os.path.normcase(profile["console_helper_executable"]): {"sha256":profile["console_helper_sha256"],
            "snapshot":str(folder/"console_helper.bin"),"phase":"before_host_Popen","kind":"console_helper"},
        os.path.normcase(profile["terminal_cleanup_executable"]):{"sha256":profile["terminal_cleanup_sha256"],"snapshot":str(folder/"terminal_cleanup.bin"),"phase":"before_host_Popen","kind":"terminal_cleanup"}}
    def expired():
        return deadline_expired(intent)
    def spawn(command, role, out, err, cwd, visible=False):
        with (folder / out).open("wb") as stdout, (folder / err).open("wb") as stderr:
            process = subprocess.Popen(command, cwd=str(cwd), env=sanitized_env(), stdout=stdout, stderr=stderr,
                creationflags=0 if visible else getattr(subprocess, "CREATE_NO_WINDOW", 0))
        popens[process.pid] = process
        try: ident = identity(psutil.Process(process.pid))
        except psutil.NoSuchProcess:
            actual_exit = process.wait(timeout=3)
            raise RuntimeError(f"{role} exited before identity receipt; actual exit {actual_exit}")
        tracked[f"{ident['pid']}:{ident['create_time']:.6f}"] = {"role": role, "identity": ident}
        return process, ident
    try:
        with CampaignLock():
            launcher, launcher_state = exact_live(intent["launcher_identity"])
            if launcher is None or os.getppid() != intent["launcher_identity"]["pid"]:
                raise RuntimeError("Guardian must be a direct child of its exact new arm launcher: " + launcher_state)
            if (folder / "session.json").exists():
                raise RuntimeError("A portable Host session already exists; never replay an old run folder")
            check = preflight(intent["deadline_seconds"], intent.get("remaining_percent"),
                              exclude=(intent["launcher_identity"]["pid"],))
            if check["blocked"]: raise RuntimeError("Launch blocked: " + repr(check["blocked"]))
            if check["profile"] != profile or expired(): raise RuntimeError("Profile changed or deadline reached before launch")
            command = commands(profile, intent["deadline_seconds"])
            self_check = subprocess.run(command["self_check"], env=sanitized_env(), cwd=HERE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=min(45, intent["deadline_seconds"]),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if self_check.returncode != 0: raise RuntimeError("Portable runtime self-check failed: " + self_check.stderr.decode("utf-8", "replace"))
            self_receipt = {"command": command["self_check"], "actual_exit_code": self_check.returncode,
                            "result": json.loads(self_check.stdout.decode("utf-8-sig"))}
            atomic(folder / "runtime_self_check.json", self_receipt)
            sources = snapshot_inputs(folder, profile)
            host = Path(profile["host_dir"])
            runtime = Path(os.environ["LOCALAPPDATA"]) / "JSBsimHost_1_0_0_0"
            preexisting = {str(path): {"size": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
                for directory in (host, runtime) if directory.is_dir() for path in directory.glob("*.csv")}
            before = terminal.before_logs([host / "player2_runtime.log", runtime / "player2_runtime.log"])
            cache_receipt = {"path": profile["cached_host_executable"], "sha256": profile["cached_host_sha256"],
                             "snapshot": str(folder / "cachedHost_executable.bin"), "phase": "before_host_Popen"}
            launch = {"profile": PROFILE, "captured_utc": now(), "setting_capture_phase": "before_host_Popen",
                      "terminal_capture_version": terminal.VERSION, "p2_logs_before_launch": before,
                      "host_exe_sha256": profile["host_inputs_sha256"]["JSB_host_GUI_publish.exe"],
                      "host_setting_sha256": profile["host_inputs_sha256"]["Setting.txt"],
                      "cached_executable_receipt": cache_receipt}
            atomic(folder / "inputs_before_launch.json", launch)
            atomic(ACTIVE, active)
            atomic(folder / "armed.json", active)
            if expired(): raise RuntimeError("Deadline before Host launch")
            _, host_ident = spawn(command["host"], "host_root", "host_stdout.log", "host_stderr.log", host, visible=True)
            launch.update(host_ident)
            atomic(folder / "launch.json", launch)
            # Track bootloader/internal P2 quickly, before their root can exit.
            limit = min(time.monotonic() + 1., intent["deadline_monotonic"])
            while time.monotonic() < limit:
                discover(tracked, allowed); time.sleep(.02)
            _, player_ident = spawn(command["player"], "player_root", "player_stdout.log", "player_stderr.log", HERE)
            session = {"profile": PROFILE, "folder": str(folder), "controller": "repair_guide", "model": None,
                       "fixed_profile": profile, "package_snapshots": sources, "package_self_check": self_receipt,
                       "watchdog_token": intent["token"], "watchdog_identity": active["identity"],
                       "host_launch_identity": {key:host_ident[key] for key in ("pid", "create_time", "command")},
                       "host_process_identity": host_ident, "host_processes": [host_ident], "player": player_ident,
                       "host_launch_record": str(folder / "launch.json"), "host_dir": str(host), "runtime_dir": str(runtime),
                       "preexisting_csv": preexisting, "terminal_capture_version": terminal.VERSION,
                       "p2_logs_before_launch": before, "cached_executable_receipt": cache_receipt,
                       "status": "waiting_init", "validation_exit_code": None}
            atomic(folder / "session.json", session)
            atomic(folder / "ui_ready.json", {"profile": PROFILE, "folder": str(folder), "host_started": True,
                  "player_started": True, "instruction": "INIT; wait both READY/GO; mark-start then START"})
            while True:
                discover(tracked, allowed)
                live = {**active, "tracked": tracked, "observed_utc": now()}
                publish_best_effort(folder / "live.json", live, errors)
                if expired(): reason = "hard_deadline"; break
                if (ROOT / "STOP").exists() or (HERE / "STOP").exists(): reason = "STOP"; break
                session = read(folder / "session.json")
                if terminal.probe(session, live) is not None:
                    receipt = terminal.capture(session, folder, live)
                    if receipt is None: continue
                    session["p2_terminal_receipt"] = receipt
                    atomic(folder / "session.json", session)
                    atomic(folder / "collector_input_session.json", session)
                    collector_command = command["prefix"] + [str(Path(__file__)), "collect", "--folder", str(folder)]
                    collector, collector_ident = spawn(collector_command, "collector_root", "collector_stdout.log", "collector_stderr.log", HERE)
                    began = now()
                    collector_limit = min(time.monotonic() + 60, intent["deadline_monotonic"])
                    while collector.poll() is None and time.monotonic() < collector_limit and not expired():
                        if (ROOT / "STOP").exists() or (HERE / "STOP").exists(): break
                        time.sleep(.1)
                    if collector.poll() is not None:
                        collector_code = collector.wait(timeout=3)
                    atomic(folder / "collector_exit.json", {"command": collector_command, "identity": collector_ident,
                        "actual_exit_code": collector_code, "started_utc": began, "exited_utc": now(),
                        "collector_source_sha256": sha(__file__), "input_sha256": sha(folder / "collector_input_session.json")})
                    reason = "collector_terminal" if collector_code is not None else "collector_timeout_or_deadline"
                    break
                time.sleep(.2)
    except BaseException as error:
        reason = "failed"
        errors.append({"error": repr(error), "utc": now()})
        print(repr(error), file=sys.stderr, flush=True)
    finally:
        try:
            discover(tracked, allowed)
        except Exception as error:
            errors.append({"final_discovery_error": repr(error)})
        cleanup_receipt = cleanup(tracked, popens)
        result_path = folder / "portable_result.json"
        completed = False
        if result_path.is_file():
            result = read(result_path)
            result.update(actual_collector_exit_code=collector_code,
                portable_rehearsal_complete=result.get("portable_rehearsal_artifacts_complete") is True and
                    collector_code == 0 and cleanup_receipt["all_known_processes_stopped"] and not errors)
            completed = result["portable_rehearsal_complete"]
            publish_best_effort(result_path, result, errors)
        final = {**active, "status": "finished", "terminal_reason": reason, "finished_utc": now(),
                 "cleanup": cleanup_receipt, "errors": errors, "portable_rehearsal_complete": completed,
                 "actual_collector_exit_code": collector_code, "new_packaged_rounds": int(completed),
                 "eligible_for_old_six_round_gate": False, "packaged_six_round_gate_complete": False}
        publish_best_effort(folder / "watchdog_receipt.json", final, errors)
        publish_best_effort(ACTIVE, final, errors)
        try:
            ledger = read(intent["ledger_path"])
            for item in ledger["items"]:
                if item["id"] == intent["token"]: item.update(status="completed" if completed else "incomplete", output=str(folder))
            publish_best_effort(Path(intent["ledger_path"]), ledger, errors)
        except OSError as error: errors.append({"budget_update_error": repr(error)})
    return 0 if completed and not errors else 2


def arm(args):
    with CampaignLock():
        check = preflight(args.deadline_seconds, args.remaining_percent)
        verify_supervisor_runtime(check["profile"])
        if check["blocked"]: raise RuntimeError("Preflight blocked: " + repr(check["blocked"]))
        token = "portable_" + datetime.now(TAIPEI).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        folder = HERE / "runs" / token
        folder.mkdir(parents=True, exist_ok=False)
        ledger = reserve_budget(check, token)
        intent = {"profile": PROFILE, "token": token, "fixed_profile": check["profile"],
                  "deadline_seconds": args.deadline_seconds,
                  "deadline_epoch": time.time() + args.deadline_seconds,
                  "deadline_monotonic": time.monotonic() + args.deadline_seconds,
                  "launcher_identity": identity(psutil.Process()), "remaining_percent": args.remaining_percent,
                  "ledger_path": ledger, "warnings": check["warnings"]}
        atomic(folder / "intent.json", intent)
        command = check["commands"]["prefix"] + [str(Path(__file__)), "watchdog", "--folder", str(folder)]
        with (folder / "watchdog_stdout.log").open("wb") as out, (folder / "watchdog_stderr.log").open("wb") as err:
            process = subprocess.Popen(command, cwd=HERE, env=sanitized_env(), stdout=out, stderr=err,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try: guard_identity = identity(psutil.Process(process.pid))
        except psutil.NoSuchProcess:
            actual_exit = process.wait(timeout=3)
            atomic(folder / "guard_early_exit.json", {"actual_exit_code": actual_exit, "command": command})
            raise RuntimeError(f"Guard exited before identity capture; actual exit={actual_exit}")
        atomic(folder / "guard_spawn.json", {"identity": guard_identity, "command": command})
    limit = time.monotonic() + 60
    while time.monotonic() < limit:
        if (folder / "ui_ready.json").is_file():
            print(json.dumps({"folder": str(folder), "watchdog": guard_identity, "deadline_seconds": args.deadline_seconds,
                "profile": PROFILE, "instruction": "操作此Host：INIT；雙方READY/GO；mark-start，再按START",
                "old_six_rounds_reused": False}, ensure_ascii=False), flush=True)
            return 0
        if process.poll() is not None:
            code = process.wait(timeout=3)
            raise RuntimeError(f"Portable watchdog exited before UI ready, actual exit={code}; inspect {folder}")
        time.sleep(.1)
    # The independent guard still owns its 720-second deadline; arming timeout
    # cannot silently claim completion or remove that guard.
    raise RuntimeError("UI-ready receipt pending; independent guard remains bounded: " + str(folder))


def aggregate(paths):
    results = []
    for path in paths:
        row = read(path)
        if row.get("profile") != PROFILE: continue
        folder = checked_folder(Path(path).parent)
        if not watchdog_observation_valid(folder, row["fixed_profile_hash"]): continue
        receipt = read(folder / "watchdog_receipt.json")
        collector = read(folder / "collector_exit.json")
        source_csv = folder / Path(row["source_csv"]).name
        if receipt.get("portable_rehearsal_complete") is not True or not receipt["cleanup"]["all_known_processes_stopped"]:
            continue
        if collector.get("actual_exit_code") != 0 or sha(source_csv) != row["csv_sha256"]:
            continue
        if sha(folder / "collector_input_session.json") != collector["input_sha256"]:
            continue
        if row["fixed_profile_hash"] != read(folder / "intent.json")["fixed_profile"]["fixed_profile_hash"]:
            continue
        results.append(row)
    valid = [row for row in results if row.get("profile") == PROFILE and
             row.get("portable_rehearsal_complete") is True and row.get("actual_collector_exit_code") == 0]
    unique = {}
    csv_seen = set()
    for row in valid:
        if row["csv_sha256"] in csv_seen: continue
        csv_seen.add(row["csv_sha256"])
        unique.setdefault(row["round_identity"], row)
    profiles = {row["fixed_profile_hash"] for row in unique.values()}
    return {"profile": PROFILE, "requested_reports": len(paths), "verified_unique_packaged_rounds": len(unique),
            "required_packaged_rounds": 6, "packaged_six_round_gate_complete": len(unique) >= 6 and len(profiles) == 1,
            "legacy_rounds_imported": 0, "eligible_for_old_six_round_gate": False, "competition_certification": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="隔離portable套件公告Host驗證：不用Conda、不混入舊六場")
    parser.add_argument("action", choices=("check", "arm", "watchdog", "observe-watchdog", "mark-start", "collect", "aggregate"))
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--report", type=Path, action="append")
    parser.add_argument("--deadline-seconds", type=int, default=720)
    parser.add_argument("--remaining-percent", type=float)
    args = parser.parse_args(argv)
    if not 60 <= args.deadline_seconds <= 720: parser.error("deadline-seconds must be 60..720")
    if args.action == "check":
        result = preflight(args.deadline_seconds, args.remaining_percent)
        if args.out: atomic(args.out, result)
        print(json.dumps({key: value for key, value in result.items() if key not in ("profile", "commands")}, ensure_ascii=False))
        return 0
    if args.action == "arm": return arm(args)
    if args.action == "aggregate":
        result = aggregate(args.report or [])
        if args.out: atomic(args.out, result)
        print(json.dumps(result, ensure_ascii=False)); return 0
    if not args.folder: parser.error("--folder required for this action")
    if args.action == "observe-watchdog": return observe_watchdog(args.folder)
    if args.action == "watchdog": return monitor(args.folder)
    if args.action == "mark-start": mark_start(args.folder); return 0
    return collect(args.folder)


if __name__ == "__main__":
    raise SystemExit(main())
