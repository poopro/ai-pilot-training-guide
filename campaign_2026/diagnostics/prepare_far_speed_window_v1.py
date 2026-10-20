from pathlib import Path
import ast,json
ROOT=Path(r'E:\ai_pilot\campaign_2026')
old=(ROOT/'diagnostics/latch_window_guardian_v1.py').read_text(encoding='utf8')
new=old.replace('latch_window','far_speed_window').replace('rear_latch60_v2','far_speed_v1').replace('run_20261017_203915_d840e7','run_20261018_033053_98bc0f')
oldline="        link=read(RUN/'SAVED_DATA_AUDIT_LINK.json');spec.update(comparison_path=link['comparison'],comparison_sha256=link['comparison_sha256'],analysis_worker_sha256=sha(ROOT/'diagnostics/far_speed_window_worker_v1.py'),anchors={'0':3458,'1':3854},window_seconds=[-5,0,5,10,20,40])"
assert oldline in new
new=new.replace(oldline,"        spec.update(comparison_path=str(RUN/'COMPARISON.json'),comparison_sha256=sha(RUN/'COMPARISON.json'),analysis_worker_sha256=sha(ROOT/'diagnostics/far_speed_window_worker_v1.py'),window_definitions='early0to10s/late240to260s/minimum-post-distance+-5s',hypothesis='Test whether enemy-equivalentCAS plus desired-close term repeatedly saturates450; distinguish target saturation from actual speed/turn response, no intervention',model_inference_calls=0,controller_calls=0)")
new=new.replace('reserved_offline_latch_window','reserved_offline_far_speed_window').replace('offline_latch_window','offline_far_speed_window')
new=new.replace("        write(out/'CONTRACT.json',spec)","        write(out/'CONTRACT.json',spec)\n        write(Path(__file__).with_suffix('.latest.json'),dict(out=str(out),guardian=spec['guardian'],deadline_epoch=spec['deadline_epoch']))")
target=ROOT/'diagnostics/far_speed_window_guardian_v1.py'
assert not target.exists();ast.parse(new);target.write_text(new,encoding='utf8')
worker=ROOT/'diagnostics/far_speed_window_worker_v1.py';ast.parse(worker.read_text(encoding='utf8'))
usage=dict(observed_utc='2026-10-17 22:33:58 UTC',remaining_percent=96,primary=dict(usedPercent=4,windowDurationMins=300,resetsAt=1792292334),weekly=dict(usedPercent=1,windowDurationMins=10080,resetsAt=1792879134),credits_used=False,reset_credit_used=False)
target.with_suffix('.usage.json').write_text(json.dumps(usage,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(guardian=str(target),AST_files=2,new_FDM_ticks=0,training_started=False)))
