from pathlib import Path
import ast,sys,datetime,json
root=Path(r'E:\ai_pilot\campaign_2026');here=root/'experiments/opponent_pool/bank_residual_eval_v1';sys.path.insert(0,str(here));import common as c;import guard
for path in here.glob('*.py'):ast.parse(path.read_text(encoding='utf8'))
_,seen=guard.seen_seeds();assert not set(c.SEEDS)&seen
assert len(c.plan())==6 and not (here/'PREPARATION.json').exists()
sources=c.sources();c.write(here/'BRANCH_FREEZE.json',dict(sources=sources,prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
c.write(here/'PREPARATION.json',dict(status='isolated_full_evaluation_implementation_pending_actual_precheck',consumed=False,FDM_launch_allowed=False,reason='Only guardian after actual precheck0; no training or deployment',sources=sources,cases=c.plan(),seeds_unclaimed=list(c.SEEDS),original_total_seconds=900,case_seconds=90,precheck_seconds=30,verifier_seconds=180,reserved_hours_on_launch=.25,full_packet_CSV_ACMI_and_replay_required=True,formal_deployment='repair_guide',deployment_allowed=False))
print(json.dumps(dict(prepared=True,syntax_files=len(list(here.glob('*.py'))),seeds_unclaimed=list(c.SEEDS),new_FDM_ticks=0)),flush=True)
