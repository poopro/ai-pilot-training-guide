"""Full saved packet, actor/controller, judge, CSV/ACMI paired audit."""
from pathlib import Path
import copy,csv,hashlib,json,math,sys
import numpy as np
import common as c
def poses(path):
    result={};tick=None;lines=path.read_text(encoding='utf8').splitlines();assert lines[:2]==['FileType=text/acmi/tacview','FileVersion=2.2']
    for line in lines:
        if line.startswith('#'):tick=round(float(line[1:])*60);assert tick not in result;result[tick]={}
        elif ',T=' in line:
            key,body=line.split(',T=');result[tick][int(key)]=[float(x) for x in body.split('|')]
    return result
def pose_check(actual,packets):
    assert set(actual)=={1,2}
    for oid,packet in enumerate(packets,1):
        p=actual[oid];assert len(p)==6;a=20925646.32546*.3048;b=20855486.5951*.3048;e=1-(b/a)**2;gd=math.radians(p[1]);rn=a/math.sqrt(1-e*math.sin(gd)**2)
        gc=math.degrees(math.atan2((rn*(1-e)+p[2])*math.sin(gd),(rn+p[2])*math.cos(gd)));assert abs(gc-packet[0])<1e-8
        np.testing.assert_allclose([p[0],*p[2:]],[packet[1],packet[2]*.3048,packet[3],packet[4],packet[5]],rtol=0,atol=1e-5)
def run(out):
    spec=c.check(out,'VERIFIER');c.gate(spec)
    import policy as p
    import combat_v3.interface as interface
    sys.path.insert(0,str(c.ROOT/'experiments/rules_v20261014'));from judge import Judge,RuleProfile,Frame
    settings=c.read(Path(interface.__file__).parent/'config.json');results=[];heights={};models={};total=0
    for index,case in enumerate(spec['cases']):
        c.check(out,'VERIFIER');folder=out/'cases'/case['id'];phase=f'CASE{index}';exit=c.read(out/(phase+'_EXIT.json'));r=c.read(folder/'RESULT.json');start=c.read(folder/'START.json')
        assert exit['actual_exit']==0 and exit['absent'] and exit['result_sha256']==c.sha(folder/'RESULT.json')
        assert r['case']==start['case']==case and r['status']=='complete_game_pending_verifier' and r['rows']<=18000
        assert all(c.sha(folder/name)==h for name,h in r['artifacts'].items());assert c.digest(start['initial'])==start['initial_sha256']==r['initial_sha256']
        assert start['parent_step_path']==str(c.ROOT/'repair_v1/env.py') and not start['opponent_fallback']
        actor=p.model() if case['mode']=='learned' else None;blue=p.BluePolicy(case['mode'],settings,actor);red=p.make_red(case['opponent'],settings,start['initial'][1],start['red_rng_state'])
        assert blue.receipt==start['blue'] and blue.command_source==start['command_source'] and p.red_receipt(red,case['opponent'])==start['red']
        j=Judge(RuleProfile(**r['final']['profile']));acmi=poses(folder/'duel.acmi');pose_check(acmi[0],start['initial']);last=None;rows=0;redattack=0;peak=[0.,0.];mins=[float('inf'),float('inf')];band=front=0;blueAGL=[];cmdsha=hashlib.sha256();numericsha=hashlib.sha256();closest=float('inf')
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream,(folder/'telemetry.csv').open(encoding='utf8',newline='') as cs:
            csvrows=csv.DictReader(cs)
            for tick,line in enumerate(stream,1):
                row=json.loads(line);csvrow=next(csvrows,None);assert row['tick']==tick and csvrow is not None
                for key,value in csvrow.items():
                    if key in ('event','winner'):assert value==('' if row[key] is None else row[key])
                    else:assert float(value)==float(row[key])
                assert all(v==tick for v in row['counts'].values())
                for side,k in (('blue',0),('red',1)):
                    packet=row[side+'_packet_pre'];post=row[side+'_packet_post'];p.features.validate_observation(packet);p.features.validate_observation(post)
                    assert packet==(last[side+'_packet_post'] if last else start['initial'][k])
                    geo=p.features.geometry_from_observation(post);assert abs(geo['distance_m']-row['distance_m'])<1e-5 and abs(geo['blue_angle_deg']-row[side+'_angle_deg'])<1e-5
                    assert post[14]==row[side+'_g']
                bluevalue=blue.next(row['blue_packet_pre'],tick-1);np.testing.assert_array_equal(bluevalue,row['blue_command']);np.testing.assert_array_equal(c.bridge.residual(blue.bank),row['blue_residual'])
                assert blue.bank==row['bank_action'] and blue.goals==row['blue_goals'] and blue.guard==row['blue_guard']
                if (tick-1)%20==0:np.testing.assert_array_equal(blue.last_features,row['decision_features'])
                else:assert row['decision_features'] is None
                redvalue,redguard,redmode=p.fixed.opponent_command(red,case['opponent'],np.asarray(row['red_packet_pre'],dtype=float),tick-1)
                np.testing.assert_array_equal(redvalue,row['red_command']);assert redguard==row['red_guard'] and redmode==row['red_mode']
                if case['opponent']=='sac5000':assert red.status()==row['red_adapter']
                else:assert row['red_adapter'] is None
                blue.observe(row['blue_packet_post'],tick);redgeo=p.features.geometry_from_observation(row['red_packet_post']);redattack+=int(152.4<=redgeo['distance_m']<=914.4 and redgeo['blue_angle_deg']<=1.)
                snap=j.advance(Frame(row['distance_m'],row['blue_angle_deg'],row['red_angle_deg'],row['blue_g'],row['red_g'],row['blue_agl_m'],row['red_agl_m']),started=True)
                assert [blue.attack,redattack]==[row['blue_private_attack'],row['red_private_attack']]==snap['attack_ticks']
                assert [row['blue_attack'],row['red_attack']]==snap['attack_ticks'] and [row['blue_overG'],row['red_overG']]==snap['over_g_ticks']
                for key,expected in (('blue_position',snap['position_sum'][0]),('red_position',snap['position_sum'][1]),('blue_advantage',snap['advantage'][0]),('red_advantage',snap['advantage'][1])):assert abs(row[key]-expected)<1e-8
                assert row['event']==snap['event'] and row['winner']==snap['winner'] and abs(row['blue_g'])<=9
                if last:assert all(abs(a-b-1/60)<1e-9 for a,b in zip(row['sim_times'],last['sim_times']))
                if tick%20==0 or snap['event']!='ongoing':pose_check(acmi[tick],[row['blue_packet_post'],row['red_packet_post']])
                for k,side in enumerate(('blue','red')):peak[k]=max(peak[k],abs(row[side+'_g']));mins[k]=min(mins[k],row[side+'_agl_m'])
                inband=152.4<=row['distance_m']<=914.4;band+=int(inband);front+=int(inband and row['blue_angle_deg']<=90);closest=min(closest,row['distance_m']);blueAGL.append(row['blue_agl_m'])
                cmdsha.update(np.asarray(row['blue_command'],dtype=np.float64).tobytes());numericsha.update(np.asarray([row[k] for k in ('distance_m','blue_angle_deg','red_angle_deg','blue_g','red_g','blue_agl_m','red_agl_m')],dtype=np.float64).tobytes())
                rows=tick;last=row
                if tick%1000==0:c.check(out,'VERIFIER')
            assert next(csvrows,None) is None
        final=j.snapshot();assert rows==r['rows'] and final==r['final'] and final['event']!='ongoing'
        assert set(acmi)==set(range(0,rows+1,20))|{rows};assert r['final_packets']==[last['blue_packet_post'],last['red_packet_post']]
        assert blue.act_calls==blue.command_calls==rows and blue.predict_calls==r['blue_predict_calls']==(math.ceil(rows/20) if case['mode']=='learned' else 0)
        if actor is not None:assert c.tc.actor_digest(actor)==r['blue_actor_sha256']==c.read(c.BUNDLE/'RESULT.json')['final_actor_sha256']
        if case['opponent']=='sac5000':
            np.testing.assert_array_equal(red.command(r['final_packets'][1],completed_tick=rows),r['pending_red_command_not_sent']);assert red.status()==r['red_final_adapter'] and red.attack_ticks==final['attack_ticks'][1]
        else:assert r['pending_red_command_not_sent'] is None and r['red_final_adapter'] is None
        assert peak==r['peak_g'] and mins==r['min_AGL_m'] and band==r['in_range_ticks'] and front==r['in_range_front_ticks']
        heights[case['id']]=blueAGL;event=final['event'];results.append(dict(case=case,rows=rows,initial_sha256=r['initial_sha256'],final=final,scoremargin=final['advantage'][0]-final['advantage'][1],attack=final['attack_ticks'],kill=[int(event in ('blue_kill','simultaneous_kill')),int(event in ('red_kill','simultaneous_kill'))],shot_down=[int(event in ('red_kill','simultaneous_kill')),int(event in ('blue_kill','simultaneous_kill'))],crash=[int(event in ('blue_crash','mutual_crash')),int(event in ('red_crash','mutual_crash'))],collision=int(event=='collision'),over9G=final['over_g_ticks'],peak_G=peak,min_AGL_m=mins,in_range_ticks=band,in_range_front_ticks=front,closest_m=closest,blue_actual_command_sha256=cmdsha.hexdigest(),numerical_trajectory_sha256=numericsha.hexdigest(),full_actor_controller_judge_CSV_ACMI=True));total+=rows
    pairs=[]
    for i in range(3):
        base,candidate=results[2*i:2*i+2];assert base['case']['mode']=='neutral' and candidate['case']['mode']=='learned' and base['initial_sha256']==candidate['initial_sha256'] and base['case']['seed']==candidate['case']['seed']
        n=min(base['rows'],candidate['rows']);bh=heights[base['case']['id']][:n];ch=heights[candidate['case']['id']][:n]
        pairs.append(dict(opponent=base['case']['opponent'],baseline=base,candidate=candidate,paired_score_change=candidate['scoremargin']-base['scoremargin'],common_exposure_ticks=n,common_min_AGL_baseline=min(bh),common_min_AGL_candidate=min(ch),common_min_AGL_change=min(ch)-min(bh),actual_commands_equal=base['rows']==candidate['rows'] and base['blue_actual_command_sha256']==candidate['blue_actual_command_sha256'],numerical_trajectory_equal=base['rows']==candidate['rows'] and base['numerical_trajectory_sha256']==candidate['numerical_trajectory_sha256']))
    c.check(out,'VERIFIER');c.gate(spec)
    comparison=dict(verified_comparison=True,errors=[],complete_games=6,matched_pairs=3,new_FDM_ticks=total,source_XML_models_fixed=True,full_actor_controller_judge_CSV_ACMI=True,pairs=pairs,training_started=False,holdout=False,formal_deployment='repair_guide',deployment_allowed=False,scope='Three development opponent/opening cells, one matched pair each; not unknown-team win rate')
    c.write(out/'COMPARISON.json',comparison);print(json.dumps(dict(verified=True,games=6,pairs=3,ticks=total)),flush=True);return 0
if __name__=='__main__':raise SystemExit(run(Path(sys.argv[1])))
