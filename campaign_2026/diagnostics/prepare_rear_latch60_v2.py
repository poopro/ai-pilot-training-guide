from pathlib import Path
import json,hashlib,datetime,sys
ROOT=Path(r'E:\ai_pilot\campaign_2026');OLD=ROOT/'experiments/opponent_pool/rear_latch60_v1';NEW=ROOT/'experiments/opponent_pool/rear_latch60_v2';RUN=OLD/'run_20261017_203724_6cbe6e'
NEW.mkdir(exist_ok=False)
read=lambda p:json.loads(p.read_text(encoding='utf8'))
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name in ('battle.py','verify.py','candidate.py','test_static.py','USAGE_OBSERVATION.json'):
    s=(OLD/name).read_text(encoding='utf8')
    if name in ('battle.py','test_static.py'):s=s.replace('rear_latch60_v1','rear_latch60_v2').replace('2026310500','2026310600').replace('2026310501','2026310601')
    if name=='candidate.py':
        a='        wrapped=self.previous_he is not None'
        assert a in s;s=s.replace(a,'        he=float(he);body_angle=float(body_angle)  # Normalize NumPy scalar types only.\n'+a)
    if name=='verify.py':
        a="check(value==str(expected) if isinstance(expected,str) or expected is None else abs(float(value)-expected)<=1e-9,tag+' CSV numeric/event field '+key)"
        assert a in s;s=s.replace(a,"check(value==('' if expected is None else str(expected)) if isinstance(expected,str) or expected is None else abs(float(value)-expected)<=1e-9,tag+' CSV numeric/event field '+key)")
    if name=='test_static.py':
        s+='\n# Regression: legal packet geometry yields NumPy scalar headings.\nimport numpy as np,json\nl=c.RearLatch()\nfor he in (np.float64(179.),np.float64(-179.),np.float64(-170.)):\n    goals,trace=l.apply([60.,0.,290.,0.],he,np.float64(140.),enabled=True)\n    json.dumps(trace,allow_nan=False)\n    assert all(type(trace[k]) is bool for k in (\"enabled\",\"wrapped\",\"triggered\",\"released\",\"active\"))\nprint({\"numpy_scalar_trace_serialization\":\"passed\",\"new_FDM_ticks\":0})\n'
        s+='\noldtree=ast.parse((HERE.parent/\"rear_latch60_v1/candidate.py\").read_text(encoding=\"utf8\"));newtree=ast.parse((HERE/\"candidate.py\").read_text(encoding=\"utf8\"))\noldfn=next(n for n in ast.walk(oldtree) if isinstance(n,ast.FunctionDef) and n.name==\"apply\");newfn=next(n for n in ast.walk(newtree) if isinstance(n,ast.FunctionDef) and n.name==\"apply\")\nnewfn.body=[n for n in newfn.body if not (isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id==\"float\")]\nassert ast.dump(oldfn,include_attributes=False)==ast.dump(newfn,include_attributes=False)\nprint({\"control_AST_same_except_scalar_normalization\":True})\n'
    (NEW/name).write_text(s,encoding='utf8')
sys.path.insert(0,str(OLD));import battle as b
report=read(RUN/'report.json');identities=[read(RUN/'CONTRACT.json')['guardian']]
for r in report['cases']:
    identities.append(r['identity']);identities.extend(d['identity'] for d in r['descendants'])
audit=[dict(identity=i,exact_identity_live=b.live(i)) for i in identities]
assert not any(a['exact_identity_live'] for a in audit)
write(RUN/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=1,tool_session=30771,tool_chunk='e07363',observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
write(RUN/'FAILURE_REVIEW.json',dict(status='failed_partial_preserved_not_restarted',actual_parent_tool_exit=1,actual_workers=[r['actual_worker_exit'] for r in report['cases']],cause='NumPy bool_ in latch wrapped/released trace cannot JSON serialize; failure during first case judge logging',complete_games=0,observed_CSV_data_rows=sum(max(0,len((RUN/'cases'/r['case']['id']/'telemetry.csv').read_text(encoding='utf8').splitlines())-1) for r in report['cases']),possible_FDM_initialized_and_stepped=True,seeds=[2026310500,2026310501],reservation_seconds_retained=600,verified_comparison=False,identity_audit=audit,source_unchanged=read(RUN/'GUARD_EXIT.json')['source_unchanged'],deployment_allowed=False))
write(NEW/'PREPARATION.json',dict(status='isolated_type_normalization_recovery_pending_tests',production_change='Only normalize he/body_angle NumPy scalars to Python float before boolean trace computations; numerical control law unchanged',additional_verifier_only_fix='CSV writes None as empty cell; compare that exact encoding, retain all numeric/event checks',prior_failure=str(RUN/'FAILURE_REVIEW.json'),prior_pretrigger_proof=str(ROOT/'diagnostics/rear_latch_precheck_v1_20261017_203552_9a320f/VERIFICATION.json'),new_seeds=[2026310600,2026310601],prior_seeds_not_reused=True,whole_seconds=600,worker_seconds=90,preplanned_verifier_seconds=120,training_started=False,deployment_allowed=False,baseline='rejected unlatched60, not original72 or repair_guide'))
print(json.dumps(dict(prepared=str(NEW),prior_identity_audit=audit)))
