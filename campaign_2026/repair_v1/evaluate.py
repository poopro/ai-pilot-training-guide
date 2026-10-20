"""Fixed opponent/seed comparison with exact-tick attack stats and telemetry."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid
import csv
import shutil
import numpy as np
import torch
from env import RepairDuel, DEFAULT_BUNDLE, file_hash
from artifacts import load_policy

torch.set_num_threads(1)

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--controller',choices=['old','repair'],default='repair')
    parser.add_argument('--p2',choices=['rule','rl'],default='rule')
    parser.add_argument('--seed',type=int,default=20271000)
    parser.add_argument('--distance-ft',type=int,choices=[3000,6000,9000],default=3000)
    parser.add_argument('--angle',type=float,default=1.)
    parser.add_argument('--bundle',type=Path,help='Optional old/new blue actor')
    parser.add_argument('--steps',type=int,default=18000)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    folder=args.out or ROOT/'evaluations'/('eval_'+str(args.seed)+'_'+args.p2+'_'+args.controller+'_'+uuid.uuid4().hex[:4])
    folder.mkdir(parents=True,exist_ok=False)
    snapshot=folder/'source'; snapshot.mkdir()
    for name in ['controller.py','env.py','evaluate.py','artifacts.py']:
        shutil.copy2(ROOT/name,snapshot/name)
    policy=load_policy(args.bundle) if args.bundle else None
    repeat=getattr(policy,'combat_fix_manifest',{}).get('decision_repeat',1) if policy else 1
    enemy=load_policy(DEFAULT_BUNDLE) if args.p2=='rl' else None
    env=RepairDuel(p2=args.p2,policy=enemy,attack_angle=args.angle,max_steps=args.steps,distance_ft=args.distance_ft,controller=args.controller)
    obs,_=env.reset(seed=args.seed)
    total=0.; samples=[]; start=time.monotonic()
    acmi=folder/'duel.acmi'
    with acmi.open('w',encoding='utf-8') as stream:
        stream.write('FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime='+datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')+'\n')
        stream.write('1,Type=Air+FixedWing,Name=F16,CallSign=P1 '+args.controller+',Color=Blue\n2,Type=Air+FixedWing,Name=F16,CallSign=P2 '+args.p2+',Color=Red\n')
        env.write_frame(stream)
        a=np.zeros(4,dtype=np.float32)
        for step in range(args.steps):
            if step%repeat==0:
                a=policy.predict(obs,deterministic=True)[0] if policy else np.zeros(4,dtype=np.float32)
            obs,reward,term,trunc,info=env.step(a); total+=reward
            if (step+1)%6==0 or term or trunc:
                env.write_frame(stream)
                row={k:info.get(k) for k in ['distance','blue_angle_deg','red_angle_deg','altitude_m','speed_kts','load_factor','bank_deg','pitch_deg','alpha_deg','bank_target','pitch_target','pitch_rate_euler_deg_s','trim','closing_mps','controller_mode','guard_active','attack_seconds','enemy_attack_seconds']}
                row['t']=(step+1)/60; samples.append(row)
            if term or trunc: break
    with (folder/'telemetry.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(samples[0])); writer.writeheader(); writer.writerows(samples)
    report={'official_validation':False,'attack_angle':args.angle,'seed':args.seed,'p2':args.p2,'controller':args.controller,
            'blue_bundle':str(args.bundle) if args.bundle else None,'red_bundle':str(DEFAULT_BUNDLE) if enemy else None,
            'steps':step+1,'decision_repeat':repeat,'full_round_completed':bool(term or trunc and args.steps==18000),'final':info,'local_reward':total,
            'wall_seconds':time.monotonic()-start,'acmi':str(acmi),
            'sources':{name:file_hash(ROOT/name) for name in ['controller.py','env.py','evaluate.py']},
            'diagnostics':{'range_seconds_10hz':.1*sum(152.4<=r['distance']<=914.4 for r in samples),
                           'best_angle_in_range':min((r['blue_angle_deg'] for r in samples if 152.4<=r['distance']<=914.4),default=None),
                           'minimum_altitude':min(r['altitude_m'] for r in samples)}}
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    env.close()
    print(json.dumps({'report':str(folder/'report.json'),'steps':step+1,'final':{k:info[k] for k in ['outcome','attack_seconds','enemy_attack_seconds','survived','min_altitude_m','guard_fraction']},'diagnostics':report['diagnostics']},ensure_ascii=False),flush=True)


if __name__=='__main__': main()
