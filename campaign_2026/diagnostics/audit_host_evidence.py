"""Mandatory terminal-log guard for saved Host evidence; never launches Host."""
from pathlib import Path
import argparse,csv,hashlib,json,math,re
from p2_terminal_evidence import verify as verify_p2_terminal

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def valid_sha256(value):
    return isinstance(value,str) and re.fullmatch(r'[0-9a-fA-F]{64}',value) is not None

def fixed_metadata_checks(session):
    sources=session.get('source_sha256')
    return {
      'source_hashes_valid':isinstance(sources,dict) and bool(sources) and all(isinstance(k,str) and bool(k.strip()) and valid_sha256(v) for k,v in sources.items()),
      'player_hash_valid':valid_sha256(session.get('player_sha256')),
      'host_exe_hash_valid':valid_sha256(session.get('host_exe_sha256')),
      'host_setting_hash_valid':valid_sha256(session.get('host_setting_sha256')),
      'actual_validation_exit_zero':type(session.get('validation_exit_code')) is int and session['validation_exit_code']==0}

def capture_receipt_checks(folder,session):
    folder=Path(folder).resolve()
    result={'setting_snapshot_matches':False,'player_snapshot_matches':False,'source_snapshots_match':False,
      'host_exe_snapshot_matches':False,'prelaunch_receipt_matches':False,'collector_receipt_matches':False}
    def local(value):
        path=Path(value).resolve()
        if not path.is_relative_to(folder):raise ValueError('Snapshot outside round folder')
        return path
    try:
        result['setting_snapshot_matches']=sha(folder/'Setting.txt')==session['host_setting_sha256']
        result['player_snapshot_matches']=sha(folder/'player.py')==session['player_sha256']
        result['source_snapshots_match']=bool(session['source_sha256']) and set(session['source_snapshots'])==set(session['source_sha256']) and all(sha(local(session['source_snapshots'][k]))==v for k,v in session['source_sha256'].items())
        result['host_exe_snapshot_matches']=sha(local(session['host_exe_snapshot']))==session['host_exe_sha256']
        pre=read(local(session['host_launch_record']))
        result['prelaunch_receipt_matches']=(pre.get('evidence_capture_version')==2 and pre.get('setting_capture_phase')=='before_host_Popen'
          and pre.get('setting_unchanged_immediately_after_launch') is True and pre.get('exe_unchanged_immediately_after_launch') is True
          and pre.get('host_setting_sha256')==session['host_setting_sha256'] and pre.get('host_exe_sha256')==session['host_exe_sha256']
          and datetime_epoch(pre['captured_utc'])<=session['start_clicked_epoch'])
        exit_record=read(local(session['validation_exit_receipt']));inputs=read(folder/'collector_input_session.json')
        keys=['source_sha256','player_sha256','host_exe_sha256','host_setting_sha256','start_clicked_epoch',
              'terminal_capture_version','p2_logs_before_launch','p2_terminal_receipt','host_launch_identity']
        result['collector_receipt_matches']=(session.get('evidence_capture_version')==2 and session.get('validation_capture_sources_unchanged') is True
          and type(exit_record.get('actual_exit_code')) is int and exit_record['actual_exit_code']==session.get('validation_exit_code')==0
          and type(exit_record.get('pid')) is int and type(exit_record.get('create_time')) in (int,float)
          and Path(exit_record['folder']).resolve()==folder and sha(folder/'collector_snapshot.py')==exit_record['collector_sha256']
          and sha(folder/'collector_input_session.json')==exit_record['input_session_sha256'] and all(inputs.get(k)==session.get(k) for k in keys)
          and isinstance(exit_record.get('command'),list) and Path(exit_record['command'][-1]).name=='collect_host_test.py'
          and session['start_clicked_epoch']<=datetime_epoch(exit_record['started_utc'])<=datetime_epoch(exit_record['exited_utc']))
    except (KeyError,TypeError,ValueError,IndexError,OSError):pass
    return result

def datetime_epoch(value):
    from datetime import datetime
    result=datetime.fromisoformat(value)
    if result.tzinfo is None:raise ValueError('Timestamp without timezone')
    return result.timestamp()

def completion_checks(rows,stdout):
    if len(rows)<2:return {'enough_rows':False}
    times=[float(r['time']) for r in rows];last=rows[-1]
    finite=all(math.isfinite(float(v)) for row in rows for v in row.values())
    full=times[-1]>=299.9 and len(rows)>=17900
    early=float(last['system_Final_whoiswinner'])!=0 and min(float(last['player1_Score_RemainingHP']),float(last['player2_Score_RemainingHP']))<=0
    terminal_lines=[line for line in stdout.splitlines() if '[GAME OVER]' in line]
    roles=re.findall(r'Player\s+([12])',terminal_lines[-1]) if terminal_lines else []
    raw=float(last['system_Final_whoiswinner'])
    # Preserve unrecognized raw codes; only detect explicit P1/P2 contradictions.
    consistent=not (raw in (1.,2.) and roles and int(raw)!=int(roles[-1]))
    return {'finite_csv':finite,'strictly_increasing_time':all(b>a for a,b in zip(times,times[1:])),
      'full_round_or_early_adjudication':full or early,'host_game_over_logged':bool(terminal_lines),'csv_terminal_log_consistent':consistent}

def audit(report_path):
    report_path=Path(report_path).resolve();folder=report_path.parent;r=read(report_path);s=read(folder/'session.json')
    csv_path=folder/Path(r['source_csv']).name
    with csv_path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    stdout=folder/'host_stdout.log';stderr=folder/'host_stderr.log'
    text=stdout.read_bytes().decode('cp950',errors='replace');checks=completion_checks(rows,text)
    checks.update(csv_sha_matches=sha(csv_path)==r['csv_sha256'],reported_rows_match=len(rows)==r['rows'],reported_duration_matches=abs(float(rows[-1]['time'])-r['sim_seconds'])<1e-6,
      observed_player1_ready=any(float(x['player1_state'])==2 for x in rows),
      observed_player1_moved=any(abs(float(x['player1_lat_deg'])-float(rows[0]['player1_lat_deg']))>1e-7 or abs(float(x['player1_lon_deg'])-float(rows[0]['player1_lon_deg']))>1e-7 for x in rows),
      host_stderr_exists=stderr.is_file())
    acmi=[]
    for x in r.get('acmi',[]):
        path=Path(x['path']).resolve()
        valid=path.is_relative_to(folder) and path.is_file() and sha(path)==x['sha256']
        if valid:
            lines=path.read_text(encoding='utf-8-sig').splitlines();times=[float(v[1:]) for v in lines if v.startswith('#')]
            valid=bool(times) and all(math.isfinite(t) for t in times) and all(b>=a for a,b in zip(times,times[1:])) and abs(times[-1]-float(rows[-1]['time']))<=.1
        acmi.append(valid)
    checks['acmi_hash_and_terminal_time']=bool(acmi) and all(acmi)
    # GAME OVER remains a factual observation. A new capture can instead prove
    # terminal state using a fresh owned P2 STOPPED log bound to the same CSV.
    game_over=checks.pop('host_game_over_logged')
    p2_checks=verify_p2_terminal(folder,s,rows,sha(csv_path))
    p2_verified=all(p2_checks.values())
    checks['host_terminal_evidence_verified']=game_over or p2_verified
    observed_exit=s.get('validation_exit_code')
    metadata_checks=fixed_metadata_checks(s)
    receipt_checks=capture_receipt_checks(folder,s)
    eligible=all(checks.values()) and all(metadata_checks.values()) and all(receipt_checks.values())
    identity={k:s.get(k) for k in ['player','host_processes','start_clicked_epoch']}
    key=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    profile={k:s.get(k) for k in ['controller','model','source_sha256','player_sha256','host_exe_sha256','host_setting_sha256']}
    signature=hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'report':str(report_path),'report_sha256':sha(report_path),'round_identity':key,'csv_sha256':sha(csv_path),'stdout_sha256':sha(stdout),
      'checks':checks,'saved_host_artifact_valid':all(checks.values()),'fixed_profile_hash':signature,'actual_validation_exit_code':observed_exit,
      'host_setting_hash_recorded':bool(s.get('host_setting_sha256')),'fixed_metadata_checks':metadata_checks,'capture_receipt_checks':receipt_checks,
      'eligible_for_six_round_fixed_source_gate':eligible,
      'terminal_evidence':{'host_game_over_logged':game_over,'fresh_owned_p2_stop':p2_verified,
                           'p2_checks':p2_checks},
      'host_winner_raw':rows[-1]['system_Final_whoiswinner'],'scope':'Historical evidence audit only; no new Host, package approval, or competition certification'}

def aggregate(results):
    # A renamed report or altered session cannot establish another raw Host round.
    unique={};seen_identity=set();seen_csv=set()
    for x in results:
        if x['round_identity'] in seen_identity or x['csv_sha256'] in seen_csv:continue
        seen_identity.add(x['round_identity']);seen_csv.add(x['csv_sha256'])
        unique[x['round_identity']]=x
    valid=[x for x in unique.values() if x['saved_host_artifact_valid']]
    eligible=[x for x in unique.values() if x['eligible_for_six_round_fixed_source_gate']]
    profiles={x['fixed_profile_hash'] for x in eligible}
    return {'requested_reports':len(results),'unique_saved_rounds':len(unique),'duplicates_excluded':len(results)-len(unique),
      'valid_saved_host_artifacts':len(valid),'eligible_fixed_source_rounds':len(eligible),
      'six_round_fixed_source_evidence_complete':len(eligible)>=6 and len(profiles)==1,'new_host_rounds':0,'competition_certification':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,action='append',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    cache={};results=[]
    for path in a.report:
        key=str(path.resolve())
        if key not in cache:cache[key]=audit(path)
        results.append(cache[key])
    output={'audits':results,'summary':aggregate(results)}
    a.out.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(output['summary'],ensure_ascii=False))
