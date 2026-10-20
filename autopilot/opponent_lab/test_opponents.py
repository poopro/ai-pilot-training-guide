"""Behavior checks for symmetric observations, aggressive rule logic and judgment."""
import unittest
import numpy as np
from duel_lab import BASE, DuelLab, RuleFighter, DiagnosticJudge
import json


class OpponentChecks(unittest.TestCase):
    def test_rule_breaks_when_pursued_then_reengages(self):
        cfg = json.loads((BASE / "combat_v3" / "config.json").read_text(encoding="utf-8"))
        fighter = RuleFighter(cfg, 4572, np.random.default_rng(12))
        observation = np.array([23, 121, 15000, 0, 0, 0, 600, 0, 0,
                                0, 0, 0, 573.8, 700, 1, 700, 0, 0, 3, 0,
                                22.995, 121, 15000, 600, 0, 0], dtype=float)
        action = fighter.act(observation, 0)
        self.assertEqual(fighter.mode, "defensive_break")
        self.assertTrue(np.isfinite(action).all())
        self.assertTrue(np.all(action[:3] >= -1) and np.all(action[:3] <= 1))
        self.assertTrue(0 <= action[3] <= 1)
        fighter.act(observation, 2.6)
        self.assertNotEqual(fighter.mode, "defensive_break")
        self.assertEqual(fighter.next_break_allowed, 6)

    def test_one_degree_does_not_count_two_degree_near_misses(self):
        cfg = json.loads((BASE / "combat_v3" / "config.json").read_text(encoding="utf-8"))
        judge = DiagnosticJudge(cfg["reference_score_weights"], 1)
        geometry = {"distance_m": 600, "blue_angle_deg": 1.5, "red_angle_deg": .5}
        for _ in range(180):
            judge.update(geometry, 1, 1)
        self.assertEqual(judge.attack, [0, 180])
        self.assertEqual(judge.outcome(False, False), "shot_down")

    def test_initialization_and_rule_commands_for_three_distances(self):
        for distance in [3000, 6000, 9000]:
            with self.subTest(distance=distance):
                env = DuelLab(p2="rule", distance_ft=distance, max_steps=12)
                try:
                    env.reset(seed=20264000)
                    self.assertAlmostEqual(env.geometry["distance_m"] / .3048, distance, delta=.5)
                    self.assertAlmostEqual(env.fdm1.fdm["velocities/vc-kts"], 340, places=6)
                    self.assertAlmostEqual(env.fdm2.fdm["velocities/vc-kts"], 340, places=6)
                    difference = (env.fdm1.fdm["attitude/psi-deg"] - env.fdm2.fdm["attitude/psi-deg"]) % 360
                    self.assertAlmostEqual(difference, 180, places=5)
                    self.assertAlmostEqual(env.geometry["blue_angle_deg"], 90, delta=.1)
                    self.assertAlmostEqual(env.geometry["red_angle_deg"], 90, delta=.1)
                    obs, reward, terminated, truncated, info = env.step(np.zeros(4, dtype=np.float32))
                    self.assertEqual(obs.shape, (20,))
                    self.assertTrue(np.isfinite(obs).all() and np.isfinite(reward))
                    self.assertEqual(info["p2_type"], "rule")
                    self.assertEqual(info["attack_angle_deg"], 1)
                finally:
                    env.close()


if __name__ == "__main__":
    unittest.main()
