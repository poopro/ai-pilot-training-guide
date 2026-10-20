"""Analyze existing 10 Hz ACMI without modifying models or running simulation."""
from pathlib import Path
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parent
EVAL = Path('E:/ai_pilot/autopilot/opponent_lab/evaluations/eval_20261006_044647_0d64')


def trajectory(path):
    rows = []
    current = {}
    timestamp = 0.
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.startswith('#'):
            timestamp = float(line[1:])
        elif line.startswith(('1,T=', '2,T=')):
            plane, pose = line.split(',T=', 1)
            current[int(plane)] = [float(v) for v in pose.split('|')]
            if plane == '2' and 1 in current:
                rows.append([timestamp, *current[1], *current[2]])
    data = np.asarray(rows)
    blue, red = data[:, 1:7], data[:, 7:13]
    latitude = np.radians((blue[:, 1] + red[:, 1]) / 2)
    rel = np.column_stack([np.radians(red[:, 1]-blue[:, 1])*6378137,
                           np.radians(red[:, 0]-blue[:, 0])*6378137*np.cos(latitude),
                           blue[:, 2]-red[:, 2]])
    distance = np.linalg.norm(rel, axis=1)
    pitch, heading = np.radians(blue[:, 4]), np.radians(blue[:, 5])
    nose = np.column_stack([np.cos(pitch)*np.cos(heading), np.cos(pitch)*np.sin(heading), -np.sin(pitch)])
    error = np.degrees(np.arccos(np.clip(np.sum(nose*rel, axis=1) / np.maximum(distance, 1e-9), -1, 1)))
    in_range = (distance >= 152.4) & (distance <= 914.4)
    return data[:, 0], distance, error, blue, red, in_range


def main():
    report = json.loads((EVAL/'report.json').read_text(encoding='utf-8'))
    cases = []
    for case in report['cases']:
        t, distance, error, blue, red, near = trajectory(case['acmi'])
        cases.append({'p2': case['p2'], 'blue': case['blue'], 'seed': case['seed'],
                      'min_distance_m': float(distance.min()),
                      'approx_range_seconds_10hz': float(near.sum()*.1),
                      'best_angle_in_range_deg': float(error[near].min()) if near.any() else None,
                      'median_angle_in_range_deg': float(np.median(error[near])) if near.any() else None,
                      'min_blue_altitude_m': float(blue[:,2].min()),
                      'time_below_1500m_fraction': float(np.mean(blue[:,2]<1500)),
                      'initial_blue_altitude_m': float(blue[0,2]),
                      'attack_seconds_60hz': case['final']['attack_seconds'],
                      'guard_fraction_60hz': case['final']['guard_fraction']})
    output={'source_report': str(EVAL/'report.json'), 'note': 'range/angle statistics sampled at 10 Hz; attack totals from true 60 Hz judge', 'cases':cases}
    (ROOT/'diagnostics').mkdir(exist_ok=True)
    (ROOT/'diagnostics/old_trajectory_metrics.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    for p2 in ['rule','rl']:
        for blue in ['guide','rl']:
            selected=[c for c in cases if c['p2']==p2 and c['blue']==blue]
            print(json.dumps({'p2':p2,'blue':blue,'range_seconds_mean':np.mean([c['approx_range_seconds_10hz'] for c in selected]),
                              'best_range_angles':[c['best_angle_in_range_deg'] for c in selected],
                              'min_altitudes':[round(c['min_blue_altitude_m']) for c in selected],
                              'below1500_fraction_mean':np.mean([c['time_below_1500m_fraction'] for c in selected])}))


if __name__=='__main__':
    main()
