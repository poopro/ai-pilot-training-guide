"""Independent bounded pilot bundle/record audit; no simulator advancement."""
from pathlib import Path
import csv,json,sys,math
import numpy as np
import common as c
from policy_features import observation
def run(out):
    spec=c.check(out,'VERIFIER');c.gate(spec);r=c.read(out/'RESULT.json');exit=c.read(out/'WORKER_EXIT.json')
    assert exit['actual_exit']==0 and exit['result_sha256']==c.sha(out/'RESULT.json')
    assert r['status']=='fresh_training_complete_pending_independent_verification'
    assert r['actual_decisions']==r['decisions']==r['replay_size']==3000 and r['gradient_updates']>0 and r['new_FDM_ticks']<=60000
    assert r['initial_actor_sha256']!=r['final_actor_sha256'] and r['blue_over9G']==0 and r['fresh_actor'] and r['fresh_critic_optimizer_replay'] and not r['actor_transfer'] and not r['exact_resume']
    assert all(c.sha(out/name)==h for name,h in r['artifact_sha256'].items())
    import torch;torch.set_num_threads(1)
    from stable_baselines3 import SAC
    model=SAC.load(out/'model.zip',device='cpu');model.load_replay_buffer(out/'replay.pkl')
    assert model.observation_space.shape==(17,) and model.action_space.shape==(1,) and model.gamma==.9995 and model.replay_buffer.size()==3000 and model.num_timesteps==3000
    assert c.actor_digest(model)==r['final_actor_sha256']
    np.testing.assert_array_equal(model.predict(np.asarray(r['probe_observations'],dtype=np.float32),deterministic=True)[0],r['probe_outputs'])
    sys.path.insert(0,str(c.ROOT/'experiments/rules_v20261014'));from judge import Judge,RuleProfile,Frame
    sys.path.insert(0,str(c.b.base.ADAPTER));from factory import build_frozen_opponent,source_gate
    from packet_features import tactical_obs,geometry_from_observation
    import environment as envmodule
    import combat_v3.interface as interface
    settings=c.read(Path(interface.__file__).parent/'config.json');source_gate()
    boundary={};ticks={};judges={};last={};total=0;peak=0.;minimum=float('inf');starts={}
    for start in r['episode_starts']:
        case=start['case'];ep=case['episode'];assert case==spec['episodes'][ep]
        assert start['initial_sha256']==c.digest(start['initial']) and start['opponent_fallback'] is False
        assert c.read(out/f'episode_{ep:03d}_start.json')==start
        starts[ep]=start
        j=Judge(RuleProfile('line_20261014_1deg','AGL','right_bin'));judges[ep]=j;ticks[ep]=0;boundary[(ep,0)]=j.snapshot()
    with (out/'physics.csv').open(encoding='utf8',newline='') as stream:
        for row in csv.DictReader(stream):
            total+=1;ep=int(row['episode']);tick=int(row['tick']);assert ep in starts and tick==ticks[ep]+1 and int(row['total_tick'])==total;ticks[ep]=tick
            assert all(int(row[key])==tick for key in ('act','command','blue_send','red_send','blue_physics','red_physics','judge'))
            nums={k:float(row[k]) for k in ('distance_m','blue_angle_deg','red_angle_deg','blue_G','red_G','blue_AGL_m','red_AGL_m','aileron','elevator','rudder','throttle','bank_action')};assert all(math.isfinite(v) for v in nums.values())
            assert all(-1<=nums[k]<=1 for k in ('aileron','elevator','rudder','bank_action')) and 0<=nums['throttle']<=1
            assert abs(nums['blue_G'])<=9
            snap=judges[ep].advance(Frame(nums['distance_m'],nums['blue_angle_deg'],nums['red_angle_deg'],nums['blue_G'],nums['red_G'],nums['blue_AGL_m'],nums['red_AGL_m']),started=True)
            for k,expected in (('blue_attack',snap['attack_ticks'][0]),('red_attack',snap['attack_ticks'][1]),('blue_overG',snap['over_g_ticks'][0]),('red_overG',snap['over_g_ticks'][1]),('blue_position',snap['position_sum'][0]),('red_position',snap['position_sum'][1]),('blue_advantage',snap['advantage'][0]),('red_advantage',snap['advantage'][1])):assert abs(float(row[k])-expected)<1e-8,(ep,tick,k)
            assert row['event']==snap['event'] and row['winner']==('' if snap['winner'] is None else snap['winner'])
            if tick%20==0 or snap['event']!='ongoing':boundary[(ep,tick)]=snap
            peak=max(peak,abs(nums['blue_G']));minimum=min(minimum,nums['blue_AGL_m']);last[ep]=row
            if total%10000==0:c.check(out,'VERIFIER')
    assert total==r['new_FDM_ticks'] and peak==r['peak_abs_blue_G'] and minimum==r['min_AGL_m']
    assert {str(k):v for k,v in ticks.items()}==r['episode_physics_ticks']
    for episode in r['completed_episodes']:assert episode['ticks']==ticks[episode['case']['episode']] and episode['final']==judges[episode['case']['episode']].snapshot()
    assert r['last_episode']['final']==judges[r['last_episode']['case']['episode']].snapshot()
    blue=c.bridge.controller(settings);zero=c.bridge.controller(settings);red=build_frozen_opponent('sac5000',settings)
    assert c.bridge.receipt(blue)==starts[0]['blue']
    decision_count=0;effect=0;red_predictions=0;max_feature=0.;episode_decisions={};action_stats={};lastdecision={}
    with (out/'decisions.jsonl').open(encoding='utf8') as stream:
        for line in stream:
            row=json.loads(line);decision_count+=1;ep=row['episode'];n=row['completed_tick'];n1=n+row['physical_ticks'];case=spec['episodes'][ep]
            assert row['decision']==decision_count and 0<row['physical_ticks']<=20 and n%20==0
            assert row['before']==boundary[(ep,n)] and row['after']==boundary[(ep,n1)]
            assert row['own_attack_pre']==row['before']['attack_ticks'][0] and row['own_attack_post']==row['after']['attack_ticks'][0]
            pre=observation(row['blue_pre'],row['own_attack_pre'],row['own_guard_pre'],n);post=observation(row['blue_post'],row['own_attack_post'],row['own_guard_post'],n1)
            np.testing.assert_array_equal(pre,row['features_pre']);np.testing.assert_array_equal(post,row['features_post']);max_feature=max(max_feature,float(np.max(np.abs(pre))))
            reward=((row['after']['advantage'][0]-row['after']['advantage'][1])-(row['before']['advantage'][0]-row['before']['advantage'][1]))/(10000/60)
            term=row['after']['event']!='ongoing'
            if term:reward+={'blue':180.,'red':-180.,'draw':0.}[row['after']['winner']]
            assert reward==row['reward'] and row['terminated']==term and row['truncated']==(not term and n1==18000)
            envmodule.restore(blue,row['blue_state']);value,guard=blue.act(row['blue_pre'],residual=c.bridge.residual(row['action']),started=True)
            np.testing.assert_array_equal(value,row['actual_blue_command'])
            envmodule.restore(zero,row['blue_state']);neutral,_=zero.act(row['blue_pre'],residual=None,started=True);effect+=int(not np.array_equal(value,neutral))
            if case['opponent']=='sac5000':
                obs13=tactical_obs(np.asarray(row['red_pre']),geometry_from_observation(row['red_pre']),int(row['before']['attack_ticks'][1]),bool(row['red_guard_pre']),elapsed_ticks=n)
                predicted=red.actor.predict(obs13,deterministic=True)[0]
                np.testing.assert_array_equal(predicted,row['red_tactical']);red_predictions+=1
            else:assert row['red_tactical'] is None
            episode_decisions[ep]=episode_decisions.get(ep,0)+1;action_stats.setdefault(case['opponent'],[]).append(float(row['action'][0]));lastdecision[ep]=n1
            if decision_count%100==0:c.check(out,'VERIFIER')
    assert decision_count==3000 and all(lastdecision.get(ep,0)==n for ep,n in ticks.items())
    reached=[s['case'] for ep,s in starts.items() if ticks[ep]>0];assert reached==r['actual_reached_cells']
    c.gate(spec);c.check(out,'VERIFIER')
    audit=dict(verified_fresh_bank_residual_pilot=True,errors=[],decisions=decision_count,new_FDM_ticks=total,updates=r['gradient_updates'],replay_size=3000,
        full_tick_count_and_judge_recompute=True,full_decision_feature_reward_recompute=True,sampled_first_tick_original_blue_act_command_replay=decision_count,sampled_nonzero_action_command_effect=effect,
        frozen_red_model_decision_replay=red_predictions,full_frame_packet_geometry_replay=False,full_frame_red_controller_replay=False,ACMI_recorded=False,
        actual_reached_cells=reached,completed_episodes=r['completed_episodes'],last_episode=r['last_episode'],zero_tick_auto_reset_starts=[s['case'] for ep,s in starts.items() if ticks[ep]==0],
        action_by_opponent={k:dict(count=len(v),mean=float(np.mean(v)),minimum=min(v),maximum=max(v)) for k,v in action_stats.items()},
        peak_abs_blue_G=peak,min_AGL_m=minimum,blue_over9G=0,model_sha256=c.sha(out/'model.zip'),actor_sha256=r['final_actor_sha256'],source_XML_red_model_fixed=True,bundle_reload_exact=True,
        strength_verified=False,fair_comparison=False,deployment_allowed=False,scope='Fresh bounded learning/interface/bundle evidence; not a full league, matched policy evaluation, or competition win rate')
    c.write(out/'VERIFICATION.json',audit)
    c.write(out/'BUNDLE_MANIFEST.json',dict(contract_sha256=c.sha(out/'CONTRACT.json'),result_sha256=c.sha(out/'RESULT.json'),verification_sha256=c.sha(out/'VERIFICATION.json'),sources=spec['sources'],artifacts=r['artifact_sha256'],fresh17x1=True,formal_deployment='repair_guide',deployment_allowed=False))
    print(json.dumps(dict(verified_pilot=True,decisions=decision_count,ticks=total,updates=r['gradient_updates'],sample_command_effect=effect,strength_verified=False)),flush=True);return 0
if __name__=='__main__':raise SystemExit(run(Path(sys.argv[1])))
