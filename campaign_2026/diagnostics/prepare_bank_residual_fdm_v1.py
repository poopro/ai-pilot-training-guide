from pathlib import Path
import ast,json,sys
ROOT=Path(r'E:\ai_pilot\campaign_2026');HERE=ROOT/'experiments/opponent_pool/bank_residual_fdm_v1'
assert not (HERE/'PREPARATION.json').exists()
usage=dict(observed_utc='2026-10-18 07:29:14 UTC',remaining_percent=89,primary=dict(usedPercent=11,windowDurationMins=300,resetsAt=1792316224),weekly=dict(usedPercent=5,windowDurationMins=10080,resetsAt=1792879134),credits_used=False,reset_credit_used=False)
(HERE/'USAGE_OBSERVATION.json').write_text(json.dumps(usage,ensure_ascii=False,indent=2),encoding='utf8')
for path in HERE.glob('*.py'):ast.parse(path.read_text(encoding='utf8'))
sys.path.insert(0,str(HERE));import common as c
c.write(HERE/'BRANCH_FREEZE.json',dict(sources=c.sources(),source_count=len(list(HERE.glob('*.py'))),no_formal_source_edits=True))
c.write(HERE/'PREPARATION.json',dict(status='prepared_pending_real_precheck',hypothesis='Existing original bank-only residual reaches actual60Hz physics/judge, neutral first100-frame fallback remains exact',
    source_freeze=str(HERE/'BRANCH_FREEZE.json'),entry=str(HERE/'guard.py'),FDM_launch_allowed=False,reason='Guard must pass actual precheck0 and unusedseed/resources/OSlock/STOP before consuming a new trial.',
    phases=dict(precheck_seconds=30,worker_seconds=90,verifier_seconds=60,independent_original_total_seconds=240),planned_seed=c.SEED,seed_claimed=False,
    expected_total_FDM_ticks=600,closed_loop_strength_claim=False,training_started=False,deployment_allowed=False))
print(json.dumps(dict(prepared=True,source_AST_files=len(list(HERE.glob('*.py'))),seed_planned_not_claimed=c.SEED,expected_FDM_ticks=600,actual_FDM_ticks=0)))
