"""Regression checks for the isolated repair, exact local judge, and legal ICD.

The integration checks run frozen zero residual guidance against moving aircraft.
Judge truth is used only by assertions; it is never fed back to the controller.
No training, network, GUI, or judge monkey-patching is performed.
"""
from pathlib import Path
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import sys
import time
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from controller import RepairController, BASE
from env import RepairDuel, precision_terms
from duel_lab import DiagnosticJudge
from combat_v3.controller import wrap_deg
from combat_v3.interface import simulator_observation, geometry_from_observation

SETTINGS = json.loads((BASE/'combat_v3/config.json').read_text(encoding='utf8'))
EVIDENCE = {}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {str(p):sha256(p) for p in (ROOT/'controller.py', ROOT/'env.py',
        BASE/'combat_v3/interface.py', BASE/'combat_v3/rules.py',
        BASE/'combat_v3/config.json',
        Path(r'E:\ai_pilot\autopilot\opponent_lab\duel_lab.py'))}


def sample_observation():
    speed_fps = 340.*1.6878098571011957
    return np.array([24.,121.,14000.,0.,0.,0.,speed_fps,0.,0.,
                     0.,0.,0.,speed_fps,speed_fps,1.,speed_fps,0.,0.,3.,0.,
                     24.+math.degrees(600./6378137.),121.,14000.,speed_fps,0.,0.])


class RepairChecks(unittest.TestCase):
    def assert_legal(self, command):
        a = np.asarray(command)
        self.assertEqual(a.shape, (4,))
        self.assertTrue(np.isfinite(a).all())
        self.assertTrue(np.all(a >= [-1.,-1.,-1.,0.]))
        self.assertTrue(np.all(a <= [1.,1.,1.,1.]))

    def test_coordinated_turn_damps_euler_pitch_rate(self):
        observation = sample_observation()
        observation[3] = 60.
        yaw_rate = .1
        observation[10] = yaw_rate*math.sin(math.radians(60.))
        observation[11] = yaw_rate*math.cos(math.radians(60.))
        control = RepairController(SETTINGS)
        command, guard = control.command(observation, 60., 0., 340.)
        self.assertFalse(guard)
        self.assert_legal(command)
        self.assertAlmostEqual(control.telemetry['pitch_rate_euler_deg_s'], 0., places=12)
        self.assertAlmostEqual(control.telemetry['trim'], .07, places=12)
        self.assertAlmostEqual(command[1], -.07, places=12)
        EVIDENCE['coordinated_turn'] = {
            'body_q_deg_s':math.degrees(observation[10]),
            'body_r_deg_s':math.degrees(observation[11]),
            'euler_pitch_rate_deg_s':control.telemetry['pitch_rate_euler_deg_s'],
            'command':command.tolist()}

    def test_legal_rate_limits_integral_bounds_and_init_state(self):
        observation = sample_observation()
        control = RepairController(SETTINGS)
        limits = np.array([.12,.08,.06,.025])
        for i in range(240):
            previous = control.last.copy()
            roll, pitch, speed, rudder = ((72.,25.,450.,1.) if i < 120 else (-72.,-18.,260.,-1.))
            command, _ = control.command(observation, roll, pitch, speed, rudder)
            self.assert_legal(command)
            self.assertTrue(np.all(abs(command-previous) <= limits+1e-12))
            self.assertLessEqual(abs(control.pitch_integral), .25+1e-12)
            self.assertTrue(-.5-1e-12 <= control.speed_integral <= .5+1e-12)
        before = copy.deepcopy(control.__dict__)
        for _ in range(20):
            command, guard = control.act(observation, np.ones(4), started=False)
            np.testing.assert_array_equal(command, [0.,0.,0.,.8])
            self.assertFalse(guard)
        self.assertEqual(set(before), set(control.__dict__))
        for name, value in before.items():
            if isinstance(value, np.ndarray):
                np.testing.assert_array_equal(value, control.__dict__[name])
            else:
                self.assertEqual(value, control.__dict__[name], name)
        EVIDENCE['init_state_preserved'] = True

    def test_invalid_official_observations_are_rejected(self):
        invalid = [np.zeros(25), np.zeros(27)]
        for index, value in ((0,91.),(1,181.),(20,-91.),(21,-181.),(2,float('nan')),(12,float('inf'))):
            observation = sample_observation()
            observation[index] = value
            invalid.append(observation)
        for observation in invalid:
            with self.subTest(shape=observation.shape, invalid=observation.tolist()):
                with self.assertRaises(ValueError):
                    RepairController(SETTINGS).act(observation, np.zeros(4), started=True)

    def test_official_reset_preserves_side_opposite_ic(self):
        measurements = []
        for distance_ft in (3000,6000,9000):
            with self.subTest(distance_ft=distance_ft):
                environment = RepairDuel(p2='rule', stage='official',
                    attack_angle=1., max_steps=12, distance_ft=distance_ft)
                try:
                    state, info = environment.reset(seed=20271000)
                    blue = simulator_observation(environment.fdm1,environment.fdm2)
                    red = simulator_observation(environment.fdm2,environment.fdm1)
                    self.assertEqual(state.shape, (20,))
                    self.assertTrue(np.isfinite(state).all())
                    self.assertEqual(info['training_stage'], 'official')
                    self.assertIs(info['official_validation'], False)
                    self.assertAlmostEqual(environment.geometry['distance_m']/.3048,distance_ft,delta=.5)
                    self.assertAlmostEqual(blue[2],red[2],places=6)
                    self.assertTrue(10000. <= blue[2] <= 20000.)
                    self.assertAlmostEqual(blue[12]/1.6878098571011957,340.,places=6)
                    self.assertAlmostEqual(red[12]/1.6878098571011957,340.,places=6)
                    self.assertAlmostEqual(abs(wrap_deg(blue[5]-red[5])),180.,places=6)
                    self.assertAlmostEqual(environment.geometry['blue_angle_deg'],90.,delta=.1)
                    self.assertAlmostEqual(environment.geometry['red_angle_deg'],90.,delta=.1)
                    geo = geometry_from_observation(blue)
                    self.assertAlmostEqual(abs(wrap_deg(geo['bearing_deg']-blue[5])),90.,delta=.1)
                    measurements.append({'distance_ft':distance_ft,
                        'actual_distance_ft':environment.geometry['distance_m']/.3048,
                        'shared_altitude_ft':float(blue[2]), 'blue_cas_kts':float(blue[12]/1.6878098571011957),
                        'red_cas_kts':float(red[12]/1.6878098571011957),
                        'blue_heading_deg':float(blue[5]),'red_heading_deg':float(red[5])})
                finally:
                    environment.close()
        EVIDENCE['official_initial_conditions'] = measurements

    def test_curriculum_rear_is_labeled_training(self):
        environment = RepairDuel(p2='mixed', stage='rear', attack_angle=1., max_steps=12)
        try:
            _, info = environment.reset(seed=20271000)
            self.assertEqual(info['training_stage'],'rear')
            self.assertNotEqual(info['training_stage'],'official')
            self.assertIs(info['official_validation'],False)
            self.assertEqual(environment.p2_type,'rule')
            self.assertTrue(500. <= environment.geometry['distance_m'] <= 751.)
            self.assertLess(environment.geometry['blue_angle_deg'],2.1)
            self.assertGreater(environment.geometry['red_angle_deg'],177.9)
            blue = simulator_observation(environment.fdm1,environment.fdm2)
            red = simulator_observation(environment.fdm2,environment.fdm1)
            self.assertAlmostEqual(blue[2],red[2],places=6)
            self.assertAlmostEqual(blue[12]/1.6878098571011957,340.,places=6)
            self.assertAlmostEqual(red[12]/1.6878098571011957,340.,places=6)
            _, _, _, _, step_info = environment.step(np.zeros(4,dtype=np.float32))
            self.assertEqual(step_info['training_stage'],'rear')
            self.assertEqual(step_info['p2_mode'],'training_level')
            self.assertIs(step_info['official_validation'],False)
        finally:
            environment.close()

    def test_precision_improves_before_one_degree_window(self):
        values = [precision_terms({'distance_m':550.,'blue_angle_deg':angle}) for angle in (20.,5.,1.)]
        for term in range(3):
            self.assertLess(values[0][term], values[1][term])
            self.assertLess(values[1][term], values[2][term])
        EVIDENCE['precision_angles_20_5_1'] = [list(v) for v in values]

    def test_exact_diagnostic_window_and_179_180_frame_kill(self):
        judge = DiagnosticJudge(SETTINGS['reference_score_weights'],1.)
        for distance in (500*.3048,3000*.3048):
            self.assertTrue(judge.window(distance,1.))
        self.assertFalse(judge.window(500*.3048-1e-8,1.))
        self.assertFalse(judge.window(3000*.3048+1e-8,1.))
        self.assertTrue(judge.window(550.,0.))
        self.assertFalse(judge.window(550.,-1e-8))
        self.assertFalse(judge.window(550.,1.+1e-8))
        geometry = {'distance_m':550.,'blue_angle_deg':1.,'red_angle_deg':180.}
        for _ in range(179):
            judge.update(geometry,1.,1.)
        self.assertEqual(judge.attack,[179,0])
        self.assertEqual(judge.outcome(False,False),'ongoing')
        judge.update({'distance_m':550.,'blue_angle_deg':1.00001,'red_angle_deg':180.},1.,1.)
        self.assertEqual(judge.attack,[179,0])
        self.assertEqual(judge.outcome(False,False),'ongoing')
        judge.update(geometry,1.,1.)
        self.assertEqual(judge.attack,[180,0])
        self.assertEqual(judge.outcome(False,False),'kill')
        EVIDENCE['exact_judge'] = {'range_m':[500*.3048,3000*.3048],
                                  'angle_deg':1.,'kill_ticks':180,'not_kill_ticks':179}

    def run_zero_residual_duel(self, stage, seed):
        environment = RepairDuel(p2='rule', stage=stage, controller='repair',
            reward_profile='precision', attack_angle=1., max_steps=18000,distance_ft=3000)
        ticks, independent_blue, independent_red = 0,0,0
        min_height, max_g, guards = float('inf'),0.,0
        started = time.monotonic()
        try:
            environment.reset(seed=seed)
            initial_red = simulator_observation(environment.fdm2,environment.fdm1)[:3].copy()
            self.assertEqual(environment.judge.angle_deg,1.)
            terminated, truncated = False,False
            for ticks in range(1,18001):
                _, reward, terminated, truncated, info = environment.step(np.zeros(4,dtype=np.float32))
                self.assertTrue(math.isfinite(reward))
                geometry = environment.geometry
                distance = geometry['distance_m']
                independent_blue += int(500*.3048 <= distance <= 3000*.3048 and 0. <= geometry['blue_angle_deg'] <= 1.)
                independent_red += int(500*.3048 <= distance <= 3000*.3048 and 0. <= geometry['red_angle_deg'] <= 1.)
                self.assertEqual(environment.judge.attack,[independent_blue,independent_red])
                min_height = min(min_height,info['altitude_m'])
                max_g = max(max_g,info['load_factor'])
                guards += int(info['guard_active'])
                self.assert_legal(info['actual_action'])
                if terminated or truncated:
                    break
            final_red = simulator_observation(environment.fdm2,environment.fdm1)[:3]
            final_details = {'stage':stage,'seed':seed,'ticks':ticks,'seconds':ticks/60.,
                'terminated':terminated,'truncated':truncated,'outcome':info['outcome'],
                'angle_deg':environment.judge.angle_deg,'independent_attack_ticks':independent_blue,
                'enemy_attack_ticks':independent_red,'attack_seconds':info['attack_seconds'],
                'min_altitude_m':min_height,'max_g':max_g,'guard_frames':guards,
                'initial_red_position':initial_red.tolist(),'final_red_position':final_red.tolist(),
                'wall_seconds':time.monotonic()-started,'official_validation':False}
            EVIDENCE['zero_residual_'+stage] = final_details
            self.assertTrue(terminated)
            self.assertFalse(truncated)
            self.assertEqual(info['outcome'],'kill')
            self.assertEqual(independent_blue,180)
            self.assertAlmostEqual(info['attack_seconds'],3.,places=12)
            self.assertGreater(float(np.linalg.norm(final_red-initial_red)),1e-5)
            self.assertEqual(info['mean_residual'],0.)
            self.assertEqual(info['training_stage'],stage)
            self.assertIs(info['official_validation'],False)
        finally:
            environment.close()

    def test_rear_zero_residual_kills_moving_red_at_true_one_degree(self):
        self.run_zero_residual_duel('rear',20271000)

    def test_official_zero_residual_regression_kill_at_true_one_degree(self):
        self.run_zero_residual_duel('official',20271000)


class JsonResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.cases = []
    def addSuccess(self,test):
        super().addSuccess(test)
        self.cases.append({'test':test.id(),'status':'passed'})
    def addFailure(self,test,err):
        super().addFailure(test,err)
        self.cases.append({'test':test.id(),'status':'failed','error':self._exc_info_to_string(err,test)})
    def addError(self,test,err):
        super().addError(test,err)
        self.cases.append({'test':test.id(),'status':'error','error':self._exc_info_to_string(err,test)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=ROOT/'diagnostics/test_repair_report.json')
    args = parser.parse_args()
    before = sources()
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RepairChecks)
    result = unittest.TextTestRunner(verbosity=2,resultclass=JsonResult).run(suite)
    after = sources()
    report = {'status':'passed' if result.wasSuccessful() and before == after else 'failed',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'cases':result.cases,'evidence':EVIDENCE,'sources_before':before,'sources_after':after,
        'source_drift':before != after,'wall_seconds':time.monotonic()-started,
        'finished_utc':datetime.now(timezone.utc).isoformat(),'official_validation':False,
        'training_steps_added':0,'test_source_sha256':sha256(Path(__file__))}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'report':str(args.out),'status':report['status'],
                      'tests_run':result.testsRun,'source_drift':report['source_drift']},ensure_ascii=False),flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
