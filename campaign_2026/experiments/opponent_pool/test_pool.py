"""Offline protocol/adapter checks. Mock reports are not simulation evidence."""
from pathlib import Path
from dataclasses import asdict
from types import SimpleNamespace
from datetime import datetime,timezone
from unittest.mock import patch
import ast,copy,json,sys,time,unittest,numpy as np,os,subprocess,tempfile,psutil
EXP=Path(__file__).resolve().parent;ROOT=EXP.parents[1]
sys.path.insert(0,str(EXP));sys.path.insert(0,str(ROOT))
import benchmark_pool as bench,launch_pool,verify_pool,budget
class Tests(unittest.TestCase):
    def mock_report(self):
        planned=bench.plan_cases(3,2026102100,'both',True)
        rows=[]
        for p in planned:
            rows.append({'case':asdict(p),'case_id':p.case_id,'pair_key':p.pair_key,'worker_exit_code':0,'worker_wait_reason':'exited',
              'score_eligible':True,'full_round_completed':True,'initial_sha256':'mock_initial_'+p.pair_key,'opponent_id':p.opponent,
              'opponent_initial_rng_sha256':'mock_rng_'+p.pair_key,'steps':18000,'stop_reason':'round_horizon',
              'metrics':{'kills':0,'deaths':0,'own_crashes':0,'enemy_crashes':0,'survival':1,'attack_seconds':0.,'enemy_attack_seconds':0.,'over_9g_seconds':0.,'min_altitude_m':2000.}})
        return {'format':'campaign_expanded_bank80_pool_v1','seed_role':'expanded_development_not_holdout','status':'completed','benchmark_complete':True,'planned_cases':144,'cases':rows,'summary':{'paired_completed':72}},planned
    def test_full_balanced_pair_grid(self):
        p=bench.plan_cases(3,2026102100,'both',True)
        self.assertEqual(len(p),144);self.assertEqual(len(set(c.case_id for c in p)),144)
        self.assertEqual(len(set(c.pair_key for c in p)),72);self.assertEqual(len(set(c.seed for c in p)),36)
        for opp in ['rule','rl','repair_guide','rule_bank60']:
            for arm in ['guide','candidate']:self.assertEqual(sum(c.opponent==opp and c.actor==arm for c in p),18)
        for key in set(c.pair_key for c in p):self.assertEqual({c.actor for c in p if c.pair_key==key},{'guide','candidate'})
        registry=json.loads((ROOT/'seed_registry.json').read_text(encoding='utf-8'))
        next_registry=budget.claim_seeds(registry,'offline_mock_pool',sorted(set(c.seed for c in p)))
        self.assertEqual(len(next_registry['trials']['offline_mock_pool']['seeds']),36)
        self.assertNotIn('offline_mock_pool',registry['trials'])
    def test_fairness_header_rejects_missing_rng_or_wrong_opponent(self):
        r,p=self.mock_report();verify_pool.assert_full_header(r,p)
        for field,value in [('worker_exit_code',2),('initial_sha256','different'),('opponent_initial_rng_sha256','different'),('opponent_id','wrong')]:
            bad=copy.deepcopy(r);bad['cases'][1][field]=value
            with self.assertRaises(AssertionError):verify_pool.assert_full_header(bad,p)
        bad=copy.deepcopy(r);bad['cases'].pop()
        with self.assertRaises(AssertionError):verify_pool.assert_full_header(bad,p)
        with self.assertRaises(AssertionError):verify_pool.assert_full_header(r,bench.plan_cases(3,2026102200,'both',True))
    def test_original_physics_reset_metrics_timeout_unchanged(self):
        old=ast.parse((ROOT/'experiments/fresh_bank80/benchmark_fresh.py').read_text(encoding='utf-8-sig'))
        new=ast.parse((EXP/'benchmark_pool.py').read_text(encoding='utf-8-sig'))
        def method(t,n):return ast.dump(next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name==n),include_attributes=False)
        for name in ['reset_initial_side','case_metrics','wait_process','summarize']:
            self.assertEqual(method(old,name),method(new,name))
        self.assertEqual((EXP/'candidate.py').read_bytes(),(ROOT/'experiments/fresh_bank80/candidate.py').read_bytes())
    def test_rule_variant_only_pursuit_bank_limit_changed(self):
        original=ast.parse(Path(r'E:\ai_pilot\autopilot\opponent_lab\duel_lab.py').read_text(encoding='utf-8-sig'))
        source=(EXP/'opponents.py').read_text(encoding='utf-8-sig').replace('class RuleBank60:','class RuleFighter:').replace('heading_error, -60, 60','heading_error, -72, 72')
        restored=ast.parse(source)
        cl=lambda tree:ast.dump(next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='RuleFighter'),include_attributes=False)
        self.assertEqual(cl(original),cl(restored))
    def test_real_adapter_commands_no_fdm(self):
        runtime=bench.load_runtime(ROOT/'repair_v1')
        import opponents
        self.assertEqual(Path(opponents.__file__).resolve(),EXP/'opponents.py')
        raw=json.loads((ROOT/'experiments/near_bank80/run_20261012_2050/cases/r000_rule_3000_mirrored_2026101100_guide/result.json').read_text(encoding='utf-8'))
        initial=raw['initial'];obs=np.array(initial['red_own20_audit_only']+initial['blue_own20_audit_only'][:3]+initial['blue_own20_audit_only'][6:9])
        settings=json.loads((runtime.artifacts.BASE/'combat_v3/config.json').read_text(encoding='utf-8'))
        adapter=opponents.RepairGuideFighter(settings);command=adapter.act(obs,0)
        reference=runtime.RepairController(settings,'repair');expected,guard=reference.act(obs,residual=None)
        np.testing.assert_array_equal(command,expected);self.assertEqual(adapter.guard,guard)
        self.assertEqual(command.shape,(4,));self.assertTrue(np.isfinite(command).all())
        with self.assertRaises(ValueError):adapter.act(np.append(obs,1.),0)
        fighter=opponents.RuleBank60(settings,4000,np.random.default_rng(5))
        captured=[]
        def level(own,alt,bank,speed):captured.append((alt,bank,speed));return np.array([0.,0.,0.,.8]),False
        geometry={'distance_m':2000,'aspect_proxy_deg':90,'blue_angle_deg':100,'bearing_deg':obs[5]+80}
        with patch.object(opponents,'geometry_from_observation',return_value=geometry),patch.object(fighter.controller.control,'level',side_effect=level):
            fighter.act(obs,0)
        self.assertEqual(captured[0][1],60.)
        env=SimpleNamespace(settings=settings,fdm2=SimpleNamespace(getProperty=lambda key:[0,0,4000]),np_random=np.random.default_rng(6),p2_type='rule')
        before=copy.deepcopy(env.np_random.bit_generator.state)
        for name in ['repair_guide','rule_bank60']:
            record=opponents.configure_red(env,name);self.assertEqual(record['opponent_id'],name)
            self.assertEqual(before,env.np_random.bit_generator.state)
        with self.assertRaises(ValueError):opponents.configure_red(env,'unknown')
    def test_two_hour_day_guard_and_holdout(self):
        ledger=json.loads((ROOT/'compute_budgets/2026-10-12.json').read_text(encoding='utf-8'))
        with self.assertRaises(ValueError):budget.reserve(ledger,'2026-10-12','pool',2.)
        ledger=budget.reserve(None,'2026-10-13','fresh',40/60)
        self.assertAlmostEqual(budget.reserve(ledger,'2026-10-13','pool',2.)['reserved_hours'],2+40/60)
        reg=json.loads((ROOT/'seed_registry.json').read_text(encoding='utf-8'))
        held=reg['reserved_holdout_seeds']
        with self.assertRaises(ValueError):budget.claim_seeds(reg,'pool',[held[0]])
    def test_prerequisite_current_is_pending(self):
        self.assertFalse(launch_pool.fresh_readiness()['ready'])
    def test_unreadable_process_stays_unknown(self):
        class Proc:
            pid=42;info={'name':'python.exe'}
            def cmdline(self):raise launch_pool.psutil.AccessDenied(42)
        with patch.object(launch_pool.psutil,'process_iter',return_value=[Proc()]):
            with self.assertRaisesRegex(RuntimeError,'unknown'):launch_pool.occupied()
    def test_low_usage_denied_before_preflight(self):
        args=SimpleNamespace(check_only=False,remaining_percent=10.,usage_epoch=time.time(),seed=2026102100)
        with patch.object(launch_pool,'preflight') as pre:
            with self.assertRaises(ValueError):launch_pool.main(args)
            pre.assert_not_called()
    def test_owned_private_pool_worker_requires_two_hour_manifest(self):
        work=EXP/'test_work';work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as d:
            output=Path(d);self.assertTrue(output.resolve().is_relative_to(work.resolve()))
            folder=output/'cases'/'mock';folder.mkdir(parents=True)
            me=psutil.Process(os.getpid());ident={'pid':me.pid,'creation_epoch':me.create_time(),'cmdline':me.cmdline()}
            case=asdict(bench.plan_cases(3,2026102100,'both',True)[0])
            launch={'supervisor':ident,'compute_budget_date':'2026-10-13','reservation_id':'pool_mock','seed':2026102100,
             'source_sha256':{'mock':'same'},'planned_cases':144,'reserved_hours':2.,'opponent_pool_manifest_sha256':bench.file_hash(EXP/'POOL_FREEZE.json')}
            spec={'out':str(output),'case':case,'source_sha256':launch['source_sha256'],'bundle':None,'max_steps':18000,'case_seconds':150}
            (folder/'input.json').write_text(json.dumps(spec),encoding='utf-8')
            (output/'launch.json').write_text(json.dumps(launch),encoding='utf-8')
            (output/'compute_budgets').mkdir()
            ledger=budget.reserve(None,'2026-10-13','pool_mock',2.)
            lp=output/'compute_budgets/2026-10-13.json';lp.write_text(json.dumps(ledger),encoding='utf-8')
            code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import benchmark_pool as b;b.ROOT=Path(sys.argv[2]);\ndef fake_worker(path):\n print('AUTHORIZED_MOCK_NO_FDM');return 0\nb.run_worker=fake_worker;raise SystemExit(b.main(['--_worker',sys.argv[3]]))"
            def child():return subprocess.run([sys.executable,'-B','-X','utf8','-c',code,str(EXP),str(output),str(folder/'input.json')],capture_output=True,text=True,timeout=10)
            ok=child();self.assertEqual(ok.returncode,0,ok.stderr);self.assertIn('AUTHORIZED_MOCK_NO_FDM',ok.stdout)
            ledger=budget.reserve(None,'2026-10-13','pool_mock',1.)
            lp.write_text(json.dumps(ledger),encoding='utf-8')
            bad=child();self.assertNotEqual(bad.returncode,0);self.assertIn('reservation amount differs',bad.stderr);self.assertNotIn('AUTHORIZED_MOCK_NO_FDM',bad.stdout)
            lp.write_text(json.dumps(budget.reserve(None,'2026-10-13','pool_mock',2.)),encoding='utf-8')
            launch['opponent_pool_manifest_sha256']='different';(output/'launch.json').write_text(json.dumps(launch),encoding='utf-8')
            bad=child();self.assertNotEqual(bad.returncode,0);self.assertIn('manifest changed',bad.stderr)
    def test_safety_prerequisite_accepts_only_hash_bound_review(self):
        work=EXP/'test_work';work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as d:
            directory=Path(d);rp=directory/'report.json';cp=directory/'COMPARISON.json'
            rp.write_text(json.dumps({'format':'campaign_fresh_guided_bank80_paired_v1'}),encoding='utf-8')
            comparison={'report':str(rp),'report_sha256':bench.file_hash(rp),'verified_comparison':True,'actual_parent_exit_code':0,'eligible_cases':24,'matched_pairs':12,
             'gates':{'metric':True,'outcome_safety':True,'per_opponent':True},'source_sha256':{'candidate/near_bank80.py':bench.file_hash(EXP/'candidate.py')}}
            cp.write_text(json.dumps(comparison),encoding='utf-8')
            pointer={'experiment':'fresh_bank80','verified_comparison':True,'comparison':str(cp)}
            real_read=launch_pool.read
            def read(p):return pointer if Path(p)==ROOT/'research_latest.json' else real_read(p)
            with patch.object(launch_pool,'read',side_effect=read):
                self.assertFalse(launch_pool.fresh_readiness()['ready'])
                dp=directory/'SAFETY_DECISION.json';decision={'comparison_sha256':bench.file_hash(cp),'review_complete':True,'recommendation':'expand_frozen_opponents','altitude_assessment':'MOCK','recovery_assessment':'MOCK'}
                dp.write_text(json.dumps(decision),encoding='utf-8');self.assertTrue(launch_pool.fresh_readiness()['ready'])
                decision['comparison_sha256']='stale';dp.write_text(json.dumps(decision),encoding='utf-8');self.assertFalse(launch_pool.fresh_readiness()['ready'])
if __name__=='__main__':unittest.main(verbosity=2)
