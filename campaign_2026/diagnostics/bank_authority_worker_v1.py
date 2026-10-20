"""Existing bank-residual API authority, on saved packets with private clones.

No physics, actor, training, new control limit or modification of frozen code.
Each alternative starts from the exact same pre-act neutral-history state.
"""
from pathlib import Path
import ast,copy,csv,importlib.util,json,math,os,sys
import numpy as np
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/far_speed_v1';RUN=SOURCE/'run_20261018_033053_98bc0f'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
def residual(action):
    value=float(action)
    if not math.isfinite(value) or not -1<=value<=1:raise ValueError('One finite existing bank residual in[-1,1]')
    return np.asarray([value,0.,0.,0.],dtype=float)
def probe(controller,packet,action):
    # The master is never patched: deepcopy cannot accidentally preserve a
    # hook closure bound to another controller. Only this private clone is hooked.
    private=copy.deepcopy(controller)
    assert private is not controller and private.settings is not controller.settings
    assert not np.shares_memory(private.last,controller.last)
    before=private.last.copy();original=private.command;calls=[]
    def command(obs,roll,pitch,speed,rudder=0.,safety=True):
        if safety is not True:raise RuntimeError('Safety disabled')
        calls.append([float(roll),float(pitch),float(speed),float(rudder)])
        return original(obs,roll,pitch,speed,rudder,safety=True)
    private.command=command
    output,guard=private.act(packet,residual=None if action is None else residual(action),started=True)
    assert len(calls)==1 and np.isfinite(output).all()
    # Independent scalar reconstruction of original aileron clipping and slew,
    # using the AFTER-safety roll target recorded by real command().
    p=np.asarray(packet,dtype=float);phi=math.radians(p[3]);theta=math.radians(p[4])
    rate=math.degrees(p[9]+math.tan(max(-.7,min(.7,theta)))*(p[10]*math.sin(phi)+p[11]*math.cos(phi)))
    raw=.025*((private.bank_target-p[3]+180)%360-180)-.008*rate
    clipped=max(-1.,min(1.,raw));predicted=float(before[0]+max(-.12,min(.12,clipped-before[0])))
    assert abs(predicted-float(output[0]))<1e-12
    return dict(command=output.tolist(),guard=bool(guard),goals=calls[0],actual_after_safety_bank=float(private.bank_target),
        aileron_raw=float(raw),aileron_output_clipped=bool(raw!=clipped),aileron_slew_active=bool(abs(clipped-before[0])>.12),
        master_last_unchanged=bool(np.array_equal(controller.last,before)),single_act_command=True)

def worker(out):
    spec=read(out/'CONTRACT.json');assert os.getppid()==spec['guardian']['pid'] and b.live(spec['guardian'])
    for path,h in spec['new_sources'].items():assert sha(Path(path))==h
    s=importlib.util.spec_from_file_location('bank_authority_exact_factory',ROOT/'experiments/opponent_pool/rule_family_v1/policy.py');f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
    module=f.exact_module('rule_family_v1_exact_repair',f.REPAIR)
    import combat_v3.interface as interface
    settings=read(Path(interface.__file__).parent/'config.json')
    # Extract existing literal limits from the immutable source instead of
    # introducing a diagnostic-specific action magnitude.
    tree=ast.parse(f.REPAIR.read_text(encoding='utf8'))
    limitnode=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='limits' for t in n.targets))
    assert isinstance(limitnode,ast.IfExp)
    near_limits=ast.literal_eval(limitnode.body);far_limits=ast.literal_eval(limitnode.orelse)
    records=[];synthetic=[];invalid_checks=0;all_rows=[]
    for invalid in (-1.01,1.01,float('nan'),float('inf')):
        try:residual(invalid)
        except ValueError:invalid_checks+=1
        else:raise AssertionError('Invalid residual accepted')
    firstpacket=None
    for case in b.plan():
        if case['actor']!='station_zero':continue
        folder=RUN/'cases'/case['id'];r=read(folder/'RESULT.json');assert sha(folder/'telemetry.jsonl')==r['artifacts']['telemetry.jsonl']
        master=f.build_controller('pure_guide',settings);receipt=f.controller_receipt(master)
        assert receipt['class_path']==receipt['act_path']==receipt['command_path']==str(f.REPAIR)
        stats={str(action):dict(goal_changed_ticks=0,command_changed_ticks=0,aileron_changed_ticks=0,other_surfaces_changed_ticks=0,goal_clipped_ticks=0,goal_change_masked_ticks=0,first_changed_command_tick=None,slew_mask_ticks=0,output_clip_mask_ticks=0,safety_mask_ticks=0) for action in (-1,0,1)}
        count=0;case_firstpacket=None
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                row=json.loads(line);tick=int(row['tick'])
                if tick>300:break
                if b.expired(spec) or b.stop(out) or not b.live(spec['guardian']):raise RuntimeError('Original authority deadline/STOP/parent')
                packet=row['blue_packet_pre'];original=np.asarray(packet).copy();firstpacket=firstpacket or packet;case_firstpacket=case_firstpacket or packet
                none=probe(master,packet,None);variants={a:probe(master,packet,a) for a in (-1,0,1)}
                assert variants[0]['command']==none['command'] and variants[0]['guard']==none['guard'] and variants[0]['goals']==none['goals']
                geo=module.geometry_from_observation(packet);scale=near_limits[0] if geo['distance_m']<1100 and geo['blue_angle_deg']<10 else far_limits[0]
                for action,test in variants.items():
                    expected=max(-72.,min(72.,none['goals'][0]+action*scale))
                    assert abs(test['goals'][0]-expected)<1e-12
                    assert test['goals'][1:]==none['goals'][1:]
                    assert test['command'][1:]==none['command'][1:]
                    assert test['master_last_unchanged'] and test['guard']==none['guard']
                    changed=test['command']!=none['command'];goal_changed=test['goals'][0]!=none['goals'][0]
                    stat=stats[str(action)];stat['goal_changed_ticks']+=int(goal_changed);stat['command_changed_ticks']+=int(changed)
                    stat['aileron_changed_ticks']+=int(test['command'][0]!=none['command'][0]);stat['other_surfaces_changed_ticks']+=int(test['command'][1:]!=none['command'][1:])
                    stat['goal_clipped_ticks']+=int(expected!=none['goals'][0]+action*scale)
                    masked=goal_changed and not changed;stat['goal_change_masked_ticks']+=int(masked)
                    stat['slew_mask_ticks']+=int(masked and (test['aileron_slew_active'] or none['aileron_slew_active']))
                    stat['output_clip_mask_ticks']+=int(masked and (test['aileron_output_clipped'] or none['aileron_output_clipped']))
                    stat['safety_mask_ticks']+=int(masked and test['guard'])
                    if changed and stat['first_changed_command_tick'] is None:stat['first_changed_command_tick']=tick
                    all_rows.append(dict(case=case['id'],tick=tick,bank_residual=action,source_bank_scale=float(scale),neutral_requested_bank=none['goals'][0],requested_bank=test['goals'][0],after_safety_bank=test['actual_after_safety_bank'],
                        neutral_aileron=none['command'][0],aileron=test['command'][0],command_changed=changed,goal_changed=goal_changed,guard=test['guard'],slew_active=test['aileron_slew_active'],aileron_raw=test['aileron_raw']))
                master_output=master.act(packet,residual=None,started=True)
                np.testing.assert_array_equal(master_output[0],none['command']);np.testing.assert_array_equal(master_output[0],row['blue_command'])
                assert master_output[1]==none['guard']==row['blue_private_guard'];np.testing.assert_array_equal(packet,original);count=tick
        assert count==300 and stats['0']['command_changed_ticks']==stats['0']['goal_changed_ticks']==0
        fresh=f.build_controller('pure_guide',settings);assert fresh is not master and fresh.settings is not master.settings
        start=fresh.act(case_firstpacket,residual=None,started=True)
        baseline_first=probe(f.build_controller('pure_guide',settings),case_firstpacket,None)
        np.testing.assert_array_equal(start[0],baseline_first['command'])
        records.append(dict(case=case['id'],saved_packet_frames=count,source_artifact_sha256=r['artifacts']['telemetry.jsonl'],runtime_receipt=receipt,existing_bank_limits=[near_limits[0],far_limits[0]],
            neutral_residual_exact=True,neutral_matches_saved_actual_commands=True,private_clone_state=True,single_act_and_command=True,reset_first_command_exact=True,actions=stats))
    for kind in ('low_altitude','low_speed','overG'):
        packet=np.asarray(firstpacket,dtype=float).copy()
        if kind=='low_altitude':packet[2]=1.;packet[8]=0.
        if kind=='low_speed':packet[12]=150.*1.6878098571011957
        if kind=='overG':packet[14]=8.6
        master=f.build_controller('pure_guide',settings);neutral=probe(master,packet,None)
        for a in (-1,0,1):
            got=probe(master,packet,a);assert got['command'][1:]==neutral['command'][1:] and got['guard']==neutral['guard']
            synthetic.append(dict(kind=kind,action=a,guard=got['guard'],requested_bank=got['goals'][0],after_safety_bank=got['actual_after_safety_bank'],non_aileron_channels_unchanged=True))
    for path,h in spec['new_sources'].items():assert sha(Path(path))==h
    b.source_gate(read(RUN/'CONTRACT.json'));assert not b.expired(spec) and not b.stop(out)
    assert any(x['actions']['-1']['command_changed_ticks'] or x['actions']['1']['command_changed_ticks'] for x in records)
    with (out/'AUTHORITY.csv').open('w',encoding='utf8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(all_rows[0]));w.writeheader();w.writerows(all_rows)
    write(out/'VERIFICATION.json',dict(verified_existing_bank_residual_authority=True,errors=[],results=records,unique_saved_input_frames=600,alternative_action_rows=len(all_rows),
        invalid_input_checks=invalid_checks,synthetic_safety_parity=synthetic,independent_aileron_clip_and_slew_math=True,
        authority_csv_sha256=sha(out/'AUTHORITY.csv'),new_FDM_ticks=0,model_inference_calls=0,training_started=False,seed_claims=[],deployment_allowed=False,
        scope='Real original act/command calls on saved packets, each alternative private clone of neutral history. No alternative action is sent to a simulator. Synthetic safety parity is not dynamic9G safety or combat advantage.'))
    print(json.dumps(dict(verified_existing_bank_residual_authority=True,results=records,unique_saved_input_frames=600,alternative_action_rows=len(all_rows)),ensure_ascii=False),flush=True)
    return 0
if __name__=='__main__':raise SystemExit(worker(Path(sys.argv[1])))
