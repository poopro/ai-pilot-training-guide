"""Prepare isolated saved-packet wiring check; no seeds/physics/training."""
from pathlib import Path
import ast,hashlib,json
ROOT=Path(r'E:\ai_pilot\campaign_2026');NEW=ROOT/'experiments/opponent_pool/rule_family_v1'
old=(ROOT/'diagnostics/far_speed_window_guardian_v1.py').read_text(encoding='utf8')
new=old.replace('far_speed_window','rule_family_precheck')
new=new.replace("    return rule_family_precheck_worker_v1.worker(out)","    return rule_family_precheck_worker_v1.worker(out)")
needle="        write(out/'CONTRACT.json',spec)"
assert needle in new
new=new.replace(needle,"        spec['new_sources']={str(p):sha(p) for p in (ROOT/'experiments/opponent_pool/rule_family_v1/policy.py',ROOT/'diagnostics/rule_family_precheck_worker_v1.py',Path(__file__))}\n        spec.update(hypothesis='Real untouched pure RepairController.act versus zero-tactical StationController, actual saved-packet command/reset/safety wiring before any new FDM',comparison_goal='controller family only, no new parameter',window_definitions='first300 saved baseline packets per two openings',controller_calls='real act and real inherited command on saved prefixes',model_inference_calls=0)\n"+needle)
target=ROOT/'diagnostics/rule_family_precheck_guardian_v1.py';assert not target.exists()
ast.parse(new);target.write_text(new,encoding='utf8')
files=[target,ROOT/'diagnostics/rule_family_precheck_worker_v1.py',NEW/'policy.py']
for p in files:ast.parse(p.read_text(encoding='utf8'))
usage=dict(observed_utc='2026-10-18 01:26:48 UTC',remaining_percent=85,primary=dict(usedPercent=15,windowDurationMins=300,resetsAt=1792292334),weekly=dict(usedPercent=2,windowDurationMins=10080,resetsAt=1792879134),credits_used=False,reset_credit_used=False)
target.with_suffix('.usage.json').write_text(json.dumps(usage,ensure_ascii=False,indent=2),encoding='utf8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
contract=dict(status='prepared_saved_packet_precheck_only',hypothesis='Compare retained pure guide versus StationController directly; no assumed superiority',
    families=['station_zero','pure_guide'],single_factor='blue rule family, not a one-line ablation',residual=None,learned_tactical_injection=False,
    allowed_input='legal OWN20+ENEMY6 packet only',policy_path=str(NEW/'policy.py'),pure_guide_source=str(ROOT/'repair_v1/controller.py'),station_source=str(ROOT/'experiments/m4_tactical_v4/m1_station.py'),
    unchanged_shared_command_source=str(ROOT/'repair_v1/controller.py'),sources_sha256={str(p):sha(p) for p in files},
    formal_sources_sha256={str(p):sha(p) for p in (ROOT/'repair_v1/controller.py',ROOT/'experiments/m4_tactical_v4/m1_station.py')},
    precheck=dict(seconds=120,guardian=str(target),expected_saved_prefixes=2,frames_per_prefix=300,checks='actual act/command, baseline saved exact, pure guide direct exact, reset, safety parity, no residual/tactic injection'),
    new_FDM_ticks=0,model_inference_calls=0,training_started=False,seed_claims=[],FDM_launch_allowed=False,reason='Real saved-packet precheck still pending; comparison runner and verifier not implemented.')
(NEW/'CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf8')
(NEW/'PREPARATION.json').write_text(json.dumps(dict(status='precheck_prepared_not_run',contract=str(NEW/'CONTRACT.json'),guardian=str(target),FDM_launch_allowed=False,full_comparison_runner_implemented=False,seed_claims=[],deployment_allowed=False),ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(AST_files=3,guardian=str(target),FDM_launch_allowed=False)))
