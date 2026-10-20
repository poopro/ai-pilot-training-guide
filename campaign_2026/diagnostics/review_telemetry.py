"""Read-only sampling diagnostics. Exact attack/kill totals come from result.json."""
import argparse, csv, hashlib, json, math
from pathlib import Path

def percentile(values,q):
    if not values: return None
    ordered=sorted(values); pos=(len(ordered)-1)*q
    lo=int(pos); hi=min(lo+1,len(ordered)-1)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(pos-lo)

def review(folder):
    folder=Path(folder)
    report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
    output={'benchmark_complete':report.get('benchmark_complete',False),
        'report_status':report.get('status'),'official_validation':False,
        'sampling_note':'CSV samples are not physics-tick durations; angle funnel is diagnostic, not scoring. Close means <1100m, matching controller track mode.',
        'source_report_sha256':hashlib.sha256((folder/'report.json').read_bytes()).hexdigest(),
        'cases':[]}
    for case in report['cases']:
        if not case.get('score_eligible') or not case.get('full_round_completed'):
            continue
        path=folder/'cases'/case['case_id']/'telemetry.csv'
        with path.open(encoding='utf-8-sig',newline='') as stream: raw=list(csv.DictReader(stream))
        angles=[]; distances=[]
        for row in raw:
            d=float(row['distance_m']); a=float(row['blue_angle_deg_judge_only'])
            if not math.isfinite(d) or not math.isfinite(a): raise ValueError('Nonfinite telemetry')
            distances.append(d)
            if d<1100: angles.append(a)
        output['cases'].append({'case_id':case['case_id'],'case':case['case'],
            'exact_metrics':case['metrics'],'sample_count':len(raw),'close_sample_count':len(angles),
            'sampled_min_range_m':min(distances) if distances else None,
            'close_angle_min_deg':min(angles) if angles else None,
            'close_angle_p10_deg':percentile(angles,.1),'close_angle_p50_deg':percentile(angles,.5),
            'close_fractions_in_cones':{str(cone):sum(a<=cone for a in angles)/len(angles) if angles else None for cone in [45,10,3,1]}})
    for actor in ['guide','candidate']:
        for opponent in ['rule','rl']:
            rows=[r for r in output['cases'] if r['case']['actor']==actor and r['case']['opponent']==opponent]
            samples=sum(r['close_sample_count'] for r in rows)
            output[f'{actor}_{opponent}']={'completed_cases':len(rows),'kills':sum(r['exact_metrics']['kills'] for r in rows),
                'close_sample_count':samples,'near_cone_fractions':{str(c):sum((r['close_fractions_in_cones'][str(c)] or 0)*r['close_sample_count'] for r in rows)/samples if samples else None for c in [45,10,3,1]}}
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('folder'); p.add_argument('--out',required=True); a=p.parse_args()
    result=review(a.folder); Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['cases','sampling_note','source_report_sha256']},ensure_ascii=False))
