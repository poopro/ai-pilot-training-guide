"""Static/controller/lifecycle tests only; no FDM or original run rewrite."""
import copy,importlib.util,json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import psutil

spec=importlib.util.spec_from_file_location('near75_test',Path(__file__).with_name('launch_diagnostic.py'))
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)

class DiagnosticTests(unittest.TestCase):
    def test_explicit_two_pairs_four_actor_cases(self):
        cases=tool.known_cases()
        self.assertEqual(len(cases),4);self.assertEqual({r['case']['actor'] for r in cases},set(tool.ACTORS))
        for key in tool.PAIRS:
            pair=[r for r in cases if r['pair_key']==key]
            self.assertEqual(len({r['initial_sha256'] for r in pair}),1)
        self.assertEqual({r['case']['side'] for r in cases},{'mirrored'})

    def test_only_bank_constant_changes_and_command_same(self):
        self.assertTrue(all(tool.ast_check().values()))
        classes=tool.controls();old=classes['bank80_latch'];new=classes['bank75_latch']
        self.assertIs(old.command,new.command);self.assertIs(old.__init__,new.__init__)

    def test_act_changes_near_ceiling_only_without_FDM(self):
        classes=tool.controls()
        from controller import np
        obs=np.zeros(26);obs[[0,20]]=23;obs[[1,21]]=121;obs[[2,22]]=12000
        obs[5]=0;obs[21]+=.005;obs[12]=340*1.6878098571011957;obs[13]=600;obs[15]=600
        a=classes['bank80_latch']({'safety_floor_m':800});b=classes['bank75_latch']({'safety_floor_m':800})
        a.act(obs);b.act(obs)
        self.assertEqual(a.bank_target,80);self.assertEqual(b.bank_target,75)
        self.assertEqual(a.pitch_target,b.pitch_target);self.assertEqual(a.speed_target,b.speed_target)

    def test_atomic_retry_is_bounded_and_writes_real_json(self):
        with tempfile.TemporaryDirectory() as directory:
            destination=Path(directory)/'test.json';real=tool.os.replace;calls=[]
            def retry(source,target):
                calls.append(1)
                if len(calls)<3:
                    error=PermissionError('fixture sharing violation');error.winerror=5;raise error
                return real(source,target)
            with patch.object(tool.os,'replace',side_effect=retry):tool.atomic_json(destination,{'tested':True})
            self.assertEqual(len(calls),3);self.assertTrue(json.loads(destination.read_text())['tested'])

    def test_atomic_retry_never_renews_expired_original_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            original=tool.REAL_TIME.monotonic()-1;error=PermissionError('fixture');error.winerror=5
            with patch.object(tool,'deadline_monotonic',original),patch.object(tool.os,'replace',side_effect=error) as replace:
                with self.assertRaises(PermissionError):tool.atomic_json(Path(directory)/'blocked.json',{})
                self.assertEqual(replace.call_count,1);self.assertEqual(tool.deadline_monotonic,original)

    def test_NoSuchProcess_preserves_command_without_inventing_creation_time(self):
        child=Mock(pid=31337)
        with patch.object(tool.REAL_SUBPROCESS,'Popen',return_value=child),patch.object(tool.psutil,'Process',side_effect=psutil.NoSuchProcess(31337)):
            p=tool.recorded_popen(['fixture','no-FDM']);identity=tool.ident(p.pid)
        self.assertEqual(identity['cmdline'],['fixture','no-FDM']);self.assertIsNone(identity['create_time'])
        self.assertFalse(identity['identity_observed']);self.assertIsNone(tool.live(identity))

    def test_mature_run_is_360s_and_original_source_untouched(self):
        source=Path(tool.base.run.__code__.co_filename)
        self.assertIn('shared_run_case360',str(source))
        self.assertIn(360.,tool.base.run.__code__.co_consts)
        self.assertNotIn(310,tool.base.run.__code__.co_consts)

    def test_gate_rejects_any_candidate_over9_and_attack_regression(self):
        results=[dict(case=dict(actor='bank75_latch',opponent=opponent),overload_ticks=0,peak_abs_g=8.8,
                      metrics=dict(deaths=0,own_crashes=0),attack_ticks=166) for opponent in ('rule','rl')]
        pairs=[dict(pair_key='r000_rule_known',candidate_minus_baseline_common_min_hsl_m=32.)]
        self.assertTrue(tool.decision(results,pairs)['hypothesis_supported_on_known_cases'])
        bad=copy.deepcopy(results);bad[0]['peak_abs_g']=9.00001
        self.assertEqual(tool.decision(bad,pairs)['gate'],'reject_candidate')
        bad=copy.deepcopy(results);bad[1]['attack_ticks']=165
        self.assertFalse(tool.decision(bad,pairs)['hypothesis_supported_on_known_cases'])
        pairs[0]['candidate_minus_baseline_common_min_hsl_m']=0
        self.assertFalse(tool.decision(results,pairs)['hypothesis_supported_on_known_cases'])

    def test_shared_worker_selects_explicit_controller_and_known_initial(self):
        classes=tool.controls()
        from types import SimpleNamespace
        from controller import np
        reference=tool.known_cases()[0]
        initial=tool.read(reference['fixture'])['initial']
        def fake_runtime(_):
            class NoSimulator:pass
            return SimpleNamespace(env=SimpleNamespace(RepairDuel=NoSimulator),RepairController=object)
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);input_path=folder/'input.json'
            manifest=folder/'manifest.json';tool.atomic_json(manifest,dict(trial_id='fixture_no_FDM'))
            for actor in tool.ACTORS:
                case={**reference['case'],'actor':actor}
                tool.atomic_json(input_path,dict(case=case,max_steps=18000,case_seconds=360,diagnostic_source_sha256={}))
                def fake_worker(path):
                    runtime=tool.bench.load_runtime(tool.REPAIR)
                    self.assertIs(runtime.RepairController,classes[actor])
                    env=SimpleNamespace(packet_controller=runtime.RepairController({'safety_floor_m':800}))
                    tool.bench.reset_initial_side(env,'mirrored',runtime)
                    tool.atomic_json(folder/'result.json',dict(case=case,initial=initial,initial_sha256=reference['initial_sha256']))
                    return 0
                with patch.object(tool.engine,'frozen_sources',return_value={}),patch.object(tool.bench,'load_runtime',side_effect=fake_runtime),\
                     patch.object(tool.bench,'run_worker',side_effect=fake_worker),patch.object(tool,'original_reset',return_value=(np.zeros(20),initial)),\
                     patch.object(tool,'MANIFEST',manifest):
                    self.assertEqual(tool.worker(input_path),0)
                self.assertEqual(tool.read(folder/'result.json')['controller_actor'],actor)
                self.assertFalse(tool.read(folder/'result.json')['paired_baseline_is_repair_guide'])

    def test_verify_refuses_legacy_or_missing_new_guardian_handle_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            for name in ('launch.json','state.json','supervisor_exit.json','guard_status.json'):
                tool.atomic_json(folder/name,{})
            with self.assertRaises(FileNotFoundError):tool.verify(folder)

    def test_monotonic_deadline_clock_ignores_later_wallclock_change(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);now=time.monotonic()
            tool.atomic_json(folder/'launch.json',dict(started_epoch=1000,started_monotonic=now-10,deadline_monotonic=now+1190))
            tool.bind_deadline(folder)
            self.assertAlmostEqual(tool.base.time.time(),1010,delta=.1)
            self.assertEqual(tool.deadline_monotonic,now+1190)
        tool.deadline_monotonic=None

    @unittest.skipUnless(os.name=='nt','Windows handle evidence')
    def test_real_mock_guardian_handle_exit_and_missing_process_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);script=folder/'mock_guardian.py'
            script.write_text('import time\ntime.sleep(.3)\n',encoding='utf-8')
            command=[str(tool.PYTHON),'-B','-X','utf8',str(script),'guard','--job',str(folder)]
            child=tool.recorded_popen(command,creationflags=tool.base.NO_WINDOW)
            identity=tool.ident(child.pid);digest=tool.bench.file_hash(script)
            tool.atomic_json(folder/'launch.json',dict(source_sha256={'new/launcher':digest},deadline_monotonic=time.monotonic()+5))
            tool.atomic_json(folder/'guardian_spawn.json',dict(identity=identity,command=command,source_sha256=digest))
            with patch.object(tool,'__file__',str(script)):
                self.assertEqual(tool.observe_guardian(folder),0)
            receipt=tool.read(folder/'guardian_exit_observed.json')
            self.assertTrue(receipt['wait_return_observed']);self.assertEqual(receipt['actual_exit_code'],0)
            child.wait(timeout=5)
            with patch.object(tool,'__file__',str(script)):
                with self.assertRaises(RuntimeError):tool.observe_guardian(folder)

if __name__=='__main__':unittest.main()
