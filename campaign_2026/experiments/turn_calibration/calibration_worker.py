"""Bounded 60 Hz calibration worker for the UNCHANGED RepairController.

One worker = one fresh adapter + one fresh controller + exactly ONE case:
900 warmup ticks then 1200 test ticks (2100 expected); seven cases mean seven
fresh worker processes, never a loop over one adapter/controller. Measurement
only: no gain, trim, PI, guard, rudder-sign or learner change appears here.
numpy + stdlib only; no CLI, no guessed local paths, no invented FDM init.
"""
import csv
import hashlib
import json
import math
import os
import time

import numpy as np

DT = 1.0 / 60.0
WARMUP_TICKS, TEST_TICKS, EXPECTED_TICKS = 900, 1200, 2100
FT_TO_M, FPS_TO_KTS = 0.3048, 1.0 / 1.6878098571011957
WALL_BUDGET_S, FINALIZE_RESERVE_S = 150.0, 6.0   # parent also kills this child at 150 s
STEP_DEADLINE_S = WALL_BUDGET_S - FINALIZE_RESERVE_S  # reserve to flush, close, return
CMD_LO, CMD_HI = np.array([-1.0, -1.0, -1.0, 0.0]), np.array([1.0, 1.0, 1.0, 1.0])
BOUND_TOL, SINGULAR_COS_THETA = 1e-9, 0.05
OBS_KEYS = ('lat_gc_deg', 'lon_gc_deg', 'h_sl_ft', 'phi_deg', 'theta_deg', 'psi_deg', 'v_north_fps',
            'v_east_fps', 'v_down_fps', 'p_rad_s', 'q_rad_s', 'r_rad_s', 'vc_fps', 'vt_fps',
            'pilot_z_norm', 'u_fps', 'v_fps', 'w_fps', 'alpha_deg', 'beta_deg', 'enemy_lat_gc_deg',
            'enemy_lon_gc_deg', 'enemy_h_sl_ft', 'enemy_v_north_fps', 'enemy_v_east_fps',
            'enemy_v_down_fps')
CSV_COLS = (['phase', 'tick', 'sim_time_s', 'wall_s'] + ['pre_' + k for k in OBS_KEYS]
            + ['post_' + k for k in OBS_KEYS]
            + ['cmd_aileron', 'cmd_elevator', 'cmd_rudder', 'cmd_throttle', 'bank_target_deg',
               'pitch_target_deg', 'speed_target_cas_kts', 'guard_active', 'mode_before', 'mode_after',
               'effective_bank_target_deg', 'effective_pitch_target_deg', 'effective_speed_target_cas_kts',
               'pitch_integral', 'speed_integral', 'recovering_before', 'recovering_after',
               'euler_roll_rate_deg_s', 'euler_pitch_rate_deg_s', 'euler_yaw_rate_deg_s',
               'euler_roll_rate_clipped_deg_s', 'euler_roll_singular', 'fd_roll_rate_deg_s',
               'fd_pitch_rate_deg_s', 'fd_yaw_rate_deg_s', 'bank_error_deg', 'pitch_error_deg',
               'speed_error_cas_kts', 'pilot_load_signed', 'pilot_load_abs', 'alpha_deg', 'beta_deg',
               'cas_kts', 'tas_kts', 'alt_msl_m', 'sec_bank_denominator_observed'])
STAT_KEYS = ('pre_phi_deg', 'pre_theta_deg', 'pre_psi_deg', 'bank_error_deg', 'pitch_error_deg',
             'speed_error_cas_kts', 'alpha_deg', 'beta_deg', 'cas_kts', 'pilot_load_signed',
             'euler_roll_rate_deg_s', 'euler_pitch_rate_deg_s', 'euler_yaw_rate_deg_s',
             'fd_roll_rate_deg_s', 'fd_pitch_rate_deg_s', 'fd_yaw_rate_deg_s')
CAVEATS = ('short 1200 tick calibration, not an 18000 tick combat comparison; '
 'official_validation=False and combat_score_eligible=False on every record',
           'sec_bank_denominator_observed only mirrors the controller trim denominator:1/cos(bank) '
           'and |pilot load| are NOT asserted calibrated here',
           'Euler singularity |cos(theta)|<0.05 fails this calibration (not cos(phi)=0); '
           'a median bank error is not a roll rate; 8.5G guard != 9G scoring',
           'AGL and enemy attitude are absent from the ICD and are not synthesized')


class Incomplete(RuntimeError):
    """Stop request, wall deadline or contract failure: the run stays incomplete."""


def obs_vector(raw):
    """Legal observation: exactly 26 finite doubles; never clipped, padded or repaired."""
    o = np.asarray(raw, dtype=np.float64)
    if o.shape != (26,) or not bool(np.isfinite(o).all()):
        raise Incomplete('numerical: observation must be 26 finite doubles')
    return o


def state_sha(obs, controller, tick):
    """Process-independent SHA over obs26 + last command + integrals + recovering + mode."""
    body = ['t=%d' % int(tick)]
    body += [float(v).hex() for v in np.asarray(obs, dtype=np.float64).reshape(-1)]
    body += [float(v).hex() for v in np.asarray(controller.last, dtype=np.float64).reshape(-1)]
    body += [float(controller.pitch_integral).hex(), float(controller.speed_integral).hex()]
    body += ['recovering=%d' % int(bool(controller.recovering)), 'mode=%s' % str(controller.mode)]
    return hashlib.sha256('\n'.join(body).encode('utf-8')).hexdigest()


def euler_rates_deg_s(obs):
    """Euler rates from body p,q,r (obs[9:12] rad/s); roll rate singular at cos(theta)=0."""
    phi, theta = math.radians(float(obs[3])), math.radians(float(obs[4]))
    p, q, r = float(obs[9]), float(obs[10]), float(obs[11])
    coupling = q * math.sin(phi) + r * math.cos(phi)
    singular = int(abs(math.cos(theta)) < SINGULAR_COS_THETA)
    if singular:
        raise Incomplete('numerical: Euler rates singular at cos(theta)=0')
    roll = math.degrees(p + math.tan(theta) * coupling)
    clipped = math.degrees(p + math.tan(float(np.clip(theta, -0.7, 0.7))) * coupling)
    return (roll, math.degrees(q * math.cos(phi) - r * math.sin(phi)),
            math.degrees(coupling / math.cos(theta)), clipped, singular)


def fd_rates_deg_s(pre, post, dt=DT):
    """Finite-difference roll/pitch/yaw deg/s over one 1/60 s tick; roll and yaw wrapped."""
    return ((float(post[3] - pre[3]) + 180.0) % 360.0 - 180.0) / dt, \
        float(post[4] - pre[4]) / dt, ((float(post[5] - pre[5]) + 180.0) % 360.0 - 180.0) / dt


def summarize(values):
    """Distribution of one measured channel; singular nan samples are dropped, never filled."""
    vals = list(values)
    a = np.asarray([float(v) for v in vals if math.isfinite(float(v))], dtype=np.float64)
    if a.size == 0:
        return {'n': 0, 'n_nonfinite_dropped': len(vals), 'finite_samples': False}
    q10, q50, q90 = (float(x) for x in np.percentile(a, [10, 50, 90]))
    return {'n': int(a.size), 'n_nonfinite_dropped': len(vals) - int(a.size), 'min': float(a.min()),
            'p10': q10, 'median': q50, 'p90': q90, 'max': float(a.max()), 'mean': float(a.mean())}


def publish(path, payload):
    """Bounded heartbeat/progress/result file: compact JSON, atomically replaced."""
    with open('%s.tmp' % path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, separators=(',', ':'), sort_keys=True,allow_nan=False)
    os.replace('%s.tmp' % path, path)


def tick_row(phase, tick, wall_s, pre, post, cmd, m):
    """One streamed CSV record: pre/post obs26, commands, targets, guard, mode, rates, loads."""
    er, ep, ey, ecl, sing = euler_rates_deg_s(pre)
    fr, fp, fy = fd_rates_deg_s(pre, post)
    cas, nz, alt = float(pre[12]) * FPS_TO_KTS, float(pre[14]), float(pre[2]) * FT_TO_M
    vals = [phase, int(tick), int(tick) * DT, round(float(wall_s), 6)]
    vals += [float(v) for v in pre] + [float(v) for v in post] + [float(v) for v in cmd]
    vals += [float(m['bank']), float(m['pitch']), float(m['speed']), int(bool(m['guard'])),
             m['mode_before'], m['mode_after'],m['effective_bank'],m['effective_pitch'],m['effective_speed'],
             float(m['pitch_integral']), float(m['speed_integral']),
             int(bool(m['recovering_before'])), int(bool(m['recovering_after'])),
             er, ep, ey, ecl, sing, fr, fp, fy, float(m['bank']) - float(pre[3]),
             float(m['pitch']) - float(pre[4]), float(m['speed']) - cas, nz, abs(nz),
             float(pre[18]), float(pre[19]), cas, float(pre[13]) * FPS_TO_KTS, alt,
             1.0 / max(math.cos(math.radians(min(abs(float(pre[3])),75.))), 0.25)]
    if len(vals) != len(CSV_COLS):
        raise Incomplete('numerical: csv column/value mismatch')
    return dict(zip(CSV_COLS, vals))


def run_case(adapter, controller, case_spec, output_dir, clock, should_stop):
    """ONE fresh worker, ONE case: 900 warmup + 1200 test ticks, 60 Hz command and logging.

    'complete' requires exactly 2100 executed ticks, no stop, no wall timeout,
    no numerical failure; anything else is 'incomplete' and never score eligible.
    """
    cid = str(case_spec['case_id'])
    if not cid or len(cid)>80 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in cid):
        raise ValueError('case_id must be a bounded basename')
    bank, spec = float(case_spec.get('bank_deg', 0.0)), str(case_spec.get('pitch_spec', 'path_alpha'))
    spd = float(case_spec.get('speed_kts', 320.0))
    if spec not in ('nose0', 'path_alpha'):
        raise ValueError('pitch_spec must be nose0 or path_alpha')
    os.makedirs(output_dir, exist_ok=True)
    csv_path, res_path, prog_path = [os.path.join(output_dir, cid + s)
                                     for s in ('.csv', '.result.json', '.progress.json')]
    t0, tick, fh, writer = float(clock()), 0, None, None
    status, reason = 'incomplete', ''
    counts = dict.fromkeys(('guard', 'recovering', 'cas_lt_180kts', 'abs_nz_gt_8p5', 'abs_nz_gt_9',
                            'euler_roll_singular', 'warmup_guard', 'warmup_recovering'), 0)
    warm, modes, series, boundary = {'min_cas_kts': None, 'max_abs_nz': 0.0}, {}, {}, {}
    res = {'case_id': cid, 'bank_deg': bank, 'pitch_spec': spec, 'speed_target_cas_kts': spd,
           'dt_s': DT, 'warmup_ticks': WARMUP_TICKS, 'test_ticks': TEST_TICKS,
           'expected_ticks': EXPECTED_TICKS, 'wall_budget_s': WALL_BUDGET_S,
           'controller_variant': 'unchanged_repair', 'official_validation': False,
           'combat_score_eligible': False, 'status': 'incomplete', 'complete': False, 'reason': '',
           'ticks_executed': 0, 'csv_path': csv_path, 'caveats': list(CAVEATS)}
    try:
        res['initial_state_sha'] = state_sha(obs_vector(adapter.read_obs()), controller, 0)
        fh = open(csv_path, 'w', newline='')
        writer = csv.DictWriter(fh, fieldnames=CSV_COLS)
        writer.writeheader(); fh.flush()
        controller.mode = 'track' # diagnostic path-hold warmup, set before the first command
        for phase, span in (('warmup', WARMUP_TICKS), ('test', TEST_TICKS)):
            for _ in range(span):
                if float(clock()) - t0 > STEP_DEADLINE_S:
                    raise Incomplete('wall: 150 s budget exceeded')
                if should_stop():
                    raise Incomplete('stop: should_stop requested')
                pre = obs_vector(adapter.read_obs())
                controller.mode = 'track' # same per-tick mode selection used by act()
                m = {'bank': 0.0 if phase == 'warmup' else bank,
                     'pitch': 0.0 if (phase == 'test' and spec == 'nose0') else float(pre[18]),
                     'speed': spd, 'mode_before': str(controller.mode),
                     'recovering_before': bool(controller.recovering)}
                cmd, guard = controller.command(pre, m['bank'], m['pitch'], m['speed'],
                                                rudder=0.0, safety=True)
                c, pin = np.asarray(cmd, dtype=np.float64), float(controller.pitch_integral)
                sint = float(controller.speed_integral)
                if (c.shape != (4,) or not bool(np.isfinite(c).all())
                        or (c < CMD_LO).any() or (c > CMD_HI).any()
                        or not math.isfinite(pin) or not math.isfinite(sint)):
                    raise Incomplete('numerical: command bounds/finiteness contract violated')
                m.update({'guard': guard, 'mode_after': str(controller.mode), 'pitch_integral': pin,
                          'speed_integral': sint, 'recovering_after': bool(controller.recovering),
                          'effective_bank':float(controller.bank_target),
                          'effective_pitch':float(controller.pitch_target),
                          'effective_speed':float(controller.speed_target)})
                adapter.advance(c)
                post = obs_vector(adapter.read_obs())
                tick += 1
                cas, absz = float(pre[12]) * FPS_TO_KTS, abs(float(pre[14]))
                row = tick_row(phase, tick, float(clock()) - t0, pre, post, c, m)
                writer.writerow(row)
                if phase == 'test':
                    for key in STAT_KEYS:
                        series.setdefault(key, []).append(float(row[key]))
                    counts['guard'] += int(bool(guard))
                    counts['recovering'] += int(bool(m['recovering_after']))
                    counts['cas_lt_180kts'] += int(cas < 180.0)
                    counts['abs_nz_gt_8p5'] += int(absz > 8.5)
                    counts['abs_nz_gt_9'] += int(absz > 9.0)
                    counts['euler_roll_singular'] += row['euler_roll_singular']
                    modes[m['mode_after']] = modes.get(m['mode_after'], 0) + 1
                else:
                    counts['warmup_guard'] += int(bool(guard))
                    counts['warmup_recovering'] += int(bool(m['recovering_before']))
                    warm['min_cas_kts'] = cas if warm['min_cas_kts'] is None else min(warm['min_cas_kts'], cas)
                    warm['max_abs_nz'] = max(warm['max_abs_nz'], absz)
                    if tick == WARMUP_TICKS:   # boundary hash; integrals/history are NOT reset here
                        res['warmup_boundary_sha'] = state_sha(post, controller, tick)
                        boundary = {'mode': m['mode_after'], 'recovering': m['recovering_after'],
                                    'pitch_integral': pin, 'speed_integral': sint}
                if tick % 60 == 0:
                    fh.flush()
                    publish(prog_path, {'case_id': cid, 'phase': phase, 'status': 'running',
                                        'tick': tick, 'expected_ticks': EXPECTED_TICKS,
                                        'wall_s': round(float(clock()) - t0, 3),
                                        'heartbeat_utc': time.time()})
        status = 'complete'
    except Exception as failure:      # stop, numerical failure or crash is never completion
        reason = '%s: %s' % (type(failure).__name__, failure)
    finally:
        for fn in (lambda: fh.flush(), lambda: fh.close(), lambda: adapter.close()):
            try:
                fn()
            except Exception:
                pass
        res['ticks_executed'], res['csv_rows'] = tick, tick
        res['wall_s'] = round(float(clock()) - t0, 3)
        res['complete'] = bool(status == 'complete' and tick == EXPECTED_TICKS and res['wall_s']<=150 and not should_stop())
        res['status'] = 'complete' if res['complete'] else 'incomplete'
        res['reason'] = '' if res['complete'] else (reason or 'tick_count_mismatch')
        res['warmup'] = {'status': 'completed' if tick >= WARMUP_TICKS else 'interrupted',
                         'ticks_executed': min(tick, WARMUP_TICKS),
                         'min_cas_kts': warm['min_cas_kts'],
                         'max_abs_pilot_load': warm['max_abs_nz'], 'boundary_state': boundary}
        res['warmup_stability_flags'] = [n for n, hit in (
            ('warmup_guard_ticks_present', counts['warmup_guard']),
            ('warmup_recovering_ticks_present', counts['warmup_recovering']),
            ('warmup_cas_below_180kts', warm['min_cas_kts'] is not None and warm['min_cas_kts'] < 180.0),
            ('warmup_abs_pilot_load_above_8p5', warm['max_abs_nz'] > 8.5)) if hit]
        res['tick_counts'], res['test_mode_ticks'] = counts, modes
        res['test_statistics'] = {k: summarize(v) for k, v in sorted(series.items())}
        res['official_validation'], res['combat_score_eligible'] = False, False
        publish(res_path, res)
        publish(prog_path, {'case_id': cid, 'status': res['status'], 'tick': tick,
                            'reason': res['reason'], 'wall_s': res['wall_s'],
                            'heartbeat_utc': time.time()})
    return res
