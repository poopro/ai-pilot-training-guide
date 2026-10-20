"""Check true process exits, actual controls and complete both-side scoring."""
import argparse
import csv
from common import *
sys.path.insert(0,str(ROOT/'experiments'/'rules_v20261014'))
from judge import Judge, Frame, RuleProfile


def verify(out,parent_exit):
    out=Path(out).resolve()
    if out.parent!=HERE or parent_exit!=0:raise ValueError('Need exact new job and actual launcher0')
    launch=read(out/'launch.json');execution_mode_gate(launch);source_gate(launch['source_freeze'])
    if launch['tools_sha256']!=tools():raise ValueError('Executor changed')
    receipt=read(out/'launcher_receipt.json');guard=read(out/'guard.json');report=read(out/'report.json')
    errors=[]
    def require(condition,message):
        if not condition:errors.append(message)
    require(receipt['actual_parent_exit_code']==receipt['actual_guard_exit_code']==0,'parent/guard exit')
    require(read(out/'supervisor_exit.json')['actual_parent_exit_code']==0,'parent wait receipt')
    for key,name in [('report_sha256','report.json'),('guard_sha256','guard.json'),('reservation_sha256','reservation.json'),('launch_sha256','launch.json')]:
        require(receipt[key]==sha(out/name),'hash '+name)
    require(guard['target']==launch['supervisor'] and not guard.get('unknown') and not guard.get('stopped'),'guard identity/cleanup')
    require(report['status']=='completed' and len(report['cases'])==5,'all5workers')
    total=0;summaries=[]
    for case,worker in zip(launch['cases'],report['cases']):
        folder=out/'cases'/case['case_id'];result=read(folder/'result.json')
        require(worker['case_id']==case['case_id'] and worker['actual_worker_exit_code']==0,'worker exit/order')
        require(worker['input_sha256']==sha(folder/'input.json') and worker['result_sha256']==sha(folder/'result.json'),'worker input/result hash')
        require(result['status']=='interface_pass' and result['case']==case and len(result['episodes'])==2,'result incomplete')
        require(set(result['artifact_sha256'])=={'telemetry.csv','duel.acmi'},'missing artifact')
        for name,digest in result['artifact_sha256'].items():require(sha(folder/name)==digest,'artifact bytes')
        with (folder/'telemetry.csv').open(encoding='utf8',newline='') as stream:rows=list(csv.DictReader(stream))
        require(len(rows)==sum(ep['ticks'] for ep in result['episodes']),'CSV row count')
        for ep in range(2):
            summary=result['episodes'][ep];selected=[row for row in rows if int(row['episode'])==ep]
            require(0<summary['ticks']<=case['max_steps'] and len(selected)==summary['ticks'],'episode tick count')
            require(summary['tactical_observation_shape']==[13],'13value observation')
            require(jsha(summary['initial_legal_blue'])==summary['initial_sha256'],'initial bytes')
            require(jsha(summary['final_legal_blue'])==summary['final_sha256'],'final bytes')
            replay=Judge(RuleProfile(**summary['rules_profile']))
            for tick,row in enumerate(selected,1):
                require(all(int(row[k])==tick for k in ['tick','act_calls','blue_send_calls','red_send_calls','judge_calls']),'one control per tick')
                require(legal_command(json.loads(row['actual_command']))==legal_command(json.loads(row['command_from_act'])),'actual sent command')
                frame=Frame(float(row['distance_m']),float(row['blue_angle_deg']),float(row['red_angle_deg']),
                            float(row['blue_g']),float(row['red_g']),float(row['blue_agl_m']),float(row['red_agl_m']))
                state=replay.advance(frame,started=True)
                require(state['attack_ticks']==[int(row['attack_ticks']),int(row['red_attack_ticks'])],'both attack counters')
                require(state['over_g_ticks']==[int(row['blue_over_g_ticks']),int(row['red_over_g_ticks'])],'both G counters')
                require(state['position_sum']==[float(row['position_blue']),float(row['position_red'])],'raw positions')
                require(state['advantage']==[float(row['advantage_blue']),float(row['advantage_red'])],'advantages')
                require(state['event']==row['event'] and str(state['winner'] or '')==row['winner'],'per-frame event/winner')
            state=replay.snapshot()
            require(summary['counts']=={k:summary['ticks'] for k in ['act','blue','red','judge']},'summary control counts')
            require(summary['attack_ticks']==summary['tactical_attack_ticks']==state['attack_ticks'][0],'tactical counter')
            require(summary['max_command_error']==0 and summary['fallbacks']==0,'error/fallback')
            require(summary['opponent_actual']==case['opponent_id'],'opponent')
            require(summary['judge_event']==state['event'] and summary['judge_winner']==state['winner'],'terminal event')
            require(summary['reported_won']==(state['event']!='ongoing' and state['winner']=='blue'),'won mapping')
            if case['expect_nonzero']:require(state['attack_ticks'][0]>0,'rear fixture missed nonzero path')
            if summary['ticks']<case['max_steps']:require(state['event']!='ongoing','unexplained early stop')
            total+=len(selected)
        first,second=result['episodes']
        for key in ['initial_legal_blue','initial_legal_red','final_legal_blue','final_legal_red','counts','ticks','judge_event','judge_winner','reward']:
            require(first[key]==second[key],'reset reproduce '+key)
        times=[float(line[1:]) for line in (folder/'duel.acmi').read_text(encoding='utf8').splitlines() if line.startswith('#')]
        require(len(times)>1 and all(b>a for a,b in zip(times,times[1:])),'nonmonotonic ACMI clock')
        summaries.append({'case_id':case['case_id'],'stage':case['stage'],'opponent':case['opponent_id'],
                          'ticks_per_reset':first['ticks'],'attack_ticks_per_reset':first['attack_ticks'],
                          'event':first['judge_event'],'winner':first['judge_winner'],
                          'same_seed_reset_reproduced':True,'score_eligible':False})
    result={'verified_rules_FDM_integration':not errors,'errors':errors,'new_FDM_ticks':total,'cases':summaries,
            'complete_worker_count':5,'actual_observed_launcher_exit_code':parent_exit,
            'training_started':False,'official_Host_conformance_verified':False,'combat_win_rate_evidence':False,
            'deployment_allowed':False,'report_sha256':sha(out/'report.json')}
    write(out/'VERIFICATION.json',result)
    if errors:raise RuntimeError(repr(errors))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--parent-exit-code',type=int,required=True)
    a=p.parse_args();print(json.dumps(verify(a.out,a.parent_exit_code),ensure_ascii=False))
