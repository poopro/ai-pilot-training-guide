from pathlib import Path
import csv,json,statistics,hashlib
ROOT=Path(r'E:\ai_pilot\campaign_2026');OUT=ROOT/'experiments/opponent_pool/far_bank60_v2/run_20261017_153047_104619'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=read(OUT/'SAFETY_REVIEW.json')
for r in a['results']:
    blue=[];red=[]
    with (OUT/'cases'/r['case']['id']/'telemetry.csv').open(encoding='utf8',newline='') as f:
        for row in csv.DictReader(f):
            if 152.4<=float(row['distance_m'])<=914.4:blue.append(float(row['blue_angle_deg']));red.append(float(row['red_angle_deg']))
    r['in_range_geometry']=dict(samples=len(blue),blue_min_angle_deg=min(blue) if blue else None,blue_median_angle_deg=statistics.median(blue) if blue else None,red_min_angle_deg=min(red) if red else None,red_median_angle_deg=statistics.median(red) if red else None,enemy_behind_blue_body_x_samples=sum(v>90 for v in blue))
write(OUT/'SAFETY_REVIEW.json',a)
r=read(ROOT/'research_latest.json');r['wall_seconds']=276.438;r['benchmark_return_code']=0;r['verification_mode']='direct_frozen_verifier_within_original_600s_deadline'
r['current_verifier']=dict(actual_internal_exit=0,actual_wrapper_exit=0,receipt=str(OUT/'VERIFIER_EXIT.json'),actual_wrapper_observation=str(OUT/'VERIFIER_PARENT_EXIT_OBSERVED.json'))
old={k:r.pop(k) for k in ('original_verifier_exit_code','original_verifier_failure','independent_saved_data_audit','independent_audit_worker_exit','independent_audit_guardian_exit') if k in r}
if old:r['prior_six_game_audit_history']=old
write(ROOT/'research_latest.json',r)
p=read(ROOT/'pipeline_latest.json');p['campaign_latest_20261017']['next_research']=r['next_action'];p['campaign_latest_20261017']['candidate_gate']=a['gate'];write(ROOT/'pipeline_latest.json',p)
n=read(ROOT/'review_notice.json');events=n.setdefault('events',{})
previous=[k for k in events if k.startswith(OUT.name+'|')]
for key in previous:del events[key]
events[OUT.name+'|'+a['gate']+'|'+sha(OUT/'SAFETY_REVIEW.json')]=dict(status=a['gate'],report=str(OUT/'SAFETY_REVIEW.json'),report_sha256=sha(OUT/'SAFETY_REVIEW.json'),notified_utc=a['updated_utc'],channel='ai heartbeat final')
write(ROOT/'review_notice.json',n)
for result in a['results']:
    if result['case']['actor']=='far_bank60':print(json.dumps(dict(case=result['case']['id'],in_range_geometry=result['in_range_geometry']),ensure_ascii=False))
