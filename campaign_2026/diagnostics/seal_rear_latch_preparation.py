from pathlib import Path
import json,hashlib,datetime
ROOT=Path(r'E:\ai_pilot\campaign_2026');NEW=ROOT/'experiments/opponent_pool/rear_latch60_v1';PRE=ROOT/'diagnostics/rear_latch_precheck_v1_20261017_203552_9a320f'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
receipt=read(PRE/'WORKER_EXIT.json');verification=read(PRE/'VERIFICATION.json');spec=read(PRE/'CONTRACT.json')
assert receipt['actual_worker_exit']==0 and receipt['absent'] and verification['verified_pretrigger_actual_command_replay']
assert all(sha(Path(p))==h for p,h in spec['new_sources'].items())
write(PRE/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=0,tool_session=10304,tool_chunk='484970',evidence='Observed write_stdin completion; not inferred from child receipt',observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
write(NEW/'PREPARATION.json',dict(status='isolated_latch_implementation_prerequisite_verified_no_new_FDM',hypothesis='Rear ±180 heading wrap causes reversal; latch direction only until forward hemisphere',baseline='rejected bank60 zero-tactical StationController, not original72 or repair_guide',single_factor='Rear wrap turn-direction sign latch; all magnitudes far60/near72, pitch/speed/rudder and unchanged inner safety retained',prerequisite=str(PRE/'VERIFICATION.json'),prerequisite_sha256=sha(PRE/'VERIFICATION.json'),static_checks=17,pretrigger_actual_inner_command_replay_ticks=[3590,3973],both_parent_worker_exit=0,source_sha256={str(p):sha(p) for p in NEW.glob('*.py')},plan_games=4,plan_pairs=2,seeds=[2026310500,2026310501],seeds_claimed=False,worker_seconds=90,whole_seconds=600,preplanned_verifier_seconds=120,training_started=False,deployment_allowed=False,acceptance='Any >9G rejected; independent events/full scores/common AGL/first trigger and actual command prefix. Superiority to weak60 is not superiority to72 or repair_guide.'))
print('Prerequisite sealed; no FDM/seed claimed')
