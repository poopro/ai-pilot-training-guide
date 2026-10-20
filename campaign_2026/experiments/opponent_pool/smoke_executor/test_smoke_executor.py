"""Non-FDM checks. Dummy-process tests only touch their own spawned process."""
import unittest,tempfile,subprocess,time,sys,json
from pathlib import Path
from unittest.mock import patch
import common
import run_smoke

class Gates(unittest.TestCase):
    def test_grid_has_six_independent_guide_mirrors(self):
        cases=common.prep.plan_cases()
        self.assertEqual(common.prep.assert_plan(cases)['self_play_cases'],6)
        self.assertTrue(all(x['max_steps']==300 and x['blue_controller']=='repair_guide' and x['score_eligible'] is False for x in cases))
    def test_bad_controls_rejected_before_application(self):
        for command in ([0,0,0,float('nan')],[0,0,0,1.01],[1.001,0,0,.8],[0,0,.1],[0,0,0,-.1]):
            with self.assertRaises(ValueError):common.legal_command(command)
        self.assertEqual(common.legal_command([-1,1,0,1]),[-1.,1.,0.,1.])
    def test_seed_collision_and_holdout_blocked(self):
        cases=common.prep.plan_cases()
        self.assertFalse(common.prep.seed_status({'reserved_holdout_seeds':[cases[0]['seed']]},cases)['fresh_relative_to_registry'])
        self.assertFalse(common.prep.seed_status({'trials':{'old':{'seeds':[cases[0]['seed']]}}},cases)['fresh_relative_to_registry'])
    def test_forged_identity_does_not_match_own_dummy(self):
        p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(5)'],creationflags=common.NO_WINDOW)
        try:
            ident=common.identity(p.pid);self.assertIsNotNone(common.matching(ident))
            ident['cmdline']=['wrong-command'];self.assertIsNone(common.matching(ident));self.assertIsNone(p.poll())
        finally:p.terminate();p.wait(timeout=3)
    def test_guard_no_armed_record_blocks_without_FDM(self):
        import jsbsim
        with tempfile.TemporaryDirectory(dir=common.HERE) as td,patch.object(jsbsim,'FGFDMExec',side_effect=AssertionError('FDM forbidden')) as fdm:
            common.write(Path(td)/'STOP',{})
            with self.assertRaisesRegex(RuntimeError,'STOP'):run_smoke.await_guard(Path(td),{'supervisor':common.identity()})
            self.assertEqual(fdm.call_count,0)
    def test_direct_worker_wrong_parent_blocked_without_FDM(self):
        import jsbsim
        case=common.prep.plan_cases()[0]
        with tempfile.TemporaryDirectory(dir=common.HERE) as td,patch.object(jsbsim,'FGFDMExec',side_effect=AssertionError('FDM forbidden')) as fdm:
            out=Path(td);folder=out/'cases'/case['case_id'];folder.mkdir(parents=True)
            common.write(folder/'input.json',{'out':str(out),'case':case})
            common.write(out/'launch.json',{'supervisor':{'pid':-9876}})
            with self.assertRaisesRegex(RuntimeError,'ownership'):run_smoke.worker(folder/'input.json')
            self.assertEqual(fdm.call_count,0)
    def test_source_mismatch_rejected(self):
        with patch.object(common.prep,'frozen_status',return_value={'verified':False,'changed':['controller']}):
            with self.assertRaisesRegex(RuntimeError,'Frozen source'):common.source_gate()
    def test_access_denied_is_unknown(self):
        with patch.object(common.psutil,'Process',side_effect=common.psutil.AccessDenied(100)):
            with self.assertRaises(common.psutil.AccessDenied):common.matching({'pid':100,'creation_epoch':1,'cmdline':[]})

    def test_verifier_complete_mock_and_missing_tick_rejection(self):
        import csv
        import verify_smoke
        import jsbsim
        with tempfile.TemporaryDirectory(dir=common.HERE) as td,patch.object(jsbsim,'FGFDMExec',side_effect=AssertionError('FDM forbidden')) as fdm,patch.object(verify_smoke,'source_gate',return_value={}):
            out=Path(td);cases=common.prep.plan_cases();ident={'pid':1,'creation_epoch':1,'cmdline':['mock']}
            launch={'cases':cases,'tools_sha256':common.tools(),'source_freeze':{},'supervisor':ident}
            common.write(out/'launch.json',launch);common.write(out/'reservation.json',{'scope':'mock fixture only'})
            common.write(out/'supervisor_exit.json',{'identity':ident,'actual_parent_exit_code':0})
            common.write(out/'guard.json',{'status':'finished','unknown':[],'reason':'supervisor_missing'})
            common.write(out/'launcher_receipt.json',{'actual_parent_exit_code':0,'actual_guard_exit_code':0,'launch_sha256':common.sha(out/'launch.json'),'reservation_sha256':common.sha(out/'reservation.json')})
            items=[]
            for case in cases:
                folder=out/'cases'/case['case_id'];folder.mkdir(parents=True)
                common.write(folder/'input.json',{'case':case,'tools_sha256':launch['tools_sha256'],'source_freeze':{}})
                fields=['tick','simulation_seconds','blue_observation_sha256','red_observation_sha256','blue_command','red_command','distance_m','blue_altitude_m','red_altitude_m','blue_g','red_g']
                with (folder/'telemetry.csv').open('w',newline='',encoding='utf8') as f:
                    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
                    for tick in range(1,301):w.writerow(dict(tick=tick,simulation_seconds=tick/60,blue_observation_sha256='a'*64,red_observation_sha256='b'*64,blue_command='[0,0,0,0.8]',red_command='[0,0,0,0.8]',distance_m=1000,blue_altitude_m=4500,red_altitude_m=4500,blue_g=1,red_g=1))
                (folder/'duel.acmi').write_text('FileType=text/acmi/tacview\n'+''.join(f'#{tick/60:.3f}\n1,T=1|2|3|4|5|6\n2,T=1|2|3|4|5|6\n' for tick in range(301)),encoding='utf8')
                own=[0.]*20;own[2]=15000;own[12]=340
                initial={'red_own20_audit_only':own,'blue_own20_audit_only':own,'cross_track_m':-1000 if case['side']=='normal' else 1000,'distance_m':1000}
                record={'case':case,'worker_identity':ident,'status':'interface_pass','score_eligible':False,'official_validation':False,'wall_seconds':1,'steps':300,'legal_termination':False,'command_counts':{'blue':300,'red':300},'independent_rng':True,'independent_controller_state':True,'policy_observation':'OWN20+ENEMY6','source_freeze':{},'initial':initial,'initial_sha256':common.jsha(initial),'artifact_sha256':{n:common.sha(folder/n) for n in ('telemetry.csv','duel.acmi')},'blue_rng_initial_sha256':'c'*64,'red_rng_initial_sha256':'d'*64}
                common.write(folder/'result.json',record)
                item={'identity':ident,'case_id':case['case_id'],'actual_worker_exit_code':0,'input_sha256':common.sha(folder/'input.json'),'result_sha256':common.sha(folder/'result.json')}
                common.write(folder/'worker_exit.json',item);items.append(item)
            report={'status':'completed','cases':items,'wall_seconds':10,'plan_sha256':common.jsha(cases),'score_eligible':False,'official_validation':False};common.write(out/'report.json',report)
            receipt=common.read(out/'launcher_receipt.json');receipt.update(report_sha256=common.sha(out/'report.json'),guard_sha256=common.sha(out/'guard.json'));common.write(out/'launcher_receipt.json',receipt)
            self.assertTrue(verify_smoke.verify(out)['verified_interface_smoke'])
            folder=out/'cases'/cases[0]['case_id'];lines=(folder/'telemetry.csv').read_text().splitlines();(folder/'telemetry.csv').write_text('\n'.join(lines[:-1])+'\n')
            record=common.read(folder/'result.json');record['artifact_sha256']['telemetry.csv']=common.sha(folder/'telemetry.csv');common.write(folder/'result.json',record)
            items[0]['result_sha256']=common.sha(folder/'result.json');common.write(folder/'worker_exit.json',items[0]);common.write(out/'report.json',report)
            receipt['report_sha256']=common.sha(out/'report.json');common.write(out/'launcher_receipt.json',receipt)
            result=verify_smoke.verify(out)
            self.assertFalse(result['verified_interface_smoke']);self.assertIn('CSV tick coverage',result['errors'][0]);self.assertEqual(fdm.call_count,0)

    def test_independent_guard_stops_only_owned_dummy(self):
        import guard
        p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(5)'],creationflags=common.NO_WINDOW)
        try:
            with tempfile.TemporaryDirectory(dir=common.HERE) as td:
                out=Path(td);common.write(out/'launch.json',{'supervisor':common.identity(p.pid)});common.write(out/'STOP',{})
                self.assertEqual(guard.run_guard(out),0)
                self.assertIsNotNone(p.poll());receipt=common.read(out/'guard.json')
                self.assertEqual(receipt['reason'],'STOP');self.assertIn(p.pid,[item['identity']['pid'] for item in receipt['stopped']])
        finally:
            if p.poll() is None:p.terminate();p.wait(timeout=3)

    def test_missing_exit_receipt_is_a_saved_failed_verdict(self):
        import verify_smoke
        with tempfile.TemporaryDirectory(dir=common.HERE) as td:
            result=verify_smoke.verify(Path(td))
            self.assertFalse(result['verified_interface_smoke'])
            self.assertTrue((Path(td)/'VERIFICATION.json').is_file())

if __name__=='__main__':unittest.main()
