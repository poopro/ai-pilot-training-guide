"""Exercise the real class methods with explicit fake physics; no Torch or FDM.

The original and corrected methods are loaded from AST to isolate the API
boundary. Passing these tests is not flight, reward-learning, or Host evidence.
"""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class Controller:
    def __init__(self):
        self.calls = 0
        self.tactical = None

    def set_tactical(self, *action):
        self.tactical = action

    def act(self, observation, residual=None, started=True):
        self.calls += 1
        return np.array([.2, -.3, 0., .8]), True


class Parent:
    def step(self, action):
        self.packet_controller.act(self.obs, action)
        self.received.append(np.array(action))
        self.current_step += 1
        if self.current_step % self.judge_interval == 0:
            self.blue_frames += 1
        self.obs[14] = self.post_g
        term = self.end_outcome is not None
        return None, 100., term, False, {
            "guard_active": True, "outcome": self.end_outcome or "ongoing",
            "own_crash": self.end_outcome == "own_crash",
        }

    def reset(self, **kwargs):
        self.current_step = 0
        self.blue_frames = 0
        return np.zeros(26), {}


class GymBase:
    def reset(self, seed=None):
        if seed is not None or not hasattr(self, "np_random"):
            self.np_random = np.random.default_rng(seed)


class FakeDuel:
    def reset(self, **kwargs):
        return None, {"reset_seed": kwargs.get("seed")}

    def tactical_obs_only(self):
        return np.zeros(12)

    def close(self):
        pass


def load_classes(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    selected = [node for node in tree.body if isinstance(node, ast.ClassDef)
                and node.name in ("TacticalDuel", "TacticalGym", "Telemetry")]
    namespace = {
        "np": np, "RepairDuel": Parent, "BaseCallback": object,
        "Path": Path, "time": time, "json": json,
        "gym": SimpleNamespace(Env=GymBase),
        "spaces": SimpleNamespace(Box=lambda *a, **kw: None),
        "simulator_observation": lambda first, second: first,
        "geometry_from_observation": lambda obs: {"distance_m": 200., "blue_angle_deg": 0.},
        "tactical_obs": lambda *args: np.zeros(12),
        "DECISION_EVERY": 20, "N_DECISION": 3, "N_TACTICAL": 12,
        "KILL_TICKS": 180, "BAND_LO_M": 152.4, "BAND_HI_M": 914.4,
        "OVER_9G_PENALTY": .35, "NEAR_GROUND_M": 400.,
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def instance(classes):
    duel = classes["TacticalDuel"].__new__(classes["TacticalDuel"])
    duel.obs = np.zeros(26)
    duel.obs[2] = 5000.
    duel.obs[14] = 1.
    duel.fdm1, duel.fdm2 = duel.obs, np.zeros(26)
    duel.current_step = duel.blue_frames = duel.ticks = duel.over9g = duel._frame = 0
    duel.max_steps = 100
    duel.min_alt = 1e9
    duel._last_guard = False
    duel.post_g = 1.
    duel.judge_interval = 1
    duel.end_outcome = None
    duel.packet_controller = Controller()
    duel.opponent_kind = "rule"
    duel.received = []
    return duel


NEW = load_classes(HERE / "m4_tactical_rl.py")
OLD = load_classes(ROOT / "win" / "m4_tactical_rl.py")


class ContractTests(unittest.TestCase):
    def test_original_double_calls_reproduced_at_boundary(self):
        duel = instance(OLD)
        duel.step(np.zeros(3))
        self.assertEqual(duel.packet_controller.calls, 40)
        self.assertTrue(any(np.any(action) for action in duel.received))

    def test_corrected_parent_receives_only_zero_residual_and_one_call(self):
        duel = instance(NEW)
        duel.step(np.zeros(3))
        self.assertEqual(duel.packet_controller.calls, 20)
        self.assertTrue(all(np.array_equal(action, np.zeros(4)) for action in duel.received))

    def test_judge_counter_used_instead_of_second_geometry_counter(self):
        duel = instance(NEW)
        duel.judge_interval = 2
        _, reward, _, _, info = duel.step(np.zeros(3))
        self.assertEqual(info["attack_ticks"], 10)
        self.assertEqual(reward, 10.)

    def test_parent_shaping_reward_is_not_silently_added(self):
        duel = instance(NEW)
        self.assertEqual(duel.step(np.zeros(3))[1], 20.)

    def test_guard_observation_and_post_step_g_follow_actual_tick(self):
        duel = instance(NEW)
        duel.post_g = 9.1
        _, reward, _, _, info = duel.step(np.zeros(3))
        self.assertTrue(duel._last_guard)
        self.assertEqual(info["over9g"], 20)
        self.assertAlmostEqual(reward, 20. - 20 * .35)

    def test_attack_threshold_does_not_relabel_crash_win(self):
        duel = instance(NEW)
        duel.ticks = duel.blue_frames = 179
        duel.end_outcome = "own_crash"
        info = duel.step(np.zeros(3))[-1]
        self.assertEqual(info["attack_ticks"], 180)
        self.assertFalse(info["won"])
        self.assertTrue(info["crashed"])

    def test_invalid_action_rejected_before_any_control_call(self):
        for action in ([0., 0.], [0., float("nan"), 0.], [0., float("inf"), 0.]):
            duel = instance(NEW)
            with self.assertRaises(ValueError): duel.step(action)
            self.assertEqual(duel.packet_controller.calls, 0)

    def test_reset_clears_mirror_controller_and_guard_memory(self):
        duel = instance(NEW)
        duel._mirror_p2 = object()
        duel._last_guard = True
        duel._build_blue = Controller
        duel.reset(seed=5)
        self.assertIsNone(duel._mirror_p2)
        self.assertFalse(duel._last_guard)

    def test_pool_rotates_on_reset_and_explicit_seed_reproduces(self):
        gym = NEW["TacticalGym"](["mirror", "rule", "rl"])
        def ensure(seed=None):
            if gym.env is None: gym.env = FakeDuel()
            return gym.env
        gym._ensure = ensure
        seen = [gym.reset(seed=i)[1]["opponent"] for i in range(30)]
        self.assertEqual(set(seen), {"mirror", "rule", "rl"})
        self.assertEqual(gym.reset(seed=5)[1]["opponent"], gym.reset(seed=5)[1]["opponent"])

    def test_empty_or_unknown_pool_rejected(self):
        for pool in ([], ["unknown"], ""):
            with self.assertRaises(ValueError): NEW["TacticalGym"](pool)

    def test_callback_counts_done_and_best_ticks_in_actual_on_step(self):
        callback = NEW["Telemetry"].__new__(NEW["Telemetry"])
        callback.ep = 0
        callback.model = SimpleNamespace(_best_ticks=0)
        callback.locals = {"dones": [True], "infos": [{"attack_ticks": 180, "opponent": "rule"}]}
        callback.num_timesteps = 2000
        callback.t0 = time.time()
        with tempfile.TemporaryDirectory() as directory:
            callback.path = Path(directory) / "progress.json"
            callback._on_step()
            report = json.loads(callback.path.read_text())
        self.assertEqual(report["episodes"], 1)
        self.assertEqual(report["best_ticks"], 180)


if __name__ == "__main__":
    unittest.main()
