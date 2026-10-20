from pathlib import Path
import json,datetime,hashlib,os,psutil
ROOT=Path(r'E:\ai_pilot\campaign_2026');NEW=ROOT/'experiments/opponent_pool/far_speed_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
busy=[]
for p in psutil.process_iter(['name']):
    if p.pid==os.getpid():continue
    name=(p.info['name'] or '').lower()
    if name not in ('python.exe','pythonw.exe','jsb_host_gui_publish.exe'):continue
    try:cmd=p.cmdline();exe=p.exe();created=p.create_time();parent=p.ppid()
    except psutil.NoSuchProcess:continue
    if name=='jsb_host_gui_publish.exe' or any('e:/ai_pilot/' in x.replace('\\','/').lower() and x.lower().endswith('.py') for x in cmd):busy.append(dict(pid=p.pid,create=created,cmd=cmd,exe=exe,parent=parent))
now=datetime.datetime.now(datetime.timezone.utc).isoformat();reg=read(ROOT/'seed_registry.json');seen={int(s) for s in reg.get('observed_seeds',{})}
for trial in reg.get('trials',{}).values():seen.update(trial['seeds'])
seen.update(reg.get('reserved_holdout_seeds',[]))
planned=[2026310700,2026310701];collisions=sorted(set(planned)&seen)
observation=dict(status='waiting_for_resource_before_precheck',observed_utc=now,quota_observation=read(NEW/'USAGE_OBSERVATION.json'),latest_resource_observation=dict(observed_utc='2026-10-17T16:39:25.549432+00:00',available_ram_gib=1.3578300476074219,cpu_percent=77.9,free_disk_gib=180.3450813293457),earlier_resource_observation=dict(observed_utc='2026-10-17T16:37:59.069637+00:00',available_ram_gib=1.4339637756347656,cpu_percent=68.1,GPU_percent=73,GPU_memory_used_MiB=6128,GPU_total_MiB=12288),required_ram_gib=2.,required_free_disk_gib=10.,required_cpu_percent_below=95,own_GPU_used=False,other_campaign_workloads=busy,actual_precheck_tool_exit=1,actual_precheck_tool_chunk='ec52dc',exit_reason='base.resources failed before unique out folder, budget reserve, child creation or seed claim',new_FDM_ticks=0,new_model_inference=False,full_static_and_saved_packet_precheck_completed=False,planned_seeds=planned,planned_seed_collisions=collisions,seeds_claimed=False,new_compute_reservation_made=False,needs_user_action=False,no_unrelated_processes_stopped=True,no_resource_threshold_lowered=True)
write(NEW/'PREFLIGHT_RESOURCE_WAIT_20261018.json',observation)
prep=read(NEW/'PREPARATION.json');prep.update(resource_wait_report=str(NEW/'PREFLIGHT_RESOURCE_WAIT_20261018.json'),hypothesis_plan=str(ROOT/'diagnostics/latch_window_v1_20261017_213638_941961/NEXT_HYPOTHESIS.json'),planned_seeds_not_claimed=planned,seed_collisions_at_observation=collisions,full_precheck_launcher=str(ROOT/'diagnostics/far_speed_precheck_guardian_v1.py'),full_precheck_seconds=120,full_precheck_parent_exit_not_observed_as_success=True,FDM_launch_allowed=False,proposed_worker_seconds=90,proposed_whole_seconds=600,proposed_verifier_seconds=120,source_sha256={str(p):sha(p) for p in NEW.glob('*.py')},next_action='Wait for unchanged resource gate RAM>=2GiB/CPU<95/disk>=10GiB and singleton/STOP. Then run full guarded precheck, observe real parent0 and worker0, inspect VERIFICATION. Only then source-freeze and battle --check-only/--launch; no bypass or new-seed claim before launcher.',original_sources_unchanged=True,formal_deployment='repair_guide')
write(NEW/'PREPARATION.json',prep)
j=read(ROOT/'research_latest.json');j.update(updated_utc=now,pending_research_preparation=str(NEW/'PREPARATION.json'),next_session_plan=str(NEW/'PREPARATION.json'),next_factor_status='isolated_implementation_static_only_waiting_resource_full_precheck',next_action='far_speed_v1已隔離實作，只有5檔語法與140純函式邊界測試；RAM1.358GiB低於2GiB，full cold-import/saved-packet precheck在預留/worker/seed之前退出1。資源自然恢復後，先跑diagnostics/far_speed_precheck_guardian_v1.py並觀察父/worker真0及VERIFICATION；通過才新來源凍結/check-only/4場launcher。不降門檻、不停止無關程式、不跳過前測。',current_process_alert=dict(status='temporary_resource_wait',requires_user_action=False,report=str(NEW/'PREFLIGHT_RESOURCE_WAIT_20261018.json'),available_ram_gib=1.3578300476074219,required_ram_gib=2.),active_workload=None,current_live_workloads=dict(learners=[],loops=[],evaluations=busy,observed_utc=now),latest_usage_observation=read(NEW/'USAGE_OBSERVATION.json'));write(ROOT/'research_latest.json',j)
p=read(ROOT/'pipeline_latest.json');p['updated_utc']=now;p['race_focus_update'].update(next_research=str(NEW/'PREPARATION.json'),next_factor_status='isolated_implementation_static_only_waiting_resource_full_precheck');write(ROOT/'pipeline_latest.json',p)
text=f'''## {now} 遠距速度上限新分支準備，等待記憶體

- 已隔離建立far_speed_v1：僅在距離>914.4m、|heading error|>45時移除290節速度頂限；原未latch的72度轉向、俯仰/rudder、260–450節總界限及內層安全不改。原來源及已否決分支未改。
- 已完成5檔純語法編譯與140個純函式邊界案例（工具eaee28真0）。完整cold-import、真StationController保存packet重播尚未通過；這些純靜態結果不是新FDM/戰力證據。
- full precheck工具ec52dc真1：資源閘門在建立run/預留/child/seedclaim之前拒絕。16:37:59UTC可用RAM1.434GiB、16:39:25UTC1.358GiB，低於既有2GiB門檻；後次CPU77.9%、disk180.345GiB。GPU使用為其他活動，本工作CPU-only，不停止無關程序或降低門檻。
- 無新FDM、模型推論、訓練、seed claim或研究預留；10/17的1.4h歷史帳目保留。規劃seed2026310700/1目前registry碰撞{collisions}，尚未claimed，下一次仍須重查。
- 下一輪：資源恢復後先用120秒獨立guardian執行完整前測，父/worker真0及VERIFICATION通過才凍結新來源、4場新配對，90秒/worker全600秒含120秒核對。準備檔的FDM_launch_allowed=false不能當許可；不得跳過前測。原正式repair_guide不變，暫無需本人操作。

入口：{NEW/'PREPARATION.json'}；資源收據：{NEW/'PREFLIGHT_RESOURCE_WAIT_20261018.json'}。
'''
for name in ('REVIEW_LOG.md','RACE_FOCUS_20261017.md'):
    with (ROOT/name).open('a',encoding='utf8') as f:f.write('\n\n'+text)
(ROOT/'latest_result.md').write_text('# 最新研究準備（10/18）\n\n'+text+'\n上一個完整latch四場仍否決；詳research_latest.comparison與REVIEW_LOG。\n',encoding='utf8')
print(json.dumps(dict(status=prep['status'],RAM_wait=True,other_campaign_workloads=busy,seed_collisions=collisions,new_FDM_ticks=0,no_user_action=True),ensure_ascii=False))
