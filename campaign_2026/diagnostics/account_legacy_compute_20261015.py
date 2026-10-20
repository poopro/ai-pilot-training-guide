"""Conservatively record reported legacy wall time; no simulation or refunds."""
import datetime, hashlib, json, pathlib
ROOT=pathlib.Path(r'E:\ai_pilot\campaign_2026')
path=ROOT/'compute_budgets/2026-10-15.json'
zone=datetime.timezone(datetime.timedelta(hours=8))
day=datetime.date(2026,10,15)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
ledger=read(path) if path.exists() else {'date_taipei':str(day),'daily_limit_hours':6.,'reserved_hours':0.,'items':[]}
assert abs(sum(i['hours'] for i in ledger['items'])-ledger['reserved_hours'])<1e-7
observed=[]
for line in (ROOT/'win/TRACE.jsonl').read_text(encoding='utf8').splitlines():
    if not line.strip():continue
    row=json.loads(line)
    if row.get('kind')!='step_end' or 'wall_hours' not in row:continue
    end=datetime.datetime.fromisoformat(row['utc'])
    start=end-datetime.timedelta(hours=float(row['wall_hours']))
    lo=datetime.datetime.combine(day,datetime.time.min,zone)
    hi=lo+datetime.timedelta(days=1)
    hours=max(0,(min(end,hi)-max(start,lo)).total_seconds()/3600)
    if not hours:continue
    token='legacy_trace_'+hashlib.sha256(line.encode()).hexdigest()[:20]
    observed.append({'id':token,'job':row['id'],'reported_wall_hours':row['wall_hours'],'charged_day_hours':hours})
    if any(i['id']==token for i in ledger['items']):continue
    ledger['items'].append({'id':token,'hours':hours,'status':'reported_terminal_legacy_provenance_unverified',
        'kind':'legacy_training_or_evaluation','job_id':row['id'],'reported_exit_code':row['exit_code'],
        'reported_end_utc':row['utc'],'reported_wall_hours':row['wall_hours'],'reported_log':row.get('log'),
        'source':'win/TRACE.jsonl','pid_specific_exit_verified':False,
        'budget_note':'Conservatively charged from rounded legacy wall-time receipt; concurrent copies all count. Not model provenance or combat qualification.'})
ledger.update(reserved_hours=sum(i['hours'] for i in ledger['items']),policy='warning_only_no_refund_single_run_hard_deadline_required',
 updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),daily_warning=sum(i['hours'] for i in ledger['items'])>6)
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
alert_path=ROOT/'diagnostics/M4_DUPLICATE_REVIEW_20261015.json'
alert=read(alert_path)
alert.update(latest_observation_utc=ledger['updated_utc'],latest_phase='zero_live_learners_three_idle_loops_permission_pending',
 current_preservation=str(ROOT/'quarantine/m4_shared_outputs_20261015/PRESERVATION.json'),
 proposed_action='After human confirmation, revalidate and stop the three remaining idle win_loop identities. Prior learner identities are absent; no learner is stopped or restarted. Preserve shared outputs as provenance-unverified and prepare isolated singleton orchestration.',
 reported_daily_compute_hours=ledger['reserved_hours'])
alert_path.write_text(json.dumps(alert,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
pointer_path=ROOT/'research_latest.json';pointer=read(pointer_path)
pointer.update(daily_compute_budget_date=str(day),daily_compute_reserved_hours=ledger['reserved_hours'],daily_compute_warning=ledger['daily_warning'])
pointer_path.write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
log=ROOT/'REVIEW_LOG.md';text=log.read_text(encoding='utf-8-sig');marker='## 2026-10-15 06:32：共享訓練終態與隔離保存'
if marker not in text:
    with log.open('a',encoding='utf8') as f:
        f.write('\n'+marker+'\n\n- CIM/psutil核對：原三個m4 learner已不存在，三個原win_loop PID/create/cmd仍活且queue=[]。沒有自行停止/重啟；learner消失本身不能證明退出0。TRACE有三筆completed/exit0但step_id共享、end不含PID，不升格成逐PID完整退出收據。\n- 已隔離保存9個ZIP checkpoint及progress，共10份；來源/副本SHA一致且9ZIP CRC合法。只讀SB3 JSON metadata，未unpickle/reload/evaluate；各檔最後writer不明，不能稱精確續訓、成功戰鬥或部署候選。\n- legacy日誌計時已按台灣日回補，並行副本各計入、不退款；本日累計 '+str(ledger['reserved_hours'])+'h，超6h僅警告。現有整理確認仍待使用者回答，當前只需整理三個idle loop，沒有活learner可保留或停止。不重寄同一Gmail通知。\n')
latest=ROOT/'latest_result.md';text=latest.read_text(encoding='utf-8-sig')
text=text.replace('目前三份相同m4訓練同時寫experiments/m4_tactical，shared progress/模型來源暫不verified。已詢問是否整理成一份繼續並寄Gmail；未停止未核對所有權的程序，未啟新研究。',
 '原三份相同m4訓練已退出，三個win_loop仍活但queue空。共享存檔已隔離：9個ZIP與progress來源/副本SHA一致、ZIP CRC合法，最後writer及戰鬥效果未verified；目前只待整理三個idle loop的確認，沒有新learner/Host/評估。')
if '日誌回補約7.6456' not in text:text+='\n- 10/15 legacy運算日誌回補約7.6456h，並行副本各算、超6h警告；來源日誌時間為四位小數，非重新量測。\n'
latest.write_text(text,encoding='utf8')
print(json.dumps({'reported_steps_charged':len(observed),'reserved_hours':ledger['reserved_hours'],'daily_warning':ledger['daily_warning'],'new_compute_started':False},ensure_ascii=False))
