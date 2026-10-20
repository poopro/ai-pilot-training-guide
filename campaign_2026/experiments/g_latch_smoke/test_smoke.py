import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('g_latch_smoke',Path(__file__).with_name('launch_smoke.py'))
smoke=importlib.util.module_from_spec(spec); spec.loader.exec_module(smoke)
module=smoke.load_candidate()
from candidate import Bank80Controller
np=module.np


def obs(g=1.):
    o=np.zeros(26,dtype=float);o[2]=10000.;o[3]=60.;o[12]=340*1.6878098571011957;o[13]=600.;o[14]=g;o[18]=5.
    return o


class LatchTests(unittest.TestCase):
    def test_only_one_control_factor_ast_and_inherited_act(self):
        self.assertTrue(smoke.single_factor_check())
        self.assertIs(module.GGuardLatchBank80.act,Bank80Controller.act)

    def test_no_trigger_is_exactly_original(self):
        old=Bank80Controller({'safety_floor_m':800.});new=module.GGuardLatchBank80({'safety_floor_m':800.})
        for g in (1.,4.,8.,8.5,8.49,-8.5):
            self.assertTrue(np.array_equal(old.command(obs(g),65.,25.,400.)[0],new.command(obs(g),65.,25.,400.)[0]))
            self.assertFalse(new.g_guard_latched)

    def test_hysteresis_boundaries_and_negative_g(self):
        c=module.GGuardLatchBank80({'safety_floor_m':800.})
        for g,expected in ((8.5,False),(8.5001,True),(8.4,True),(8.,True),(7.999,False),(-8.6,True),(-7.9,False)):
            c.command(obs(g),65.,25.,400.)
            self.assertEqual(c.g_guard_latched,expected)

    def test_one_frame_dip_keeps_existing_limiter(self):
        old=Bank80Controller({'safety_floor_m':800.});new=module.GGuardLatchBank80({'safety_floor_m':800.})
        old.command(obs(8.6),65.,25.,400.);new.command(obs(8.6),65.,25.,400.)
        original=old.command(obs(8.4),65.,25.,400.)[0];latched=new.command(obs(8.4),65.,25.,400.)[0]
        self.assertGreater(latched[1],original[1])
        self.assertTrue(np.array_equal(latched[[0,2,3]],original[[0,2,3]]))

    def test_slew_and_trim_are_retained(self):
        old=Bank80Controller({'safety_floor_m':800.});new=module.GGuardLatchBank80({'safety_floor_m':800.})
        old.last[1]=new.last[1]=-.5
        a=old.command(obs(8.6),65.,25.,400.)[0];b=new.command(obs(8.6),65.,25.,400.)[0]
        self.assertTrue(np.array_equal(a,b));self.assertAlmostEqual(b[1],-.42)
        self.assertEqual(old.telemetry['trim'],new.telemetry['trim'])

    def test_init_does_not_change_latch_and_new_instance_resets(self):
        c=module.GGuardLatchBank80({'safety_floor_m':800.});c.g_guard_latched=True
        before=c.last.copy();c.act(obs(),started=False)
        self.assertTrue(c.g_guard_latched);self.assertTrue(np.array_equal(before,c.last))
        self.assertFalse(module.GGuardLatchBank80({'safety_floor_m':800.}).g_guard_latched)

    def test_guard_records_real_popen_parent_exit(self):
        with tempfile.TemporaryDirectory(dir=smoke.EXP) as temp:
            folder=Path(temp);smoke.bench.atomic_json(folder/'launch.json',{'source_sha256':{},'deadline_epoch':100000.})
            smoke.bench.atomic_json(folder/'state.json',{'status':'preparing','supervisor':None,'worker':None})
            child=Mock();child.pid=55;child.poll.return_value=0;child.wait.return_value=0
            with patch.object(smoke,'frozen_sources',return_value={}),patch.object(smoke.subprocess,'Popen',return_value=child),patch.object(smoke.base,'ident',return_value={'pid':55}),patch.object(smoke.base,'cleanup',return_value=[]):
                self.assertEqual(smoke.guardian(folder),0)
            receipt=smoke.base.read(folder/'supervisor_exit.json')
            self.assertTrue(receipt['wait_return_observed']);self.assertEqual(receipt['actual_exit_code'],0)
            child.wait.assert_called()

    def test_smoke_plan_has_exactly_frozen_bank80_and_candidate(self):
        cases=smoke.planned_cases()
        self.assertEqual(len(cases),2);self.assertEqual({c['case']['actor'] for c in cases},{'guide','candidate'})
        self.assertEqual(len({c['initial_sha256'] for c in cases}),1)
        self.assertEqual({c['case']['distance_ft'] for c in cases},{6000})


if __name__=='__main__':unittest.main()
