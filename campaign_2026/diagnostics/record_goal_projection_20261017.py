"""Audit and record a completed offline projection, without running physics."""
from pathlib import Path
import datetime,json,sys,hashlib
import psutil

ROOT=Path(r'E:\ai_pilot\campaign_2026')
OUT=ROOT/'diagnostics/sac_goal_projection_20261017_122745_b73993'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

a=read(OUT/'ANALYSIS.json');spec=read(OUT/'CONTRACT.json');e=read(OUT/'WORKER_EXIT.json');p=read(OUT/'PARENT_EXIT_OBSERVED.json')
assert e['actual_worker_exit']==0 and e['reason'] is None and e['absent'] and p['actual_exit']==0
assert a['status']=='completed_offline_goal_projection' and len(a['results'])==6
assert sha(ROOT/'diagnostics/sac_goal_projection_v1.py')==spec['diagnostic_source_sha256']
assert sum(r['counts']['frames'] for r in a['results'])==108000
assert all(r['tactical_values_delivered_exactly'] and r['counts']['frames']==r['counts']['bank_binding']==r['counts']['heading_speed_cap_binding']==18000 and r['counts']['near']==r['counts']['in_band']==0 for r in a['results'])
assert all(r['identical_requested_goals'] and r['different_preclip_bank'] for r in a['equivalence'])
identities=[spec['guardian'],e['identity']]+[d['identity'] for d in e['descendants']]
audit=[]
for i in identities:
    try:
        process=psutil.Process(i['pid']);same=abs(process.create_time()-i['create'])<.01 and process.cmdline()==i['cmd'] and process.exe().lower()==i['exe'].lower() and process.ppid()==i['parent']
        if same:raise RuntimeError('Original identity still live')
        state='reused_or_identity_mismatch'
    except psutil.NoSuchProcess:state='absent_no_exit_inferred'
    audit.append(dict(identity=i,state=state))
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
verification=dict(verified_offline_goal_projection=True,created_utc=now,analysis_sha256=sha(OUT/'ANALYSIS.json'),actual_parent_exit=0,actual_worker_exit=0,
                  saved_packets_projected=108000,new_FDM_ticks=0,training_started=False,source_unchanged=True,
                  terminal_identity_audit=audit,inner_controller_replayed=False,saved_stub_outputs_not_new_evidence=True,
                  statement='所有保存幀的tactical確實到達離線act；裁切前bank有差異，但6軌跡108000幀均在bank與290節速度上限binding，兩開局內三actor requested goals hash一致。只說明保存軌跡的映射，不是新閉迴路戰力。',
                  deployment_allowed=False)
write(OUT/'VERIFICATION.json',verification)
next_action='新單因素完整開發比較：考慮只將遠距>914.4m的bank目標上限72降為60，以改變持續飽和轉彎的幾何關係；先做隔離來源與安全/近距不變核對，再用2新開局baseline/candidate共4場對固定SAC紅方。此假設未實作、未證明更強；不掃參數、不續訓。'
plan=dict(status='proposed_not_implemented',basis=str(OUT/'VERIFICATION.json'),
          hypothesis='在本批持續72度/290節的閉迴路幾何中，降低單方遠距bank可能改變雙方相位而進入射程；可能變好或變差，必須完整對戰。',
          proposed_single_factor='Only blue StationController requested roll target: outside distance>914.4m, clamp to ±60 instead of ±72 before unchanged RepairController.command; all other goals, safety, G protection, trim and opponents unchanged.',
          baseline='station_zero signed-yaw StationController, not pure repair_guide',opponent='frozen sac5000',
          development_design='2 unused seed openings including opposite sides; baseline/candidate same full initial SHA within each opening; 4 complete games max18000tick,90s/worker,600s whole; independent watchdog and sources/XML/model freeze.',
          seed_status='not_selected_or_claimed',no_run_started=True,
          acceptance='逐開局進入射程/1度命中/完整event與timeout score/kill/death/crash/collision/over9G/共同曝光AGL；任何candidate過9G拒絕，勝負或高度退步需獨立審查，不能平均掩蓋。無改善則否決，不以步數補救。',
          rationale_for_60='Single predeclared doctrine probe using an already represented bank60 opponent setting; not a parameter sweep or known optimum.',
          training_contract='任何控制契約變更均不精確續用critic/optimizer/replay；本項先用規則，不開始訓練。',
          formal_deployment='repair_guide',deployment_allowed=False)
write(OUT/'NEXT_EXPERIMENT.json',plan)
lp=ROOT/'compute_budgets/2026-10-17.json';ledger=read(lp)
for item in ledger['items']:
    if item['id']==OUT.name:item.update(status='completed_verified_offline_projection',actual_parent_exit=0,actual_worker_exit=0,actual_wall_seconds=e['wall_seconds'],original_reservation_retained=True)
write(lp,ledger)
rpath=ROOT/'research_latest.json';r=read(rpath)
r.update(updated_utc=now,next_action=next_action,next_session_plan=str(OUT/'NEXT_EXPERIMENT.json'),active_workload=None,
         current_live_workloads=dict(learners=[],loops=[],evaluations=[],observed_utc=now),
         latest_goal_projection=str(OUT),latest_goal_projection_verification=str(OUT/'VERIFICATION.json'),
         latest_goal_projection_status='completed_verified_offline_goal_projection',daily_compute_reserved_hours=ledger['reserved_hours'],
         current_research_diagnostic=dict(run=str(OUT),status='completed_verified',new_FDM_ticks=0,actual_parent_exit=0,actual_worker_exit=0),
         next_factor_status='proposed_not_implemented',next_factor='far requested bank cap72→60, distance>914.4m only')
write(rpath,r)
pp=ROOT/'pipeline_latest.json';pipe=read(pp);pipe['campaign_latest_20261017'].update(latest_diagnostic=str(OUT/'VERIFICATION.json'),next_research=str(OUT/'NEXT_EXPERIMENT.json'),next_factor_status='proposed_not_implemented');write(pp,pipe)
text='''# 最新進度：找到本批模型戰術無法改變飛行的限制

- 離線完整追蹤六場已保存的108,000幀：戰術值有送進控制器，裁切前的轉彎計算也不同；但每一幀的轉彎目標都被限制在±72度，速度目標都被限制為290節。每個開局三版本的最終目標完全相同。
- 這說明這批軌跡的戰術差異在目標裁切處被抹去；不是只靠零命中猜原因。此診斷沒有重跑FDM、沒有新模型推論或訓練；內層command只用記錄器替代，不把記錄器回傳的舊命令冒充新控制重播。
- 診斷67.532秒完成，worker與父程序實際0、來源SHA固定、原PID/建立時間/命令身分已無；VERIFICATION通過。
- 先前六場完整對戰仍有效：三版本各0勝2負、皆時間到由紅方積分勝；雙方0命中/擊落/墜機/碰撞/過9G，最近距離1166.81/1144.43m，未進入攻擊距離。這不是未知隊伍勝率。
- 下一個待測假設：只降低藍方遠距轉彎目標上限72→60，嘗試改變持續繞圈的幾何關係。會先隔離來源，再用兩個新開局、baseline/candidate共4場完整比較；尚未實作或啟動，不能稱已改善。
- 正式基準repair_guide與兩個凍結模型保留，不盲續訓練、不自動部署。10/17報名提醒已寄，尚無報名完成證據。

最新診斷：diagnostics/sac_goal_projection_20261017_122745_b73993/VERIFICATION.json；下一步：同資料夾NEXT_EXPERIMENT.json。
'''
(ROOT/'latest_result.md').write_text(text,encoding='utf8')
with (ROOT/'REVIEW_LOG.md').open('a',encoding='utf8') as f:
    f.write('\n\n## '+now+' 保存軌跡的戰術目標裁切追蹤\n\n'+text.split('\n',1)[1])
    f.write('\n- 完整6×18000幀用原StationController.act與原bearing history投影；實際_build_blue載入路徑為凍結m4_tactical_v4/m1_station.py，不能事後補成舊worker當時__file__收據。command換記錄器，只捕獲目標，不重播內層控制。每幀setter→act相等、bank前後公式與speed裁切重算相等；near/inband全0。正常側rawbank約-298至-169度；鏡像約152至296度；全被夾至±72。速度裁切前約350至451節，全被限到290。鏡像10k的break門檻9820tick有觸發，仍沒改變目標。\n')
    f.write('- 120秒原harddeadline/JobLock/STOP/source144+23+4/CPU RAM disk/固定來源/唯讀舊packet SHA，新輸出獨立；沒有新seed claim、FDM或模型predict。原來源未改。session28492 chunk0a886f實際parent0，worker0，67.532秒；3個原identity已無，未知退出不補0。120秒預留保留，今日總'+str(ledger['reserved_hours'])+'h。診斷sha '+sha(OUT/'ANALYSIS.json')+'。\n')
    f.write('- 下一factor只是預先寫定假設：遠距bank cap72→60。目的改變飽和幾何，不宣稱更好或參數最佳；不得把降低角度等同安全保證，仍檢查9G/高度/逐開局輸贏，無改善則拒絕。\n')
with (ROOT/'RACE_FOCUS_20261017.md').open('a',encoding='utf8') as f:f.write('\n\n## 10/17 12:30 最新裁切診斷（覆蓋先前根因仍待查）\n\n'+text.split('\n',1)[1])
npath=ROOT/'review_notice.json';notice=read(npath);key=OUT.name+'|completed_verified|'+sha(OUT/'VERIFICATION.json')
notice.setdefault('events',{})[key]=dict(status='completed_verified_offline_goal_projection',notified_utc=now,report=str(OUT/'VERIFICATION.json'),report_sha256=sha(OUT/'VERIFICATION.json'),channel='ai heartbeat final',message='108000保存幀確認戰術到act但bank/速度全程裁切；下一項單因素遠距bank60假設，尚無改善對戰證據。');write(npath,notice)
print(json.dumps(dict(verified_offline_goal_projection=True,original_identities=len(audit),reserved_hours=ledger['reserved_hours'],next_experiment=str(OUT/'NEXT_EXPERIMENT.json')),ensure_ascii=False))
