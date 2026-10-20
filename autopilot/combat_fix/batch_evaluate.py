"""Evaluate frozen repair guidance/model on complete, previously unused cases."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time
import csv
import numpy as np
import torch
from artifacts import ROOT,load_policy,atomic_json,contract_sources,snapshot_sources
from env import RepairDuel,DEFAULT_BUNDLE,simulator_observation

torch.set_num_threads(1)

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--bundle',type=Path);p.add_argument('--per-opponent',type=int,default=10)
    p.add_argument('--seed',type=int,default=20278000)
    a=p.parse_args()
    if not 1<=a.per_opponent<=100:p.error('per-opponent must be 1–100')
    a.out.mkdir(parents=True,exist_ok=False);snapshot_sources(a.out/'source')
    sources=contract_sources();model=load_policy(a.bundle) if a.bundle else None
    repeat=getattr(model,'combat_fix_manifest',{}).get('decision_repeat',1) if model else 1
    red=load_policy(DEFAULT_BUNDLE)
    report={'status':'running','official_validation':False,'controller':'repair','bundle':str(a.bundle) if a.bundle else None,
        'seed_role':'locked new test cases; no tuning after scoring','attack_angle_deg':1.,
        'scenario':'side separated opposite headings, 3000/6000/9000ft, 340CAS, shared 10000–20000ft altitude',
        'expected_cases':2*a.per_opponent,'source_sha256':sources,'cases':[]}
    path=a.out/'report.json';atomic_json(path,report)
    try:
        for p2 in ('rule','rl'):
            for i in range(a.per_opponent):
                seed=a.seed+i;distance=(3000,6000,9000)[i%3]
                env=RepairDuel(p2=p2,policy=red if p2=='rl' else None,controller='repair',distance_ft=distance,attack_angle=1.,max_steps=18000)
                obs,info=env.reset(seed=seed);initial=simulator_observation(env.fdm1,env.fdm2).tolist()
                folder=a.out/f'{p2}_{seed}';folder.mkdir();acmi=folder/'duel.acmi';total=0.;ticks=0;max_g=0.;modes={};rows=[];start=time.monotonic()
                try:
                    with acmi.open('w',encoding='utf-8') as stream:
                        stream.write('FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime='+datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')+'\n')
                        stream.write('1,Type=Air+FixedWing,Name=F16,CallSign=P1 Repair,Color=Blue\n2,Type=Air+FixedWing,Name=F16,CallSign=P2 '+p2+',Color=Red\n')
                        env.write_frame(stream);action=np.zeros(4,dtype=np.float32)
                        for step in range(18000):
                            if step%repeat==0 and model:action=model.predict(obs,deterministic=True)[0]
                            obs,reward,term,trunc,info=env.step(action);total+=reward;ticks+=1
                            max_g=max(max_g,info['load_factor']);modes[info['p2_mode']]=modes.get(info['p2_mode'],0)+1
                            if ticks%6==0 or term or trunc:
                                env.write_frame(stream)
                                rows.append({'t':ticks/60,**{k:info[k] for k in ('distance','blue_angle_deg','red_angle_deg','altitude_m','load_factor','attack_seconds','enemy_attack_seconds')}})
                            if term or trunc:break
                    with (folder/'telemetry.csv').open('w',encoding='utf-8',newline='') as stream:
                        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
                    item={'seed':seed,'p2':p2,'distance_ft':distance,'initial_obs26':initial,'steps':ticks,
                        'full_round_completed':bool(term or trunc and ticks==18000),'final':info,'max_g':max_g,'p2_mode_ticks':modes,
                        'local_reward':total,'wall_seconds':time.monotonic()-start,'acmi':str(acmi)}
                    if not item['full_round_completed']:raise RuntimeError('Incomplete case')
                    report['cases'].append(item);atomic_json(folder/'report.json',item);atomic_json(path,report)
                    print(f'{p2} {i+1}/{a.per_opponent}: {info["outcome"]}, attack={info["attack_seconds"]:.3f}s',flush=True)
                finally:env.close()
        report['summary']={}
        for p2 in ('rule','rl'):
            items=[x for x in report['cases'] if x['p2']==p2]
            report['summary'][p2]={'n':len(items),'kills':sum(x['final']['is_kill'] for x in items),
                'survived':sum(x['final']['survived'] for x in items),'crashes':sum(x['final']['own_crash'] for x in items),
                'mean_attack_seconds':sum(x['final']['attack_seconds'] for x in items)/len(items),
                'minimum_altitude_m':min(x['final']['min_altitude_m'] for x in items),'max_g':max(x['max_g'] for x in items)}
        if contract_sources()!=sources:raise RuntimeError('Source drift while evaluating')
        report['status']='completed';atomic_json(path,report);print(json.dumps(report['summary'],ensure_ascii=False),flush=True)
    except BaseException as error:
        report.update(status='failed',error=repr(error));atomic_json(path,report);raise

if __name__=='__main__':main()
