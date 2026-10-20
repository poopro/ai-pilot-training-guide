"""Finish this job from existing evidence; never trains or changes frozen runtime sources."""
import collections, math
from datetime import datetime
from common import *
from summarize import build

def finite(value):
    if isinstance(value,float):return math.isfinite(value)
    if isinstance(value,dict):return all(finite(v) for v in value.values())
    if isinstance(value,list):return all(finite(v) for v in value)
    return True

def finish():
    job=read(ROOT/'最新狀態.json');folder=experiment_dir(job)
    assert job['pipeline_finished'] and job['status']=='completed'
    assert not alive(job.get('supervisor')) and not alive(job.get('process'))
    count=sum(r.get('counted_steps',0) for r in job['results'] if r.get('training'))
    assert count==job['new_steps'] and count<=job['step_budget']
    manifest=valid_bundle(job['checkpoint'])
    frozen=read(folder/'frozen_source/hashes.json')
    assert frozen and all(digest(BASE/'combat_v3'/n)==v for n,v in frozen.items())
    assert all(frozen[n]==v for n,v in manifest['config']['source_sha256'].items())
    holdout=read(folder/'holdout/report.json');rows=holdout['episodes']
    expected={(p,o) for p in ('guide','policy') for o in ('easy','maneuver','duel')}
    grouped=collections.Counter((r['policy'],r['opponent']) for r in rows)
    assert set(grouped)==expected and all(n==20 for n in grouped.values()) and len(rows)==120
    assert len({(r['policy'],r['opponent'],r['seed']) for r in rows})==120
    development=read(folder/'dev_199000/report.json')
    assert set(holdout['seed_list']).isdisjoint(development['seed_list'])
    assert all(r['completed'] and 0<r['steps']<=18000 for r in rows)
    assert all(not r['is_kill'] or r['attack_seconds']>=3-1e-9 for r in rows)
    assert all(r['mean_residual']==0 for r in rows if r['policy']=='guide')
    assert finite(holdout) and all(holdout['source_sha256'][n]==v for n,v in frozen.items())
    selection=read(folder/'selection.json');assert selection['bundle']==holdout['bundle']==job['checkpoint']
    assert datetime.fromisoformat(selection['utc'])<datetime.fromisoformat(next(r['started_utc'] for r in job['results'] if r['name']=='c2_holdout'))
    udp={name:read(folder/name/'report.json') for name in ('deployment_udp_final','deployment_udp_guide')}
    assert all(r and r['passed'] for r in udp.values())
    modelcheck=read(folder/'deployment_latency/model_check.json')
    assert modelcheck['load_passed'] and modelcheck['timesteps']==manifest['timesteps']
    assert modelcheck['n_updates']==manifest['n_updates']>0
    assert read(Path(job['job_dir'])/'baseline_preservation_audit.json')['all_preserved']
    supervisor_log=(Path(job['job_dir'])/'supervisor_tests_latest.log').read_text(encoding='utf-8')
    assert 'Ran 9 tests' in supervisor_log and 'OK' in supervisor_log
    compliance_log=(folder/'compliance_tests/stderr.log').read_text(encoding='utf-8')
    assert 'Ran 8 tests' in compliance_log and 'OK' in compliance_log
    paired={o:{} for o in ('easy','maneuver','duel')}
    for o in paired:
        seeds=sorted({r['seed'] for r in rows if r['opponent']==o})
        improve=regress=equal=0
        for seed in seeds:
            g=next(r for r in rows if (r['policy'],r['opponent'],r['seed'])==('guide',o,seed))
            p=next(r for r in rows if (r['policy'],r['opponent'],r['seed'])==('policy',o,seed))
            delta=p['is_kill']-g['is_kill']
            improve+=delta>0;regress+=delta<0;equal+=delta==0
        paired[o]={'policy_only_kills':improve,'guide_only_kills':regress,'equal_kill_outcomes':equal}
    # Preserve the pre-holdout choice and all evaluation data. Release is a separate decision.
    deployment={'decision':'retain_guide','bundle':None,'evaluation_selection':selection,
        'reason':'保留測試擊殺與存活均未優於純引導器，未證明 SAC 可靠改善；依原任務發布門檻保留純引導器。',
        'holdout_not_reused_for_training':True,'utc':stamp()}
    atomic(folder/'deployment_selection.json',deployment)
    end=max(datetime.fromisoformat(r['finished_utc']).timestamp() for r in job['results'] if r.get('finished_utc'))
    job.update(pipeline_completed_epoch=end,learning='本輪未證明 SAC 可靠勝過引導器；預設保留純引導器，SAC 模型完整保留',
        deployment_selection=deployment,verification='監督程序 9 項、環境與規則 8 項、CUDA optimizer、完整模型／replay 校驗及載入、合作停止／續訓、最終 SAC 與引導器 UDP 測試均通過',
        tacview='pending_manual：使用者以 Esc 停止電腦操作，已產檔／格式檢查，未完成視覺確認',
        next_action='先看最新結果與回放；預設用純引導器進行官方 Host 人工驗證。本輪已收尾，不重開訓練。',
        finalized_utc=stamp())
    audit={'passed':True,'job_id':job['job_id'],'counted_steps':count,'budget':job['step_budget'],
        'pipeline_minutes':(end-job['first_started_epoch'])/60,'model_timesteps':manifest['timesteps'],
        'optimizer_updates':manifest['n_updates'],'model_and_replay_checksums':True,'source_frozen_matches':True,
        'holdout_episodes':len(rows),'holdout_not_in_development':True,'paired_kill_outcomes':paired,
        'pre_holdout_selection_preserved':selection,'released_selection':deployment,
        'no_owned_training_or_supervisor_running':True,'official_host':'pending_manual','tacview':'pending_manual',
        'udp_reports':{name:str(folder/name/'report.json') for name in udp},'utc':stamp()}
    atomic(folder/'final_audit.json',audit)
    job.setdefault('artifacts',{}).update(final_audit=str(folder/'final_audit.json'),deployment_selection=str(folder/'deployment_selection.json'))
    publish(job);result=build(job,require_finished=True)
    print(json.dumps({'audit':audit,'report':result},ensure_ascii=False,indent=2))

if __name__=='__main__':finish()
