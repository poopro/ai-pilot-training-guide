"""Publish an independently audited saved-state diagnostic, not new combat."""
from pathlib import Path
import datetime,json,hashlib
import psutil
ROOT=Path(r'E:\ai_pilot\campaign_2026')
OUT=ROOT/'diagnostics/pursuit_window_trace_v2_20261017_183554_46bebe'
OLD=ROOT/'diagnostics/pursuit_window_trace_20261017_183319_9e78be'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=read(OUT/'TRACE_AUDIT.json');e=read(OUT/'WORKER_EXIT.json');spec=read(OUT/'CONTRACT.json');p=read(OUT/'PARENT_EXIT_OBSERVED.json')
assert a['verified_saved_trace_math'] and a['saved_frames']==72000 and len(a['results'])==4
assert e['actual_worker_exit']==p['actual_exit']==0 and e['reason'] is None and e['absent']
assert read(OLD/'PARENT_EXIT_OBSERVED.json')['actual_exit']==read(OLD/'WORKER_EXIT.json')['actual_worker_exit']==1
assert sha(ROOT/'diagnostics/pursuit_window_trace_v2.py')==spec['diagnostic_source_sha256']
assert sha(ROOT/'diagnostics/pursuit_window_trace_v1.py')==read(OLD/'CONTRACT.json')['diagnostic_source_sha256']
candidates=[r for r in a['results'] if r['case']['actor']=='far_bank60']
assert len(candidates)==2 and all(len(r['heading_wraps'])==13 and r['heading_wraps']==r['goal_reversals'] and r['in_band_requested_bank_opposite_heading']==0 for r in candidates)
audit=[]
for folder in (OUT,OLD):
    s=read(folder/'CONTRACT.json');w=read(folder/'WORKER_EXIT.json');ids=[s['guardian'],w['identity']]+[d['identity'] for d in w['descendants']]
    for i in ids:
        try:
            proc=psutil.Process(i['pid']);same=abs(proc.create_time()-i['create'])<.01 and proc.cmdline()==i['cmd'] and proc.exe().lower()==i['exe'].lower() and proc.ppid()==i['parent']
            if same:raise RuntimeError('Original diagnostic identity still live')
            state='reused_or_identity_mismatch'
        except psutil.NoSuchProcess:state='absent_no_exit_inferred'
        audit.append(dict(identity=i,state=state))
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
v=dict(verified_saved_pursuit_trace=True,created_utc=now,trace_audit_sha256=sha(OUT/'TRACE_AUDIT.json'),actual_parent_exit=0,actual_worker_exit=0,terminal_identity_audit=audit,
       prior_failed_parent_exit=1,prior_failed_worker_exit=1,prior_failure_preserved=True,normal_controller_projection_not_repeated=True,scope='2 preserved normal trace CSV + 2 new mirror projections; independent original-packet geometry/rate/goal and row audit for all 72000 saved states',new_FDM_ticks=0,new_model_inference=False,training_started=False,inner_command_replayed=False,closed_loop_intervention_tested=False,deployment_allowed=False,
       finding='Both bank60 cases have 13 goal reversals exactly on the 13 ±180 heading-error wrap frames; zero baseline has none. Only 2/13 candidate reversals are within2s of 914.4m crossings. Saved-state requested bank otherwise follows shortest heading-error sign. This identifies a discontinuous pursuit mechanism, not proof a latch wins.',
       timing_basis='All diagnostic geometry/branches use pre-step packet. Candidate in-band counts7603/7535 differ by1 from original post-step7604/7536 because initial is outside and terminal is inside.')
write(OUT/'VERIFICATION.json',v)
plan=dict(status='proposed_not_implemented',basis=str(OUT/'VERIFICATION.json'),
          hypothesis='When the enemy crosses directly behind, preserving the existing turn direction through ±180 heading-error wrap may avoid repeated left/right reversals and help bring the nose forward; untested closed-loop.',
          proposed_single_factor='Add rear-sector turn-direction latch on wrap event while legal body-X target angle>90deg. Preserve prior nonzero requested turn sign and existing magnitude; release when target enters forward hemisphere <=90deg; reset every episode. All speed/pitch/rudder and inner safety unchanged.',
          working_baseline='Already rejected bank60 zero-tactical controller; compare latch60 vs unlatched60 to isolate latch. This does not prove superiority to station_zero72 or repair_guide.',
          comparison_design='New frozen controller contract and unused initial seeds, two openings, 4 full paired games;90s/worker,600s including preplanned sufficient verifier cap. Both full initial SHA identical within pair; source/model/XML/STOP/resources/OSlock and independent watchdog. No new seeds selected/claimed yet.',
          prerequisite='Before any FDM, isolated latch/reset/sign/magnitude/safety tests plus saved-packet replay proving no change before first qualifying wrap, same original cap and safety invocation. Never silently change near bank or speed while adding latch.',
          acceptance='Measure real latch activation/first changed command, front-hemisphere time/1deg attack, event/score/death/crash/collision/over9G and common AGL per opening. Any candidate>9G reject. Compare to rejected60 only for mechanism; if promising, require new same-initial reference72 comparison and wider frozen opponents before consideration.',
          deployment_allowed=False,training_started=False,no_parameter_sweep=True,no_new_FDM_started=True)
write(OUT/'NEXT_HYPOTHESIS.json',plan)
lp=ROOT/'compute_budgets/2026-10-17.json';ledger=read(lp)
for item in ledger['items']:
    if item['id']==OUT.name:item.update(status='completed_verified_saved_trace_audit',actual_parent_exit=0,actual_worker_exit=0,original_reservation_retained=True)
    elif item['id']==OLD.name:item.update(status='failed_post_trace_output_serialization',actual_parent_exit=1,actual_worker_exit=1,original_reservation_retained=True,normal_trace_inputs_preserved=True)
write(lp,ledger)
r=read(ROOT/'research_latest.json');r.update(updated_utc=now,active_workload=None,current_live_workloads=dict(learners=[],loops=[],evaluations=[],observed_utc=now),latest_pursuit_trace=str(OUT),latest_pursuit_trace_verification=str(OUT/'VERIFICATION.json'),latest_pursuit_trace_status='completed_verified_saved_pursuit_trace',next_session_plan=str(OUT/'NEXT_HYPOTHESIS.json'),next_action='先隔離實作後半球轉向方向latch；驗證不觸發前與原bank60相同、只改方向不改幅度/速度/安全，再以全新開局latch60對未latch60作完整配對。這是修復已否決分支的機制試驗，仍須之後同initial參考72與更廣對手比較；不部署或盲續訓練。',daily_compute_reserved_hours=ledger['reserved_hours'],next_factor_status='rear_wrap_latch_proposed_not_implemented')
write(ROOT/'research_latest.json',r)
pipe=read(ROOT/'pipeline_latest.json');pipe['campaign_latest_20261017'].update(latest_diagnostic=str(OUT/'VERIFICATION.json'),next_research=str(OUT/'NEXT_HYPOTHESIS.json'),next_factor_status=r['next_factor_status']);write(ROOT/'pipeline_latest.json',pipe)
text='''# 最新進度：定位到目標在後方時反覆換邊轉彎的機制

- 已核對四條保存軌跡，共72,000幀；沒有新模擬或訓練。兩個bank60開局各13次轉彎目標反向，都與方位誤差跨越正負180度發生在同一幀；原72度版本各0次。
- 每個bank60開局有27次射程邊界切換，但僅2次反向落在邊界切換前後2秒。射程內方位誤差中位數約139度、目標方位移動約12.86/13.16度每秒，而我機轉向約6.23/5.88度每秒。
- 下一個待測假設：敵機經過正後方時暫時維持原轉向方向，進入前半球再解除。尚未實作、沒有閉迴路改善證據；須先測重置/安全/未觸發前完全相同，再作新開局完整比較。
- 機制試驗將比較latch60與已否決的unlatched60，只能判斷latch作用；仍需之後和原72度版本在相同開局比較，不能直接取代正式repair_guide。
- 原bank60四場退步結論不變；兩個凍結模型與正式基準保留，不盲續訓練或部署。
- v1正常側兩CSV寫完後因NumPy整數無法輸出JSON而退出1，原失敗保留。v2只投影剩餘鏡像兩條，並從原始packet獨立重算核對四條CSV；worker與parent實際0，沒有重跑對戰或正常側controller投影。

證據：diagnostics/pursuit_window_trace_v2_20261017_183554_46bebe/VERIFICATION.json；下一步同資料夾NEXT_HYPOTHESIS.json。
'''
(ROOT/'latest_result.md').write_text(text,encoding='utf8')
for path,title in ((ROOT/'REVIEW_LOG.md','保存追瞄軌跡的wrap反轉診斷'),(ROOT/'RACE_FOCUS_20261017.md','最新追瞄診斷與待測latch')):
    with path.open('a',encoding='utf8') as f:f.write('\n\n## '+now+' '+title+'\n\n'+text.split('\n',1)[1])
with (ROOT/'REVIEW_LOG.md').open('a',encoding='utf8') as f:
    f.write('\n- v1原120秒/worker1/parent真1(session20860 chunka8fa84)、27.188s，失敗發生在normal candidate trace CSV完成後的JSON print，np.int32 TypeError；不改成完整成功。v2原120秒/worker0/parent真0(session32357 chunk006889)、58.875s，只新增mirror36000保存幀投影。normal2CSV SHA先凍結，audit以原legal packet獨立重算bearing/heading error/EMA LOS rate/feedforward/bank目標及每列g.requested/applied，72000列一致；本次actual來源劇本未改、無新模型predict或FDM/seed claim。\n')
    f.write('- 六個已記錄原identity均已無/重用，未知退出不補0；v1+v2各120秒預留不退款，當日'+str(ledger['reserved_hours'])+'h。TRACE_AUDIT SHA '+sha(OUT/'TRACE_AUDIT.json')+'；診斷只揭露保存軌跡的反轉機制，latch是否能贏需新閉迴路驗證。pre-step in-band7603/7535對原post-step7604/7536差1有明確初末曝光解釋。\n')
n=read(ROOT/'review_notice.json');n.setdefault('events',{})[OUT.name+'|verified_saved_pursuit_trace|'+sha(OUT/'VERIFICATION.json')]=dict(status='verified_saved_pursuit_trace',report=str(OUT/'VERIFICATION.json'),report_sha256=sha(OUT/'VERIFICATION.json'),notified_utc=now,channel='ai heartbeat final');write(ROOT/'review_notice.json',n)
print(json.dumps(dict(verified_saved_pursuit_trace=True,original_identity_count=len(audit),reserved_hours=ledger['reserved_hours'],candidate_exact_wrap_reversals=[len(r['goal_reversals']) for r in candidates]),ensure_ascii=False))
