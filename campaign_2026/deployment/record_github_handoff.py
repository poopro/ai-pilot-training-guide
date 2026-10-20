from pathlib import Path
import json, subprocess, datetime
root=Path(r'E:\ai_pilot\campaign_2026')
out=root/'deployment/github_cpu_release_20261016'
gh=r'C:\Program Files\GitHub CLI\gh.exe'
def call(*args):
    r=subprocess.run([gh,*args],capture_output=True,text=True,encoding='utf8',timeout=30)
    assert r.returncode==0,r.stderr
    return json.loads(r.stdout)
repo=call('repo','view','poopro/ai-pilot-cpu-player','--json','url,visibility')
release=call('release','view','cpu-player-20261016','--repo','poopro/ai-pilot-cpu-player','--json','url,assets,isDraft')
local=json.loads((out/'LOCAL_RELEASE_VERIFICATION.json').read_text(encoding='utf8'))
asset=next(a for a in release['assets'] if a['name'].endswith('.zip'))
assert repo['visibility']=='PRIVATE' and release['isDraft'] is False
assert asset['digest']=='sha256:'+local['sha256'] and asset['size']==local['size'] and asset['state']=='uploaded'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
receipt={'observed_utc':now,'repository':repo,'release':release,'remote_digest_matches_local':True,'fresh_extract_probe_actual_exit':0,'ASUS_execution_verified':False,'LAN_verified':False,'email_message_id':'1a1448a9a3633688','initial_packaging_attempt':'Rejected suffix scan found manifest-tracked NumPy vendor test CSV/PKL, not campaign telemetry; corrected allowlist only for manifest-tracked NumPy tests/data; original files unchanged.'}
(out/'GITHUB_RELEASE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
event={'status':'sent_waiting_actual_ASUS_probe','sent_utc':now,'to':'me','message_id':'1a1448a9a3633688','thread_id':'1a1448a9a3633688','evidence_sha256':local['sha256'],'release_url':release['url'],'private_repository':True,'next_action':'ASUS login poopro, download ZIP from Assets, extract, run ASUS_先檢查.cmd, return new vivobook_readiness.json','ASUS_execution_verified':False,'LAN_verified':False}
p=root/'email_notice.json'; data=json.loads(p.read_text(encoding='utf8')); data.setdefault('events',{})['vivobook_github_release_20261016']=event; p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
p=root/'research_latest.json'; data=json.loads(p.read_text(encoding='utf8')); data['github_second_pc_handoff']=event; p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
with (root/'REVIEW_LOG.md').open('a',encoding='utf8') as f:
    f.write('\n\n## '+now+' GitHub CPU Player交付\n\n使用者要求另一台PC可從GitHub下載。已建立私人repo並發布36,256,095bytes ZIP；遠端asset digest與本機SHA一致：'+local['sha256']+'。2115基準檔逐檔核對、主PC新解壓probe實際退出0/p99 0.422ms；未修改原套件或controller。僅新增外層操作文件，移除主PC範例報告；無官方Host、訓練模型或個人遙測外傳。初次suffix掃描遇NumPy原廠測試CSV/PKL拒絕，核對manifest後僅容許該vendor tests/data，非研究資料。GitHub發布與寄信已完成，ASUS實機及LAN仍待使用者執行。發布頁：'+release['url']+'；Gmail message 1a1448a9a3633688。無新訓練/FDM。\n')
with (root/'latest_result.md').open('a',encoding='utf8') as f:
    f.write('\n\n## ASUS已可從GitHub下載\n\n私人下載頁：'+release['url']+'。登入poopro→Assets下載ZIP→解壓→雙擊ASUS_先檢查.cmd→傳回新vivobook_readiness.json。主PC新解壓檢查通過，ASUS/LAN未驗證。新下載步驟已寄信，正式仍repair_guide。\n')
print(json.dumps({'release_url':release['url'],'private':True,'remote_digest_matches':True,'email_message_id':event['message_id']},ensure_ascii=False))
