from pathlib import Path
ROOT=Path(r'E:\ai_pilot\campaign_2026');OLD=ROOT/'experiments/opponent_pool/far_bank60_v2';NEW=ROOT/'experiments/opponent_pool/far_speed_v1'
NEW.mkdir(exist_ok=False)
def rep(s,a,z):assert a in s,a;return s.replace(a,z)
s=(OLD/'battle.py').read_text(encoding='utf8').replace('far_bank60_v2','far_speed_v1').replace('2026310400','2026310700').replace('2026310401','2026310701').replace("'far_bank60'","'far_speed_unclipped'")
s=rep(s,"HERE/'candidate.py')}","HERE/'candidate.py',HERE/'post_review.py')}")
s=rep(s,"            distance=geometry_from_observation(packet)['distance_m']\n            requested=[float(roll),float(pitch),float(speed),float(rudder)]\n            applied=project_goal(distance,requested,enabled=case['actor']=='far_speed_unclipped')\n            state['blue_guidance']=dict(distance_m=distance,requested=requested,applied=applied,far_cap_enabled=case['actor']=='far_speed_unclipped',safety=safety)","            requested=[float(roll),float(pitch),float(speed),float(rudder)]\n            applied,trace=project_goal(packet,requested,enabled=case['actor']=='far_speed_unclipped')\n            state['blue_guidance']=dict(distance_m=trace['distance_m'],requested=requested,applied=applied,far_speed_enabled=case['actor']=='far_speed_unclipped',safety=safety,speed_trace=trace)")
s=rep(s,"        original_command=env.packet_controller.command","        import inspect\n        controller_path=Path(inspect.getfile(type(env.packet_controller))).resolve()\n        command_path=Path(env.packet_controller.command.__func__.__code__.co_filename).resolve()\n        if controller_path!=ROOT/'experiments/m4_tactical_v4/m1_station.py' or command_path!=ROOT/'repair_v1/controller.py':raise RuntimeError('Wrong runtime controller/command source')\n        result.update(controller_module_path=str(controller_path),controller_source_sha256=sha(controller_path),inner_command_path=str(command_path),inner_command_source_sha256=sha(command_path))\n        original_command=env.packet_controller.command")
s=rep(s,"profile='far_bank60_four_game_development_v1',hypothesis='Changing only the blue far requested bank cap72 to60 may break persistent symmetric saturated turn geometry and enter firing range; may regress',single_factor='Blue requested roll cap60 only at distance>914.4m before unchanged command; baseline72, zero tactical both'","profile='far_speed_ceiling_four_game_v1',hypothesis='Removing only the far heading speed ceiling290 may change pursuit energy/repositioning; higher speed may also worsen turning',single_factor='Original zero-tactical unlatched bank72, only disable290kt ceiling at distance>914.4 and abs heading error>45; final260..450 and other goals/inner safety unchanged'")
s=rep(s,"lp=ROOT/'compute_budgets'/f'{day}.json';ledger=read(lp);","lp=ROOT/'compute_budgets'/f'{day}.json';ledger=read(lp) if lp.exists() else dict(date_taipei=day,daily_limit_hours=6.,reserved_hours=0.,items=[],policy='warning_only_no_refund');")
(NEW/'battle.py').write_text(s,encoding='utf8')
s=(OLD/'verify.py').read_text(encoding='utf8').replace("'far_bank60'","'far_speed_unclipped'")
originalmap="""                expected_roll=max(-60.,min(60.,requested[0])) if c['actor']=='far_speed_unclipped' and g['distance_m']>914.4 else requested[0]
                check(g['far_cap_enabled']==(c['actor']=='far_speed_unclipped') and g['safety'] is True and applied==[expected_roll,*requested[1:]],tag+' unique cap mapping, other goals and safety unchanged')"""
newmap="""                wrap=lambda x:(x+180)%360-180
                bearing=pregeo['bearing_deg'];distance=pregeo['distance_m'];band=152.4<=distance<=914.4
                if not band:bearing+=max(-20.,min(20.,wrap(pregeo['lead_bearing_deg']-bearing)))*.35
                he=wrap(bearing-row['blue_packet_pre'][5]);close=max(-30.,min(65.,(distance-600.)*.07)) if not band else 0.
                raw=pregeo['enemy_equivalent_cas_kts']+close*1.9438444924*pregeo['cas_ratio']
                old_speed=max(260.,min(450.,min(raw,290.) if abs(he)>45 and not band else raw))
                eligible=bool(distance>914.4 and abs(he)>45)
                speed=max(260.,min(450.,raw)) if c['actor']=='far_speed_unclipped' and eligible else requested[2]
                t=g['speed_trace']
                check(abs(requested[2]-old_speed)<1e-8 and abs(t['heading_error_deg']-he)<1e-9 and abs(t['raw_speed_kts']-raw)<1e-8 and t['eligible']==eligible,tag+' original zero-tactical speed and legal projection')
                check(g['far_speed_enabled']==(c['actor']=='far_speed_unclipped') and t['enabled']==g['far_speed_enabled'] and g['safety'] is True and applied==[requested[0],requested[1],speed,requested[3]],tag+' only far speed ceiling removed; other goals/safety unchanged')"""
s=rep(s,originalmap,newmap)
# Reuse the already validated geodetic-aware ACMI and exact CSV checks, not the failed equality.
audit=(ROOT/'diagnostics/saved_latch_audit_v1.py').read_text(encoding='utf8')
pose=audit[audit.index('        acmilines='):audit.index('        j=Judge(')]
s=rep(s,"        j=Judge(",pose+"        j=Judge(")
extra=audit[audit.index('                if csvrow is not None:'):audit.index("                check(row['tick']==n")]
s=rep(s,"                check(row['tick']==n",extra+"                check(row['tick']==n")
s=rep(s,"        check(r['final']['event']!='ongoing'","        check(set(poses)==set([0,*range(20,n+1,20),n]),tag+' ACMI complete frame coverage')\n        check(r['final']['event']!='ongoing'")
s=rep(s,"check(r['case']==c and r['initial_sha256']", "check(r['controller_module_path']==str(ROOT/'experiments/m4_tactical_v4/m1_station.py') and r['controller_source_sha256']==sha(Path(r['controller_module_path'])) and r['inner_command_path']==str(ROOT/'repair_v1/controller.py') and r['inner_command_source_sha256']==sha(Path(r['inner_command_path'])),tag+' actual runtime module receipt')\n        check(r['case']==c and r['initial_sha256']")
s=rep(s,"return 0 if valid else 2","\n    if valid:\n        import importlib.util\n        exact=importlib.util.spec_from_file_location('far_speed_post_review_exact',Path(__file__).parent/'post_review.py');review=importlib.util.module_from_spec(exact);exact.loader.exec_module(review);review.run(out,verification)\n    return 0 if valid else 2")
(NEW/'verify.py').write_text(s,encoding='utf8')
print(str(NEW))
