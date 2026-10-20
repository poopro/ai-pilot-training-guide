from pathlib import Path
from datetime import datetime,timezone
import ast,copy,json,os,subprocess,sys,tempfile,time,unittest
from unittest.mock import patch
exp=Path(r'E:\ai_pilot\campaign_2026\experiments\fresh_bank80');root=exp.parents[1]
sys.path.insert(0,str(exp));sys.path.insert(0,str(root))
import budget,launch_fresh,verify_fresh,benchmark_fresh,psutil
from runner import JobLock
work=exp/'test_work';work.mkdir(exist_ok=True)
class Tests(unittest.TestCase):
    def test_calendar_budget_rollover(self):
        self.assertEqual(budget.date_taipei(datetime(2026,10,12,15,59,tzinfo=timezone.utc)),'2026-10-12')
        self.assertEqual(budget.date_taipei(datetime(2026,10,12,16,0,tzinfo=timezone.utc)),'2026-10-13')
        old=json.loads((root/'compute_budgets'/'2026-10-12.json').read_text(encoding='utf-8'))
        with self.assertRaises(ValueError):budget.reserve(old,'2026-10-12','fresh',40/60)
        self.assertAlmostEqual(budget.reserve(None,'2026-10-13','fresh',40/60)['reserved_hours'],40/60)
    def test_duplicate_or_corrupt_budget_denied(self):
        x=budget.reserve(None,'2026-10-13','first',1.)
        with self.assertRaises(ValueError):budget.reserve(x,'2026-10-13','first',1.)
        for h in [float('nan'),float('inf'),-1,True]:
            bad=copy.deepcopy(x);bad['items'][0]['hours']=h
            with self.assertRaises(ValueError):budget.checked(bad,'2026-10-13')
        with self.assertRaises(ValueError):budget.checked(x,'2026-10-14')
        bad=copy.deepcopy(x);bad['reserved_hours']=0
        with self.assertRaises(ValueError):budget.checked(bad,'2026-10-13')
    def test_seen_attempted_and_holdout_denied(self):
        r={'observed_seeds':{'1':[]},'reserved_holdout_seeds':[2],'trials':{}}
        for s in [1,2]:
            with self.assertRaises(ValueError):budget.claim_seeds(r,'trial',[s])
        q=budget.claim_seeds(r,'trial',[3,4])
        with self.assertRaises(ValueError):budget.claim_seeds(q,'new',[3])
        self.assertEqual(r['trials'],{})
    def test_original_worker_and_candidate_preserved(self):
        old=ast.parse((root/'experiments'/'near_bank80'/'benchmark_bank80.py').read_text(encoding='utf-8'))
        new=ast.parse((exp/'benchmark_fresh.py').read_text(encoding='utf-8'))
        method=lambda t,n:ast.dump(next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name==n),include_attributes=False)
        for name in ['run_worker','reset_initial_side','case_metrics','wait_process']:
            self.assertEqual(method(old,name),method(new,name))
        snap=root/'candidates'/'near_bank80_20261012'/'sources'/'candidate'/'near_bank80.py'
        self.assertEqual(snap.read_bytes(),(exp/'candidate.py').read_bytes())
    def test_incomplete_wrong_seed_or_initial_denied(self):
        r=json.loads((root/'experiments'/'near_bank80'/'run_20261012_2050'/'report.json').read_text(encoding='utf-8'))
        r['format']='campaign_fresh_guided_bank80_paired_v1';r['seed_role']='fresh_development_not_holdout'
        planned=benchmark_fresh.plan_cases(1,r['seed'],'both',True)
        verify_fresh.assert_full_header(r,planned)
        bad=copy.deepcopy(r);bad['cases'].pop()
        with self.assertRaises(AssertionError):verify_fresh.assert_full_header(bad,planned)
        bad=copy.deepcopy(r);bad['cases'][1]['initial_sha256']='different'
        with self.assertRaises(AssertionError):verify_fresh.assert_full_header(bad,planned)
        with self.assertRaises(AssertionError):verify_fresh.assert_full_header(r,benchmark_fresh.plan_cases(1,2026101300,'both',True))
        bad=copy.deepcopy(r);bad['cases'][0]['worker_exit_code']=2
        with self.assertRaises(AssertionError):verify_fresh.assert_full_header(bad,planned)
    def test_unreadable_process_is_unknown(self):
        class Proc:
            pid=42;info={'name':'python.exe'}
            def cmdline(self):raise launch_fresh.psutil.AccessDenied(42)
        with patch.object(launch_fresh.psutil,'process_iter',return_value=[Proc()]):
            with self.assertRaisesRegex(RuntimeError,'unknown'):launch_fresh.occupied()
    def test_os_lock_blocks_second_owner(self):
        with tempfile.TemporaryDirectory(dir=work) as d:
            self.assertTrue(Path(d).resolve().is_relative_to(work.resolve()))
            path=Path(d)/'lock'
            code="import sys;sys.path.insert(0,sys.argv[1]);from runner import JobLock;from pathlib import Path;\nwith JobLock(Path(sys.argv[2])): print('UNEXPECTED_SECOND_OWNER')"
            with JobLock(path):
                p=subprocess.run([sys.executable,'-B','-X','utf8','-c',code,str(root),str(path)],capture_output=True,text=True,timeout=10)
            self.assertNotEqual(p.returncode,0)
            self.assertNotIn('UNEXPECTED_SECOND_OWNER',p.stdout)
            self.assertIn('已有同一作業',p.stderr)
    def test_low_usage_denied_before_launch(self):
        p=subprocess.run([sys.executable,'-B','-X','utf8',str(exp/'launch_fresh.py'),'--remaining-percent','10','--usage-epoch',str(time.time())],capture_output=True,text=True,timeout=10)
        self.assertNotEqual(p.returncode,0);self.assertIn('>=35%',p.stderr)
    def test_unowned_private_worker_denied(self):
        with tempfile.TemporaryDirectory(dir=work) as d:
            self.assertTrue(Path(d).resolve().is_relative_to(work.resolve()))
            out=Path(d);folder=out/'cases'/'mock';folder.mkdir(parents=True)
            (folder/'input.json').write_text(json.dumps({'out':str(out)}),encoding='utf-8')
            (out/'launch.json').write_text(json.dumps({'supervisor':{'pid':os.getpid(),'creation_epoch':0,'cmdline':[]}}),encoding='utf-8')
            p=subprocess.run([sys.executable,'-B','-X','utf8',str(exp/'benchmark_fresh.py'),'--_worker',str(folder/'input.json')],capture_output=True,text=True,timeout=10)
            self.assertNotEqual(p.returncode,0);self.assertIn('direct child',p.stderr)
    def test_owned_private_worker_accepts_mock_boundary(self):
        with tempfile.TemporaryDirectory(dir=work) as d:
            self.assertTrue(Path(d).resolve().is_relative_to(work.resolve()))
            out=Path(d);folder=out/'cases'/'mock';folder.mkdir(parents=True)
            me=psutil.Process(os.getpid());ident={'pid':me.pid,'creation_epoch':me.create_time(),'cmdline':me.cmdline()}
            from dataclasses import asdict
            case=asdict(benchmark_fresh.plan_cases(1,2026101300,'both',True)[0])
            launch={'supervisor':ident,'compute_budget_date':'2026-10-13','reservation_id':'mocktrial',
                    'seed':2026101300,'source_sha256':{'mock':'same'}}
            spec={'out':str(out),'case':case,'source_sha256':launch['source_sha256'],'bundle':None,'max_steps':18000,'case_seconds':150}
            (folder/'input.json').write_text(json.dumps(spec),encoding='utf-8')
            (out/'launch.json').write_text(json.dumps(launch),encoding='utf-8')
            (out/'compute_budgets').mkdir()
            (out/'compute_budgets'/'2026-10-13.json').write_text(json.dumps({'items':[{'id':'mocktrial'}]}),encoding='utf-8')
            code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import benchmark_fresh as b;b.ROOT=Path(sys.argv[2]);\ndef fake_worker(path):\n print('AUTHORIZED_WITHOUT_SIMULATOR');return 0\nb.run_worker=fake_worker;raise SystemExit(b.main(['--_worker',sys.argv[3]]))"
            child=subprocess.run([sys.executable,'-B','-X','utf8','-c',code,str(exp),str(out),str(folder/'input.json')],capture_output=True,text=True,timeout=10)
            self.assertEqual(child.returncode,0,child.stderr)
            self.assertIn('AUTHORIZED_WITHOUT_SIMULATOR',child.stdout)
if __name__=='__main__':unittest.main(verbosity=2)

