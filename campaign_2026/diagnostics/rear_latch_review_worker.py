"""Bounded saved-data review. No FDM or learned inference; fixed prior inputs."""
from pathlib import Path
import sys,json,csv,statistics,time,hashlib,os
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/rear_latch60_v2';RUN=SOURCE/'run_20261017_203915_d840e7'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha

def worker(out):
    spec=read(out/'CONTRACT.json')
    if os.getppid()!=spec['guardian']['pid'] or not b.live(spec['guardian']):raise RuntimeError('Review parent identity')
    if sha(Path(__file__))!=spec['review_worker_sha256']:raise RuntimeError('Review code changed')
    comparison_path=Path(read(RUN/'SAVED_DATA_AUDIT_LINK.json')['comparison'])
    comparison=read(comparison_path);assert comparison['verified_comparison'] and comparison['errors']==[]
    assert read(RUN/'PARENT_EXIT_OBSERVED.json')['actual_exit']==0
    assert read(RUN/'VERIFIER_EXIT.json')['actual_exit']==2
    assert read(RUN/'VERIFIER_WRAPPER_EXIT_OBSERVED.json')['actual_exit']==1
    assert sha(RUN/'COMPARISON.json')==spec['failed_comparison_sha256']
    b.source_gate(read(RUN/'CONTRACT.json'));summaries=[];heights={}
    for case in b.plan():
        folder=RUN/'cases'/case['id'];r=read(folder/'RESULT.json');assert all(sha(folder/n)==h for n,h in r['artifacts'].items())
        rows=list(csv.DictReader((folder/'telemetry.csv').open(encoding='utf8',newline='')))
        inband=[x for x in rows if 152.4<=float(x['distance_m'])<=914.4]
        fronts=[x for x in inband if float(x['blue_angle_deg'])<=90]
        triggers=[];releases=[];active=0;flips=[];prev=None;first_active=None;min_inband=min([float(x['blue_angle_deg']) for x in inband],default=None)
        with (folder/'telemetry.jsonl').open(encoding='utf8') as f:
            for line in f:
                row=json.loads(line);n=row['tick'];g=row['blue_guidance'];t=g['latch']
                if n%300==0 and (b.expired(spec) or b.stop(out)):raise RuntimeError('Review deadline/STOP')
                if t['triggered']:triggers.append(n)
                if t['released']:releases.append(n)
                active+=int(t['active'])
                if prev is not None and g['applied'][0]*prev<0:flips.append(n)
                prev=g['applied'][0]
        heights[case['id']]=[float(x['blue_agl_m']) for x in rows]
        s=dict(case=case,ticks=r['final']['ticks'],event=r['final']['event'],winner=r['final']['winner'],score=r['final']['total_score'],score_margin=r['final']['total_score'][0]-r['final']['total_score'][1],attack_ticks=r['final']['attack_ticks'],over9G_ticks=r['final']['over_g_ticks'],peak_abs_g=r['peak_abs_g'],minimum_agl_m=r['min_agl_m'],closest_distance_m=min(float(x['distance_m']) for x in rows),inband_ticks=len(inband),inband_forward_ticks=len(fronts),best_inband_nose_deg=min_inband,latch_trigger_ticks=triggers,latch_release_ticks=releases,latch_active_ticks=active,requested_turn_reversals=flips)
        summaries.append(s)
    pairs=[]
    for i in (0,1):
        base=next(x for x in summaries if x['case']['opening']==i and x['case']['actor']=='bank60');cand=next(x for x in summaries if x['case']['opening']==i and x['case']['actor']=='latch60')
        common=min(base['ticks'],cand['ticks']);bh=heights[base['case']['id']][:common];ch=heights[cand['case']['id']][:common]
        pairs.append(dict(opening=i,side=cand['case']['side'],baseline_winner=base['winner'],candidate_winner=cand['winner'],baseline_score_margin=base['score_margin'],candidate_score_margin=cand['score_margin'],score_margin_delta=cand['score_margin']-base['score_margin'],baseline_attack=base['attack_ticks'],candidate_attack=cand['attack_ticks'],baseline_inband_ticks=base['inband_ticks'],candidate_inband_ticks=cand['inband_ticks'],baseline_front_inband_ticks=base['inband_forward_ticks'],candidate_front_inband_ticks=cand['inband_forward_ticks'],common_ticks=common,common_minimum_agl_delta_m=min(ch)-min(bh),worst_simultaneous_agl_delta_m=min(c-b for c,b in zip(ch,bh)),actual_prefix=comparison['paired_tradeoffs'][i]['latch_prefix']))
    candidates=[x for x in summaries if x['case']['actor']=='latch60']
    unsafe=any(x['over9G_ticks'][0]>0 or x['event'] in ('blue_crash','mutual_crash','collision','red_kill') for x in candidates)
    if unsafe:gate='reject_candidate_safety_or_loss_event'
    elif all(p['score_margin_delta']>0 for p in pairs) and any(p['candidate_front_inband_ticks']>p['baseline_front_inband_ticks'] for p in pairs):gate='promising_mechanism_only_original72_reference_required'
    elif all(p['score_margin_delta']<=0 for p in pairs):gate='reject_latch_no_paired_score_improvement'
    else:gate='mixed_mechanism_signal_no_promotion'
    nextplan=dict(status='proposed_not_implemented',basis=str(RUN/'SAFETY_REVIEW.json'),gate=gate,priority='Use this saved telemetry and latch activation/prefix to choose one justified next step. No blind training or angle sweep.',if_promising='New matched-initial original72 reference vs latch60 in fresh development seeds before wider opponents; benefit versus weak rejected60 is insufficient.',if_mixed_or_rejected='Review earliest post-trigger geometry and actual bank/safety lag using existing packets; do not repeat completed games or tune multiple factors.',formal_deployment='repair_guide',deployment_allowed=False,training_started=False)
    review=dict(verified_comparison=True,comparison_path=str(comparison_path),comparison_sha256=sha(comparison_path),original_failed_verifier_exit=2,original_failed_verifier_preserved=True,gate=gate,results=summaries,paired_review=pairs,scope='Two new development openings, 4 complete games. Mechanism against already rejected bank60; not original72 or repair_guide superiority or unknown-team win rate.',hypothesis='Rear wrap turn-direction latch only; numerical magnitude and all other goals/safety unchanged',prior_pretrigger_replay='3590/3973 original inner-command frames exactly reproduced before saved wrap',failed_v1_preserved=str(ROOT/'experiments/opponent_pool/rear_latch60_v1/run_20261017_203724_6cbe6e/FAILURE_REVIEW.json'),source_manifest=str(RUN/'CONTRACT.json'),no_automatic_deployment=True,formal_deployment='repair_guide',training_started=False)
    b.source_gate(read(RUN/'CONTRACT.json'));write(RUN/'SAFETY_REVIEW.json',review);write(RUN/'NEXT_RESEARCH_PLAN.json',nextplan);write(out/'REVIEW_RESULT.json',review)
    print(json.dumps(dict(gate=gate,pairs=pairs,results=summaries)),flush=True);return 0

if __name__=='__main__':raise SystemExit(worker(Path(sys.argv[1])))
