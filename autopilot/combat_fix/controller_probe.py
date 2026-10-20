"""Standalone, bounded single-aircraft PI probe; never imports combat_fix controller.

Only official ownship values are used. No enemy state, policy, network, or GUI.
"""
from pathlib import Path
import argparse
from datetime import datetime
import json
import math
import sys
import time

import numpy as np

BASE = Path(r'E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test')
sys.path.insert(0, str(BASE))
from combat_v3.fdm import JsbsimFdm
from combat_v3.interface import OWN_KEYS, validate_observation


def wrap_deg(x):
    return (float(x)+180.) % 360.-180.


def own_observation(plane):
    own = np.asarray([plane.fdm[k] for k in OWN_KEYS], dtype=np.float64)
    # Unused ENEMY6 slots are a same-position placeholder. The probe reads OWN20.
    return validate_observation(np.r_[own, own[[0, 1, 2, 6, 7, 8]]])


class ProbeController:
    def __init__(self, pitch_ki=0., speed_ki=0., projected_alpha=False,
                 pitch_kp=.035, pitch_kd=.009):
        self.last = np.array([0., 0., 0., .8])
        self.pitch_i = 0.
        self.speed_i = 0.
        self.pitch_ki = float(pitch_ki)
        self.speed_ki = float(speed_ki)
        self.projected_alpha = bool(projected_alpha)
        self.pitch_kp = float(pitch_kp)
        self.pitch_kd = float(pitch_kd)
        self.recovering = False
        self.telemetry = {}

    def command(self, obs, roll_target, pitch_target, speed_target, safety=True):
        o = validate_observation(obs)
        altitude, downward = o[2]*.3048, o[8]*.3048
        cas = o[12]/1.6878098571011957
        roll, pitch, alpha = o[3], o[4], o[18]
        guard = False
        if safety and (altitude < 800 or downward > 10 and altitude/downward < 15):
            self.recovering = True
        if self.recovering and altitude > 1200 and downward <= 0 and cas > 220:
            self.recovering = False
        if safety and self.recovering:
            roll_target, pitch_target, speed_target, guard = 0., 12., 400., True
        if safety and (cas < 180 or alpha > 22):
            roll_target, pitch_target, speed_target, guard = 0., min(pitch, 2.), 420., True
        phi, theta = np.radians([roll, pitch])
        p, q, r = o[9:12]
        pitch_rate = math.degrees(q*math.cos(phi)-r*math.sin(phi))
        roll_rate = math.degrees(p+math.tan(float(np.clip(theta, -.7, .7)))*(q*math.sin(phi)+r*math.cos(phi)))
        trim = .035/max(math.cos(math.radians(min(abs(roll), 75.))), .25)
        pitch_error, speed_error = pitch_target-pitch, speed_target-cas
        if guard:
            self.pitch_i *= .98
            self.speed_i *= .98
        else:
            self.pitch_i = float(np.clip(self.pitch_i+self.pitch_ki*pitch_error/60., -.25, .25))
            self.speed_i = float(np.clip(self.speed_i+self.speed_ki*speed_error/60., -.5, .5))
        aileron = .025*wrap_deg(roll_target-roll)-.008*roll_rate
        elevator = -self.pitch_kp*pitch_error+self.pitch_kd*pitch_rate-trim-self.pitch_i
        throttle = .65+.008*speed_error+self.speed_i
        if guard:
            throttle = 1.
        if safety and abs(o[14]) > 8.5:
            elevator = max(elevator, -.08)
            self.pitch_i = max(0., self.pitch_i-.01)
        target = np.clip([aileron, elevator, 0., throttle], [-1,-1,-1,0], [1,1,1,1])
        self.last += np.clip(target-self.last, [-.12,-.08,-.06,-.025], [.12,.08,.06,.025])
        self.telemetry = {'guard':guard, 'pitch_target':float(pitch_target),
                          'pitch_i':self.pitch_i, 'speed_i':self.speed_i,
                          'pitch_rate_euler':pitch_rate}
        return self.last.copy(), guard

    def level(self, obs, altitude_m, bank, cas=340.):
        o = validate_observation(obs)
        alt, down = o[2]*.3048, o[8]*.3048
        gamma = float(np.clip((altitude_m-alt)*.012+down*.16, -8, 12))
        if self.projected_alpha:
            phi = math.radians(o[3])
            # Solve the own-body velocity projection for zero NED-down velocity.
            baseline = math.degrees(math.atan2(o[16]*math.sin(phi)+o[17]*math.cos(phi), max(o[15], 1.)))
        else:
            baseline = o[18]
        pitch = float(np.clip(baseline+gamma, -18, 25))
        return self.command(o, bank, pitch, cas)


def run_case(label, pitch_ki, speed_ki, projected_alpha, bank, seconds):
    plane = JsbsimFdm(fdm_ic_lat=24, fdm_ic_long=121, fdm_ic_h=14000,
                     fdm_ic_v=340, fdm_ic_psi=0)
    controller = ProbeController(pitch_ki, speed_ki, projected_alpha)
    target_alt = 14000*.3048
    rows = []
    guard_frames = 0
    all_tick_max_g = 0.
    all_tick_min_alt = target_alt
    all_tick_max_alt = target_alt
    all_tick_min_cas = 340.
    all_tick_max_cas = 340.
    heading_turn = 0.
    prev_heading = 0.
    started = time.monotonic()
    for step in range(round(seconds*60)):
        obs = own_observation(plane)
        command, guard = controller.level(obs, target_alt, bank)
        plane.sendAction(command)
        plane.step()
        guard_frames += int(guard)
        now = own_observation(plane)
        all_tick_max_g = max(all_tick_max_g, abs(float(now[14])))
        all_tick_min_alt = min(all_tick_min_alt, now[2]*.3048)
        all_tick_max_alt = max(all_tick_max_alt, now[2]*.3048)
        all_tick_min_cas = min(all_tick_min_cas, now[12]/1.6878098571011957)
        all_tick_max_cas = max(all_tick_max_cas, now[12]/1.6878098571011957)
        heading_turn += wrap_deg(now[5]-prev_heading)
        prev_heading = now[5]
        if step % 6 == 0:
            rows.append([float((step+1)/60), now[2]*.3048,
                         now[12]/1.6878098571011957, float(now[3]), float(now[4]),
                         float(abs(now[14])), now[8]*.3048,
                         controller.telemetry['pitch_target'], controller.pitch_i,
                         controller.speed_i, float(command[1]), float(command[3])])
    a = np.asarray(rows)
    last = a[a[:, 0] >= max(0., seconds-60.)]
    return {
        'label':label, 'pitch_ki':pitch_ki, 'speed_ki':speed_ki,
        'projected_alpha':projected_alpha, 'bank_target_deg':bank, 'seconds':seconds,
        'final_altitude_m':float(now[2]*.3048), 'min_altitude_m':float(all_tick_min_alt),
        'max_altitude_m':float(all_tick_max_alt), 'max_altitude_error_m':float(max(abs(all_tick_min_alt-target_alt), abs(all_tick_max_alt-target_alt))),
        'last60_max_altitude_error_m':float(abs(last[:,1]-target_alt).max()),
        'last60_altitude_mean_m':float(last[:,1].mean()),
        'final_cas_kts':float(now[12]/1.6878098571011957), 'min_cas_kts':float(all_tick_min_cas),
        'max_cas_kts':float(all_tick_max_cas), 'last60_cas_mean_kts':float(last[:,2].mean()),
        'last60_cas_max_error_kts':float(abs(last[:,2]-340).max()),
        'final_bank_deg':float(now[3]), 'max_g':float(all_tick_max_g),
        'final_downward_mps':float(now[8]*.3048), 'guard_frames':guard_frames,
        'heading_turn_deg':heading_turn, 'pitch_i_final':controller.pitch_i,
        'speed_i_final':controller.speed_i, 'wall_seconds':time.monotonic()-started,
        'trace_columns':['time_s','altitude_m','cas_kts','bank_deg','pitch_deg','abs_g',
                         'downward_mps','pitch_target','pitch_i','speed_i','elevator','throttle'],
        'trace':rows,
    }


def run_dynamic_case(kp, kd, bank, seconds=120., pitch_ki=.0015, pitch_ff_seconds=0.):
    """Synthetic LOS-like pitch sine: 5 +/- 3 deg, 24 s period, peak .785 deg/s."""
    plane = JsbsimFdm(fdm_ic_lat=24, fdm_ic_long=121, fdm_ic_h=14000,
                     fdm_ic_v=340, fdm_ic_psi=0)
    controller = ProbeController(pitch_ki, .0008, True, kp, kd)
    rows = []
    max_g, min_alt, guards = 0., 14000*.3048, 0
    omega = 2*math.pi/24.
    for step in range(round(seconds*60)):
        obs = own_observation(plane)
        t = step/60.
        target = 5.+3.*math.sin(omega*t)+pitch_ff_seconds*3.*omega*math.cos(omega*t)
        action, guard = controller.command(obs, bank, target, 340.)
        plane.sendAction(action)
        plane.step()
        now = own_observation(plane)
        expected = 5.+3.*math.sin(omega*(t+1/60.))
        max_g = max(max_g, abs(float(now[14])))
        min_alt = min(min_alt, now[2]*.3048)
        guards += int(guard)
        if step % 6 == 0:
            rows.append([t+1/60., expected, float(now[4]), float(now[4]-expected),
                         now[2]*.3048, now[12]/1.6878098571011957,
                         float(now[3]), controller.pitch_i, float(action[1])])
    a = np.asarray(rows)
    steady = a[a[:,0] >= 48.]
    return {'pitch_kp':kp, 'pitch_kd':kd, 'pitch_ki':pitch_ki, 'cas_ki':.0008,
            'pitch_ff_seconds':pitch_ff_seconds,
            'bank_target_deg':bank, 'seconds':seconds,
            'pitch_target_description':'5 +/- 3 deg sine; period 24s; peak rate .785deg/s',
            'steady_pitch_rmse_deg':float(np.sqrt(np.mean(steady[:,3]**2))),
            'steady_pitch_max_error_deg':float(abs(steady[:,3]).max()),
            'steady_pitch_bias_deg':float(steady[:,3].mean()),
            'max_g':max_g, 'min_altitude_m':min_alt,
            'final_altitude_m':float(now[2]*.3048),
            'final_cas_kts':float(now[12]/1.6878098571011957),
            'steady_cas_max_error_kts':float(abs(steady[:,5]-340).max()),
            'guard_frames':guards, 'pitch_i_final':controller.pitch_i,
            'trace_columns':['time_s','pitch_target_deg','pitch_actual_deg','pitch_error_deg',
                             'altitude_m','cas_kts','bank_deg','pitch_i','elevator'],
            'trace':rows}


def main():
    parser = argparse.ArgumentParser(description='Bounded, single-aircraft PI probe; no training or GUI.')
    parser.add_argument('--seconds', type=float, default=180.)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--dynamic', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 300:
        parser.error('seconds must be 1..300')
    variants = [
        ('baseline', 0., 0., False),
        ('pi_slow', .0006, .0004, False),
        ('pi_medium', .0015, .0008, False),
        ('pi_projected', .0015, .0008, True),
        ('pi_projected_fast', .003, .0008, True),
    ]
    out = args.out or Path(__file__).parent/'diagnostics'/('controller_probe_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    report = {'status':'running', 'official_validation':False,
              'training_steps_added':0, 'input_contract':'OWN20 of official 26 doubles; ENEMY6 unused',
              'cases':[]}
    if args.dynamic:
        cases = ((kp, kd, bank) for bank in (0.,55.,70.) for kp in (.035,.05,.07) for kd in (.009,.012))
        for kp, kd, bank in cases:
            result = run_dynamic_case(kp, kd, bank, args.seconds)
            report['cases'].append(result)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
            print(json.dumps({k:v for k,v in result.items() if k not in ('trace','trace_columns')}, ensure_ascii=False), flush=True)
    else:
        for label, pki, ski, projected in variants:
            for bank in (0., 55., 70.):
                result = run_case(label, pki, ski, projected, bank, args.seconds)
                report['cases'].append(result)
                out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
                print(json.dumps({k:v for k,v in result.items() if k not in ('trace','trace_columns')}, ensure_ascii=False), flush=True)
    report['status'] = 'completed'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print('REPORT '+str(out), flush=True)


if __name__ == '__main__':
    main()
