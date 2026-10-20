"""Bounded first-difference search; not a second full precheck or FDM run.

Rebuild each controller's first300-frame history, then search only the next
3300 saved frames. Stop at first output difference. Never full72k/108k replay.
"""
from pathlib import Path
import importlib.util,sys,json,os,hashlib
import numpy as np
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/far_speed_v1';RUN=SOURCE/'run_20261018_033053_98bc0f'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
def worker(out):
    spec=read(out/'CONTRACT.json');assert os.getppid()==spec['guardian']['pid'] and b.live(spec['guardian'])
    for p,h in spec['new_sources'].items():assert sha(Path(p))==h
    prior=Path(spec['prior_precheck']);verified=read(prior/'VERIFICATION.json')
    assert verified['verified_rule_family_saved_packet_wiring'] and read(prior/'WORKER_EXIT.json')['actual_worker_exit']==read(prior/'PARENT_EXIT_OBSERVED.json')['actual_exit']==0
    assert sha(prior/'VERIFICATION.json')==spec['prior_precheck_verification_sha256']
    sys.path.insert(0,str(ROOT/'experiments/m4_tactical_v4'));import m4_tactical_rl as m
    import combat_v3.env as ce
    settings=read(Path(ce.__file__).parent/'config.json')
    path=ROOT/'experiments/opponent_pool/rule_family_v1/policy.py';s=importlib.util.spec_from_file_location('rule_family_activation_exact',path);f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
    results=[]
    for case in b.plan():
        if case['actor']!='station_zero':continue
        folder=RUN/'cases'/case['id'];r=read(folder/'RESULT.json');assert sha(folder/'telemetry.jsonl')==r['artifacts']['telemetry.jsonl']
        policies={family:f.RulePolicy(family,settings) for family in f.FAMILIES};hashes={family:hashlib.sha256() for family in f.FAMILIES}
        first=None;goal_difference=0;count=0;final_goals=None
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                row=json.loads(line);tick=int(row['tick'])
                if tick>spec['max_prefix_ticks']:break
                if b.expired(spec) or b.stop(out) or not b.live(spec['guardian']):raise RuntimeError('Original activation deadline/STOP/parent')
                values={family:policy.act(row['blue_packet_pre'],residual=None,started=True) for family,policy in policies.items()}
                np.testing.assert_array_equal(values['station_zero'][0],row['blue_command']);assert values['station_zero'][1]==row['blue_private_guard']
                assert all(policy.act_calls==policy.command_calls==tick for policy in policies.values())
                final_goals={family:policy.last['requested'] for family,policy in policies.items()}
                goal_difference+=int(final_goals['station_zero']!=final_goals['pure_guide'])
                for family in f.FAMILIES:hashes[family].update(json.dumps([values[family][0].tolist(),bool(values[family][1])],separators=(',',':'),allow_nan=False).encode())
                count=tick
                if not np.array_equal(values['station_zero'][0],values['pure_guide'][0]) or values['station_zero'][1]!=values['pure_guide'][1]:
                    first=dict(tick=tick,packet_sha256=b.digest(row['blue_packet_pre']),station_command=values['station_zero'][0].tolist(),pure_command=values['pure_guide'][0].tolist(),goals=final_goals,
                        scope='Actual controller outputs on saved common input; NOT sent in a new FDM run')
                    break
        assert count>=300
        results.append(dict(case=case['id'],history_reconstruction_ticks=min(300,count),new_suffix_ticks=max(0,count-300),tested_prefix_ticks=count,
            first_counterfactual_command_difference=first,goal_difference_ticks=goal_difference,last_requested_goals=final_goals,source_artifact_sha256=r['artifacts']['telemetry.jsonl'],
            prefix_output_sha256={family:h.hexdigest() for family,h in hashes.items()},runtime_receipts={family:policy.receipt for family,policy in policies.items()},baseline_saved_actual_commands_exact=True))
    for p,h in spec['new_sources'].items():assert sha(Path(p))==h
    b.source_gate(read(RUN/'CONTRACT.json'));assert not b.expired(spec) and not b.stop(out)
    seen=any(x['first_counterfactual_command_difference'] is not None for x in results)
    write(out/'VERIFICATION.json',dict(verified_bounded_prefix_activation_search=True,errors=[],results=results,max_ticks_per_prefix=spec['max_prefix_ticks'],
        total_tested_saved_frames=sum(x['tested_prefix_ticks'] for x in results),history_only_frames=sum(x['history_reconstruction_ticks'] for x in results),new_suffix_saved_frames=sum(x['new_suffix_ticks'] for x in results),
        command_difference_observed=seen,new_FDM_ticks=0,model_inference_calls=0,training_started=False,seed_claims=[],deployment_allowed=False,
        scope='History-only prefix300 needed to extend stateful comparison; no repeated combat/static/safety precheck, no controller traces beyond3600/case.',
        next_gate='Distinct output seen; still requires new runner/strict verifier/source contract before FDM' if seen else 'No controller-family effect through60s; do not launch duplicate four-game family comparison. Not proof of equality for all300s.'))
    print(json.dumps(dict(verified=True,command_difference_observed=seen,results=results),ensure_ascii=False),flush=True);return 0
if __name__=='__main__':raise SystemExit(worker(Path(sys.argv[1])))
