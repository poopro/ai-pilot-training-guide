"""Read-only terminal audit. Learner updates are never a combat success gate."""
import argparse,csv
from common import *

def verify(out):
    out=Path(out);launch=read(out/'launch.json');execution_mode_gate(launch);source_gate(launch['source_freeze'])
    receipt=read(out/'launcher_receipt.json');guard=read(out/'guard.json');report=read(out/'report.json')
    errors=[]
    if receipt['actual_parent_exit_code']!=0 or receipt['actual_guard_exit_code']!=0:errors.append('parent/guard nonzero or unknown')
    if guard['unknown'] or guard['stopped']:errors.append('guard unknown or intervention')
    if report['status']!='completed' or len(report['cases'])!=1:errors.append('incomplete single learner report')
    folder=out/'cases/actor_transfer_10000';result=read(folder/'result.json');worker_exit=read(folder/'worker_exit.json')
    if worker_exit['actual_worker_exit_code']!=0:errors.append('worker nonzero')
    if worker_exit['result_sha256']!=sha(folder/'result.json'):errors.append('result receipt hash')
    if result['status']!='completed_actor_transfer_training' or result['decisions']!=10000 or result['gradient_updates']<=0 or result['replay_size']!=10000:errors.append('training completion criteria')
    if not result.get('bundle_reload_verified') or result['initial_actor_sha256']==result['final_actor_sha256']:errors.append('bundle/actor update')
    transfer=result.get('actor_transfer_audit',{})
    if not transfer.get('verified_actor_only_transfer') or not transfer.get('fresh_critic_unchanged') or transfer.get('replay_size')!=0 or transfer.get('gradient_updates')!=0:errors.append('actor transfer provenance')
    for name,digest in result['artifact_sha256'].items():
        if sha(folder/name)!=digest:errors.append('bundle hash '+name)
    ticks=0;over=0;peak=0.;lowest=math.inf;last={}
    with (folder/'physics.csv').open(encoding='utf8',newline='') as stream:
        for row in csv.DictReader(stream):
            ticks+=1;episode=int(row['episode']);tick=int(row['tick'])
            if int(row['total_tick'])!=ticks or tick!=last.get(episode,0)+1:errors.append('physics discontinuity');break
            last[episode]=tick
            if any(int(row[k])!=tick for k in ('act_calls','blue_sends','red_sends')):errors.append('not single act/send');break
            legal_command(json.loads(row['actual_command']))
            g=abs(float(row['blue_G']));peak=max(peak,g);over+=g>9.;lowest=min(lowest,float(row['AGL_m']))
    if ticks!=result['new_fdm_ticks'] or ticks>200000 or over!=0 or result['over9G_ticks']!=0:errors.append('physics/G gate')
    if abs(peak-result['max_abs_G'])>1e-9 or abs(lowest-result['min_AGL_m'])>1e-7:errors.append('extrema replay')
    if sha(folder/'physics.csv')!=result['physics_csv_sha256']:errors.append('physics hash')
    schedule=launch['cases'][0]['episodes']
    for index,start in enumerate(result['episode_starts']):
        if any(start[k]!=schedule[index][k] for k in schedule[index]):errors.append('episode schedule mismatch')
        if jsha(start['initial_blue'])!=start['initial_blue_sha256'] or jsha(start['initial_red'])!=start['initial_red_sha256']:errors.append('initial packet hash')
    identities=[launch['launcher'],launch['supervisor'],read(out/'guard_identity.json'),worker_exit['identity']]
    for ident in identities:
        if matching(ident):errors.append('owned process still live')
    verification={'verified_actor_transfer_training':not errors,'errors':errors,'decisions':result['decisions'],
        'new_fdm_ticks':ticks,'gradient_updates':result['gradient_updates'],'completed_episodes':len(result['completed_episodes']),
        'actual_cells':sorted({(s['opponent'],s['distance_ft']) for s in result['episode_starts']}),
        'peak_abs_G':peak,'over9G_ticks':over,'min_AGL_m':lowest,'bundle_reload_verified':result.get('bundle_reload_verified'),
        'win_rate_evidence':False,'official_validation':False,'deployment_allowed':False,
        'next_action':'Freeze final model; separate same-seed initial-SHA matched evaluation, no blind training continuation.',
        'launcher_receipt_sha256':sha(out/'launcher_receipt.json'),'result_sha256':sha(folder/'result.json')}
    write(out/'VERIFICATION.json',verification);print(json.dumps(verification,ensure_ascii=False))
    return 0 if not errors else 2

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    raise SystemExit(verify(parser.parse_args().out))
