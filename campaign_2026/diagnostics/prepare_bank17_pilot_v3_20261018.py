from pathlib import Path
import ast,json,sys,datetime
root=Path(r'E:\ai_pilot\campaign_2026');here=root/'experiments/opponent_pool/bank_residual_train_v3';sys.path.insert(0,str(here));import common as c
for path in here.glob('*.py'):ast.parse(path.read_text(encoding='utf8'))
assert len({(v['opponent'],v['distance_ft'],v['side']) for v in c.plan()[:18]})==18
import guard
_,seen=guard.seen_seeds();assert not set(c.SEEDS)&seen
assert not (here/'PREPARATION.json').exists()
sources=c.sources();c.write(here/'BRANCH_FREEZE.json',dict(sources=sources,prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
c.write(here/'PREPARATION.json',dict(status='isolated_implementation_pending_guarded_precheck',consumed=False,training_launch_allowed=False,reason='Only independent guardian may proceed after actual precheck0 within original900s',sources=sources,unused_seedpool=list(c.SEEDS),episodes=c.plan(),max_decisions=3000,max_blue_ticks=60000,original_total_seconds=900,phase_seconds=dict(PRECHECK=30,WORKER=780,VERIFIER=90),reserved_hours_on_launch=.25,fresh17x1=True,old13x3_incompatible=True,formal_deployment='repair_guide',deployment_allowed=False,verification_scope='Full-tick counters/judge math plus first-tick-per-decision true controller replay; training logs omit ACMI and full per-frame packets. Matched complete policy games still required.'))
print(json.dumps(dict(syntax_files=len(list(here.glob('*.py'))),unclaimed_seeds=len(c.SEEDS),prepared=True,learner_started=False,new_FDM_ticks=0)),flush=True)
