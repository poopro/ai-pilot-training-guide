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
    require(report['status']=='completed' and len(report['cases'])==4,'all4workers')
    import numpy as np
    import torch
    from stable_baselines3 import SAC
    torch.set_num_threads(1)
    model=SAC.load(MODEL,device='cpu')
    total=0;summaries=[]
    for case,worker in zip(launch['cases'],report['cases']):
        folder=out/'cases'/case['case_id'];result=read(folder/'result.json')
        require(worker['case_id']==case['case_id'] and worker['actual_worker_exit_code']==0,'worker exit/order')
        require(worker['input_sha256']==sha(folder/'input.json') and worker['result_sha256']==sha(folder/'result.json'),'worker input/result hash')
        require(result['status']=='interface_pass' and result['case']==case and len(result['episodes'])==1,'result incomplete')
        require(set(result['artifact_sha256'])=={'telemetry.csv','duel.acmi'},'missing artifact')
        for name,digest in result['artifact_sha256'].items():require(sha(folder/name)==digest,'artifact bytes')
        expected_tick=0
        for decision in result['tactical_decisions']:
            obs=np.asarray(decision['observation'],dtype=np.float32);actual=np.asarray(decision['action'],dtype=np.float32)
            require(obs.shape==(13,) and np.isfinite(obs).all(),'legal13decision observation')
            expected=model.predict(obs,deterministic=True)[0] if case['actor_id']=='sac5000' else np.zeros(3,dtype=np.float32)
            require(np.allclose(actual,expected,atol=1e-7,rtol=0),'frozen deterministic actor mismatch')
            require(decision['start_tick']==expected_tick,'decision clock mismatch');expected_tick+=20
        with (folder/'telemetry.csv').open(encoding='utf8',newline='') as stream:rows=list(csv.DictReader(stream))
        require(len(rows)==sum(ep['ticks'] for ep in result['episodes']),'CSV row count')
        for ep in range(1):
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
        first=result['episodes'][0]
        require(first['true_round_complete'] and first['terminated'] and not first['truncated'],'not full completed game')
        times=[float(line[1:]) for line in (folder/'duel.acmi').read_text(encoding='utf8').splitlines() if line.startswith('#')]
        require(len(times)>1 and all(b>a for a,b in zip(times,times[1:])),'nonmonotonic ACMI clock')
        summaries.append({'case_id':case['case_id'],'pair_key':case['pair_key'],'actor_id':case['actor_id'],'heading_error_deg':case['heading_error_deg'],'initial_blue_sha256':first['initial_sha256'],'initial_red_sha256':jsha(first['initial_legal_red']),'stage':case['stage'],'opponent':case['opponent_id'],
                          'ticks_per_reset':first['ticks'],'attack_ticks_per_reset':first['attack_ticks'],
                          'event':first['judge_event'],'winner':first['judge_winner'],
                          'one_full_round':True,'score_eligible':False})
    groups={}
    comparisons=[]
    for case in launch['cases']:
        folder=out/'cases'/case['case_id']
        item=read(folder/'result.json')['episodes'][0]
        with (folder/'telemetry.csv').open(encoding='utf8',newline='') as stream:
            rows=[row for row in csv.DictReader(stream) if int(row['episode'])==0]
        groups.setdefault(case['pair_key'],{})[case['actor_id']]={'case':case,'episode':item,'rows':rows}
    require(len(groups)==2,'not2pairs')
    for key,pair in groups.items():
        require(set(pair)=={'zero','sac5000'},'missing paired actor')
        baseline,candidate=pair['zero'],pair['sac5000']
        require(baseline['episode']['initial_legal_blue']==candidate['episode']['initial_legal_blue'] and
                baseline['episode']['initial_legal_red']==candidate['episode']['initial_legal_red'],'paired initial packet differs')
        exposure=min(len(baseline['rows']),len(candidate['rows']))
        stats={}
        for actor,data in pair.items():
            rows=data['rows'];common_rows=rows[:exposure]
            stats[actor]={'ticks':len(rows),'attack_ticks':data['episode']['attack_ticks'],
                'event':data['episode']['judge_event'],'winner':data['episode']['judge_winner'],
                'red_attack_ticks':int(rows[-1]['red_attack_ticks']),
                'final_advantage_blue':float(rows[-1]['advantage_blue']),'final_advantage_red':float(rows[-1]['advantage_red']),
                'red_over9G_ticks':sum(abs(float(x['red_g']))>9 for x in rows),
                'min_TA_deg':min(float(x['blue_angle_deg']) for x in rows),
                'max_abs_G':max(abs(float(x['blue_g'])) for x in rows),
                'over9G_ticks':sum(abs(float(x['blue_g']))>9 for x in rows),
                'min_AGL_m':min(float(x['blue_agl_m']) for x in rows),
                'common_min_AGL_m':min(float(x['blue_agl_m']) for x in common_rows),
                'common_attack_ticks':int(common_rows[-1]['attack_ticks'])}
        comparisons.append({'pair_key':key,'initial_heading_error_deg':baseline['case']['heading_error_deg'],
                            'same_initial_blue_red_SHA':True,'common_exposure_ticks':exposure,'actors':stats})
    result={'verified_paired_final_policy':not errors,'errors':errors,'new_FDM_ticks':total,'cases':summaries,
            'complete_worker_count':4,'paired_openings':2,'comparisons':comparisons,'actual_observed_launcher_exit_code':parent_exit,
            'training_started':False,'frozen_actor_model_sha256':sha(MODEL),'official_Host_conformance_verified':False,'combat_win_rate_evidence':False,
            'deployment_allowed':False,'report_sha256':sha(out/'report.json')}
    write(out/'VERIFICATION.json',result)
    if errors:raise RuntimeError(repr(errors))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--parent-exit-code',type=int,required=True)
    a=p.parse_args();print(json.dumps(verify(a.out,a.parent_exit_code),ensure_ascii=False))
