import copy
import importlib.util
from pathlib import Path
import unittest
import tempfile

spec=importlib.util.spec_from_file_location('post_audit',Path(__file__).with_name('post_audit.py'))
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def raw(steps=18000,outcome='timeout',reason='round_horizon'):
    return {'steps':steps,'status':'completed','score_eligible':True,'full_round_completed':True,
        'outcome':outcome,'stop_reason':reason,'initial':{'blue_own20_audit_only':[0.]*14+[1.]},
        'metrics':{'kills':int(outcome=='kill'),'deaths':0,'own_crashes':0,'enemy_crashes':0,'survival':1,
            'attack_seconds':3. if outcome=='kill' else 0.,'enemy_attack_seconds':0.,'over_9g_seconds':0.,'min_altitude_m':1000.}}


def row(tick,g,flag=0,counter=0):
    value={k:0. for k in audit.dev.engine.COLUMNS}
    value.update(tick=tick,simulation_seconds=tick/60,controller_mode='track',signed_g=g,
        abs_g=abs(g),g_guard_latched=flag,overload_ticks=counter,throttle=.8,altitude_m=1000.)
    return value


class PostAuditTests(unittest.TestCase):
    def test_legal_early_kill_remains_eligible(self):
        audit.legal_terminal(raw(5000,'kill','legal_termination'))
        audit.legal_terminal(raw())

    def test_short_timeout_or_false_full_cannot_pass(self):
        for invalid in (raw(5000,'timeout','legal_termination'),raw(5000),raw(18001,'kill','legal_termination')):
            with self.assertRaises(RuntimeError):audit.legal_terminal(invalid)
        invalid=raw();invalid['full_round_completed']=False
        with self.assertRaises(RuntimeError):audit.legal_terminal(invalid)

    def test_outcome_counter_contradiction_rejected(self):
        invalid=raw();invalid['metrics']['kills']=1
        with self.assertRaises(RuntimeError):audit.legal_terminal(invalid)

    def test_previous_tick_latch_positive_and_counterexample(self):
        evidence=[row(1,8.6),row(2,8.4,1),row(3,8.,1),row(4,7.9,1),row(5,7.9,0)]
        result=audit.check_ticks(evidence,raw(5),True)
        self.assertEqual(result['latched_ticks'],3)
        invalid=copy.deepcopy(evidence);invalid[1]['g_guard_latched']=0
        with self.assertRaises(RuntimeError):audit.check_ticks(invalid,raw(5),True)

    def test_abs_g_and_fractional_overload_metadata_rejected(self):
        evidence=[row(1,1.)];invalid=copy.deepcopy(evidence);invalid[0]['abs_g']=.9
        with self.assertRaises(RuntimeError):audit.check_ticks(invalid,raw(1),False)
        invalid_raw=raw(1);invalid_raw['metrics']['over_9g_seconds']=.49/60
        with self.assertRaises(RuntimeError):audit.check_ticks(evidence,invalid_raw,False)

    def test_baseline_latch_alias_cannot_pass(self):
        with self.assertRaises(RuntimeError):audit.check_ticks([row(1,1.,1)],raw(1),False)

    def test_existing_verified_smoke_positive_no_simulator(self):
        result=audit.terminal_audit(audit.dev.SMOKE_RUN,smoke=True)
        self.assertTrue(result['passed']);self.assertEqual(result['complete_cases'],2)
        self.assertEqual(result['matched_pairs'],1);self.assertFalse(result['simulator_started'])

    def test_partial_live_run_is_refused_before_receipts(self):
        with tempfile.TemporaryDirectory(dir=audit.EXP) as temporary:
            folder=Path(temporary)
            audit.dev.bench.atomic_json(folder/'launch.json',{'source_sha256':{}})
            audit.dev.bench.atomic_json(folder/'state.json',{'status':'running'})
            with self.assertRaisesRegex(RuntimeError,'partial/live'):
                audit.terminal_audit(folder)


if __name__=='__main__':unittest.main()
