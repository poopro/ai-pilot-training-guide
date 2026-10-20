from pathlib import Path
import argparse,csv,hashlib,json,math,sys
from datetime import datetime,timezone
import psutil
root=Path(r'E:\ai_pilot\campaign_2026'); exp=root/'experiments'/'near_bank80';sys.path.insert(0,str(exp))
import benchmark_bank80 as bench

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def totals(rows):
    return {k:sum(c['metrics'][k] for c in rows) for k in ['kills','deaths','own_crashes','survival','attack_seconds','enemy_attack_seconds','over_9g_seconds']}|{
        'cases':len(rows),'min_altitude_m':min(c['metrics']['min_altitude_m'] for c in rows)}

def main(args):
    pointer=read(root/'research_latest.json');ident=pointer['supervisor']
    try:
        p=psutil.Process(ident['pid'])
        if p.is_running() and abs(p.create_time()-ident['creation_epoch'])<.01 and p.cmdline()==ident['cmdline']:
            raise RuntimeError('Supervisor still active; no terminal comparison')
    except psutil.NoSuchProcess:pass
    # AccessDenied deliberately propagates: an unreadable process is unknown.
    report_path=Path(pointer['report']);r=read(report_path)
    assert args.parent_exit_code==0 and r['status']=='completed' and r['benchmark_complete']
    assert r['planned_cases']==24 and len(r['cases'])==24 and r['summary']['paired_completed']==12
    assert r['actor_policy_used'] is False and r['candidate_bundle'] is None
    assert bench.capture_sources(root/'repair_v1')==r['source_sha256'],'Frozen sources changed'
    assert bench.bundle_hashes(bench.DEFAULT_RED_BUNDLE)==r['red_bundle_sha256']
    old_path=root/'jobs'/'job_20261012_184123_68be'/'dev_01'/'report.json';old=read(old_path)
    assert all(r['source_sha256'][k]==v for k,v in old['source_sha256'].items())
    assert r['red_bundle_sha256']==old['red_bundle_sha256']
    originals={c['case_id']:c for c in old['cases'] if c['case']['actor']=='guide'}
    groups={}; artifacts=[]
    for c in r['cases']:
        assert c['worker_exit_code']==0 and c['worker_wait_reason']=='exited' and c['score_eligible'] and c['full_round_completed']
        assert c['actor_policy_used'] is False
        assert c['steps']==18000 or c['stop_reason']=='legal_termination'
        folder=report_path.parent/'cases'/c['case_id'];raw=read(folder/'result.json');spec=read(folder/'input.json')
        assert raw['status']=='completed' and raw['score_eligible'] and raw['metrics']==c['metrics']
        assert raw['initial_sha256']==c['initial_sha256'] and raw['steps']==c['steps']
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
        if c['case']['actor']=='guide':
            prev=originals[c['case_id']]
            assert prev['initial_sha256']==c['initial_sha256'] and prev['metrics']==c['metrics'] and prev['steps']==c['steps'],'Guide did not reproduce'
    deltas=[]
    for key,pair in groups.items():
        assert set(pair)=={'guide','candidate'} and pair['guide']['initial_sha256']==pair['candidate']['initial_sha256']
        g,c=pair['guide'],pair['candidate']
        deltas.append({'pair_key':key,'opponent':g['case']['opponent'],
                       'delta':{k:c['metrics'][k]-g['metrics'][k] for k in bench.METRIC_DIRECTIONS}})
    by_opponent={}
    for opp in ['rule','rl']:
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
         'verified_comparison':True,'guide_reproduces_original_development':True,'matched_pairs':12,'eligible_cases':24,
         'actor_policy_used':False,'candidate_factor':r['candidate_factor'],'source_sha256':r['source_sha256'],
         'original_guide_report':str(old_path),'original_guide_report_sha256':bench.file_hash(old_path),
         'by_opponent':by_opponent,'totals':r['summary']['totals'],'paired_deltas':deltas,
         'artifact_hashes':artifacts,'altitude_regressions_requiring_review':altitude_regressions,
         'gate':gate,'gates':{'metric':metric_gate,'outcome_safety':outcome_safe,'per_opponent':opponent_safe},
         'deployment_allowed':False,'official_validation':False,'daily_compute_reserved_hours':5.75,
         'next_action':'Analyze the largest regressions with saved legal telemetry; no further research compute today.' if not passing else
                       'Review altitude regressions, then freeze candidate and design unseen-seed/opponent validation on a new daily budget; no deployment yet.'}
    bench.atomic_json(report_path.parent/'COMPARISON.json',out)
    pointer.update(status='completed',actual_parent_exit_code=args.parent_exit_code,comparison=str(report_path.parent/'COMPARISON.json'),
                   verified_comparison=True,gate=gate,next_action=out['next_action'])
    bench.atomic_json(root/'research_latest.json',pointer)
    bench.atomic_json(exp/'latest.json',pointer)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,4),layout='constrained');x=list(range(12))
    ax.bar([i-.18 for i in x],[p['guide']['metrics']['attack_seconds'] for p in groups.values()],width=.36,label='Original guide')
    ax.bar([i+.18 for i in x],[p['candidate']['metrics']['attack_seconds'] for p in groups.values()],width=.36,label='Near bank80')
    labels=[k.replace('r000_','').replace('_202610110','_s').replace('_202610111','_s') for k in groups]
    ax.set_xticks(x,labels,rotation=50,ha='right',fontsize=8);ax.set_ylabel('Attack seconds');ax.legend()
    ax.set_title('12 matched development starts; local simulation, not official win probability')
    fig.savefig(report_path.parent/'paired_attack.png',dpi=150);plt.close(fig)
    print(json.dumps({'gate':gate,'totals':out['totals'],'by_opponent':by_opponent,'comparison':str(report_path.parent/'COMPARISON.json')},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--parent-exit-code',type=int,required=True)
    main(p.parse_args())
