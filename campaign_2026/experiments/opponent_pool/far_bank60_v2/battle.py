"""Six preregistered full development games; frozen sources, no learning."""
from pathlib import Path
import sys,os,time,math,json,uuid,datetime,subprocess,traceback,csv,importlib.util
import psutil

ROOT=Path(r'E:\ai_pilot\campaign_2026');HERE=Path(__file__).resolve().parent
PROBE=ROOT/'diagnostics/frozen_sac_fdm_v1/probe.py'
_s=importlib.util.spec_from_file_location('validated_fdm_probe_v1',PROBE)
base=importlib.util.module_from_spec(_s);_s.loader.exec_module(base)
read,write,sha,digest,identity,live=base.read,base.write,base.sha,base.digest,base.identity,base.live
ACTORS=('station_zero','far_bank60');SEEDS=(2026310400,2026310401)
TRIAL='far_bank60_v2_2026310400_two_openings_two_doctrines'
# Bind the precise file before framework imports can change sys.path or cache
# another experiment's generic candidate module.
_goal_spec=importlib.util.spec_from_file_location('far_bank60_v2_goal_projection',HERE/'candidate.py')
_goal_module=importlib.util.module_from_spec(_goal_spec);_goal_spec.loader.exec_module(_goal_module)
project_goal=_goal_module.project_goal
if Path(project_goal.__code__.co_filename).resolve()!=HERE/'candidate.py':raise RuntimeError('Wrong exact projection source')
TOTAL=600;CASE_SECONDS=90;MAX_TICKS=18000

def plan():
    return [dict(id=f'{side}_{actor}_{seed}',opening=i,side=side,seed=seed,actor=actor,red='sac5000',distance_ft=6000,max_ticks=MAX_TICKS)
            for i,(seed,side) in enumerate(zip(SEEDS,('normal','mirrored'))) for actor in ACTORS]
def sources():
    return dict(validated_interface=base.dependencies(),batch_files={str(p):sha(p) for p in (HERE/'battle.py',HERE/'verify.py',HERE/'USAGE_OBSERVATION.json',HERE/'test_static.py',HERE/'candidate.py')})
def source_gate(spec):
    if spec['sources']!=sources():raise RuntimeError('Frozen source/XML/model changed')
def stop(out):return any((p/'STOP').exists() for p in (ROOT,HERE,out,ROOT/'experiments/opponent_pool',base.ADAPTER))
def expired(spec,case=None):
    epoch=spec['deadline_epoch'];mono=spec['deadline_monotonic']
    if case is not None:epoch=min(epoch,case['deadline_epoch']);mono=min(mono,case['deadline_monotonic'])
    return time.time()>=epoch or time.monotonic()>=mono
def normalized(i):return dict(pid=i['pid'],creation_epoch=i['create'],cmdline=i['cmd'],exe=i['exe'],parent_pid=i['parent'])
def publish_pointer(out,status,worker=None):
    j=read(ROOT/'research_latest.json');j.update(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status=status,experiment='far_bank60_v2',run=str(out),report=str(out/'report.json'),comparison=None,verified_comparison=False,gate='full_battle_pending_verification',supervisor=normalized(identity()),guardian=normalized(identity()),source_manifest=str(out/'CONTRACT.json'),planned_cases=4,matched_pairs_planned=2,actual_parent_exit_code=None,seed_role='new_development_not_holdout',deployment_allowed=False,retained_deployment='repair_guide')
    j['active_workload']=dict(status=status,run=str(out),supervisor=normalized(identity()),worker=normalized(worker) if worker else None)
    j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[j['active_workload']] if status=='running' else [],observed_utc=j['updated_utc']);write(ROOT/'research_latest.json',j)

def initialize_side(env,side,m):
    from combat_v3.fdm import JsbsimFdm
    from combat_v3.controller import relative_geometry
    from env import precision_terms
    import numpy as np
    before=[m.simulator_observation(env.fdm1,env.fdm2).copy(),m.simulator_observation(env.fdm2,env.fdm1).copy()]
    def cross(blue,red):
        north=math.radians(blue[0]-red[0])*6378137
        east=math.radians(blue[1]-red[1])*6378137*math.cos(math.radians(red[0]));heading=math.radians(red[5])
        return -north*math.sin(heading)+east*math.cos(heading)
    initial_cross=cross(*before)
    if side=='mirrored':
        ic=dict(env.fdm1.param);ric=env.fdm2.param
        ic.update(fdm_ic_lat=2*ric['fdm_ic_lat']-ic['fdm_ic_lat'],fdm_ic_long=2*ric['fdm_ic_long']-ic['fdm_ic_long'],fdm_id=1)
        env.fdm1=JsbsimFdm(**ic)
    elif side!='normal':raise RuntimeError('Unknown side')
    after=[m.simulator_observation(env.fdm1,env.fdm2),m.simulator_observation(env.fdm2,env.fdm1)]
    if side=='mirrored':
        if initial_cross*cross(*after)>=0:raise RuntimeError('Mirrored cross-track not reversed')
        np.testing.assert_allclose(after[0][[2,3,4,5,12]],before[0][[2,3,4,5,12]],rtol=0,atol=1e-5)
        np.testing.assert_array_equal(after[1][:20],before[1][:20])
    env.geometry=relative_geometry(env.fdm1,env.fdm2);env.prev_potential=env._potential(env.geometry)
    env.precision_previous=precision_terms(m.geometry_from_observation(after[0]))[0]
    env.min_altitude_m=float(env.fdm1.fdm['position/h-agl-ft'])*.3048
    if env.current_step!=0 or env.judge.core.ticks!=0:raise RuntimeError('Side transform must be before physical step1')
    return dict(side=side,normal_cross_track_m=initial_cross,actual_cross_track_m=cross(*after),distance_m=env.geometry['distance_m'])

def worker(folder):
    entry=read(folder/'INPUT.json');out=Path(entry['out']);spec=read(out/'CONTRACT.json');case=entry['case'];limits=entry['limits']
    if case not in spec['cases'] or folder!=out/'cases'/case['id']:raise RuntimeError('Unreserved case')
    if os.getppid()!=spec['guardian']['pid'] or not live(spec['guardian']):raise RuntimeError('Worker parent identity')
    if expired(spec,limits) or stop(out):raise RuntimeError('STOP/deadline before worker')
    source_gate(spec);started=time.monotonic();env=None
    result=dict(status='running',case=case,training_started=False,official_validation=False,deployment_allowed=False)
    try:
        sys.path.insert(0,str(ROOT/'experiments/m4_tactical_v4'))
        import m4_tactical_rl as m
        import numpy as np
        m.torch.set_num_threads(1)
        sys.path.insert(0,str(base.ADAPTER));from factory import build_frozen_opponent,frozen_actor,station_controller,source_gate as actor_gate
        from adapter import legal_command
        from packet_features import tactical_obs,geometry_from_observation
        actor_gate()
        blue_actor=None  # This experiment compares two zero-tactical rule controllers only.
        env=m.TacticalDuel(opponent='rule',distance_ft=case['distance_ft'],max_steps=MAX_TICKS)
        env.reset(seed=case['seed']);side=initialize_side(env,case['side'],m)
        initial=[m.simulator_observation(env.fdm1,env.fdm2).tolist(),m.simulator_observation(env.fdm2,env.fdm1).tolist()]
        red=build_frozen_opponent('sac5000',env.settings)
        if red.controller is env.packet_controller:raise RuntimeError('Shared controller')
        env.p2_type='frozen_sac5000'
        counts=dict(blue_act=0,blue_send=0,red_send=0,blue_physics=0,red_physics=0,judge=0)
        state=dict(blue_cmd=None,red_cmd=None,blue_pre=None,red_pre=None,blue_attack=0,blue_guard=False)
        decisions=[];peak=[0.,0.];minimum=[float('inf'),float('inf')]
        original_command=env.packet_controller.command
        def logged_command(packet,roll,pitch,speed,rudder=0.,safety=True):
            distance=geometry_from_observation(packet)['distance_m']
            requested=[float(roll),float(pitch),float(speed),float(rudder)]
            applied=project_goal(distance,requested,enabled=case['actor']=='far_bank60')
            state['blue_guidance']=dict(distance_m=distance,requested=requested,applied=applied,far_cap_enabled=case['actor']=='far_bank60',safety=safety)
            return original_command(packet,*applied,safety=safety)
        env.packet_controller.command=logged_command
        old_act=env.packet_controller.act
        def blue_act(packet,*a,**kw):
            state['blue_pre']=np.asarray(packet,dtype=float).tolist();cmd,guard=old_act(packet,*a,**kw)
            counts['blue_act']+=1;state['blue_cmd']=legal_command(cmd).tolist();state['blue_guard']=bool(guard);return cmd,guard
        env.packet_controller.act=blue_act
        def red_action():
            n=counts['red_physics']
            if env.current_step!=n or counts['blue_physics']!=n:raise RuntimeError('Red completed-state timing')
            packet=m.simulator_observation(env.fdm2,env.fdm1);cmd=red.command(packet,completed_tick=n)
            if red.attack_ticks!=env.judge.attack[1]:raise RuntimeError('Red own counter differs from audit judge')
            state['red_pre']=packet.tolist();state['red_cmd']=cmd.tolist();env.p2_mode='frozen_sac5000';env.p2_guard=red.status()['guard_active'];return cmd
        env._red_action=red_action
        old_bsend=env.fdm1.sendAction;old_rsend=env.fdm2.sendAction
        def blue_send(cmd):counts['blue_send']+=1;np.testing.assert_array_equal(legal_command(cmd),state['blue_cmd']);return old_bsend(cmd)
        def red_send(cmd):counts['red_send']+=1;np.testing.assert_array_equal(legal_command(cmd),state['red_cmd']);return old_rsend(cmd)
        env.fdm1.sendAction=blue_send;env.fdm2.sendAction=red_send
        for plane,key in ((env.fdm1,'blue_physics'),(env.fdm2,'red_physics')):
            original=plane.step
            def physics(plane=plane,key=key,original=original):
                before=plane.fdm.get_sim_time();value=original()
                if abs(plane.fdm.get_sim_time()-before-1/60)>1e-9:raise RuntimeError('Not one60Hz physical step')
                counts[key]+=1;return value
            plane.step=physics
        old_judge=env.judge.update
        fields=['tick','distance_m','blue_angle_deg','red_angle_deg','blue_g','red_g','blue_agl_m','red_agl_m','blue_attack','red_attack','blue_overG','red_overG','blue_position','red_position','blue_advantage','red_advantage','event','winner']
        with (folder/'telemetry.jsonl').open('w',encoding='utf8') as data,(folder/'telemetry.csv').open('w',newline='',encoding='utf8') as csvfile,(folder/'duel.acmi').open('w',encoding='utf8') as acmi:
            writer=csv.DictWriter(csvfile,fieldnames=fields);writer.writeheader()
            acmi.write('FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime=2026-10-17T00:00:00Z\n1,Type=Air+FixedWing,Name=Blue\n2,Type=Air+FixedWing,Name=Frozen SAC Red\n');env.write_frame(acmi)
            def judge(geo,bg,rg):
                old_judge(geo,bg,rg);counts['judge']+=1;n=counts['judge']
                if env.current_step!=n or any(v!=n for v in counts.values()):raise RuntimeError('act/send/physics/judge count mismatch')
                bpost=m.simulator_observation(env.fdm1,env.fdm2);rpost=m.simulator_observation(env.fdm2,env.fdm1)
                own_geo=geometry_from_observation(bpost);state['blue_attack']+=int(500*.3048<=own_geo['distance_m']<=3000*.3048 and own_geo['blue_angle_deg']<=1.)
                if state['blue_attack']!=env.judge.attack[0]:raise RuntimeError('Blue private counter differs from audit judge')
                alts=[float(p.fdm['position/h-agl-ft'])*.3048 for p in (env.fdm1,env.fdm2)]
                for i,g in enumerate((bg,rg)):peak[i]=max(peak[i],abs(g));minimum[i]=min(minimum[i],alts[i])
                snap=env.judge.core.snapshot()
                row=dict(tick=n,distance_m=geo['distance_m'],blue_angle_deg=geo['blue_angle_deg'],red_angle_deg=geo['red_angle_deg'],blue_g=bg,red_g=rg,blue_agl_m=alts[0],red_agl_m=alts[1],blue_attack=snap['attack_ticks'][0],red_attack=snap['attack_ticks'][1],blue_overG=snap['over_g_ticks'][0],red_overG=snap['over_g_ticks'][1],blue_position=snap['position_sum'][0],red_position=snap['position_sum'][1],blue_advantage=snap['advantage'][0],red_advantage=snap['advantage'][1],event=snap['event'],winner=snap['winner'])
                writer.writerow(row)
                row.update(blue_packet_pre=state['blue_pre'],red_packet_pre=state['red_pre'],blue_packet_post=bpost.tolist(),red_packet_post=rpost.tolist(),blue_command=state['blue_cmd'],red_command=state['red_cmd'],counts=counts.copy(),red_adapter=red.status(),blue_private_attack=state['blue_attack'],blue_private_guard=state['blue_guard'],blue_guidance=state['blue_guidance'],sim_times=[env.fdm1.fdm.get_sim_time(),env.fdm2.fdm.get_sim_time()])
                data.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n')
            env.judge.update=judge
            while env.current_step<MAX_TICKS:
                if expired(spec,limits) or stop(out):raise RuntimeError('STOP/original deadline')
                packet=m.simulator_observation(env.fdm1,env.fdm2);geo=geometry_from_observation(packet)
                # All policy features are private legal packet/clock/counter/guard values.
                features=tactical_obs(packet,geo,state['blue_attack'],state['blue_guard'],elapsed_ticks=counts['blue_physics'])
                action=np.zeros(3,dtype=np.float32) if blue_actor is None else np.asarray(blue_actor.predict(features,deterministic=True)[0],dtype=np.float32)
                if action.shape!=(3,) or not np.isfinite(action).all() or np.any(np.abs(action)>1):raise RuntimeError('Invalid blue tactical output')
                decisions.append(dict(tick=env.current_step,features=features.tolist(),action=action.tolist()))
                _,_,term,trunc,info=env.step(action);env.write_frame(acmi)
                if term or trunc:break
                if env.current_step%1200==0:
                    data.flush();csvfile.flush();acmi.flush();write(folder/'progress.json',dict(tick=env.current_step,attack=list(env.judge.attack),overG=list(env.judge.over_g)))
        final=env.judge.core.snapshot()
        if final['event']=='ongoing' or final['winner'] is None:raise RuntimeError('Not a complete resolved game')
        final_red=m.simulator_observation(env.fdm2,env.fdm1);pending=red.command(final_red,completed_tick=env.current_step)
        if red.attack_ticks!=env.judge.attack[1]:raise RuntimeError('Final red completed-state count')
        # Durable physical terminal evidence precedes any further source audit.
        # All 60Hz controller outputs were compared to actual sendAction above.
        # Independent verifier re-evaluates EVERY learned 3Hz decision; do not
        # repeat the entire 60Hz controller trajectory inside this90s worker.
        write(folder/'PHYSICS_COMPLETE.json',dict(initial=initial,initial_sha256=digest(initial),final=final,counts=counts,red_final_adapter=red.status(),side_transform=side))
        source_gate(spec);actor_gate()
        result.update(status='complete_game',initial=initial,initial_sha256=digest(initial),side_transform=side,final_packets=[m.simulator_observation(env.fdm1,env.fdm2).tolist(),final_red.tolist()],final=final,counts=counts,red_final_adapter=red.status(),pending_red_commands_not_sent=1,blue_private_attack=state['blue_attack'],peak_abs_g=peak,min_agl_m=minimum,tactical_decisions=decisions,own_packet_policy_only=True,all_actual_send_commands_equal_single_act_output=True,full_60Hz_controller_replay_performed=False,model_decision_replay_pending_independent_verifier=True,artifacts={n:sha(folder/n) for n in ('telemetry.jsonl','telemetry.csv','duel.acmi')})
    except Exception as e:traceback.print_exc();result.update(status='failed',error=repr(e))
    finally:
        if env is not None:env.close()
        result['wall_seconds']=time.monotonic()-started;write(folder/'RESULT.json',result)
    return 0 if result['status']=='complete_game' else 2

def terminate_known(p,i,descendants):
    actions=[]
    for item in sorted(descendants.values(),key=lambda x:len(x['chain']),reverse=True):
        d=item['identity']
        if live(d):
            child=psutil.Process(d['pid']);child.terminate();actions.append(d)
    if p.poll() is None:
        if not live(i):raise RuntimeError('Unknown worker identity; refusing termination')
        p.terminate();actions.append(i)
    try:code=p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if not live(i):raise RuntimeError('Unknown identity before kill')
        p.kill();code=p.wait(timeout=3)
    for item in descendants.values():
        d=item['identity']
        if live(d):
            child=psutil.Process(d['pid'])
            try:child.wait(timeout=1)
            except psutil.TimeoutExpired:
                if live(d):child.kill();child.wait(timeout=2)
    return code,actions

def launch(check_only=False):
    sys.path.insert(0,str(ROOT));from runner import JobLock
    with JobLock(ROOT/'launch.lock'):
        busy=base.inventory()
        if busy:raise RuntimeError('Other/unknown campaign work '+repr(busy))
        if stop(HERE):raise RuntimeError('STOP')
        resources=base.resources();registry=read(ROOT/'seed_registry.json');seen={int(s) for s in registry.get('observed_seeds',{})}
        for trial in registry.get('trials',{}).values():seen.update(trial['seeds'])
        seen.update(registry.get('reserved_holdout_seeds',[]))
        if TRIAL in registry.get('trials',{}) or set(SEEDS)&seen:raise RuntimeError('Trial/seed already attempted/reserved; no rerun')
        frozen=sources();cases=plan()
        if check_only:
            print(json.dumps(dict(check_only=True,cases=cases,source_count=len(frozen['validated_interface']['physics_sources']),resources=resources,busy=busy,hard_deadline_seconds=TOTAL,worker_deadline_seconds=CASE_SECONDS,new_FDM_ticks=0)));return 0
        out=HERE/('run_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6]);(out/'cases').mkdir(parents=True)
        started=time.monotonic();spec=dict(profile='far_bank60_four_game_development_v1',hypothesis='Changing only the blue far requested bank cap72 to60 may break persistent symmetric saturated turn geometry and enter firing range; may regress',single_factor='Blue requested roll cap60 only at distance>914.4m before unchanged command; baseline72, zero tactical both',sources=frozen,cases=cases,guardian=identity(),deadline_monotonic=started+TOTAL,deadline_epoch=time.time()+TOTAL,worker_seconds=CASE_SECONDS,total_seconds=TOTAL,resources=resources,usage_observation=read(HERE/'USAGE_OBSERVATION.json'),formal_deployment='repair_guide',training_started=False,official_validation=False)
        write(out/'CONTRACT.json',spec)
        day=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat();lp=ROOT/'compute_budgets'/f'{day}.json';ledger=read(lp);ledger['items'].append(dict(id=out.name,hours=TOTAL/3600,status='reserved',output=str(out),warning_only=True));ledger['reserved_hours']=sum(i['hours'] for i in ledger['items']);write(lp,ledger)
        registry.setdefault('trials',{})[TRIAL]=dict(seeds=list(SEEDS),status='attempted',seed_role='new_development_not_holdout',output=str(out));write(ROOT/'seed_registry.json',registry)
        publish_pointer(out,'running');report=dict(status='running',cases=[],verified_comparison=False,training_started=False);write(out/'report.json',report)
        code=2;error=None
        try:
            for case in cases:
                if expired(spec) or stop(out):raise RuntimeError('STOP/total deadline')
                base.resources();source_gate(spec);folder=out/'cases'/case['id'];folder.mkdir()
                limits=dict(deadline_monotonic=min(spec['deadline_monotonic'],time.monotonic()+CASE_SECONDS),deadline_epoch=min(spec['deadline_epoch'],time.time()+CASE_SECONDS))
                write(folder/'INPUT.json',dict(out=str(out),case=case,limits=limits))
                descendants={};actions=[];reason=None;p=None;i=None;wcode=None
                with (folder/'worker.log').open('w',encoding='utf8') as log:
                    try:
                        p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(Path(__file__)),'--worker',str(folder)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                        i=identity(p.pid);write(folder/'worker_identity.json',i);publish_pointer(out,'running',i);write(out/'state.json',dict(status='running',case_id=case['id'],supervisor=normalized(spec['guardian']),worker=normalized(i)))
                        while p.poll() is None:
                            try:
                                root=psutil.Process(i['pid'])
                                for child in root.children(recursive=True):
                                    try:
                                        d=identity(child.pid);chain=[];node=child
                                        while node.pid!=root.pid:
                                            chain.append(identity(node.pid));node=node.parent()
                                            if node is None:raise RuntimeError('Lost own descendant chain')
                                        if not live(i):raise RuntimeError('Worker changed during descendant capture')
                                        descendants[(d['pid'],d['create'])]=dict(identity=d,chain=chain,worker=i)
                                    except psutil.NoSuchProcess:continue
                            except psutil.NoSuchProcess:
                                if p.poll() is None:raise
                            if expired(spec,limits) or stop(out):reason='STOP_or_original_case_deadline';wcode,actions=terminate_known(p,i,descendants);break
                            time.sleep(.1)
                        if wcode is None:wcode=p.wait(timeout=3)
                        # Windows may notify root exit just before its owned console exits.
                        for item in descendants.values():
                            d=item['identity']
                            if live(d):
                                try:psutil.Process(d['pid']).wait(timeout=min(1.,max(.01,limits['deadline_monotonic']-time.monotonic())))
                                except psutil.NoSuchProcess:pass
                                except psutil.TimeoutExpired:
                                    if live(d):
                                        target=psutil.Process(d['pid']);target.terminate();actions.append(d);target.wait(timeout=2)
                    finally:
                        if p is not None and p.poll() is None:
                            reason=reason or 'guardian_exception';wcode,actions=terminate_known(p,i,descendants)
                cleanup_ok=(i is not None and not live(i) and all(not live(d['identity']) for d in descendants.values()))
                receipt=dict(case=case,actual_worker_exit=wcode,identity=i,reason=reason,worker_and_descendants_absent=cleanup_ok,descendants=list(descendants.values()),cleanup_actions=actions,input_sha256=sha(folder/'INPUT.json'),result_sha256=sha(folder/'RESULT.json') if (folder/'RESULT.json').exists() else None)
                write(folder/'WORKER_EXIT.json',receipt);report['cases'].append(receipt);write(out/'report.json',report)
                if wcode!=0 or reason is not None or not cleanup_ok:raise RuntimeError('Incomplete/failed worker '+case['id'])
            source_gate(spec);code=0;report['status']='completed_pending_verifier'
        except Exception as e:traceback.print_exc();error=repr(e);report.update(status='failed_partial',error=error)
        finally:
            write(out/'report.json',report);write(out/'GUARD_EXIT.json',dict(actual_all_worker_exits=[r['actual_worker_exit'] for r in report['cases']],guardian=spec['guardian'],status=report['status'],wall_seconds=time.monotonic()-started,error=error,source_unchanged=(sources()==frozen),guardian_return_intended=code))
            ledger=read(lp)
            for item in ledger['items']:
                if item['id']==out.name:item.update(status=report['status'],actual_guard_wall_seconds=time.monotonic()-started,worker_exits=[r['actual_worker_exit'] for r in report['cases']])
            write(lp,ledger);publish_pointer(out,report['status']);write(out/'state.json',dict(status=report['status'],supervisor=normalized(spec['guardian']),worker=None,error=error))
            print(json.dumps(dict(out=str(out),status=report['status'],worker_exits=[r['actual_worker_exit'] for r in report['cases']],wall_seconds=time.monotonic()-started)),flush=True)
        return code

if __name__=='__main__':
    try:
        if len(sys.argv)==3 and sys.argv[1]=='--worker':result=worker(Path(sys.argv[2]))
        elif sys.argv[1:] in (['--launch'],['--check-only']):result=launch(sys.argv[1]=='--check-only')
        else:raise RuntimeError('Use explicit --launch or --check-only')
        raise SystemExit(result)
    except Exception:traceback.print_exc();raise SystemExit(1)

