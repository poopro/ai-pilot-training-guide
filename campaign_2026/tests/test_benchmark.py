"""Focused invariants, independent of CUDA/JSBSim or the E: experiment files."""
import importlib.util
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

MODULE_PATH = Path(__file__).resolve().parents[1] / "benchmark.py"
SPEC = importlib.util.spec_from_file_location("campaign_benchmark_under_test", MODULE_PATH)
benchmark = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = benchmark
SPEC.loader.exec_module(benchmark)


def completed_row(case, *, eligible=True, initial="same", attack=1.):
    return {
        "case": benchmark.asdict(case), "pair_key": case.pair_key,
        "score_eligible": eligible, "initial_sha256": initial,
        "metrics": {"kills": 0, "deaths": 0, "own_crashes": 0,
                    "enemy_crashes": 0, "survival": 1, "attack_seconds": attack,
                    "enemy_attack_seconds": 0., "over_9g_seconds": 0.,
                    "min_altitude_m": 5000.},
    }


class PairingTests(unittest.TestCase):
    def test_full_plan_has_exact_pairing_and_same_seed_on_both_sides(self):
        cases = benchmark.plan_cases(candidate=True)
        self.assertEqual(len(cases), 24)
        self.assertEqual(len({case.pair_key for case in cases}), 12)
        for index in range(0, len(cases), 2):
            guide, candidate = cases[index:index + 2]
            self.assertEqual(guide.actor, "guide")
            self.assertEqual(candidate.actor, "candidate")
            self.assertEqual(guide.pair_key, candidate.pair_key)
            self.assertEqual(guide.seed, candidate.seed)
        for side in ("normal", "mirrored"):
            self.assertEqual(len([case for case in cases if case.side == side]), 12)
        self.assertEqual(cases[0].seed, cases[2].seed)

    def test_rounds_and_guide_only_use_expected_count(self):
        self.assertEqual(len(benchmark.plan_cases(rounds=2)), 24)
        self.assertEqual(len(benchmark.plan_cases(mirror="normal")), 6)
        self.assertEqual(len({case.seed for case in benchmark.plan_cases(rounds=2)}), 12)

    def test_partial_or_missing_pair_cannot_be_complete(self):
        cases = benchmark.plan_cases(candidate=True)[:2]
        rows = [completed_row(cases[0]), completed_row(cases[1], eligible=False)]
        summary = benchmark.summarize(rows, cases, True)
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["score_eligible_cases"], 1)
        self.assertEqual(summary["paired_completed"], 0)
        self.assertIsNone(summary["candidate"]["mean_attack_seconds"])
        self.assertEqual(summary["paired_excluded"][0]["reason"], "missing_or_incomplete_case")

    def test_mismatched_initial_state_cannot_count_as_fair_pair(self):
        cases = benchmark.plan_cases(candidate=True)[:2]
        rows = [completed_row(cases[0]), completed_row(cases[1], initial="different")]
        summary = benchmark.summarize(rows, cases, True)
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["paired_completed"], 0)
        self.assertEqual(summary["paired_excluded"][0]["reason"], "initial_state_hash_mismatch")

    def test_equal_hash_full_pair_counts_metric_improvement(self):
        cases = benchmark.plan_cases(candidate=True)[:2]
        rows = [completed_row(cases[0]), completed_row(cases[1], attack=2.)]
        summary = benchmark.summarize(rows, cases, True)
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["paired_completed"], 1)
        self.assertEqual(summary["paired_metric_changes"]["attack_seconds"]["improved"], 1)
        self.assertEqual(summary["paired_metric_changes"]["survival"]["tied"], 1)
        self.assertEqual(summary["candidate"]["mean_attack_seconds"], 2.)


class SupervisorTests(unittest.TestCase):
    def test_hard_timeout_terminates_stuck_worker(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        reason = benchmark.wait_process(process, timeout_s=.05)
        self.assertEqual(reason, "wall_timeout")
        self.assertIsNotNone(process.poll())

    def test_cooperative_stop_has_distinct_reason(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        reason = benchmark.wait_process(process, timeout_s=10, stop_check=lambda: True)
        self.assertEqual(reason, "stopped")
        self.assertIsNotNone(process.poll())

    def test_atomic_report_preserves_partial_flag(self):
        with tempfile.TemporaryDirectory(dir=MODULE_PATH.parent) as directory:
            path = Path(directory) / "report.json"
            benchmark.atomic_json(path, {"complete": True})
            benchmark.atomic_json(path, {"complete": False, "status": "partial"})
            row = benchmark.json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(row["complete"])
            self.assertEqual(row["status"], "partial")
            self.assertEqual(len(list(path.parent.glob("*.tmp_*"))), 0)


class FakeFdm:
    def __init__(self, **params):
        self.param = params
        self.fdm = {"position/h-agl-ft": params["fdm_ic_h"]}


def fake_observation(own, enemy):
    values = [0.] * 26
    params = own.param
    values[0:3] = [params["fdm_ic_lat"], params["fdm_ic_long"], params["fdm_ic_h"]]
    values[3:6] = [params.get("fdm_ic_phi", 0.), params.get("fdm_ic_theta", 0.), params["fdm_ic_psi"]]
    values[12] = params["fdm_ic_v"]
    values[20:23] = [enemy.param["fdm_ic_lat"], enemy.param["fdm_ic_long"], enemy.param["fdm_ic_h"]]
    return values


def fake_geometry(blue, red):
    b, r = fake_observation(blue, red), fake_observation(red, blue)
    latitude = math.radians(r[0])
    north = math.radians(b[0] - r[0]) * 6378137
    east = math.radians(b[1] - r[1]) * 6378137 * math.cos(latitude)
    return {"distance_m": math.hypot(north, east)}


def make_fake_environment():
    common = {"fdm_ic_h": 15000., "fdm_ic_v": 340., "fdm_ic_phi": 0., "fdm_ic_theta": 0.}
    blue = FakeFdm(fdm_id=1, fdm_ic_lat=23., fdm_ic_long=120.99, fdm_ic_psi=180., **common)
    red = FakeFdm(fdm_id=2, fdm_ic_lat=23., fdm_ic_long=121., fdm_ic_psi=0., **common)
    return SimpleNamespace(fdm1=blue, fdm2=red, current_step=0,
        settings={"reference_score_weights": {}}, np_random=object(), attack_angle=1.,
        packet_controller="stale", red_packet_controller="stale", red_fighter="stale",
        geometry="stale", prev_potential=-1, precision_previous=-1, min_altitude_m=-1,
        _potential=lambda geometry: geometry["distance_m"] / 1000)


def fake_runtime():
    return SimpleNamespace(
        JsbsimFdm=FakeFdm, simulator_observation=fake_observation,
        relative_geometry=fake_geometry, policy_state=lambda observation: observation[:20],
        geometry_from_observation=lambda observation: {"distance_m": 100.},
        precision_terms=lambda geometry: (0.75, 0., 0.),
        RepairController=lambda *args: {"type": "repair", "args": args},
        PacketController=lambda *args: {"type": "red_packet", "args": args},
        RuleFighter=lambda *args: {"type": "red_rule", "args": args},
        DiagnosticJudge=lambda *args: {"type": "judge", "args": args},
    )


class MirrorTests(unittest.TestCase):
    def test_mirror_reverses_side_and_synchronizes_cached_state(self):
        environment = make_fake_environment()
        runtime = fake_runtime()
        original_blue = environment.fdm1
        original_red = environment.fdm2
        observation, audit = benchmark.reset_initial_side(environment, "mirrored", runtime)
        self.assertEqual(len(observation), 20)
        self.assertIsNot(environment.fdm1, original_blue)
        self.assertIs(environment.fdm2, original_red)
        self.assertLess(audit["normal_cross_track_m"], 0)
        self.assertGreater(audit["cross_track_m"], 0)
        self.assertEqual(environment.fdm1.param["fdm_ic_psi"], 180.)
        self.assertEqual(environment.geometry, fake_geometry(environment.fdm1, environment.fdm2))
        self.assertEqual(environment.precision_previous, .75)
        self.assertEqual(environment.prev_potential, environment.geometry["distance_m"] / 1000)
        self.assertEqual(environment.min_altitude_m, 15000 * .3048)
        self.assertEqual(environment.red_altitude_m, 15000 * .3048)
        self.assertEqual(environment.packet_controller["type"], "repair")
        self.assertEqual(environment.red_fighter["type"], "red_rule")
        self.assertIs(environment.red_fighter["args"][2], environment.np_random)
        self.assertEqual(environment.blue_frames, 0)

    def test_in_progress_mirror_is_rejected(self):
        environment = make_fake_environment()
        environment.current_step = 1
        with self.assertRaises(ValueError):
            benchmark.reset_initial_side(environment, "mirrored", fake_runtime())

    def test_reset_pair_initial_hashes_match(self):
        for side in ("normal", "mirrored"):
            _, first = benchmark.reset_initial_side(make_fake_environment(), side, fake_runtime())
            _, second = benchmark.reset_initial_side(make_fake_environment(), side, fake_runtime())
            self.assertEqual(benchmark.json_hash(first), benchmark.json_hash(second))


if __name__ == "__main__":
    unittest.main()
