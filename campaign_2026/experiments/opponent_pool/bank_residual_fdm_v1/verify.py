"""Independent complete600-frame saved replay. Never advances a simulator."""
from pathlib import Path
import csv,json,math,sys
import numpy as np
import common as c
import bridge
def poses(path):
    lines=path.read_text(encoding='utf8').splitlines();assert lines[:2]==['FileType=text/acmi/tacview','FileVersion=2.2'];result={};tick=None
    for line in lines:
        if line.startswith('#'):tick=round(float(line[1:])*60);assert tick not in result;result[tick]={}
        elif ',T=' in line:
            key,body=line.split(',T=');result[tick][int(key)]=[float(x) for x in body.split('|')]
    return result
def pose_check(actual,packets):
    assert set(actual)=={1,2}
    for oid,packet in enumerate(packets,1):
        p=actual[oid];assert len(p)==6
        a=20925646.32546*.3048;b=20855486.5951*.3048;e=1-(b/a)**2;gd=math.radians(p[1]);rn=a/math.sqrt(1-e*math.sin(gd)**2)
        gc=math.degrees(math.atan2((rn*(1-e)+p[2])*math.sin(gd),(rn+p[2])*math.cos(gd)))
        assert abs(gc-packet[0])<1e-8
        np.testing.assert_allclose([p[0],*p[2:]],[packet[1],packet[2]*.3048,packet[3],packet[4],packet[5]],rtol=0,atol=1e-5)
def run(out):
    spec=c.check(out,'VERIFIER');c.gate(spec);r=c.read(out/'RESULT.json')
    assert c.read(out/'WORKER_EXIT.json')['actual_exit']==0 and c.sha(out/'RESULT.json')==c.read(out/'WORKER_EXIT.json')['result_sha256']
    assert r['new_FDM_ticks']==600 and len(r['episodes'])==2
    sys.path.insert(0,str(c.ROOT/'experiments/rules_v20261014'));from judge import Judge,RuleProfile,Frame
    sys.path.insert(0,str(c.b.base.ADAPTER));from factory import build_frozen_opponent,source_gate
    from packet_features import geometry_from_observation
    module=bridge.factory.exact_module('rule_family_v1_exact_repair',bridge.factory.REPAIR)
    import combat_v3.interface as interface
    settings=c.read(Path(interface.__file__).parent/'config.json');source_gate()
    checks=[];allrows=[]
    for episode in r['episodes']:
        mode=episode['mode'];folder=out/mode;c.check(out,'VERIFIER')
        assert mode in ('neutral','exercise') and episode['seed']==spec['seed'] and episode['rows']==300
        assert episode['initial_sha256']==c.digest(episode['initial'])
        assert all(c.sha(folder/name)==h for name,h in episode['artifacts'].items())
        blue=bridge.controller(settings);assert bridge.receipt(blue)==episode['runtime_blue']
        assert episode['parent_step_path']==str(c.ROOT/'repair_v1/env.py')
        red=build_frozen_opponent('sac5000',settings);j=Judge(RuleProfile(**episode['final']['profile']))
        calls=[];original=blue.command
        def command(packet,roll,pitch,speed,rudder=0.,safety=True):
            assert safety is True;calls.append([float(roll),float(pitch),float(speed),float(rudder)])
            return original(packet,roll,pitch,speed,rudder,safety=True)
        blue.command=command;rows=[];last=None;peak=[0.,0.];mins=[float('inf'),float('inf')];acmi=poses(folder/'duel.acmi');pose_check(acmi[0],episode['initial'])
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream,(folder/'telemetry.csv').open(encoding='utf8',newline='') as csvstream:
            csvrows=csv.DictReader(csvstream)
            for tick,line in enumerate(stream,1):
                c.check(out,'VERIFIER');row=json.loads(line);csvrow=next(csvrows,None)
                assert row['tick']==tick and csvrow is not None and int(csvrow['tick'])==tick
                for k,v in csvrow.items():
                    if k in ('event','winner'):assert v==('' if row[k] is None else row[k])
                    else:assert float(v)==float(row[k])
                assert all(value==tick for value in row['counts'].values())
                for side,k in (('blue',0),('red',1)):
                    packet=row[side+'_packet_pre'];post=row[side+'_packet_post']
                    assert packet==(last[side+'_packet_post'] if last else episode['initial'][k])
                    assert len(packet)==len(post)==26 and np.isfinite(packet).all() and np.isfinite(post).all()
                    geo=geometry_from_observation(post);assert abs(geo['distance_m']-row['distance_m'])<1e-5 and abs(geo['blue_angle_deg']-row[side+'_angle_deg'])<1e-5
                    assert abs(post[14]-row[side+'_g'])<1e-10
                action=bridge.scheduled(mode,tick-1);assert row['bank_action']==action
                residual=bridge.residual(action);np.testing.assert_array_equal(residual,row['blue_residual_received'])
                got,guard=blue.act(row['blue_packet_pre'],residual=residual,started=True)
                np.testing.assert_array_equal(got,row['blue_command']);assert bool(guard)==row['blue_guard'] and len(calls)==tick and calls[-1]==row['blue_requested_goals']
                redvalue=red.command(row['red_packet_pre'],completed_tick=tick-1);np.testing.assert_array_equal(redvalue,row['red_command']);assert red.status()==row['red_adapter']
                snapshot=j.advance(Frame(row['distance_m'],row['blue_angle_deg'],row['red_angle_deg'],row['blue_g'],row['red_g'],row['blue_agl_m'],row['red_agl_m']),started=True)
                assert row['blue_attack']==row['blue_private_attack']==snapshot['attack_ticks'][0] and row['red_attack']==snapshot['attack_ticks'][1]
                assert [row['blue_overG'],row['red_overG']]==snapshot['over_g_ticks']
                for k,expected in [('blue_position',snapshot['position_sum'][0]),('red_position',snapshot['position_sum'][1]),('blue_advantage',snapshot['advantage'][0]),('red_advantage',snapshot['advantage'][1])]:assert abs(row[k]-expected)<1e-8
                assert row['event']==snapshot['event'] and row['winner']==snapshot['winner']
                if last:assert all(abs(a-b-1/60)<1e-9 for a,b in zip(row['sim_times'],last['sim_times']))
                for k,side in enumerate(('blue','red')):peak[k]=max(peak[k],abs(row[side+'_g']));mins[k]=min(mins[k],row[side+'_agl_m'])
                if tick%20==0:pose_check(acmi[tick],[row['blue_packet_post'],row['red_packet_post']])
                rows.append(row);last=row
            assert next(csvrows,None) is None
        assert len(rows)==300 and set(acmi)==set(range(0,301,20)) and j.snapshot()==episode['final']
        assert episode['final']['event']=='ongoing' and episode['final']['winner'] is None #5s diagnostic is not a round
        assert episode['final_packets']==[last['blue_packet_post'],last['red_packet_post']]
        np.testing.assert_array_equal(red.command(episode['final_packets'][1],completed_tick=300),episode['pending_red_command'])
        assert red.status()==episode['red_final_adapter'] and red.act_calls==301 and red.predict_calls==16 and episode['pending_red_commands_not_sent']==1
        assert peak==episode['peak_g'] and mins==episode['min_AGL_m'] and episode['final']['over_g_ticks'][0]==0
        allrows.append(rows);checks.append(dict(mode=mode,ticks=300,full_blue_act_command_replay=True,full_red_actor_controller_replay=True,judge_exact=True,CSV_all_fields_exact=True,ACMI_WGS84_exact=True,peak_g=peak,min_AGL_m=mins,attack=episode['final']['attack_ticks'],over9G=episode['final']['over_g_ticks']))
    assert len({e['initial_sha256'] for e in r['episodes']})==1
    key=lambda row:[row[k] for k in ('blue_packet_pre','red_packet_pre','blue_packet_post','red_packet_post','blue_command','red_command')]
    assert [key(row) for row in allrows[0][:100]]==[key(row) for row in allrows[1][:100]]
    first=next((i+1 for i,(a,z) in enumerate(zip(*allrows)) if a['blue_command']!=z['blue_command']),None)
    assert first is not None and first>100
    first_packet=next((i+1 for i,(a,z) in enumerate(zip(*allrows)) if a['blue_packet_post']!=z['blue_packet_post'] or a['red_packet_post']!=z['red_packet_post']),None)
    assert first_packet is not None and first_packet>=first
    c.gate(spec);c.check(out,'VERIFIER')
    c.write(out/'VERIFICATION.json',dict(verified_bank_residual_60Hz_interface=True,errors=[],episodes=checks,new_FDM_ticks=600,complete_combat_rounds=0,
        same_both_initial_SHA=True,first100_packet_and_command_exact=True,first_actual_sent_blue_command_difference_tick=first,first_physics_packet_difference_tick=first_packet,
        reset_controller_state_independent=True,full_blue_and_red_replay=True,source_XML_model_fixed=True,training_started=False,strength_verified=False,official_validation=False,deployment_allowed=False,
        scope='One new development opening, two5s resets, preset API sequence, not a tactical policy/league/win-rate evaluation.'))
    print(json.dumps(dict(verified_interface=True,new_FDM_ticks=600,first_actual_command_difference=first,first_physics_difference=first_packet)),flush=True);return 0
if __name__=='__main__':raise SystemExit(run(Path(sys.argv[1])))
