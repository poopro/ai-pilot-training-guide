from pathlib import Path
import sys,datetime,shutil,ast
root=Path(r'E:\ai_pilot\campaign_2026');old=root/'experiments/opponent_pool/bank_residual_train_v3';new=root/'experiments/opponent_pool/bank_residual_train_v4';sys.path.insert(0,str(old));import common as c
out=Path(c.read(old/'LATEST.json')['out']);c.write(out/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=1,session_id=7862,chunk_id='b4b30f',observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),observation_source='Actual completed unified exec wait'))
receipt=c.read(out/'PRECHECK_EXIT.json');identities=[c.read(out/'CONTRACT.json')['guardian'],receipt['identity']]+[d['identity'] for d in receipt['descendants']]
audit=[dict(identity=i,original_identity_alive=c.live(i)) for i in identities];assert not any(x['original_identity_alive'] for x in audit)
c.write(out/'TERMINAL_FAILURE.json',dict(failure='New precheck imported nonexistent opponent_lab package; existing runtime module is duel_lab loaded from exact original LAB path',actual_precheck_exit=1,actual_parent_shell_exit=1,learner_started=False,new_FDM_ticks=0,seedpool_claimed=False,source_unchanged=c.sources()==c.read(out/'CONTRACT.json')['sources'],terminal_process_audit=audit,reservation_not_refunded=True))
assert not new.exists();new.mkdir()
for name in ('common.py','policy_features.py','environment.py','train.py','test_contract.py','verify.py','guard.py','USAGE_OBSERVATION.json'):shutil.copy2(old/name,new/name)
p=new/'test_contract.py';s=p.read_text(encoding='utf8');assert 'from opponent_lab.duel_lab import RuleFighter' in s;s=s.replace('from opponent_lab.duel_lab import RuleFighter','from duel_lab import RuleFighter');p.write_text(s,encoding='utf8')
for path in new.glob('*.py'):ast.parse(path.read_text(encoding='utf8'))
c.write(new/'RECOVERY_CHANGE.json',dict(failed_precheck=str(out),failed_receipt_sha256=c.sha(out/'TERMINAL_FAILURE.json'),unique_change='Only precheck imports actual already-loaded duel_lab module matching repair_v1.env; production code unchanged from v3',seedpool='Same proposed v3 pool was never claimed or used by a learner/FDM; guard must recheck registry before claim',old_sources_unchanged=True))
print('v3 precheck-only failure preserved; isolated v4 fixes precheck module import, no production control change.')
