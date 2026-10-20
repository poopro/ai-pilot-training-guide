"""Read saved telemetry only; never constructs FDM or runs a policy."""
import sys,json,math
from pathlib import Path
from probe import read,write,sha,digest,MODELS,TICKS

def verify(folder,parent_exit):
    errors=[]
    def check(value,label):
        if not value:errors.append(label)
    spec=read(folder/'CONTRACT.json');receipt=read(folder/'EXIT_RECEIPT.json');result=read(folder/'RESULT.json')
    check(parent_exit==0 and receipt['actual_worker_exit']==0,'parent/worker exit')
    check(receipt['worker_identity_absent'] and receipt['reason'] is None and receipt['source_unchanged'],'cleanup/source')
    check(result['status']=='verified_short_FDM_timing' and result['new_FDM_ticks']==1200 and len(result['episodes'])==4,'full short batch')
    check(spec['ticks_per_repeat']==300 and spec['repeats']==2,'reserved contract')
    for ep in result['episodes']:
        tag=ep['model']+'/'+str(ep['repeat']);rows=[json.loads(l) for l in Path(ep['telemetry']).read_text(encoding='utf8').splitlines()]
        check(sha(ep['telemetry'])==ep['telemetry_sha256'] and sha(ep['acmi'])==ep['acmi_sha256'],tag+' artifacts')
        check(len(rows)==TICKS and all(v==TICKS for v in ep['counts'].values()),tag+' counts')
        check(ep['initial_sha256']==digest(ep['initial']),tag+' initial')
        expected=0;previous_time=None
        for n,row in enumerate(rows,1):
            check(row['tick']==n and row['completed_command_tick']==n-1 and all(v==n for v in row['counts'].values()),tag+' tick'+str(n))
            check(row['adapter_status']['attack_ticks']==expected,tag+' pre-counter'+str(n))
            check(row['adapter_status']['act_calls']==n and row['adapter_status']['predict_calls']==(n-1)//20+1,tag+' cadence'+str(n))
            if n==1:check(row['red_packet_pre']==ep['initial'][1],tag+' first state')
            else:check(row['red_packet_pre']==rows[n-2]['red_packet_post'],tag+' post/pre linkage'+str(n))
            expected+=int(500*.3048<=row['distance_m']<=3000*.3048 and 0<=row['red_angle']<=1)
            check(expected==row['judge_red_attack'],tag+' post judge'+str(n))
            if previous_time:check(all(abs(a-b-1/60)<1e-9 for a,b in zip(row['sim_times'],previous_time)),tag+' simtime'+str(n))
            previous_time=row['sim_times']
            for cmd in (row['blue_command'],row['red_command']):check(len(cmd)==4 and all(math.isfinite(v) for v in cmd) and all(abs(v)<=1 for v in cmd[:3]) and 0<=cmd[3]<=1,tag+' command bounds')
        check(expected==ep['final_adapter']['attack_ticks'] and ep['final_adapter']['completed_tick']==300 and ep['final_adapter']['act_calls']==301 and ep['final_adapter']['predict_calls']==16 and ep['pending_commands_not_sent']==1,tag+' final pending')
        check(ep['saved_packet_actor_replay_exact'],tag+' deterministic replay')
    for model in MODELS:
        a,b=[e for e in result['episodes'] if e['model']==model]
        check(a['initial_sha256']==b['initial_sha256'] and a['final_sha256']==b['final_sha256'] and a['telemetry_sha256']==b['telemetry_sha256'],model+' reset reproducibility')
    output=dict(verified_FDM_packet_timing=not errors,errors=errors,parent_exit_code_observed=parent_exit,actual_worker_exit=receipt['actual_worker_exit'],new_FDM_ticks=result['new_FDM_ticks'],models=list(MODELS),result_sha256=sha(folder/'RESULT.json'),contract_sha256=sha(folder/'CONTRACT.json'),exit_receipt_sha256=sha(folder/'EXIT_RECEIPT.json'),full_battle_verified=False,learned_selfplay_training=False,deployment_allowed=False,attack_counter_nonzero_exercised=any(e['attack_ticks'][1]>0 for e in result['episodes']))
    write(folder/'VERIFICATION.json',output);print(json.dumps(output));return 0 if not errors else 2

if __name__=='__main__':raise SystemExit(verify(Path(sys.argv[1]),int(sys.argv[2])))
