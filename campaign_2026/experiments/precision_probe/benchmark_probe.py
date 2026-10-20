"""Paired local JSBSim evaluation; no training, deployment, or official claim.

Each guide/candidate pair has the same frozen sources, opponent, seed, and
initial-side geometry. ``mirrored`` reflects the initial blue position across
red while preserving both headings: it tests left/right initial separation,
not the competition Host's P1/P2 role swap. Policy inputs remain OWN20+ENEMY6.
The supervisor gives every subprocess a hard wall limit, including model load.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPAIR_ROOT = ROOT / "repair_v1"
DEFAULT_RED_BUNDLE = Path(
    r"E:\ai_pilot\autopilot\jobs\job_20261004_235618_984b\candidate2\candidate1_to_199000\final_0000148682"
)
ROUND_TICKS = 18000
CASE_WALL_SECONDS = 150.0
DISTANCES_FT = (3000, 6000, 9000)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp_" + uuid.uuid4().hex)
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                        allow_nan=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Case:
    round_index: int
    opponent: str
    distance_ft: int
    side: str
    seed: int
    actor: str

    @property
    def pair_key(self):
        return f"r{self.round_index:03d}_{self.opponent}_{self.distance_ft}_{self.side}_{self.seed}"

    @property
    def case_id(self):
        return self.pair_key + "_" + self.actor


def plan_cases(rounds=1, seed=2026101100, mirror="both", candidate=False):
    if rounds < 1 or mirror not in ("both", "normal"):
        raise ValueError("Invalid rounds or mirror mode")
    sides = ("normal", "mirrored") if mirror == "both" else ("normal",)
    actors = ("guide", "candidate") if candidate else ("guide",)
    cases = []
    for index in range(rounds):
        for opponent_index, opponent in enumerate(("rule", "rl")):
            for distance_index, distance in enumerate(DISTANCES_FT):
                case_seed = seed + index * 100 + opponent_index * 10 + distance_index
                for side in sides:
                    for actor in actors:
                        cases.append(Case(index, opponent, distance, side, case_seed, actor))
    return cases


def load_artifacts(repair_root):
    path = Path(repair_root) / "artifacts.py"
    spec = importlib.util.spec_from_file_location("campaign_repair_artifacts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capture_sources(repair_root):
    artifact = load_artifacts(repair_root)
    hashes = artifact.contract_sources()
    hashes["repair/artifacts.py"] = file_hash(Path(repair_root) / "artifacts.py")
    hashes["probe/benchmark_probe.py"] = file_hash(__file__)
    return hashes


def bundle_hashes(bundle):
    if bundle is None:
        return None
    path = Path(bundle)
    return {name: file_hash(path / name) for name in ("model.zip", "manifest.json")}


def load_runtime(repair_root):
    # Worker processes have a fresh module namespace. Verify the controller was
    # resolved from the frozen repair directory despite the legacy path inserts.
    sys.path.insert(0, str(Path(repair_root).resolve()))
    import numpy as np
    import env as repair_env
    import artifacts
    import controller
    from duel_lab import DiagnosticJudge, RuleFighter
    from combat_v3.interface import PacketController
    if Path(controller.__file__).resolve() != (Path(repair_root) / "controller.py").resolve():
        raise RuntimeError("RepairController resolved outside the frozen repair root")
    from types import SimpleNamespace
    return SimpleNamespace(np=np, env=repair_env, artifacts=artifacts,
                           RepairController=repair_env.RepairController,
                           JsbsimFdm=repair_env.JsbsimFdm,
                           DiagnosticJudge=DiagnosticJudge, RuleFighter=RuleFighter,
                           PacketController=PacketController,
                           simulator_observation=repair_env.simulator_observation,
                           relative_geometry=repair_env.relative_geometry,
                           policy_state=repair_env.policy_state,
                           geometry_from_observation=repair_env.geometry_from_observation,
                           precision_terms=repair_env.precision_terms)


def cross_track_m(blue, red):
    latitude = math.radians(float(red[0]))
    north = math.radians(float(blue[0]) - float(red[0])) * 6378137
    east = math.radians(float(blue[1]) - float(red[1])) * 6378137 * math.cos(latitude)
    heading = math.radians(float(red[5]))
    return -north * math.sin(heading) + east * math.cos(heading)


def reset_initial_side(environment, side, runtime):
    """Apply the side transform before the first tick, then rebuild cached state."""
    if side not in ("normal", "mirrored") or environment.current_step != 0:
        raise ValueError("Initial side can only be set immediately after reset")
    blue_before = runtime.simulator_observation(environment.fdm1, environment.fdm2)
    red_before = runtime.simulator_observation(environment.fdm2, environment.fdm1)
    normal_cross = cross_track_m(blue_before, red_before)
    normal_distance = float(runtime.relative_geometry(environment.fdm1, environment.fdm2)["distance_m"])
    if side == "mirrored":
        blue_ic = dict(environment.fdm1.param)
        red_ic = environment.fdm2.param
        blue_ic["fdm_ic_lat"] = 2 * red_ic["fdm_ic_lat"] - blue_ic["fdm_ic_lat"]
        blue_ic["fdm_ic_long"] = 2 * red_ic["fdm_ic_long"] - blue_ic["fdm_ic_long"]
        blue_ic["fdm_id"] = 1
        environment.fdm1 = runtime.JsbsimFdm(**blue_ic)
    blue = runtime.simulator_observation(environment.fdm1, environment.fdm2)
    red = runtime.simulator_observation(environment.fdm2, environment.fdm1)
    geometry = runtime.relative_geometry(environment.fdm1, environment.fdm2)
    side_cross = cross_track_m(blue, red)
    if side == "mirrored":
        if normal_cross * side_cross >= 0 or abs(normal_cross) < 1:
            raise RuntimeError("Mirror failed to reverse the initial left/right side")
        if abs(float(geometry["distance_m"]) - normal_distance) > max(1., normal_distance * .01):
            raise RuntimeError("Mirror changed initial distance by more than 1 percent")
        if any(abs(float(blue[i]) - float(blue_before[i])) > 1e-5 for i in (2, 3, 4, 5, 12)):
            raise RuntimeError("Mirror altered blue altitude, attitude, or calibrated airspeed")
        if any(abs(float(red[i]) - float(red_before[i])) > 1e-9 for i in range(20)):
            raise RuntimeError("Mirror altered the red initial aircraft state")
    environment.packet_controller = runtime.RepairController(environment.settings, "repair")
    environment.red_packet_controller = runtime.PacketController(environment.settings)
    environment.red_fighter = runtime.RuleFighter(environment.settings, float(red[2]) * .3048,
                                                 environment.np_random)
    environment.red_altitude_m = float(red[2]) * .3048
    environment.geometry = geometry
    environment.prev_potential = environment._potential(geometry)
    legal_geometry = runtime.geometry_from_observation(blue)
    environment.precision_previous = runtime.precision_terms(legal_geometry)[0]
    environment.min_altitude_m = float(environment.fdm1.fdm["position/h-agl-ft"]) * .3048
    environment.judge = runtime.DiagnosticJudge(environment.settings["reference_score_weights"],
                                                environment.attack_angle)
    environment.blue_frames = environment.red_frames = environment.over_g_frames = environment.guard_frames = 0
    environment.p2_mode, environment.p2_guard = "initializing", False
    observation = runtime.policy_state(blue)
    if len(observation) != 20 or not all(math.isfinite(float(x)) for x in observation):
        raise RuntimeError("Initial policy observation is invalid")
    audit = {
        "side": side, "distance_m": float(geometry["distance_m"]),
        "cross_track_m": side_cross, "normal_cross_track_m": normal_cross,
        "blue_own20_audit_only": [float(x) for x in blue[:20]],
        "red_own20_audit_only": [float(x) for x in red[:20]],
        "policy_state20": [float(x) for x in observation],
        "mirror_is_official_role_swap": False,
    }
    return observation, audit


METRIC_DIRECTIONS = {
    "kills": 1, "deaths": -1, "own_crashes": -1, "enemy_crashes": 1,
    "survival": 1, "attack_seconds": 1, "enemy_attack_seconds": -1,
    "over_9g_seconds": -1, "min_altitude_m": 1,
}


def case_metrics(info):
    return {
        "kills": int(info.get("is_kill", 0)), "deaths": int(info.get("was_hit", 0)),
        "own_crashes": int(info.get("own_crash", 0)),
        "enemy_crashes": int(info.get("enemy_crash", 0)),
        "survival": int(info.get("survived", 0)),
        "attack_seconds": float(info.get("attack_seconds", 0)),
        "enemy_attack_seconds": float(info.get("enemy_attack_seconds", 0)),
        "over_9g_seconds": float(info.get("over_9g_seconds", 0)),
        "min_altitude_m": float(info.get("min_altitude_m", 0)),
    }


def summarize(results, planned, has_candidate):
    eligible = [row for row in results if row.get("score_eligible") is True]
    totals = {}
    for actor in ("guide", "candidate") if has_candidate else ("guide",):
        rows = [row for row in eligible if row["case"]["actor"] == actor]
        totals[actor] = {"completed_cases": len(rows), "kills": 0, "deaths": 0,
                         "own_crashes": 0, "enemy_crashes": 0, "survival": 0,
                         "attack_seconds": 0., "enemy_attack_seconds": 0.,
                         "over_9g_seconds": 0., "min_altitude_m": None}
        for row in rows:
            for metric in METRIC_DIRECTIONS:
                value = row["metrics"][metric]
                if metric == "min_altitude_m":
                    previous = totals[actor][metric]
                    totals[actor][metric] = value if previous is None else min(previous, value)
                else:
                    totals[actor][metric] += value
        count = len(rows)
        totals[actor]["mean_attack_seconds"] = totals[actor]["attack_seconds"] / count if count else None
        totals[actor]["mean_enemy_attack_seconds"] = totals[actor]["enemy_attack_seconds"] / count if count else None
        totals[actor]["survival_rate"] = totals[actor]["survival"] / count if count else None
    changes = {key: {"improved": 0, "regressed": 0, "tied": 0} for key in METRIC_DIRECTIONS}
    grouped = {}
    for row in results:
        grouped.setdefault(row["pair_key"], {})[row["case"]["actor"]] = row
    matched = 0
    excluded = []
    if has_candidate:
        expected_pairs = list(dict.fromkeys(case.pair_key for case in planned))
        for pair_key in expected_pairs:
            pair = grouped.get(pair_key, {})
            if not all(pair.get(actor, {}).get("score_eligible") is True for actor in ("guide", "candidate")):
                excluded.append({"pair_key": pair_key, "reason": "missing_or_incomplete_case"})
                continue
            guide, candidate = pair["guide"], pair["candidate"]
            if not guide.get("initial_sha256") or guide["initial_sha256"] != candidate.get("initial_sha256"):
                excluded.append({"pair_key": pair_key, "reason": "initial_state_hash_mismatch"})
                continue
            matched += 1
            for metric, direction in METRIC_DIRECTIONS.items():
                delta = (candidate["metrics"][metric] - guide["metrics"][metric]) * direction
                label = "tied" if math.isclose(delta, 0., abs_tol=1e-9) else ("improved" if delta > 0 else "regressed")
                changes[metric][label] += 1
    summary = {
        "score_eligible_cases": len(eligible), "planned_cases": len(planned),
        "complete": len(eligible) == len(planned) and not excluded,
        "totals": totals, "paired_completed": matched,
        "paired_metric_changes": changes if has_candidate else None,
        "paired_excluded": excluded,
        "interpretation": "Local simulation only. Metric directions are diagnostic; no deployment decision or official win probability.",
    }
    # Direct aliases let the campaign review consume means without mistaking
    # unequal sample counts for progress. Completeness remains a required gate.
    summary.update(totals)
    return summary


def stopped(output):
    return (Path(output) / "STOP").exists() or (ROOT / "STOP").exists()


def wait_process(process, *, timeout_s, stop_check=lambda: False, tick=lambda: None,
                 clock=time.monotonic, sleep=time.sleep):
    """Hard subprocess bound; returns a reason without treating partial data as a win."""
    began = clock()
    while process.poll() is None:
        if stop_check():
            reason = "stopped"
            break
        if clock() - began >= timeout_s:
            reason = "wall_timeout"
            break
        tick()
        sleep(.2)
    else:
        return "exited"
    # Give the worker a brief chance to publish partial state after cooperative
    # STOP. Timeouts terminate immediately and cannot exceed the case allowance.
    if reason == "stopped":
        try:
            process.wait(timeout=2)
            return reason
        except subprocess.TimeoutExpired:
            pass
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)
    return reason


def run_worker(input_file):
    spec = json.loads(Path(input_file).read_text(encoding="utf-8"))
    folder = Path(input_file).parent
    case = Case(**spec["case"])
    began = time.monotonic()
    result = {"case": asdict(case), "case_id": case.case_id, "pair_key": case.pair_key,
              "status": "initializing", "score_eligible": False,
              "full_round_completed": False, "official_validation": False,
              "steps": 0, "requested_max_steps": spec["max_steps"],
              "initial_sha256": None, "metrics": None}
    environment = None
    last_info = None

    def heartbeat(phase):
        atomic_json(folder / "heartbeat.json", {
            "updated_at": utc_now(), "phase": phase, "case_id": case.case_id,
            "steps": result["steps"], "wall_seconds": time.monotonic() - began,
            "pid": os.getpid(), "official_validation": False,
        })

    heartbeat("loading")
    try:
        if capture_sources(spec["repair_root"]) != spec["source_sha256"]:
            raise RuntimeError("Environment sources changed after benchmark planning")
        runtime = load_runtime(spec["repair_root"])
        if Path(runtime.env.DEFAULT_BUNDLE).resolve() != DEFAULT_RED_BUNDLE.resolve():
            raise RuntimeError("Frozen red DEFAULT_BUNDLE differs from benchmark configuration")
        if bundle_hashes(DEFAULT_RED_BUNDLE) != spec["red_bundle_sha256"]:
            raise RuntimeError("Frozen red bundle changed after benchmark planning")
        if bundle_hashes(spec["bundle"]) != spec["candidate_bundle_sha256"]:
            raise RuntimeError("Candidate bundle changed after benchmark planning")
        policy = runtime.artifacts.load_policy(Path(spec["bundle"])) if case.actor == "candidate" else None
        repeat = int(getattr(policy, "combat_fix_manifest", {}).get("decision_repeat", 1)) if policy else 1
        if repeat < 1:
            raise RuntimeError("Invalid policy decision repeat")
        red = runtime.artifacts.load_policy(runtime.env.DEFAULT_BUNDLE) if case.opponent == "rl" else None
        environment = runtime.env.RepairDuel(p2=case.opponent, policy=red, attack_angle=1.,
            max_steps=spec["max_steps"], distance_ft=case.distance_ft,
            controller="repair", stage="official")
        environment.reset(seed=case.seed)
        observation, initial = reset_initial_side(environment, case.side, runtime)
        result.update(initial=initial, initial_sha256=json_hash(initial),
                      decision_repeat=repeat, status="running")
        atomic_json(folder / "result.json", result)
        heartbeat("simulating")
        last_info = environment._info()
        columns = ("legal_obs26", "body_az_deg_legal", "body_el_deg_legal", "heading_error_deg_legal", "world_elevation_deg_legal", "command_bank_target_before_tick", "command_pitch_target_before_tick", "command_speed_target_before_tick", "own_roll_deg_after_tick", "own_pitch_deg_after_tick", "own_alpha_deg_after_tick", "tick", "simulation_seconds", "distance_m", "blue_angle_deg_judge_only",
                   "red_angle_deg_judge_only", "altitude_m", "load_factor", "attack_seconds",
                   "enemy_attack_seconds", "over_9g_seconds", "controller_mode")
        last_heartbeat = time.monotonic()
        reason = "max_steps"
        terminated = truncated = False
        with (folder / "duel.acmi").open("w", encoding="utf-8") as acmi, \
                (folder / "telemetry.csv").open("w", encoding="utf-8", newline="") as telemetry:
            acmi.write("FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime=" +
                       datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n")
            acmi.write("1,Type=Air+FixedWing,Name=F16,CallSign=P1 " + case.actor + ",Color=Blue\n")
            acmi.write("2,Type=Air+FixedWing,Name=F16,CallSign=P2 " + case.opponent + ",Color=Red\n")
            environment.write_frame(acmi)
            writer = csv.DictWriter(telemetry, fieldnames=columns)
            writer.writeheader()
            action = runtime.np.zeros(4, dtype=runtime.np.float32)
            for index in range(spec["max_steps"]):
                if stopped(spec["out"]):
                    reason = "stopped"
                    break
                if time.monotonic() - began >= spec["case_seconds"]:
                    reason = "wall_timeout"
                    break
                if index % repeat == 0 and policy is not None:
                    action = policy.predict(observation, deterministic=True)[0]
                observation, _, terminated, truncated, last_info = environment.step(action)
                result["steps"] = index + 1
                if result["steps"] % 30 == 0 or terminated or truncated:
                    environment.write_frame(acmi)
                if result["steps"] % 6 == 0 or terminated or truncated:
                    legal_obs = runtime.simulator_observation(environment.fdm1, environment.fdm2)
                    legal_geo = runtime.geometry_from_observation(legal_obs)
                    heading_error = (legal_geo["bearing_deg"] - float(legal_obs[5]) + 180) % 360 - 180
                    writer.writerow({
                        "legal_obs26": json.dumps([float(x) for x in legal_obs]),
                        "body_az_deg_legal": legal_geo["blue_az_deg"],
                        "body_el_deg_legal": legal_geo["blue_el_deg"],
                        "heading_error_deg_legal": heading_error,
                        "world_elevation_deg_legal": legal_geo["elevation_deg"],
                        "command_bank_target_before_tick": getattr(environment.packet_controller, "bank_target", None),
                        "command_pitch_target_before_tick": getattr(environment.packet_controller, "pitch_target", None),
                        "command_speed_target_before_tick": getattr(environment.packet_controller, "speed_target", None),
                        "own_roll_deg_after_tick": float(legal_obs[3]),
                        "own_pitch_deg_after_tick": float(legal_obs[4]),
                        "own_alpha_deg_after_tick": float(legal_obs[18]),
                        "tick": result["steps"], "simulation_seconds": result["steps"] / 60,
                        "distance_m": last_info["distance"],
                        "blue_angle_deg_judge_only": last_info["blue_angle_deg"],
                        "red_angle_deg_judge_only": last_info["red_angle_deg"],
                        **{key: last_info.get(key) for key in ("altitude_m", "load_factor", "attack_seconds",
                           "enemy_attack_seconds", "over_9g_seconds", "controller_mode")},
                    })
                if time.monotonic() - last_heartbeat >= 2:
                    heartbeat("simulating")
                    result.update(metrics=case_metrics(last_info), outcome=last_info["outcome"],
                                  wall_seconds=time.monotonic() - began)
                    atomic_json(folder / "result.json", result)
                    acmi.flush()
                    telemetry.flush()
                    last_heartbeat = time.monotonic()
                if terminated or truncated:
                    reason = "legal_termination" if terminated else "round_horizon"
                    break
            if result["steps"] and result["steps"] % 30:
                environment.write_frame(acmi)
        full = bool(terminated or (truncated and spec["max_steps"] == ROUND_TICKS))
        eligible = full and spec["max_steps"] == ROUND_TICKS and reason not in ("stopped", "wall_timeout")
        if capture_sources(spec["repair_root"]) != spec["source_sha256"]:
            raise RuntimeError("Environment sources changed during a case")
        if bundle_hashes(DEFAULT_RED_BUNDLE) != spec["red_bundle_sha256"] or \
                bundle_hashes(spec["bundle"]) != spec["candidate_bundle_sha256"]:
            raise RuntimeError("Model bundle changed during a case")
        result.update(status="completed" if eligible else "partial", stop_reason=reason,
                      full_round_completed=full, score_eligible=eligible,
                      metrics=case_metrics(last_info), outcome=last_info["outcome"],
                      estimated_winner_proxy=last_info.get("estimated_winner"),
                      proxy_is_official_result=False,
                      wall_seconds=time.monotonic() - began,
                      acmi=str(folder / "duel.acmi"), telemetry=str(folder / "telemetry.csv"))
    except BaseException as error:
        import traceback
        traceback.print_exc()
        result.update(status="failed", score_eligible=False, error=repr(error),
                      wall_seconds=time.monotonic() - began)
        if last_info is not None:
            result.update(metrics=case_metrics(last_info), outcome=last_info["outcome"])
    finally:
        if environment is not None:
            environment.close()
        atomic_json(folder / "result.json", result)
        heartbeat(result["status"])
    return 0 if result["status"] in ("completed", "partial") else 1


def run_benchmark(args):
    began = time.monotonic()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "report.json").exists():
        raise ValueError("Output already contains report.json; use a new directory")
    repair_root = args.repair_root.resolve()
    candidate = args.bundle.resolve() if args.bundle else None
    cases = plan_cases(args.rounds, args.seed, args.mirror, candidate is not None)
    sources = capture_sources(repair_root)
    candidate_hashes = bundle_hashes(candidate)
    red_hashes = bundle_hashes(DEFAULT_RED_BUNDLE)
    report = {
        "format": "campaign_paired_benchmark_v1", "status": "running",
        "started_at": utc_now(), "official_validation": False, "benchmark_complete": False,
        "description": "Local left/right initial geometry test; not official Host P1/P2 role swap.",
        "attack_angle_deg": 1., "physics_hz": 60, "round_ticks": ROUND_TICKS,
        "requested_max_steps": args.max_steps, "rounds": args.rounds, "seed": args.seed,
        "mirror": args.mirror, "repair_root": str(repair_root),
        "candidate_bundle": str(candidate) if candidate else None,
        "red_bundle": str(DEFAULT_RED_BUNDLE), "source_sha256": sources,
        "candidate_bundle_sha256": candidate_hashes, "red_bundle_sha256": red_hashes,
        "benchmark_sha256": file_hash(__file__), "case_wall_seconds": args.case_seconds,
        "max_minutes": args.max_minutes, "planned_cases": len(cases), "cases": [],
        "policy_inputs": "Official OWN20+ENEMY6 converted by policy_state to 20 values; hidden enemy attitude is judge/logging only.",
    }

    def save():
        report["wall_seconds"] = time.monotonic() - began
        report["summary"] = summarize(report["cases"], cases, candidate is not None)
        report["benchmark_complete"] = report["summary"]["complete"]
        report["gate"] = "review_pending" if report["benchmark_complete"] and candidate is not None else (
            "baseline_only" if report["benchmark_complete"] else "incomplete")
        report["updated_at"] = utc_now()
        atomic_json(output / "report.json", report)

    save()
    active = None
    try:
        for case in cases:
            if stopped(output):
                report.update(status="stopped", stop_reason="STOP")
                break
            remaining = args.max_minutes * 60 - (time.monotonic() - began)
            if remaining <= 0:
                report.update(status="partial", stop_reason="benchmark_wall_limit")
                break
            folder = output / "cases" / case.case_id
            folder.mkdir(parents=True, exist_ok=False)
            wall_limit = min(args.case_seconds, remaining)
            spec = {"case": asdict(case), "out": str(output), "repair_root": str(repair_root),
                    "bundle": str(candidate) if candidate else None, "max_steps": args.max_steps,
                    "case_seconds": wall_limit, "source_sha256": sources,
                    "candidate_bundle_sha256": candidate_hashes, "red_bundle_sha256": red_hashes}
            atomic_json(folder / "input.json", spec)
            current = {"case_id": case.case_id, "case": asdict(case), "started_at": utc_now(),
                       "completed_cases": len(report["cases"]), "planned_cases": len(cases),
                       "worker_heartbeat": str(folder / "heartbeat.json"), "case_wall_limit": wall_limit}
            atomic_json(output / "heartbeat.json", current)
            with (folder / "worker.log").open("w", encoding="utf-8") as log:
                active = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                    "--_worker", str(folder / "input.json")], stdout=log, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                current["worker_pid"] = active.pid
                last_write = [0.]

                def tick():
                    if time.monotonic() - last_write[0] >= 2:
                        current["updated_at"] = utc_now()
                        current["benchmark_wall_seconds"] = time.monotonic() - began
                        atomic_json(output / "heartbeat.json", current)
                        last_write[0] = time.monotonic()

                reason = wait_process(active, timeout_s=wall_limit, stop_check=lambda: stopped(output), tick=tick)
                code = active.returncode
                active = None
            result_path = folder / "result.json"
            result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {
                "case": asdict(case), "case_id": case.case_id, "pair_key": case.pair_key,
                "status": "failed", "score_eligible": False, "full_round_completed": False,
                "steps": 0, "metrics": None, "initial_sha256": None,
            }
            if reason != "exited" or code != 0:
                result.update(status="partial" if reason in ("stopped", "wall_timeout") else "failed",
                              score_eligible=False, full_round_completed=False,
                              stop_reason=reason, worker_exit_code=code)
                atomic_json(result_path, result)
            report["cases"].append(result)
            save()
            print(f"{len(report['cases'])}/{len(cases)} {case.case_id}: {result['status']} ticks={result.get('steps', 0)}", flush=True)
            if reason == "stopped":
                report.update(status="stopped", stop_reason="STOP")
                break
        else:
            report["status"] = "completed" if report["benchmark_complete"] else "partial"
            if args.max_steps < ROUND_TICKS:
                report["stop_reason"] = "smoke_horizon_not_full_evaluation"
    except KeyboardInterrupt:
        report.update(status="stopped", stop_reason="keyboard_interrupt")
    except Exception as error:
        report.update(status="failed", error=repr(error))
    finally:
        if active is not None and active.poll() is None:
            active.terminate()
            try:
                active.wait(timeout=3)
            except subprocess.TimeoutExpired:
                active.kill()
                active.wait(timeout=3)
        report["all_cases_attempted"] = len(report["cases"]) == len(cases)
        report["finished_at"] = utc_now()
        save()
        atomic_json(output / "heartbeat.json", {"phase": report["status"], "updated_at": utc_now(),
                    "completed_cases": len(report["cases"]), "planned_cases": len(cases),
                    "benchmark_complete": report["benchmark_complete"]})
    print(str(output / "report.json"), flush=True)
    return 0 if report["status"] == "completed" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description="公平配對的本地JSBSim評估；不是官方裁判或自動部署")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--repair-root", type=Path, default=DEFAULT_REPAIR_ROOT)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--seed", type=int, default=2026101100)
    parser.add_argument("--max-minutes", type=float, default=90.)
    parser.add_argument("--mirror", choices=("both", "normal"), default="both")
    parser.add_argument("--max-steps", type=int, default=ROUND_TICKS,
                        help="少於18000只作smoke，永不標示完整評估")
    parser.add_argument("--case-seconds", type=float, default=CASE_WALL_SECONDS)
    parser.add_argument("--_worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args._worker:
        return run_worker(args._worker)
    if args.out is None:
        parser.error("--out is required")
    if args.rounds < 1 or args.max_minutes <= 0 or not 1 <= args.max_steps <= ROUND_TICKS:
        parser.error("rounds/max-minutes must be positive; max-steps must be 1..18000")
    if not 0 < args.case_seconds <= CASE_WALL_SECONDS:
        parser.error("case-seconds must be positive and no more than 150")
    return run_benchmark(args)


if __name__ == "__main__":
    raise SystemExit(main())
