"""Preserve newly terminal shared outputs; do not load/evaluate/promote models."""
import datetime, hashlib, json, pathlib, shutil, zipfile
import psutil
ROOT=pathlib.Path(r'E:\ai_pilot\campaign_2026')
SOURCE=ROOT/'experiments/m4_tactical'
DEST=ROOT/'quarantine/m4_shared_outputs_20261015'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
identities=[];learners=[]
for p in psutil.process_iter(['name']):
    try:
        if 'python' not in (p.info['name'] or '').lower():continue
        cmd=p.cmdline()
        if not any('campaign_2026/win/' in a.replace('\\','/').lower() for a in cmd):continue
        row={'pid':p.pid,'create_time':p.create_time(),'cmdline':cmd,'exe':p.exe(),'parent_pid':p.ppid()}
        if any(a.replace('\\','/').endswith('/m4_tactical_rl.py') for a in cmd):learners.append(row)
        if any(a.replace('\\','/').endswith('/win_loop.py') for a in cmd):identities.append(row)
    except psutil.NoSuchProcess:continue
    except psutil.AccessDenied:raise RuntimeError('Cannot verify current writer identity')
assert not learners,'Learners still active: no terminal snapshot'
queue=read(ROOT/'win/queue.json')
assert queue['steps']==[], 'Queue changed; no assumption of idle'
DEST.mkdir(parents=True,exist_ok=True)
entries=[]
for src in sorted(SOURCE.glob('*')):
    if not src.is_file() or src.suffix not in ('.zip','.json'):continue
    before=sha(src);dst=DEST/src.name
    if dst.exists():assert sha(dst)==before,'Existing snapshot differs; preserve both with a new explicit path'
    else:shutil.copy2(src,dst)
    assert sha(src)==before==sha(dst),'Concurrent output mutation'
    item={'name':src.name,'source':str(src),'snapshot':str(dst),'sha256':before,'bytes':dst.stat().st_size}
    if src.suffix=='.zip':
        with zipfile.ZipFile(dst) as z:
            assert z.testzip() is None
            data=json.loads(z.read('data'))
            item.update(zip_crc_valid=True,num_timesteps=data.get('num_timesteps'),total_timesteps=data.get('_total_timesteps'),
                        sb3_metadata_read_without_unpickle=True)
    entries.append(item)
report={'observed_utc':now,'format':'shared_m4_terminal_preservation_v1','snapshot':str(DEST),
 'learners_currently_live':learners,'idle_loop_identities':identities,'queue_empty_observed':True,'files':entries,
 'current_source_sha256':{str(p):sha(p) for p in [ROOT/'win/m4_tactical_rl.py',ROOT/'win/win_loop.py']},
 'source_sha_scope':'Current bytes only; no source freeze at each learner launch was recorded.',
 'provenance':'Three concurrent learners shared every checkpoint/progress/final path. Last writer per artifact cannot be identified.',
 'model_reload_verified':False,'exact_resume_verified':False,'combat_evaluation_completed':False,
 'deployment_allowed':False,'new_fdm_ticks':0,'processes_stopped':[]}
(DEST/'PRESERVATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
pointer=read(ROOT/'research_latest.json')
pointer.update(updated_utc=now,current_live_workloads={'loops':identities,'learners':[]},
 m4_shared_outputs_preservation=str(DEST/'PRESERVATION.json'),
 m4_shared_outputs_status='learners_terminal_snapshot_preserved_model_provenance_unverified',
 new_run_permitted=False,new_run_block_reason='Cleanup/singleton permission pending. Three idle loops persist; no training/evaluation/Host launched while question pending.')
pointer['active_workload']['cases_saved']=24
(ROOT/'research_latest.json').write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
observation={'observed_utc':now,'idle_loop_count':len(identities),'live_learner_count':0,
 'old_expected_learner_pids':[644,2996,11592],'absent_does_not_establish_exit_code':True,
 'new_outputs_saved':len(entries),'preservation':str(DEST/'PRESERVATION.json'),
 'usage_observation':{'remaining_percent':28,'observed_utc':'2026-10-14T22:32:07Z','five_hour_resets_epoch':1792019566,'weekly_resets_epoch':1792475858}}
(ROOT/'diagnostics/monitor_20261015_0632.json').write_text(json.dumps(observation,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'snapshot':str(DEST),'files_saved':len(entries),'zip_crc_valid':sum(e.get('zip_crc_valid',False) for e in entries),
                  'idle_loops':len(identities),'live_learners':0,'deployment_allowed':False},ensure_ascii=False))
