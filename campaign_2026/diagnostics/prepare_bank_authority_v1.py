from pathlib import Path
import ast,json
ROOT=Path(r'E:\ai_pilot\campaign_2026')
old=(ROOT/'diagnostics/far_speed_window_guardian_v1.py').read_text(encoding='utf8');new=old.replace('far_speed_window','bank_authority')
needle="        write(out/'CONTRACT.json',spec)";assert needle in new
new=new.replace(needle,"        spec['new_sources']={str(p):sha(p) for p in (ROOT/'experiments/opponent_pool/rule_family_v1/policy.py',ROOT/'diagnostics/bank_authority_worker_v1.py',Path(__file__))}\n        spec.update(hypothesis='Existing original RepairController bank-only residual can change real command under saturated guidance; neutral must exactly fall back',single_factor='Original API first residual dimension -1/0/+1, other0, original source limits unchanged',window_definitions='Two saved baseline first300packet prefixes, neutral history and independent pre-act clones',controller_calls='real original act/command only, no FDM',model_inference_calls=0)\n"+needle)
target=ROOT/'diagnostics/bank_authority_guardian_v1.py';assert not target.exists();ast.parse(new);target.write_text(new,encoding='utf8');ast.parse((ROOT/'diagnostics/bank_authority_worker_v1.py').read_text(encoding='utf8'))
usage=dict(observed_utc='2026-10-18 04:37:04 UTC',remaining_percent=96,primary=dict(usedPercent=0,windowDurationMins=300,resetsAt=1792316224),weekly=dict(usedPercent=4,windowDurationMins=10080,resetsAt=1792879134),credits_used=False,reset_credit_used=False)
target.with_suffix('.usage.json').write_text(json.dumps(usage,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(AST_files=2,guardian=str(target),new_FDM_ticks=0,training_started=False)))
