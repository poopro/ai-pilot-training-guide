from pathlib import Path
import argparse,csv,hashlib,json,math,sys
from datetime import datetime,timezone
import psutil
root=Path(r'E:\ai_pilot\campaign_2026'); exp=root/'experiments'/'opponent_pool';sys.path.insert(0,str(exp))
import benchmark_pool as bench

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def totals(rows):
    return {k:sum(c['metrics'][k] for c in rows) for k in ['kills','deaths','own_crashes','survival','attack_seconds','enemy_attack_seconds','over_9g_seconds']}|{
        'cases':len(rows),'min_altitude_m':min(c['metrics']['min_altitude_m'] for c in rows)}

def assert_full_header(r,planned):
    assert r['format']=='campaign_expanded_bank80_pool_v1' and r['seed_role']=='expanded_development_not_holdout'
    assert r['status']=='completed' and r['benchmark_complete']
    assert r['planned_cases']==144 and len(r['cases'])==144 and r['summary']['paired_completed']==72
    assert [c['case_id'] for c in r['cases']]==[p.case_id for p in planned]
    from dataclasses import asdict
    groups={}
    for c,p in zip(r['cases'],planned):
        assert c['case']==asdict(p) and c['pair_key']==p.pair_key
        assert c['worker_exit_code']==0 and c['worker_wait_reason']=='exited'
        assert c['score_eligible'] and c['full_round_completed'] and c['initial_sha256']
        assert c['steps']==18000 or c['stop_reason']=='legal_termination'
        assert all(math.isfinite(float(v)) for v in c['metrics'].values())
        assert c['opponent_id']==p.opponent and c['opponent_initial_rng_sha256']
        groups.setdefault(c['pair_key'],[]).append((c['initial_sha256'],c['opponent_initial_rng_sha256']))
    assert len(groups)==72 and all(len(v)==2 and v[0]==v[1] for v in groups.values())

def main(args):
    pointer=read(root/'research_latest.json');ident=pointer['supervisor']
    assert pointer['experiment']=='opponent_pool' and pointer['benchmark_return_code']==0
    try:
        p=psutil.Process(ident['pid'])
        if p.is_running() and abs(p.create_time()-ident['creation_epoch'])<.01 and p.cmdline()==ident['cmdline']:
            raise RuntimeError('Supervisor still active; no terminal comparison')
    except psutil.NoSuchProcess:pass
    # AccessDenied deliberately propagates: an unreadable process is unknown.
    report_path=Path(pointer['report']);r=read(report_path)
    assert args.parent_exit_code==0 and r['status']=='completed' and r['benchmark_complete']
    planned=bench.plan_cases(3,r['seed'],'both',True)
    assert_full_header(r,planned)
    launch=read(report_path.parent/'launch.json')
    assert bench.file_hash(exp/'POOL_FREEZE.json')==launch['opponent_pool_manifest_sha256']
    assert launch['fresh_validation']['ready'] and launch['fresh_validation']['comparison_sha256']==bench.file_hash(launch['fresh_validation']['comparison'])
    assert launch['fresh_validation']['safety_decision_sha256']==bench.file_hash(launch['fresh_validation']['safety_decision'])
    assert launch['supervisor']==ident and launch['seed']==r['seed'] and launch['source_sha256']==r['source_sha256']
    registry=read(root/'seed_registry.json')
    trial=registry['trials'][pointer['reservation_id']]
    assert trial['status']=='completed' and trial['seed_role']=='development_from_reservation'
    assert trial['seeds']==sorted({c.seed for c in planned})
    ledger=read(root/'compute_budgets'/(pointer['compute_budget_date']+'.json'))
    assert any(x['id']==pointer['reservation_id'] and x['hours']==2. for x in ledger['items'])
    from budget import checked
    checked(ledger,pointer['compute_budget_date'])
    assert bench.summarize(r['cases'],planned,True)==r['summary']
    assert r['actor_policy_used'] is False and r['candidate_bundle'] is None
    assert bench.capture_sources(root/'repair_v1')==r['source_sha256'],'Frozen sources changed'
    assert bench.bundle_hashes(bench.DEFAULT_RED_BUNDLE)==r['red_bundle_sha256']
    old_path=root/'jobs'/'job_20261012_184123_68be'/'dev_01'/'report.json';old=read(old_path)
    assert all(r['source_sha256'][k]==v for k,v in old['source_sha256'].items())
    assert r['red_bundle_sha256']==old['red_bundle_sha256']
    groups={}; artifacts=[]
    for c in r['cases']:
        assert c['worker_exit_code']==0 and c['worker_wait_reason']=='exited' and c['score_eligible'] and c['full_round_completed']
        assert c['actor_policy_used'] is False
        assert c['steps']==18000 or c['stop_reason']=='legal_termination'
        folder=report_path.parent/'cases'/c['case_id'];raw=read(folder/'result.json');spec=read(folder/'input.json')
        assert raw['status']=='completed' and raw['score_eligible'] and raw['metrics']==c['metrics']
        assert raw['opponent_id']==c['opponent_id'] and raw['opponent_initial_rng_sha256']==c['opponent_initial_rng_sha256']
        assert raw['initial_sha256']==c['initial_sha256'] and raw['steps']==c['steps']
        assert bench.json_hash(raw['initial'])==c['initial_sha256']
        assert spec['case']==c['case']
        assert spec['source_sha256']==r['source_sha256'] and spec['red_bundle_sha256']==r['red_bundle_sha256']
        assert spec['bundle'] is None and spec['max_steps']==18000
        with (folder/'telemetry.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
        assert len(rows)==c['steps']//60+int(c['steps']%60!=0) and int(rows[-1]['tick'])==c['steps']
        for row in rows:
            assert all(math.isfinite(float(v)) for k,v in row.items() if k!='controller_mode')
        assert (folder/'duel.acmi').stat().st_size>100
        artifacts.append({'case_id':c['case_id'],'telemetry_sha256':bench.file_hash(folder/'telemetry.csv'),
                          'acmi_sha256':bench.file_hash(folder/'duel.acmi'),'csv_rows':len(rows)})
        groups.setdefault(c['pair_key'],{})[c['case']['actor']]=c
    deltas=[]
    for key,pair in groups.items():
        assert set(pair)=={'guide','candidate'} and pair['guide']['initial_sha256']==pair['candidate']['initial_sha256']
        g,c=pair['guide'],pair['candidate']
        deltas.append({'pair_key':key,'opponent':g['case']['opponent'],
                       'delta':{k:c['metrics'][k]-g['metrics'][k] for k in bench.METRIC_DIRECTIONS}})
    by_opponent={}
    for opp in ['rule','rl','repair_guide','rule_bank60']:
        by_opponent[opp]={arm:totals([c for c in r['cases'] if c['case']['actor']==arm and c['case']['opponent']==opp]) for arm in ['guide','candidate']}
    g,c=r['summary']['totals']['guide'],r['summary']['totals']['candidate']
    enough_attack=c['mean_attack_seconds']>=g['mean_attack_seconds']*1.2 and c['mean_attack_seconds']-g['mean_attack_seconds']>=.25
    metric_gate=c['kills']>g['kills'] or (c['kills']==g['kills'] and enough_attack)
    outcome_safe=all(c[k]<=g[k] for k in ['deaths','own_crashes','over_9g_seconds'])
    opponent_safe=all(v['candidate']['kills']>=v['guide']['kills'] and
                      all(v['candidate'][k]<=v['guide'][k] for k in ['deaths','own_crashes','over_9g_seconds']) for v in by_opponent.values())
    altitude_regressions=[d for d in deltas if d['delta']['min_altitude_m']<-.000001]
    passing=metric_gate and outcome_safe and opponent_safe
    gate='development_pass_safety_review_pending' if passing and altitude_regressions else ('development_pass' if passing else 'reject_promotion')
    out={'updated_utc':datetime.now(timezone.utc).isoformat(),'report':str(report_path),
         'report_sha256':bench.file_hash(report_path),'actual_parent_exit_code':args.parent_exit_code,
         'verified_comparison':True,'guide_reproduces_original_development':False,'guide_note':'New paired guide cases; source/reference unchanged, starts intentionally different','matched_pairs':72,'eligible_cases':144,
         'actor_policy_used':False,'candidate_factor':r['candidate_factor'],'source_sha256':r['source_sha256'],
         'source_reference_report':str(old_path),'source_reference_report_sha256':bench.file_hash(old_path),'seed_role':'expanded_development_not_holdout',
         'by_opponent':by_opponent,'totals':r['summary']['totals'],'paired_deltas':deltas,
         'artifact_hashes':artifacts,'altitude_regressions_requiring_review':altitude_regressions,
         'gate':gate,'gates':{'metric':metric_gate,'outcome_safety':outcome_safe,'per_opponent':opponent_safe},
         'deployment_allowed':False,'official_validation':False,'daily_compute_reserved_hours':r['daily_compute_reserved_hours'],'compute_budget_date':r['compute_budget_date'],
         'next_action':'Analyze the largest regressions with saved legal telemetry; no further research compute today.' if not passing else
                       'Review expanded per-opponent and altitude/recovery results; only then freeze a candidate for untouched holdout and >=6 official Host rounds; no deployment yet.'}
    bench.atomic_json(report_path.parent/'COMPARISON.json',out)
    pointer.update(status='completed',actual_parent_exit_code=args.parent_exit_code,comparison=str(report_path.parent/'COMPARISON.json'),
                   verified_comparison=True,gate=gate,next_action=out['next_action'])
    bench.atomic_json(root/'research_latest.json',pointer)
    bench.atomic_json(exp/'latest.json',pointer)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(18,5),layout='constrained');x=list(range(72))
    ax.bar([i-.18 for i in x],[p['guide']['metrics']['attack_seconds'] for p in groups.values()],width=.36,label='Original guide')
    ax.bar([i+.18 for i in x],[p['candidate']['metrics']['attack_seconds'] for p in groups.values()],width=.36,label='Near bank80')
    labels=[k.removeprefix('r000_').rsplit('_',1)[0] for k in groups]
    ax.set_xticks(x,labels,rotation=50,ha='right',fontsize=5);ax.set_ylabel('Attack seconds');ax.legend()
    ax.set_title('72 matched expanded development starts; local simulation, not official win probability')
    fig.savefig(report_path.parent/'paired_attack.png',dpi=150);plt.close(fig)
    print(json.dumps({'gate':gate,'totals':out['totals'],'by_opponent':by_opponent,'comparison':str(report_path.parent/'COMPARISON.json')},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--parent-exit-code',type=int,required=True)
    main(p.parse_args())
