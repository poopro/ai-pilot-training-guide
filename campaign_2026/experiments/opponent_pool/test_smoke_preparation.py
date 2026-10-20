"""Pure plan rejection tests plus guarded real controller inference, never FDM."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import prepare_smoke as prep


class SmokePreparationTests(unittest.TestCase):
    def test_balanced_grid_includes_both_side_self_play(self):
        cases = prep.plan_cases()
        counts = prep.assert_plan(cases)
        self.assertEqual(counts, {"cases": 24, "geometry_pairs": 12, "distinct_seeds": 12,
                                  "self_play_cases": 6, "balanced": True})
        self.assertEqual(sum(case["self_play"] for case in cases), 6)
        self.assertFalse(any(case["score_eligible"] for case in cases))

    def test_partial_or_inconsistent_plan_rejected(self):
        cases = prep.plan_cases()
        with self.assertRaises(ValueError): prep.assert_plan(cases[:-1])
        for key, value in (("seed", 99), ("side", "normal"), ("blue_controller", "bank80"),
                           ("score_eligible", True), ("max_steps", 18000), ("self_play", True)):
            bad = copy.deepcopy(cases)
            bad[1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): prep.assert_plan(bad)

    def test_observed_and_holdout_seed_rejected_without_mutation(self):
        cases = prep.plan_cases()
        registry = {"observed_seeds": {str(cases[0]["seed"]): []},
                    "reserved_holdout_seeds": [cases[2]["seed"]], "trials": {}}
        original = copy.deepcopy(registry)
        result = prep.seed_status(registry, cases)
        self.assertFalse(result["fresh_relative_to_registry"])
        self.assertEqual(result["seed_trials_claimed"], 0)
        self.assertEqual(registry, original)

    def test_invalid_seed_rejected(self):
        for seed in (-1, True, 2**31, "12"):
            with self.subTest(seed=seed), self.assertRaises(ValueError): prep.plan_cases(seed)

    def test_development_parameter_variant_declaration_matches_ast(self):
        result = prep.rule_variant_check()
        self.assertTrue(result["rule_bank60_single_declared_difference"])
        self.assertTrue(result["rule_bank60_is_parameter_variant"])
        self.assertEqual(len(result["structurally_distinct_families"]), 3)
        self.assertFalse(result["opponent_strength_verified"])

    def test_actual_frozen_runtime_unchanged(self):
        result = prep.frozen_status()
        self.assertTrue(result["verified"], result["changed"])

    def test_guarded_legal_commands_without_fdm(self):
        result = prep.offline_adapter_checks()
        self.assertTrue(result["passed"])
        self.assertEqual(result["opponent_commands_checked"], 24)
        self.assertEqual(result["fdm_constructor_calls"], 0)
        self.assertTrue(result["self_play_controller_equals_reference"])

    def test_actual_mirror_helper_on_non_physics_fixtures(self):
        result = prep.offline_geometry_checks()
        self.assertTrue(result["passed"])
        self.assertEqual(result["fixture_cases"], 12)

    def test_preparation_never_authorizes_execution_or_promotion(self):
        with patch.object(prep, "frozen_status", return_value={"verified": True}), \
                patch.object(prep, "offline_adapter_checks", return_value={"passed": True}), \
                patch.object(prep, "rule_variant_check", return_value={}), \
                patch.object(prep, "old_launcher_status", return_value={}), \
                patch.object(prep, "read", return_value={}):
            result = prep.prepare()
        self.assertEqual(result["status"], "offline_preparation_passed")
        self.assertFalse(result["ready_for_execution"])
        self.assertFalse(result["simulator_started"])
        self.assertFalse(result["deployment_allowed"])
        self.assertEqual(result["new_fdm_ticks"], 0)


if __name__ == "__main__":
    unittest.main()
