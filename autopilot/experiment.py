"""Headless fixed evaluation and load/deployment checks; torch only for a policy."""
import argparse,csv,collections,json,sys,time
from pathlib import Path
import numpy as np
from common import *
sys.path.insert(0,str(BASE))

def evaluate(out,episodes=5,seed=20261200,bundle=None,paired=False,max_steps=18000):
    from combat_v3.env import CombatEnvV3,INFO_KEYS
    from combat_v3.interface import simulator_observation
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    sources={p.name:digest(p) for p in list((BASE/'combat_v3').glob('*.py'))+list((BASE/'combat_v3').glob('*.json'))}
    atomic(out/'source_hashes.json',sources)
    model=None
    if bundle:
        m=valid_bundle(bundle,False)
        for name,expected in m['config']['source_sha256'].items():
            if digest(BASE/'combat_v3'/name)!=expected:raise ValueError('Source changed: '+name)
        for name,expected in m['config']['dependency_sha256'].items():
            if digest(BASE/name)!=expected:raise ValueError('Dependency changed: '+name)
        import torch;torch.set_num_threads(1)
        from stable_baselines3 import SAC
        model=SAC.load(str(Path(bundle)/'model.zip'),device='cpu')
        if not all(torch.isfinite(p).all() for p in model.policy.parameters()):raise ValueError('NaN model')
    rows=[];labels=['guide','policy'] if paired and model else (['policy'] if model else ['guide'])
    for opponent in ('easy','maneuver','duel'):
        for ep in range(episodes):
            for label in labels:
                distance=(3000,6000,9000)[ep%3];s=seed+ep
                env=CombatEnvV3(opponent=opponent,scenario='official',max_steps=max_steps,render_modes='txt')
                tag=f'{opponent}_{s}_{label}';env.record_file=str(out/(tag+'.acmi'))
                total=0.;min_angle=180.;nearest=1e20;latencies=[];began=time.monotonic()
                try:
                    obs,info=env.reset(seed=s,options={'distance_ft':distance});env.render()
                    with (out/(tag+'.csv')).open('w',newline='',encoding='utf-8') as stream:
                        fields=['time','distance','nose_angle','enemy_nose_angle','altitude_m','speed_kts','attack_seconds','enemy_attack_seconds','guard','closing_mps','roll_deg','pitch_deg','alpha_deg','bank_cmd','pitch_cmd']
                        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
                        for step in range(1,max_steps+1):
                            start=time.perf_counter()
                            a=np.zeros(4,dtype=np.float32) if label=='guide' else model.predict(obs,deterministic=True)[0]
                            obs,r,done,truncated,info=env.step(a);total+=r
                            latencies.append((time.perf_counter()-start)*1000)
                            min_angle=min(min_angle,info['blue_angle_deg']);nearest=min(nearest,info['distance'])
                            if step%6==0 or done or truncated:
                                from combat_v3.interface import geometry_from_observation
                                packet=simulator_observation(env.fdm1,env.fdm2);geo=geometry_from_observation(packet)
                                control=env.packet_controller.control
                                writer.writerow({'time':step/60,'distance':info['distance'],'nose_angle':info['blue_angle_deg'],
                                  'enemy_nose_angle':info['red_angle_deg'],'altitude_m':info['altitude_m'],
                                  'speed_kts':info['speed_kts'],'attack_seconds':info['attack_seconds'],
                                  'enemy_attack_seconds':info['enemy_attack_seconds'],'guard':info['guard_active'],
                                  'closing_mps':geo['closing_mps'],'roll_deg':packet[3],'pitch_deg':packet[4],
                                  'alpha_deg':packet[18],'bank_cmd':getattr(control,'bank_target',0),
                                  'pitch_cmd':getattr(control,'pitch_target',0)})
                            if step%3==0 or done or truncated:env.render()
                            if step%600==0:
                                atomic(out/'progress.json',{'work_tick':step,'phase':tag,'episodes_done':len(rows)})
                                if (out/'STOP').exists():raise InterruptedError('Evaluation stopped')
                            if done or truncated:break
                    row={'policy':label,'opponent':opponent,'seed':s,'steps':step,'completed':bool(done or truncated),
                      'reward':total,'min_nose_angle':min_angle,'nearest_distance_m':nearest,
                      'wall_seconds':time.monotonic()-began,'acmi':str(out/(tag+'.acmi')),
                      'timing_includes_simulation':True,'step_p95_ms':float(np.percentile(latencies,95)),
                      **{k:info[k] for k in INFO_KEYS}}
                    rows.append(row);atomic(out/'episodes.json',rows)
                    atomic(out/'progress.json',{'work_tick':step,'phase':tag,'episodes_done':len(rows)})
                    print(json.dumps(row,ensure_ascii=False),flush=True)
                    np.save(out/'last_observation.npy',simulator_observation(env.fdm1,env.fdm2))
                finally:env.close()
    groups=[]
    for label in labels:
        for opponent in ('easy','maneuver','duel'):
            g=[r for r in rows if r['policy']==label and r['opponent']==opponent]
            groups.append({'policy':label,'opponent':opponent,'episodes':len(g),
              'kills':sum(r['is_kill'] for r in g),'survivals':sum(r['survived'] for r in g),
              'crashes':sum(r['own_crash'] for r in g),'hits':sum(r['was_hit'] for r in g),
              'wins':sum(r['local_win'] for r in g),'attack_seconds':float(np.mean([r['attack_seconds'] for r in g])),
              'mean_reward':float(np.mean([r['reward'] for r in g]))})
    passed=any(r['attack_seconds']>0 for r in rows) and any(r['is_kill'] for r in rows if r['opponent']!='easy')
    decision='retain_guide'
    if model and paired:
        guide=[g for g in groups if g['policy']=='guide'];pol=[g for g in groups if g['policy']=='policy']
        safer=all(p['crashes']<=g['crashes'] and p['hits']<=g['hits'] for p,g in zip(pol,guide))
        improved=sum(p['kills'] for p in pol)>sum(g['kills'] for g in guide) or (
          sum(p['kills'] for p in pol)==sum(g['kills'] for g in guide) and
          sum(p['wins'] for p in pol)>sum(g['wins'] for g in guide))
        if safer and improved:decision='policy_candidate'
    result={'groups':groups,'episodes':rows,'end_reasons':dict(collections.Counter(r['outcome'] for r in rows)),
            'guide_gate_passed':passed,'decision':decision,'seed_role':'development' if seed<20262000 else 'holdout',
            'official_host':'not_tested','collision_model':'not_modeled','bundle':str(bundle) if bundle else None,
            'source_sha256':sources,'seed_list':[seed+i for i in range(episodes)],
            'initial_distance_schedule_ft':[3000,6000,9000]}
    atomic(out/'report.json',result);return result

def check_model(out,bundle):
    m=valid_bundle(bundle)
    import torch;torch.set_num_threads(1)
    from stable_baselines3 import SAC
    from combat_v3.interface import policy_state,PacketController
    model=SAC.load(str(Path(bundle)/'model.zip'),device='cpu')
    if model._n_updates<=0:raise ValueError('No optimizer updates')
    if not all(torch.isfinite(p).all() for p in model.policy.parameters()):raise ValueError('Nonfinite parameters')
    cfg=read(BASE/'combat_v3/config.json');o=np.zeros(26)
    o[[0,20]]=23;o[[1,21]]=121;o[[2,22]]=12000;o[12]=340*1.68781;o[13]=o[12]
    o[20]+=.005;o[15]=o[12];o[[6,23]]=o[12]
    pc=PacketController(cfg);times=[]
    for n in range(400):
        t=time.perf_counter();a=model.predict(policy_state(o),deterministic=True)[0];cmd,_=pc.act(o,a)
        times.append((time.perf_counter()-t)*1000)
        if not np.isfinite(cmd).all() or np.any(cmd<[-1,-1,-1,0]) or np.any(cmd>1):raise ValueError('Invalid controls')
    result={'load_passed':True,'n_updates':model._n_updates,'timesteps':model.num_timesteps,
      'control_p50_ms':float(np.percentile(times[10:],50)),'control_p95_ms':float(np.percentile(times[10:],95)),
      'control_p99_ms':float(np.percentile(times[10:],99)),'control_max_ms':float(max(times)),
      'scope':'local policy+feature+controller only; NOT actual Host or network'}
    atomic(Path(out)/'model_check.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['eval','modelcheck']);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--bundle',type=Path);p.add_argument('--episodes',type=int,default=5);p.add_argument('--seed',type=int,default=20261200)
    p.add_argument('--paired',action='store_true');p.add_argument('--max-steps',type=int,default=18000)
    a=p.parse_args()
    if a.mode=='eval':evaluate(a.out,a.episodes,a.seed,a.bundle,a.paired,a.max_steps)
    else:check_model(a.out,a.bundle)
