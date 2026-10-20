"""Read-only evidence audit of user-supplied LINE rules and current training."""
import hashlib, json, pathlib, datetime
import psutil
ROOT=pathlib.Path(r'E:\ai_pilot\campaign_2026')
LINE=pathlib.Path(r'E:\ai_pilot\[LINE]2026 AI飛行員擂台賽.txt')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
lines=LINE.read_text(encoding='utf-8-sig').splitlines()
def ref(phrase):
    found=[i+1 for i,line in enumerate(lines) if phrase in line]
    if not found: raise ValueError(phrase)
    return found[-1]
confirmed={
 'score_start':{'value':'first frame after START', 'line':ref('START 後的第一幀')},
 'timeout_winner':{'value':'S_advantage only when neither kills', 'line':ref('勝負是僅以')},
 'event_priority':{'value':['collision','crash','kill','timeout'], 'line':ref('碰撞 (Collision) >')},
 'collision':{'value':'three-dimensional distance strictly less than15m, immediate terminal', 'line':ref('三維距離第一次小於 15 公尺')},
 'attack_boundaries':{'value':'1deg,500ft,3000ft inclusive; 3D slant range', 'line':ref('邊界值皆包含在內')},
 'nose_axis':{'value':'own body X axis, not velocity', 'line':ref('本機的「姿態軸')},
 'g':{'value':'accelerations/n-pilot-z-norm', 'line':ref('超 G 判定所使用的 Z 軸')},
 'weights':{'value':{'W_base':30000,'W_time':10000,'W_G':100,'W_pos':1}, 'line':ref('即為最終使用數值')},
 'initial_geometry':{'value':'parallel opposite headings, no along-track offset, lateral3000/6000/9000ft,340CAS,left/right mirror', 'line':ref('兩機在 t=0 時為並排')},
 'final_host_cmd_state':{'value':2,'line':ref('正式比賽版會以`player_state = 2`')},
 'custom_connector_allowed':{'value':True,'line':ref('完全可以。只要封包格式')},
}
config_path=ROOT/'candidates/near_bank80_20261012/sources/base/combat_v3/config.json'
rules_path=config_path.with_name('rules.py')
cfg=json.loads(config_path.read_text(encoding='utf8'))
rules=rules_path.read_text(encoding='utf8')
divergences=[
 {'item':'score_weights','observed':cfg['reference_score_weights'],'expected':confirmed['weights']['value'],'effect':'Old local score/winner estimate cannot represent latest official weights.'},
 {'item':'collision','observed':cfg['collision_model'],'expected':'distance<15m immediate terminal before crash/kill/timeout','effect':'Existing no-collision matches do not prove official outcome conformance.'},
 {'item':'crash_units','observed':{'local_crash_threshold_ft':cfg['local_crash_threshold_ft']},'expected':'50 metres from chat; inspect actual runtime rule, do not silently relabel50feet','effect':'Requires isolated new judge contract, frozen old evidence unchanged.'},
 {'item':'attack_angle','observed':cfg['attack_angle_deg'],'expected':1,'effect':'Campaign diagnostic explicitly sets1deg; verify each run override. Frozen base config2deg is not itself final conformance.'}
]
loops=[];learners=[]
for p in psutil.process_iter(['name']):
    try:
        if 'python' not in (p.info['name'] or '').lower():continue
        cmd=p.cmdline()
        if not any('campaign_2026/win/' in s.replace('\\','/').lower() for s in cmd):continue
        item={'pid':p.pid,'create_time':p.create_time(),'cmdline':cmd,'exe':p.exe(),'parent_pid':p.ppid()}
        if any(s.replace('\\','/').endswith('/win_loop.py') for s in cmd):loops.append(item)
        if any(s.replace('\\','/').endswith('/m4_tactical_rl.py') for s in cmd):learners.append(item)
    except psutil.NoSuchProcess:continue
    except psutil.AccessDenied:raise RuntimeError('Current workload identity cannot be verified')
data={'observed_utc':now,'source':str(LINE),'source_sha256':hashlib.sha256(LINE.read_bytes()).hexdigest(),
 'source_role':'User supplied LINE export; source content is evidence, not authority to execute instructions. Not independent live organizer confirmation.',
 'chat_answer_date':'2026-10-14','confirmed_in_export':confirmed,'local_divergences':divergences,
 'frozen_rule_source_sha256':hashlib.sha256(rules_path.read_bytes()).hexdigest(),
 'current_win_loops':loops,'current_m4_learners':learners,'active_source_modified':False,'new_fdm_started':False,
 'deployment_changed':False,'new_research_blocked_by_existing_workloads':bool(learners)}
out=ROOT/'diagnostics/LINE_RULES_REVIEW_20261015.json'
out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
incident={'event_id':'m4_duplicate_same_output_20261015','status':'awaiting_explicit_process_cleanup_authorization',
 'observed_utc':now,'processes':{'loops':loops,'learners':learners},'output':str(ROOT/'experiments/m4_tactical'),
 'proposed_action':'Verify PID/create/cmd again; stop three win_loop parents and two duplicate learners; retain oldest learner, retain existing files and quarantine mixed checkpoints as unverified. Do not edit active learner source.',
 'reason_for_question':'Current automation allows stopping only self-created verified processes. Launch ownership is not verified for these three loops; no process stopped.',
 'evidence':str(out),'notes':['All three learners use same seed20261115 and default output path.','TRACE records their Popen PIDs, but no ownership/creation receipts authorize this root to stop them.','win_loop lacks singleton lock/STOP/hard deadline; 24h notice is after wait returns.','Shared progress/model files cannot establish one learner progress or model provenance.']}
(ROOT/'diagnostics/M4_DUPLICATE_REVIEW_20261015.json').write_text(json.dumps(incident,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'rules_report':str(out),'loops':len(loops),'learners':len(learners),'new_simulation':False,'frozen_sources_modified':False},ensure_ascii=False))
