"""Record observed terminal evidence; never launches FDM or edits frozen sources."""
import csv, hashlib, json, os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(r'E:\ai_pilot\campaign_2026')
RUN = ROOT/'experiments/g_latch_development/run_20261014_150515_b846'
SMOKE = ROOT/'experiments/opponent_pool/smoke_executor/run_20261014_195159_f7d760'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p, data):
    temp=p.with_name(p.name+'.record_tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    os.replace(temp,p)
now=datetime.now(timezone.utc).isoformat()
verified=read(RUN/'VERIFIED_DEVELOPMENT.json')
post=read(RUN/'POST_AUDIT.json')
parent=read(RUN/'supervisor_exit.json')
guardian=read(RUN/'guardian_exit_observed.json')
assert verified['verified_comparison'] and verified['eligible_cases']==24 and verified['matched_pairs']==12
assert post['passed'] and post['complete_cases']==24 and post['matched_pairs']==12
assert parent['actual_exit_code']==0 and parent['wait_return_observed'] and guardian['actual_exit_code']==0
safety=read(RUN/'SAFETY_REVIEW.json')
worst=RUN/'cases/r000_rule_3000_mirrored_2026101400_candidate/telemetry_60hz.csv'
with worst.open(encoding='utf-8-sig',newline='') as f:
    rows=list(csv.DictReader(f))
assert len(rows)==18000
flag=next(k for k in rows[0] if 'latch' in k)
count=sum(int(float(row[flag])) for row in rows)
assert count==0
safety.update(supplemental_post_audit='passed', post_audit=str(RUN/'POST_AUDIT.json'),
    altitude_references={'full_min_altitude_delta_m':'judge altitude AGL', 'common_min_altitude_m':'CSV altitude HSL', 'common_min_altitude_delta_m':'CSV altitude HSL; equal-time exposure'},
    worst_case_latch_active_ticks=count, worst_case_latch_field=flag,
    interpretation='Worst rule3000 mirrored altitude regression is not due to latch activation: zero active latch ticks. Bank80 trajectory tradeoff requires review; no causal claim from peak time.',
    deployment_allowed=False, updated_utc=now)
write(RUN/'SAFETY_REVIEW.json',safety)
pointer=read(ROOT/'research_latest.json')
assert pointer['run']==str(RUN)
pointer.update(status='completed',updated_utc=now,actual_parent_exit_code=0,benchmark_return_code=0,
    wall_seconds=read(RUN/'state.json')['finished_epoch']-pointer['supervisor']['create_time'],
    comparison=str(RUN/'VERIFIED_DEVELOPMENT.json'),verified_comparison=True,
    post_audit=str(RUN/'POST_AUDIT.json'),post_audit_passed=True,
    safety_review=str(RUN/'SAFETY_REVIEW.json'),gate='metric_pass_safety_review_pending',deployment_allowed=False,
    summary=post['summary']['totals'],
    next_action='Review saved worst altitude regression and RL no-kill cases. Opponent smoke first real attempt partial: two300-tick cases complete, third failed, parent2/guard1; repair executor with new source contract and targeted diagnostic, never retry same seeds/full batch. Formal repair_guide retained; portable Host and LAN rehearsal still pending.',
    opponent_smoke_last_run=str(SMOKE),opponent_smoke_status='partial_not_verified')
write(ROOT/'research_latest.json',pointer)
trial=pointer['reservation_id']
registry=read(ROOT/'seed_registry.json')
registry['trials'][trial].update(status='completed_verified',actual_parent_exit_code=0,verified_cases=24,matched_pairs=12,post_audit_passed=True,report=str(RUN/'VERIFIED_DEVELOPMENT.json'))
write(ROOT/'seed_registry.json',registry)
budget=read(ROOT/'compute_budgets/2026-10-14.json')
item=next(i for i in budget['items'] if i['id']==trial)
item.update(status='completed_verified',actual_wall_seconds=pointer['wall_seconds'],actual_parent_exit_code=0,actual_guardian_exit_code=0,post_audit_passed=True)
write(ROOT/'compute_budgets/2026-10-14.json',budget)
result='''# 最新結果

- 正式基線 repair_guide 已完成公告版官方 Host 固定來源六個獨立回合：6/6 P1勝、HP180:0、0過G、真退出與自建程序清理通過。這不是未知參賽隊伍勝率。
- 新開發比較完成24/24場、12配對；parent/worker/guardian真退出0，原verifier與補充POST_AUDIT通過。候選3/12擊落、原版1/12，兩者0被擊落/墜機/過9G；rule候選3/6對原1/6，RL兩者0/6。
- 候選五個開局最低高度退步；最差rule3000鏡像在共同300秒高度低約319.32m，該場latch從未啟動。維持metric_pass_safety_review_pending，不自動部署，正式仍repair_guide。
- 對手/鏡像短測首次真FDM在第3case失敗：前兩case各300tick完成，第3worker1、parent2、guard1；未完成24，不算self-play或勝率。保留12個已嘗試seed及15分鐘預算，不全批重啟。正在修復執行器與保護程序存檔問題。
- 下一步：短測根因修復與單case診斷，再驗證鏡像及不同凍結對手；保存退步case研究高度/能量取捨；正式套件Host、LAN/另一電腦和乾淨啟動彩排仍待驗證。
- 10/14塔塔加報名截止、10/19晚間依證據選擇、10/20付款決定、10/21競賽報名截止。尚無報名完成證據。
'''
(ROOT/'latest_result.md').write_text(result,encoding='utf-8')
log=ROOT/'REVIEW_LOG.md'
text=log.read_text(encoding='utf-8-sig')
marker='## 2026-10-14：24場完成與補充完整性稽核'
if marker not in text:
    with log.open('a',encoding='utf-8') as f:
        f.write('\n'+marker+'\n\n- 唯一研究變更為bank80候選的8.5/8.0 G latch。24/24、12配對、固定149來源/紅方與初始SHA；parent、24worker、guardian真0，verifier與POST_AUDIT通過。保留40分鐘預留，實際wall '+str(pointer['wall_seconds'])+'秒，不退款。\n- rule擊落1/6→3/6，RL0/6→0/6；attack合計4.3333→14.0667秒；雙方0被擊落/墜機/過9G。五個高度退步，最差rule3000鏡像共同300秒低319.318m（CSV HSL；原judge AGL低319.317m），候選latch0tick，不能歸因latch。\n- 決策metric_pass_safety_review_pending，正式repair_guide。下一步先研究保存高度取捨與RL攻擊不足，禁止重跑已完成24、把已看seed稱holdout或自動部署。\n- 對手smoke首次真FDM partial：兩完整300tick、第三worker1、parent2、guard1；guard.log為WinError5 atomic replace，已交本地executor修復。15分鐘預留保留、12seed不重用，未宣布24完成或self-play勝率。\n')
notice=read(ROOT/'monitor_notice.json')
digest=hashlib.sha256((RUN/'VERIFIED_DEVELOPMENT.json').read_bytes()).hexdigest()
notice.setdefault('notices',{})[RUN.name+'|metric_pass_safety_review_pending|'+digest]={'experiment_id':RUN.name,'status':'completed','report_sha256':digest,'report':str(RUN/'VERIFIED_DEVELOPMENT.json'),'notified_utc':now,'channel':'human what now response','message':'24場候選3擊落對原1；零過G但高度取捨與RL0擊落未解，維持基線。'}
write(ROOT/'monitor_notice.json',notice)
print(json.dumps({'recorded':True,'status':pointer['status'],'verified':True,'worst_latch_ticks':count,'wall_seconds':pointer['wall_seconds']},ensure_ascii=False))
