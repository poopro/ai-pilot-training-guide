from pathlib import Path
ROOT=Path(r'E:\ai_pilot\campaign_2026')
s=(ROOT/'diagnostics/latch_window_guardian_v1.py').read_text(encoding='utf8')
s=s.replace('latch_window_worker_v1.py','latch_window_audit_v1.py').replace('import latch_window_worker_v1','import latch_window_audit_v1').replace('return latch_window_worker_v1.worker(out)','return latch_window_audit_v1.worker(out)')
s=s.replace("'latch_window_v1_'","'latch_window_audit_v1_'")
a="        write(out/'CONTRACT.json',spec)"
assert a in s;s=s.replace(a,"        spec['extract_path']=str(ROOT/'diagnostics/latch_window_v1_20261017_213638_941961');spec['extract_analysis_sha256']=sha(Path(spec['extract_path'])/'ANALYSIS.json')\n"+a)
s=s.replace("j['latest_latch_window']=str(out)","j['latest_latch_window_audit']=str(out)")
(ROOT/'diagnostics/latch_window_audit_guardian_v1.py').write_text(s,encoding='utf8')
print('Prepared120s independent saved-window audit; no FDM')
