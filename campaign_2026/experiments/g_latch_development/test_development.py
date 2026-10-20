import copy
import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('g_latch_development',Path(__file__).with_name('launch_development.py'))
dev=importlib.util.module_from_spec(spec);spec.loader.exec_module(dev)


def completed_rows():
    rows=[]
    for case in dev.planned_cases():
        metrics={'kills':1,'deaths':0,'own_crashes':0,'enemy_crashes':0,'survival':1,
            'attack_seconds':2.5 if case['case']['actor']=='candidate' else 2.,
            'enemy_attack_seconds':0.,'over_9g_seconds':0.,'min_altitude_m':3000.}
        rows.append({**case,'metrics':metrics,'score_eligible':True,'initial_sha256':case['pair_key']})
    return rows


class DevelopmentTests(unittest.TestCase):
    def decision(self,rows):
        summary=dev.bench.summarize(rows,dev.bench.plan_cases(1,dev.SEED_BASE,'both',True),True)
        return dev.gates(rows,summary)

    def test_plan24_has12_matching_pairs(self):
        rows=completed_rows();summary=dev.bench.summarize(rows,dev.bench.plan_cases(1,dev.SEED_BASE,'both',True),True)
        self.assertEqual(len(rows),24);self.assertEqual(summary['paired_completed'],12);self.assertTrue(summary['complete'])

    def test_baseline_is_true_repair_guide(self):
        guide,candidate=dev.pure_controls()
        self.assertEqual(guide.__name__,'RepairController')
        self.assertEqual(candidate.__name__,'GGuardLatchBank80')
        self.assertNotEqual(guide.act,candidate.act)

    def test_candidate_bytes_equal_verified_smoke(self):
        self.assertEqual(dev.bench.file_hash(dev.EXP/'safe_candidate.py'),dev.bench.file_hash(dev.SMOKE/'safe_candidate.py'))
        self.assertTrue(dev.engine.single_factor_check())

    def test_worker_adapter_selects_pure_guide_and_restores_frozen_class(self):
        guide,candidate_class=dev.pure_controls()
        import candidate as frozen_bank80
        original=frozen_bank80.Bank80Controller
        with tempfile.TemporaryDirectory(dir=dev.EXP) as temporary:
            path=Path(temporary)/'input.json'
            def recorded_worker(_):
                self.assertIs(frozen_bank80.Bank80Controller,guide)
                self.assertEqual(dev.engine.load_candidate().GGuardLatchBank80.act,original.act)
                dev.bench.atomic_json(path.with_name('result.json'),{'case':{'actor':'guide'}})
                return 0
            with patch.object(dev,'original_worker',side_effect=recorded_worker):
                self.assertEqual(dev.worker(path),0)
            self.assertIs(frozen_bank80.Bank80Controller,original)
            self.assertEqual(dev.base.read(path.with_name('result.json'))['smoke_control'],'pure_repair_guide')

    def test_seed_observed_or_holdout_collision_rejected(self):
        for registry in ({'observed_seeds':{str(dev.SEED_BASE):{}},'trials':{}},
                         {'reserved_holdout_seeds':[dev.SEED_BASE],'trials':{}}):
            with self.assertRaises(RuntimeError):dev.check_seed_ownership(registry)

    def test_prepared_seeds_allowed_but_attempted_cannot_repeat(self):
        registry={'trials':{dev.trial_id():{'status':'prepared_not_run','seeds':dev.requested_seeds()}}}
        self.assertTrue(dev.check_seed_ownership(registry,True))
        registry['trials'][dev.trial_id()]['status']='attempted'
        with self.assertRaises(RuntimeError):dev.check_seed_ownership(registry,True)

    def test_24case_gate_requires_initial_sha_matching(self):
        rows=completed_rows();rows[1]['initial_sha256']='different'
        summary=dev.bench.summarize(rows,dev.bench.plan_cases(1,dev.SEED_BASE,'both',True),True)
        self.assertFalse(summary['complete']);self.assertEqual(summary['paired_completed'],11)

    def test_safe_improvement_still_has_no_deployment(self):
        decision=self.decision(completed_rows())
        self.assertEqual(decision['gate'],'development_pass_review_pending')
        self.assertFalse(decision['deployment_allowed'])

    def test_single_overg_tick_rejects_candidate(self):
        rows=completed_rows();rows[1]['metrics']['over_9g_seconds']=1/60
        self.assertFalse(self.decision(rows)['safety_pass'])

    def test_opponent_regression_cannot_hide_in_global_kills(self):
        rows=completed_rows()
        candidates=[r for r in rows if r['case']['actor']=='candidate']
        next(r for r in candidates if r['case']['opponent']=='rule')['metrics']['kills']=2
        next(r for r in candidates if r['case']['opponent']=='rl')['metrics']['kills']=0
        self.assertFalse(self.decision(rows)['safety_pass'])

    def test_altitude_loss_remains_explicit_review(self):
        rows=completed_rows();rows[1]['metrics']['min_altitude_m']-=.6002
        decision=self.decision(rows)
        self.assertEqual(decision['gate'],'metric_pass_safety_review_pending')
        self.assertAlmostEqual(decision['paired_altitude_regressions'][0]['delta_min_altitude_m'],-.6002)


if __name__=='__main__':unittest.main()
