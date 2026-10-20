"""Verify completed matched cases before comparing guide, raw SAC and gated SAC."""
from pathlib import Path
import argparse, json, math

def compare(raw, gated):
    checks={}
    for key in ['seed','rounds','mirror','round_ticks','attack_angle_deg','physics_hz','requested_max_steps','candidate_bundle_sha256','red_bundle_sha256']:
        checks[key]=raw.get(key)==gated.get(key)
    original_sources=raw['source_sha256']
    checks['base_sources_identical']=all(gated['source_sha256'].get(k)==v for k,v in original_sources.items())
    checks['source_additions_only_ablation']=all(k in original_sources or k in {'ablation/gate.py','ablation/benchmark_gate.py'} for k in gated['source_sha256'])
    checks['both_complete']=raw.get('benchmark_complete') is True and gated.get('benchmark_complete') is True
    checks['full_24_cases']=all(r.get('planned_cases')==24 and len(r['cases'])==24 and all(c.get('status')=='completed' and c.get('score_eligible') is True and c.get('full_round_completed') is True for c in r['cases']) for r in [raw,gated])
    raw_cases={c['case_id']:c for c in raw['cases']}; gate_cases={c['case_id']:c for c in gated['cases']}
    checks['same_cases']=len(raw_cases)==24 and len(gate_cases)==24 and set(raw_cases)==set(gate_cases)
    paired_valid=True
    for report in [raw,gated]:
        pairs={}
        for case in report['cases']: pairs.setdefault(case['pair_key'],{})[case['case']['actor']]=case.get('initial_sha256')
        paired_valid=paired_valid and len(pairs)==12 and all(set(p)=={'guide','candidate'} and isinstance(p['guide'],str) and len(p['guide'])==64 and p['guide']==p['candidate'] for p in pairs.values())
    checks['within_pair_initials_identical']=paired_valid
    checks['same_initials']=checks['same_cases'] and all(raw_cases[k]['initial_sha256']==gate_cases[k]['initial_sha256'] for k in raw_cases)
    checks['guide_reproduced']=checks['same_cases'] and all(all(math.isclose(float(v),float(gate_cases[k]['metrics'][m]),rel_tol=0,abs_tol=1e-6) for m,v in c['metrics'].items()) for k,c in raw_cases.items() if c['case']['actor']=='guide')
    if not all(checks.values()):
        return {'verified_comparison':False,'checks':checks,'candidate_gate':'not_eligible','official_validation':False}
    groups={}
    for label,report,actor in [('guide',raw,'guide'),('raw',raw,'candidate'),('gated',gated,'candidate')]:
        rows=[c for c in report['cases'] if c['case']['actor']==actor]
        groups[label]={}
        for opponent in ['rule','rl','all']:
            selected=[c for c in rows if opponent=='all' or c['case']['opponent']==opponent]
            groups[label][opponent]={'cases':len(selected),**{key:sum(c['metrics'][key] for c in selected) for key in ['kills','deaths','own_crashes','attack_seconds','enemy_attack_seconds','over_9g_seconds']}}
    guide,candidate=groups['guide']['all'],groups['gated']['all']
    safety=all(candidate[k]<=guide[k] for k in ['deaths','own_crashes','enemy_attack_seconds','over_9g_seconds'])
    per_opponent=all(groups['gated'][o]['kills']>=groups['guide'][o]['kills'] and groups['gated'][o]['deaths']<=groups['guide'][o]['deaths'] and groups['gated'][o]['own_crashes']<=groups['guide'][o]['own_crashes'] for o in ['rule','rl'])
    attack_improved=candidate['attack_seconds']/12>=guide['attack_seconds']/12+.25 and candidate['attack_seconds']>=guide['attack_seconds']*1.2
    quality=candidate['kills']>guide['kills'] or candidate['kills']==guide['kills'] and attack_improved
    passed=safety and per_opponent and quality
    return {'verified_comparison':True,'checks':checks,'groups':groups,
        'candidate_gate':'eligible_for_fresh_holdout_not_deployment' if passed else 'reject_promotion',
        'quality_improved_vs_guide':quality,'safety_nonregression':safety,'opponent_nonregression':per_opponent,
        'official_validation':False,'interpretation':'Same actor/controller-range ablation on a previously observed development set. No tournament win probability.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--gated',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=compare(json.loads(a.raw.read_text(encoding='utf-8')),json.loads(a.gated.read_text(encoding='utf-8')))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
