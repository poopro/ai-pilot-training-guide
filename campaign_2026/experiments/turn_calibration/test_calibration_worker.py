import csv,math,tempfile,unittest
from pathlib import Path
import numpy as np
from calibration_worker import run_case,euler_rates_deg_s,Incomplete,obs_vector
TEST_ROOT=Path(__file__).resolve().parent

class Adapter:
    def __init__(self):
        self.o=np.zeros(26);self.o[2]=12000;self.o[12]=320*1.6878098571011957;self.o[13]=self.o[12]
        self.ticks=0;self.closed=False
    def read_obs(self):return self.o.copy()
    def advance(self,cmd):self.ticks+=1
    def close(self):self.closed=True
class Controller:
    def __init__(self,bad=False):
        self.last=np.array([0.,0.,0.,.8]);self.pitch_integral=self.speed_integral=0.
        self.recovering=False;self.mode='intercept';self.bad=bad;self.modes=[]
    def command(self,o,b,p,s,**kw):
        self.modes.append(self.mode);self.mode='energy_recover' # must not persist to next tick
        self.bank_target=b;self.pitch_target=p;self.speed_target=s
        self.pitch_integral+=.00001
        return np.array([1.1 if self.bad else 0.,0.,0.,.8]),True
class Gates(unittest.TestCase):
    def test_analytic_yaw_includes_q_at_bank(self):
        o=np.zeros(26);o[3]=45;o[10]=.1
        self.assertAlmostEqual(euler_rates_deg_s(o)[2],math.degrees(.1/math.sqrt(2)),places=10)
    def test_singularity_and_bad_shape_fail(self):
        o=np.zeros(26);o[4]=90
        with self.assertRaises(Incomplete):euler_rates_deg_s(o)
        with self.assertRaises(Incomplete):obs_vector(np.zeros((1,26)))
    def test_warmup_and_test_rows_guards_and_state_retained(self):
        a,c=Adapter(),Controller()
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as d:
            r=run_case(a,c,{'case_id':'test','bank_deg':30,'pitch_spec':'nose0'},d,lambda:0.,lambda:False)
            with open(r['csv_path'],newline='') as f:rows=list(csv.DictReader(f))
        self.assertTrue(r['complete']);self.assertEqual(len(rows),2100)
        self.assertEqual(sum(x['phase']=='warmup' for x in rows),900)
        self.assertEqual(r['tick_counts']['guard'],1200)
        self.assertTrue(all(m=='track' for m in c.modes));self.assertTrue(a.closed)
        self.assertAlmostEqual(c.pitch_integral,.021);self.assertFalse(r['combat_score_eligible'])
    def test_bad_commands_do_not_advance(self):
        a=Adapter()
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as d:
            r=run_case(a,Controller(True),{'case_id':'bad'},d,lambda:0.,lambda:False)
        self.assertFalse(r['complete']);self.assertEqual(a.ticks,0)
    def test_stop_and_wall_budget_are_incomplete(self):
        for wall in [False,True]:
            a=Adapter()
            with tempfile.TemporaryDirectory(dir=TEST_ROOT) as d:
                r=run_case(a,Controller(),{'case_id':'bounded'},d,lambda:a.ticks*30 if wall else 0,
                    lambda:a.ticks>=5 and not wall)
            self.assertFalse(r['complete']);self.assertLessEqual(a.ticks,5)
    def test_initial_and_boundary_hashes_match_across_fresh_workers(self):
        hashes=[]
        for bank in [30,70]:
            with tempfile.TemporaryDirectory(dir=TEST_ROOT) as d:
                r=run_case(Adapter(),Controller(),{'case_id':'pair','bank_deg':bank},d,lambda:0.,lambda:False)
            hashes.append((r['initial_state_sha'],r['warmup_boundary_sha']))
        self.assertEqual(hashes[0],hashes[1])

if __name__=='__main__':unittest.main()
