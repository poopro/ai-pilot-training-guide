from pathlib import Path
import ast,sys,datetime,shutil
root=Path(r'E:\ai_pilot\campaign_2026');old=root/'experiments/opponent_pool/bank_residual_train_v1';new=root/'experiments/opponent_pool/bank_residual_train_v2';sys.path.insert(0,str(old));import common as c
out=Path(c.read(old/'LATEST.json')['out']);c.write(out/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=1,session_id=28873,chunk_id='652d41',observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),observation_source='Actual unified exec completed shell wait; guardian intended2 is separately recorded'))
identities=[c.read(out/'CONTRACT.json')['guardian']]
for name in ('PRECHECK','WORKER'):
    receipt=c.read(out/(name+'_EXIT.json'));identities.append(receipt['identity']);identities.extend(d['identity'] for d in receipt['descendants'])
audit=[]
for ident in identities:
    active=c.live(ident);audit.append(dict(identity=ident,original_identity_alive=active))
assert not any(x['original_identity_alive'] for x in audit)
c.write(out/'TERMINAL_FAILURE.json',dict(failure='Class inspect.getfile failed for dynamically loaded unregistered StationController; reflection only',actual_parent_shell_exit=1,actual_worker_exit=2,actual_precheck_exit=0,verifier_started=False,actual_decisions=0,gradient_updates=0,new_recorded_FDM_ticks=0,FDM_initialized=True,old_sources_unchanged=c.sources()==c.read(out/'CONTRACT.json')['sources'],no_promotion=True,seedpool_not_reusable=list(c.SEEDS),terminal_process_audit=audit))
reg=c.read(root/'seed_registry.json');reg['trials'][out.name].update(status='failed_metadata_before_first_recorded_tick',actual_decisions=0,output=str(out));c.write(root/'seed_registry.json',reg)
assert not new.exists();new.mkdir()
for name in ('common.py','policy_features.py','environment.py','train.py','test_contract.py','verify.py','guard.py','USAGE_OBSERVATION.json'):shutil.copy2(old/name,new/name)
p=new/'common.py';s=p.read_text(encoding='utf8').replace('LEARNER_SEED=2026310999;EPISODE_SEEDS=tuple(range(2026311000,2026311032))','LEARNER_SEED=2026311999;EPISODE_SEEDS=tuple(range(2026312000,2026312032))');p.write_text(s,encoding='utf8')
p=new/'environment.py';s=p.read_text(encoding='utf8').replace("path=Path(inspect.getfile(type(obj))).resolve();return dict(class_name=type(obj).__name__,path=str(path),sha256=c.sha(path))", "path=Path(inspect.getfile(obj.act)).resolve();return dict(class_name=type(obj).__name__,module=type(obj).__module__,path=str(path),sha256=c.sha(path))");p.write_text(s,encoding='utf8')
p=new/'test_contract.py';s=p.read_text(encoding='utf8');anchor="    reset=next(x for x in ast.walk"
insert="    loaded_red=e.build_frozen_opponent('sac5000',settings);receipt=e.runtime_receipt(loaded_red.controller);assert Path(receipt['path'])==c.ROOT/'experiments/m4_tactical_v4/m1_station.py';assert receipt['sha256']==c.sha(Path(receipt['path']));checks.append('true frozen model/controller dynamic-module method-source receipt, no FDM or learner')\n"
assert anchor in s;s=s.replace(anchor,insert+anchor);p.write_text(s,encoding='utf8')
for path in new.glob('*.py'):ast.parse(path.read_text(encoding='utf8'))
c.write(new/'RECOVERY_CHANGE.json',dict(failed_run=str(out),failed_receipt_sha256=c.sha(out/'TERMINAL_FAILURE.json'),unique_production_fix='Reflection uses actual bound act method code path instead of class module registry lookup; control/reward/learner unchanged',new_seedpool=True,old_source_untouched=True,static_syntax_files=7))
print('Failed v1 preserved with actual exits; isolated v2 metadata correction created; not launched.')
