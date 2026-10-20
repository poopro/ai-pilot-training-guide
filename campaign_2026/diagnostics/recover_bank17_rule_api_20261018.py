from pathlib import Path
import ast,sys,datetime,shutil
root=Path(r'E:\ai_pilot\campaign_2026');old=root/'experiments/opponent_pool/bank_residual_train_v2';new=root/'experiments/opponent_pool/bank_residual_train_v3';sys.path.insert(0,str(old));import common as c
out=Path(c.read(old/'LATEST.json')['out']);c.write(out/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=1,session_id=95077,chunk_id='e00876',observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),observation_source='Actual completed unified exec wait; intended guardian2 separately recorded'))
identities=[c.read(out/'CONTRACT.json')['guardian']]
for name in ('PRECHECK','WORKER'):
    receipt=c.read(out/(name+'_EXIT.json'));identities.append(receipt['identity']);identities.extend(d['identity'] for d in receipt['descendants'])
audit=[dict(identity=i,original_identity_alive=c.live(i)) for i in identities];assert not any(x['original_identity_alive'] for x in audit)
result=c.read(out/'RESULT.json')
c.write(out/'TERMINAL_FAILURE.json',dict(failure='RuleFighter.act returns command only with separate .guard; new wrapper incorrectly unpacked command as tuple',actual_parent_shell_exit=1,actual_worker_exit=2,actual_precheck_exit=0,verifier_started=False,actual_decisions=result['actual_decisions'],gradient_updates=result['gradient_updates'],new_recorded_FDM_ticks=result['new_FDM_ticks'],first_sac_episode_complete=True,second_episode_failed_before_recorded_physics=True,partial_model_not_promoted=True,old_sources_unchanged=c.sources()==c.read(out/'CONTRACT.json')['sources'],terminal_process_audit=audit))
reg=c.read(root/'seed_registry.json');reg['trials'][out.name].update(status='failed_rule_API_partial900_not_verified',actual_decisions=result['actual_decisions'],gradient_updates=result['gradient_updates'],new_FDM_ticks=result['new_FDM_ticks']);c.write(root/'seed_registry.json',reg)
assert not new.exists();new.mkdir()
for name in ('common.py','policy_features.py','environment.py','train.py','test_contract.py','verify.py','guard.py','USAGE_OBSERVATION.json'):shutil.copy2(old/name,new/name)
p=new/'common.py';s=p.read_text(encoding='utf8').replace('LEARNER_SEED=2026311999;EPISODE_SEEDS=tuple(range(2026312000,2026312032))','LEARNER_SEED=2026312999;EPISODE_SEEDS=tuple(range(2026314000,2026314032))');p.write_text(s,encoding='utf8')
p=new/'environment.py';s=p.read_text(encoding='utf8');anchor='class BankGym(gym.Env):'
helper="""def opponent_command(red,kind,packet,n):
    if kind=='sac5000':
        value=red.command(packet,completed_tick=n);status=red.status();guard=status['guard_active'];mode='frozen_sac5000'
    elif kind=='rule':value=red.act(packet,n/60.);guard=red.guard;mode=red.mode
    elif kind=='mirror':value,guard=red.act(packet,n,started=True);mode=red.mode
    else:raise RuntimeError('Unregistered opponent')
    if 'fallback' in mode:raise RuntimeError('No opponent fallback permitted')
    if not isinstance(guard,(bool,np.bool_)):raise RuntimeError('Opponent guard must be explicit boolean')
    return legal_command(value),bool(guard),mode
"""
s=s.replace(anchor,helper+anchor)
oldblock="""            if case['opponent']=='sac5000':
                value=self.red.command(packet,completed_tick=n);assert self.red.attack_ticks==env.judge.attack[1];guard=self.red.status()['guard_active'];mode='frozen_sac5000'
            elif case['opponent']=='rule':value,guard=self.red.act(packet,n/60.);mode=self.red.mode
            else:value,guard=self.red.act(packet,n,started=True);mode=self.red.mode
            if 'fallback' in mode:raise RuntimeError('No opponent fallback permitted')
"""
newblock="""            value,guard,mode=opponent_command(self.red,case['opponent'],packet,n)
            if case['opponent']=='sac5000':assert self.red.attack_ticks==env.judge.attack[1]
"""
assert oldblock in s;s=s.replace(oldblock,newblock);p.write_text(s,encoding='utf8')
p=new/'test_contract.py';s=p.read_text(encoding='utf8');anchor="    reset=next(x for x in ast.walk"
insert="""    from opponent_lab.duel_lab import RuleFighter
    rule=RuleFighter(copy.deepcopy(settings),float(packet[2])*.3048,np.random.default_rng(123))
    mirror_module=c.load('bank17_precheck_mirror',c.ROOT/'experiments/m4_tactical_v4/m3_mirror_league.py');mirror=mirror_module.MirrorP2Controller(copy.deepcopy(settings),.72,6.,9.)
    for kind,obj in (('sac5000',loaded_red),('rule',rule),('mirror',mirror)):
        for n in range(3):
            value,guard,mode=e.opponent_command(obj,kind,np.asarray(packet,dtype=float),n);assert value.shape==(4,) and type(guard) is bool and 'fallback' not in mode
    checks.append('actual shared production opponent_command three real CPU opponent APIs/guard/cadence no physics')
"""
assert anchor in s;s=s.replace(anchor,insert+anchor);p.write_text(s,encoding='utf8')
for path in new.glob('*.py'):ast.parse(path.read_text(encoding='utf8'))
c.write(new/'RECOVERY_CHANGE.json',dict(failed_run=str(out),failed_receipt_sha256=c.sha(out/'TERMINAL_FAILURE.json'),unique_production_fix='Normalize actual RuleFighter command-only API and separate guard in shared opponent_command; same controller/reward/learner; test all three real opponent branches before physics',fresh_actor_critic_optimizer_replay=True,partial_v2_model_not_loaded=True,new_seedpool=True,old_source_untouched=True))
print('Partial v2 failure preserved; isolated v3 correct actual opponent API and cold three-opponent precheck created, not launched.')
