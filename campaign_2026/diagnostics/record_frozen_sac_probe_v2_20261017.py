from pathlib import Path
import json,hashlib,datetime
ROOT=Path(r'E:\ai_pilot\campaign_2026')
RUN=ROOT/'diagnostics/frozen_sac_cpu_probe_v2_20261017_003552_e2ae02'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=read(RUN/'EXIT_RECEIPT.json');result=read(RUN/'RESULT.json');contract=read(RUN/'CONTRACT.json')
assert receipt['actual_worker_exit']==0 and receipt['worker_identity_absent'] and receipt['result_sha256']==sha(RUN/'RESULT.json')
for path,digest in contract['source_sha256'].items():assert sha(Path(path))==digest,path
assert set(result['models'])=={'sac5000','transfer10000'}
for name,model in result['models'].items():
    assert all(read(RUN/('RNG_'+name+'.json'))['equal_by_stream'].values())
    assert model['real_controller_act_calls_before_reset']==100 and model['real_actor_predictions_before_reset']==5
    assert model['duplicate_cache_verified'] and model['reset_command_exact_reproduction'] and model['reset_fresh_controller_actor_verified']
review={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verified_real_cpu_factories':True,'actual_watchdog_shell_exit':0,'watchdog_shell_exit_tool':'fe5891','actual_worker_exit':0,'source_model_and_input_hashes_verified':True,'result_sha256':sha(RUN/'RESULT.json'),'new_FDM_ticks':0,'FDM_timing_verified':False,'combat_strength_verified':False,'deployment_changed':False,'decision':'CPU production factories pass; next short independently guarded real FDM timing diagnostic only','prior_failure_preserved':'diagnostics/frozen_sac_cpu_probe_20261016_231331_e45d41','limitations':['Repeated saved legal packet, not physical response','No first-frame simulator/judge timing proof','Latency values include controller and selected policy calls, not real network p99','Original v1 failure fingerprints were aggregate; moved cold import passes new per-stream check but root cause not isolated with exact same fingerprint implementation'],'preflight_failure':{'actual_shell_exit':1,'tool':'dbcf52','reason':'v2 staging initially omitted manifest-tracked test_adapter.py; no worker, budget reservation or FDM. Copied exact parent file then one new reserved CPU probe.'}}
(RUN/'VERIFICATION.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf8')
branch=ROOT/'experiments/opponent_pool/frozen_sac_opponent_v2'
prep=read(branch/'PREPARATION.json');prep.update(actual_CPU_probe_pending=False,verified_real_cpu_factories=True,probe_run=str(RUN),verification_sha256=sha(RUN/'VERIFICATION.json'),FDM_timing_verified=False,learned_selfplay_verified=False,preflight_failure=review['preflight_failure']);(branch/'PREPARATION.json').write_text(json.dumps(prep,ensure_ascii=False,indent=2),encoding='utf8')
p=ROOT/'research_latest.json';pointer=read(p);pointer['frozen_sac_cpu_probe']={'run':str(RUN),'status':'verified_real_cpu_factories_not_FDM','actual_worker_exit':0,'actual_watchdog_shell_exit':0,'verification':str(RUN/'VERIFICATION.json'),'branch':str(branch),'next_action':review['decision'],'new_FDM_ticks':0};pointer['next_action']='frozen_sac_opponent_v2 real CPU factories passed. Next one independently guarded short FDM timing/packet test with new seed and contract; preserve formal repair_guide and both model snapshots. Saved regressions reviewed; no blind training.';p.write_text(json.dumps(pointer,ensure_ascii=False,indent=2),encoding='utf8')
with (ROOT/'REVIEW_LOG.md').open('a',encoding='utf8') as f:
    f.write('\n\n## '+review['created_utc']+' 凍結SAC紅方真CPU工廠通過\n\n隔離v2唯一production差異：stable_baselines3首次import移入Python/NumPy/Torch RNG還原區域；原v1來源不改。新run '+RUN.name+'，120秒預留、實際31.480秒，watchdog shell/worker真0、worker精確身份已無，來源模型/輸入/結果SHA核對。兩個真SAC模型各100次StationController.act/5次predict，加reset新物件與首命令精確重現、duplicate不變、三種RNG指紋還原皆通過。這是合成時鐘重複合法packet的CPU接口，不是FDM/聯賽/勝率，原失敗保留；聚合fingerprint與新逐stream方法不同，不過度宣稱已確定唯一根因。首個v2前置缺test_adapter.py在worker/預留前真1，補回原SHA後單次新CPU探測通過。10/17預留120秒不退款。下一步只做獨立硬限短FDM首幀/step時序/雙方私人狀態驗證，正式仍repair_guide。\n')
with (ROOT/'latest_result.md').open('a',encoding='utf8') as f:
    f.write('\n\n## 10/17 凍結對手CPU接口進度\n\n兩個真SAC模型及各自控制器的載入、重設、重複封包快取和亂數隔離已通過；worker/watchdog真0。尚未連入飛行物理模擬，不能稱已完成learned self-play。下一步短FDM時序驗證；正式版本未變。\n')
print(json.dumps(review,ensure_ascii=False))
