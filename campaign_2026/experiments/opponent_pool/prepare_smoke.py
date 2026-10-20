"""Read-only protocol/adapter preparation; this module has no simulator launcher.

The historical 144-case bank80 protocol and its POOL_FREEZE remain unchanged.
The new plan exercises the current guide against frozen opponents for 300 ticks
only, including guide-v-guide on both initial sides. Plans do not reserve seeds
or establish combat performance. FGFDMExec is forbidden during adapter checks.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import math
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import patch

EXP = Path(__file__).resolve().parent
ROOT = EXP.parents[1]
OPPONENT_IDS = ("rule", "rl", "repair_guide", "rule_bank60")
DISTANCES = (3000, 6000, 9000)
SIDES = ("normal", "mirrored")
SMOKE_TICKS = 300
sys.path.insert(0, str(EXP))
import benchmark_pool as bench


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def plan_cases(seed=2026102400):
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**31 - 40:
        raise ValueError("Seed must be a supported nonnegative integer")
    cases = []
    for opponent_index, opponent in enumerate(OPPONENT_IDS):
        for distance_index, distance in enumerate(DISTANCES):
            case_seed = seed + opponent_index * 10 + distance_index
            for side in SIDES:
                cases.append({
                    "case_id": f"smoke_{opponent}_{distance}_{side}_{case_seed}",
                    "pair_key": f"smoke_{opponent}_{distance}_{case_seed}",
                    "opponent_id": opponent, "distance_ft": distance, "side": side,
                    "seed": case_seed, "blue_controller": "repair_guide",
                    "red_controller": opponent, "max_steps": SMOKE_TICKS,
                    "score_eligible": False, "self_play": opponent == "repair_guide",
                })
    return cases


def assert_plan(cases):
    if len(cases) != 24 or len({row["case_id"] for row in cases}) != 24:
        raise ValueError("Smoke requires exactly 24 unique cases")
    groups = defaultdict(list)
    for row in cases:
        if row["opponent_id"] not in OPPONENT_IDS or row["distance_ft"] not in DISTANCES or row["side"] not in SIDES:
            raise ValueError("Unrecognized opponent/distance/side")
        if row["max_steps"] != SMOKE_TICKS or row["score_eligible"] is not False:
            raise ValueError("Smoke must never become a full-round score")
        if row["blue_controller"] != "repair_guide" or row["red_controller"] != row["opponent_id"]:
            raise ValueError("Controller mismatch")
        if row["self_play"] != (row["opponent_id"] == "repair_guide"):
            raise ValueError("Incorrect self-play label")
        groups[row["pair_key"]].append(row)
    if len(groups) != 12:
        raise ValueError("Expected 12 left/right geometry pairs")
    for pair in groups.values():
        if len(pair) != 2 or {row["side"] for row in pair} != set(SIDES):
            raise ValueError("Incomplete or duplicated geometry pair")
        for key in ("opponent_id", "distance_ft", "seed", "blue_controller", "red_controller"):
            if pair[0][key] != pair[1][key]:
                raise ValueError("Unfair geometry pair: " + key)
    counts = Counter((row["opponent_id"], row["distance_ft"], row["side"]) for row in cases)
    if any(counts[(opponent, distance, side)] != 1 for opponent in OPPONENT_IDS for distance in DISTANCES for side in SIDES):
        raise ValueError("Unbalanced opponent grid")
    return {"cases": 24, "geometry_pairs": 12, "distinct_seeds": 12,
            "self_play_cases": 6, "balanced": True}


def seed_status(registry, cases):
    requested = {row["seed"] for row in cases}
    seen = {int(value) for value in registry.get("observed_seeds", {})}
    for trial in registry.get("trials", {}).values():
        seen.update(int(value) for value in trial["seeds"])
    holdout = {int(value) for value in registry.get("reserved_holdout_seeds", [])}
    return {"requested": sorted(requested), "observed_or_attempted_collisions": sorted(requested & seen),
            "holdout_collisions": sorted(requested & holdout),
            "fresh_relative_to_registry": not bool(requested & (seen | holdout)),
            "seed_trials_claimed": 0, "seed_role": "planned_development_diagnostic_not_holdout"}


def frozen_status():
    frozen = read(EXP / "POOL_FREEZE.json")
    preparation = read(EXP / "PREPARATION.json")
    actual = bench.capture_sources(ROOT / "repair_v1")
    expected = frozen["source_sha256"]
    changed = [key for key in sorted(set(expected) | set(actual)) if expected.get(key) != actual.get(key)]
    pool = read(EXP / "OPPONENTS.json")
    ids = tuple(row["id"] for row in pool["opponents"])
    if ids != OPPONENT_IDS:
        changed.append("opponent_ids")
    if preparation["pool_manifest_sha256"] != bench.file_hash(EXP / "POOL_FREEZE.json"):
        changed.append("preparation_pool_manifest_sha256")
    red_expected = read(ROOT / "candidates" / "near_bank80_20261012" / "report.json")["red_bundle_sha256"]
    red_actual = bench.bundle_hashes(bench.DEFAULT_RED_BUNDLE)
    if red_actual != red_expected:
        changed.append("frozen_red_bundle")
    return {"verified": not changed, "changed": changed, "source_sha256": actual,
            "pool_manifest_sha256": bench.file_hash(EXP / "POOL_FREEZE.json"),
            "preparation_sha256": bench.file_hash(EXP / "PREPARATION.json"),
            "opponents_manifest_sha256": bench.file_hash(EXP / "OPPONENTS.json"),
            "red_bundle_sha256": red_actual}


def rule_variant_check():
    source = (EXP / "opponents.py").read_text(encoding="utf-8-sig")
    restored = source.replace("class RuleBank60:", "class RuleFighter:").replace(
        "heading_error, -60, 60", "heading_error, -72, 72")
    original_path = Path(r"E:\ai_pilot\autopilot\opponent_lab\duel_lab.py")
    original_tree = ast.parse(original_path.read_text(encoding="utf-8-sig"))
    restored_tree = ast.parse(restored)
    def tree_class(tree):
        return ast.dump(next(item for item in tree.body if isinstance(item, ast.ClassDef)
                             and item.name == "RuleFighter"), include_attributes=False)
    if tree_class(original_tree) != tree_class(restored_tree):
        raise ValueError("RuleBank60 differs from original beyond its declared far bank ceiling")
    return {"rule_bank60_single_declared_difference": True,
            "structurally_distinct_families": ["rule_tracking", "frozen_residual_sac", "repair_guide"],
            "rule_bank60_is_parameter_variant": True,
            "opponent_strength_verified": False}


def old_launcher_status():
    # This is a status report only. Importing launch_pool would provide a
    # launcher, so read its prerequisite evidence directly and keep this module
    # unable to invoke its main/preflight/worker paths.
    pointer = read(ROOT / "research_latest.json")
    comparison_path = pointer.get("comparison")
    comparison = read(comparison_path) if comparison_path and Path(comparison_path).is_file() else {}
    ready = (pointer.get("experiment") == "fresh_bank80" and
             comparison.get("verified_comparison") is True and
             comparison.get("actual_parent_exit_code") == 0 and
             comparison.get("eligible_cases") == 24 and comparison.get("matched_pairs") == 12 and
             all(comparison.get("gates", {}).get(key) is True for key in ("metric", "outcome_safety", "per_opponent")))
    return {"old_bank80_expansion_prerequisite_passed": bool(ready),
            "current_comparison_gate": comparison.get("gate"),
            "current_comparison": comparison_path,
            "bank80_is_not_the_smoke_candidate": True,
            "legacy_launcher_hard_quota_guard": True,
            "legacy_launcher_hard_daily_limit_hours": 6,
            "recorded_current_quota_policy": pointer.get("codex_quota_policy"),
            "policy_alignment_review_required_before_execution": True}


def offline_geometry_checks():
    """Exercise the actual reset helper on explicit non-physics plane fixtures."""
    class PlaneFixture:
        def __init__(self, **params):
            self.param = params
            self.fdm = {"position/h-agl-ft": params["fdm_ic_h"]}

    def observation(own, enemy):
        result = [0.] * 26
        result[:3] = [own.param["fdm_ic_lat"], own.param["fdm_ic_long"], own.param["fdm_ic_h"]]
        result[3:6] = [0., 0., own.param["fdm_ic_psi"]]
        result[12] = own.param["fdm_ic_v"]
        result[20:23] = [enemy.param["fdm_ic_lat"], enemy.param["fdm_ic_long"], enemy.param["fdm_ic_h"]]
        return result

    def geometry(blue, red):
        b, r = observation(blue, red), observation(red, blue)
        north = math.radians(b[0] - r[0]) * 6378137
        east = math.radians(b[1] - r[1]) * 6378137 * math.cos(math.radians(r[0]))
        return {"distance_m": math.hypot(north, east)}

    runtime = SimpleNamespace(JsbsimFdm=PlaneFixture, simulator_observation=observation,
        relative_geometry=geometry, policy_state=lambda packet: packet[:20],
        RepairController=lambda *args: object(), PacketController=lambda *args: object(),
        RuleFighter=lambda *args: object(), DiagnosticJudge=lambda *args: object(),
        geometry_from_observation=lambda packet: {}, precision_terms=lambda geo: (.5, 0, 0))
    count = 0
    for distance_ft in DISTANCES:
        for heading in (0., 42., 180., 315.):
            common = {"fdm_ic_h": 15000., "fdm_ic_v": 340., "fdm_ic_phi": 0., "fdm_ic_theta": 0.}
            bearing = math.radians(heading - 90)
            distance = distance_ft * .3048
            latitude = 23. + math.degrees(math.cos(bearing) * distance / 6378137)
            longitude = 121. + math.degrees(math.sin(bearing) * distance / (6378137 * math.cos(math.radians(23.))))
            red = PlaneFixture(fdm_id=2, fdm_ic_lat=23., fdm_ic_long=121., fdm_ic_psi=heading, **common)
            blue = PlaneFixture(fdm_id=1, fdm_ic_lat=latitude, fdm_ic_long=longitude,
                                fdm_ic_psi=(heading + 180) % 360, **common)
            env = SimpleNamespace(fdm1=blue, fdm2=red, current_step=0, np_random=object(),
                settings={"reference_score_weights": {}}, attack_angle=1., _potential=lambda geo: .75)
            _, audit = bench.reset_initial_side(env, "mirrored", runtime)
            if not audit["cross_track_m"] * audit["normal_cross_track_m"] < 0:
                raise RuntimeError("Actual mirror helper did not reverse the fixture side")
            if env.prev_potential != .75 or env.precision_previous != .5 or env.fdm2 is not red:
                raise RuntimeError("Actual mirror helper did not synchronize its cached state")
            count += 1
    return {"passed": True, "fixture_cases": count,
            "actual_reset_helper_sha256": hashlib.sha256(ast.dump(next(
                item for item in ast.parse((EXP / "benchmark_pool.py").read_text(encoding="utf-8-sig")).body
                if isinstance(item, ast.FunctionDef) and item.name == "reset_initial_side"),
                include_attributes=False).encode()).hexdigest(),
            "scope": "Non-physics fixtures test the actual mirror/reset helper; no JSBSim initialization or trajectory."}


def offline_adapter_checks():
    import jsbsim
    import numpy as np
    # This is an executable proof of the no-FDM claim, not merely a flag in JSON.
    # Model inference/controller construction are allowed; aircraft creation is not.
    with patch.object(jsbsim, "FGFDMExec", side_effect=RuntimeError("FDM forbidden during offline preparation")) as fdm_guard:
        runtime = bench.load_runtime(ROOT / "repair_v1")
        import opponents
        if Path(opponents.__file__).resolve() != (EXP / "opponents.py").resolve():
            raise RuntimeError("Wrong opponent adapter module")
        settings = read(runtime.artifacts.BASE / "combat_v3" / "config.json")
        from duel_lab import RuleFighter
        policy = runtime.artifacts.load_policy(runtime.env.DEFAULT_BUNDLE, device="cpu")
        outputs = []
        source_run = ROOT / "experiments" / "near_bank80" / "run_20261012_2050" / "cases"
        for distance in DISTANCES:
            for side in SIDES:
                result = read(source_run / f"r000_rule_{distance}_{side}_202610110{DISTANCES.index(distance)}_guide" / "result.json")
                initial = result["initial"]
                own = initial["red_own20_audit_only"]
                other = initial["blue_own20_audit_only"]
                observation = np.array(own + other[:3] + other[6:9], dtype=float)
                if observation.shape != (26,) or not np.isfinite(observation).all():
                    raise RuntimeError("Saved legal packet malformed")
                commands = {}
                for opponent_id in OPPONENT_IDS:
                    rng = np.random.default_rng(12345)
                    if opponent_id == "rule":
                        command = RuleFighter(settings, own[2] * .3048, rng).act(observation, 0.)
                    elif opponent_id == "rule_bank60":
                        command = opponents.RuleBank60(settings, own[2] * .3048, rng).act(observation, 0.)
                    elif opponent_id == "repair_guide":
                        command = opponents.RepairGuideFighter(settings).act(observation, 0.)
                        expected, _ = runtime.RepairController(settings, "repair").act(observation, residual=None)
                        np.testing.assert_array_equal(command, expected)
                    else:
                        residual, _ = policy.predict(runtime.policy_state(observation), deterministic=True)
                        command, _ = runtime.PacketController(settings).act(observation, residual)
                    command = np.asarray(command)
                    if command.shape != (4,) or not np.isfinite(command).all() or not (
                            (command[:3] >= -1).all() and (command[:3] <= 1).all() and 0 <= command[3] <= 1):
                        raise RuntimeError("Invalid legal opponent command: " + opponent_id)
                    commands[opponent_id] = [float(value) for value in command]
                outputs.append({"distance_ft": distance, "side": side,
                                "legal_observation_sha256": bench.json_hash(observation.tolist()),
                                "command_sha256": {key: bench.json_hash(value) for key, value in commands.items()}})
        if fdm_guard.call_count:
            raise RuntimeError("Offline check attempted aircraft initialization")
    return {"passed": True, "saved_legal_packets": 6, "opponent_commands_checked": 24,
            "self_play_controller_equals_reference": True, "fdm_constructor_calls": 0,
            "source_of_inputs": str(source_run), "observations": outputs,
            "scope": "One initial command on recorded legal packets. No time evolution or performance result."}


def prepare(seed=2026102400, adapter_checks=True):
    cases = plan_cases(seed)
    balance = assert_plan(cases)
    sources = frozen_status()
    seeds = seed_status(read(ROOT / "seed_registry.json"), cases)
    adapters = offline_adapter_checks() if adapter_checks and sources["verified"] else {
        "passed": False, "reason": "not_requested_or_frozen_source_check_failed"}
    mirror = offline_geometry_checks()
    return {
        "format": "campaign_pool_smoke_preparation_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "offline_preparation_passed" if sources["verified"] and seeds["fresh_relative_to_registry"] and adapters["passed"] else "offline_preparation_incomplete",
        "check_only": True, "simulator_started": False, "new_fdm_ticks": 0,
        "learner_started": False, "deployment_allowed": False, "official_validation": False,
        "ready_for_execution": False, "executor_implemented": False,
        "scope": "Frozen opponent interface and geometry smoke plan only. No league or win-rate evidence.",
        "preparation_tools_sha256": {name: bench.file_hash(EXP / name) for name in (
            "prepare_smoke.py", "test_smoke_preparation.py", "SMOKE_DESIGN.md")},
        "seed_registry_sha256_at_check": bench.file_hash(ROOT / "seed_registry.json"),
        "source_freeze": sources, "plan_sha256": bench.json_hash(cases), "cases": cases,
        "balance": balance, "seeds": seeds, "diversity": rule_variant_check(),
        "offline_adapters": adapters, "offline_geometry": mirror,
        "legacy_expansion_review": old_launcher_status(),
        "protocol": {
            "max_steps": SMOKE_TICKS, "physics_hz": 60, "per_case_wall_seconds": 30,
            "total_wall_seconds": 900, "initial_side_distance_max_error_fraction": .01,
            "required_initial_mirror_checks": ["red state unchanged", "blue altitude/heading/CAS unchanged",
                "cross_track_m reverses sign", "same opponent initial RNG SHA on both sides"],
            "required_self_play_checks": ["same frozen guide source on blue and red", "independent controller state",
                "both sides receive OWN20+ENEMY6 only", "four finite bounded controls every tick"],
            "required_execution_checks": ["STOP absent", "single owned compute job", "source/model SHA unchanged",
                "recorded quota/daily-budget warnings", "fresh development seeds claimed once before first attempt",
                "independent identity-checked deadline watchdog", "actual parent and worker exits recorded"],
            "incomplete_case_handling": "Preserve CSV/ACMI/result; exclude from interface pass and all performance summaries.",
            "success_is_not": ["full round completed", "league won", "official Host passed", "competition win probability"],
        },
        "next_action": "Implement a separate bounded smoke supervisor using this manifest; do not bypass legacy private-worker ownership or bank80 rejection gates.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="不啟動模擬的凍結對手池／鏡像自我對戰準備檢查")
    parser.add_argument("--check-only", action="store_true", required=True)
    parser.add_argument("--seed", type=int, default=2026102400)
    parser.add_argument("--out", type=Path, help="可選：原子儲存計畫；不改種子登記、預算、正式部署")
    parser.add_argument("--skip-adapter-checks", action="store_true")
    args = parser.parse_args(argv)
    report = prepare(args.seed, adapter_checks=not args.skip_adapter_checks)
    if args.out:
        bench.atomic_json(args.out, report)
    print(json.dumps({key: report[key] for key in ("status", "check_only", "simulator_started",
        "new_fdm_ticks", "ready_for_execution", "balance", "seeds", "legacy_expansion_review")}, ensure_ascii=False))
    return 0 if report["status"] == "offline_preparation_passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
