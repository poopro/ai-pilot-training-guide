from pathlib import Path
import json
ROOT=Path(r'E:\ai_pilot\campaign_2026')
OLD=ROOT/'experiments/opponent_pool/far_bank60_v2'
NEW=ROOT/'experiments/opponent_pool/rear_latch60_v1'
NEW.mkdir(exist_ok=False)
def replace(s,a,b):
    assert a in s,a
    return s.replace(a,b)
s=(OLD/'battle.py').read_text(encoding='utf8')
s=replace(s,"ACTORS=('station_zero','far_bank60');SEEDS=(2026310400,2026310401)","ACTORS=('bank60','latch60');SEEDS=(2026310500,2026310501)")
s=s.replace('far_bank60_v2','rear_latch60_v1').replace('2026310400_two_openings_two_doctrines','2026310500_two_openings_latch_mechanism')
s=replace(s,'project_goal=_goal_module.project_goal','project_goal=_goal_module.project_goal\nRearLatch=_goal_module.RearLatch\nheading_error=_goal_module.heading_error')
s=replace(s,"        original_command=env.packet_controller.command","        latch=RearLatch()  # Private state per fresh episode; never shared with red.\n        original_command=env.packet_controller.command")
s=replace(s,"            distance=geometry_from_observation(packet)['distance_m']\n            requested=[float(roll),float(pitch),float(speed),float(rudder)]\n            applied=project_goal(distance,requested,enabled=case['actor']=='far_bank60')\n            state['blue_guidance']=dict(distance_m=distance,requested=requested,applied=applied,far_cap_enabled=case['actor']=='far_bank60',safety=safety)","            geo=geometry_from_observation(packet);distance=geo['distance_m']\n            requested=[float(roll),float(pitch),float(speed),float(rudder)]\n            capped=project_goal(distance,requested,enabled=True)\n            he=heading_error(packet,geo)\n            applied,trace=latch.apply(capped,he,geo['blue_angle_deg'],enabled=case['actor']=='latch60')\n            state['blue_guidance']=dict(distance_m=distance,requested=requested,applied=applied,far_cap_enabled=True,safety=safety,heading_error_deg=he,body_angle_deg=geo['blue_angle_deg'],latch=trace)")
s=replace(s,"profile='far_bank60_four_game_development_v1',hypothesis='Changing only the blue far requested bank cap72 to60 may break persistent symmetric saturated turn geometry and enter firing range; may regress',single_factor='Blue requested roll cap60 only at distance>914.4m before unchanged command; baseline72, zero tactical both'","profile='rear_latch60_four_game_mechanism_v1',hypothesis='Preserving turn direction through rear heading-error wrap may reduce reversal lag; closed-loop unproven',single_factor='Rear wrap direction latch only; both use rejected far60/near72 zero-tactical law, original speed/pitch/rudder/inner safety. Not superiority to72 or repair_guide'")
s=replace(s,'"""Six preregistered full development games; frozen sources, no learning."""','"""Four bounded mechanism games against rejected bank60; no learning/deployment."""')
(NEW/'battle.py').write_text(s,encoding='utf8')
s=(OLD/'verify.py').read_text(encoding='utf8')
s=replace(s,'expected_red_action=None','expected_red_action=None;prev_he=None;previous_sign=0;held_sign=0')
a="""                expected_roll=max(-60.,min(60.,requested[0])) if c['actor']=='far_bank60' and g['distance_m']>914.4 else requested[0]
                check(g['far_cap_enabled']==(c['actor']=='far_bank60') and g['safety'] is True and applied==[expected_roll,*requested[1:]],tag+' unique cap mapping, other goals and safety unchanged')"""
b="""                # Independent state machine and legal-packet heading math, not candidate.apply.
                def wrap(x):return (x+180)%360-180
                bearing=pregeo['bearing_deg']
                if not 152.4<=pregeo['distance_m']<=914.4:bearing+=max(-20.,min(20.,wrap(pregeo['lead_bearing_deg']-bearing)))*.35
                he=wrap(bearing-row['blue_packet_pre'][5]);angle=pregeo['blue_angle_deg']
                check(abs(g['heading_error_deg']-he)<1e-9 and abs(g['body_angle_deg']-angle)<1e-9,tag+' legal rear latch geometry')
                capped=max(-60.,min(60.,requested[0])) if g['distance_m']>914.4 else requested[0]
                wrapped=prev_he is not None and he*prev_he<0 and abs(he-prev_he)>180
                released=held_sign!=0 and angle<=90
                triggered=False
                if c['actor']=='latch60':
                    if angle<=90:held_sign=0
                    elif held_sign==0 and wrapped and previous_sign!=0:held_sign=previous_sign;triggered=True
                else:held_sign=0
                expected_roll=math.copysign(abs(capped),held_sign) if held_sign and capped!=0 else capped
                expected_trace=dict(enabled=c['actor']=='latch60',wrapped=wrapped,triggered=triggered,released=released,active=held_sign!=0,held_sign=held_sign)
                check(g['latch']==expected_trace and g['far_cap_enabled'] is True and g['safety'] is True and applied==[expected_roll,*requested[1:]],tag+' independent latch/cap, unchanged magnitude/other goals/safety')
                if expected_roll!=0:previous_sign=1 if expected_roll>0 else -1
                prev_he=he"""
s=replace(s,a,b)
s=s.replace("=='station_zero'","=='bank60'").replace("baseline='station_zero'","baseline='bank60'")
# Every candidate pre-trigger command/packet prefix is compared with its fair pair.
s=replace(s,"        for candidate in group:","""        baseline_case=baseline['case']['id'];candidate_case=next(r['case']['id'] for r in group if r is not baseline)
        first_trigger=None;first_goal_difference=None;first_sent_difference=None;prefix_ticks=0
        with (out/'cases'/baseline_case/'telemetry.jsonl').open(encoding='utf8') as bf,(out/'cases'/candidate_case/'telemetry.jsonl').open(encoding='utf8') as cf:
            for n,(bl,cl) in enumerate(zip(bf,cf),1):
                br=json.loads(bl);cr=json.loads(cl)
                if cr['blue_guidance']['latch']['triggered'] and first_trigger is None:first_trigger=n
                if br['blue_guidance']['applied']!=cr['blue_guidance']['applied'] and first_goal_difference is None:first_goal_difference=n
                if br['blue_command']!=cr['blue_command'] and first_sent_difference is None:first_sent_difference=n
                if first_trigger is None:
                    check(br['blue_command']==cr['blue_command'] and br['red_command']==cr['red_command'] and br['blue_packet_post']==cr['blue_packet_post'] and br['red_packet_post']==cr['red_packet_post'], 'actual pre-trigger fair-pair prefix '+str(opening))
                    prefix_ticks+=1
        prefix=dict(first_trigger_tick=first_trigger,first_goal_difference_tick=first_goal_difference,first_actual_command_difference_tick=first_sent_difference,actual_pretrigger_command_and_both_packet_identical_ticks=prefix_ticks)
        for candidate in group:""")
s=replace(s,"comparisons.append(dict(opening=opening,","comparisons.append(dict(latch_prefix=prefix,opening=opening,")
(NEW/'verify.py').write_text(s,encoding='utf8')
print(str(NEW))
