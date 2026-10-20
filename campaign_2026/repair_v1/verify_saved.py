"""Verify actual complete model/replay reload and finite policy actions."""
import argparse
import json
from pathlib import Path
import numpy as np
from artifacts import load_policy,read_manifest,atomic_json
from env import RepairDuel

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();m=read_manifest(args.bundle,verify_replay=True);model=load_policy(args.bundle)
    model.load_replay_buffer(str(args.bundle/'replay.pkl'))
    env=RepairDuel(p2='rule',controller='repair');obs,_=env.reset(seed=20299000)
    action=model.predict(obs,deterministic=True)[0];env.close()
    samples=model.replay_buffer.sample(min(128,model.replay_buffer.size()))
    finite=all(bool(t.isfinite().all()) for t in (samples.observations,samples.actions,samples.rewards,samples.next_observations))
    report={'passed':bool(np.isfinite(action).all() and action.shape==(4,) and np.max(abs(action))<=1 and finite),
        'bundle':str(args.bundle),'model_sha_verified':True,'replay_sha_verified':True,
        'actual_replay_size':model.replay_buffer.size(),'manifest_replay_size':m['replay_size'],
        'decision_steps':m['decision_steps'],'physics_ticks':m['physics_ticks'],'n_updates':m['n_updates'],
        'actor_updates':m['actor_updates'],'sampled_replay_finite':finite,'action':action.tolist(),
        'official_validation':False}
    report['passed']=report['passed'] and report['actual_replay_size']==report['manifest_replay_size']
    atomic_json(args.out,report);print(json.dumps(report,ensure_ascii=False))
    if not report['passed']:raise RuntimeError('Reload verification failed')
