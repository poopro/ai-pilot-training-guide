from pathlib import Path
ROOT=Path(r'E:\ai_pilot\campaign_2026')
s=(ROOT/'diagnostics/pursuit_window_trace_v2.py').read_text(encoding='utf8')
head=s[:s.index('def worker(out):')].replace("SOURCE=ROOT/'experiments/opponent_pool/far_bank60_v2'","SOURCE=ROOT/'experiments/opponent_pool/rear_latch60_v2'").replace("RUN=SOURCE/'run_20261017_153047_104619'","RUN=SOURCE/'run_20261017_203915_d840e7'")
worker='''def worker(out):
    spec=read(out/'CONTRACT.json')
    if sha(Path(__file__))!=spec['diagnostic_source_sha256']:raise RuntimeError('Guardian source changed')
    if sha(ROOT/'diagnostics/rear_latch_review_worker.py')!=spec['review_worker_sha256']:raise RuntimeError('Review worker changed')
    import rear_latch_review_worker
    return rear_latch_review_worker.worker(out)

'''
launch=s[s.index('def launch():'):]
start=launch.index("        old=ROOT/'diagnostics/pursuit_window_trace_")
end=launch.index("        write(out/'CONTRACT.json',spec)",start)
launch=launch[:start]+"        spec['comparison_sha256']=sha(RUN/'COMPARISON.json')\n        spec['review_worker_sha256']=sha(ROOT/'diagnostics/rear_latch_review_worker.py')\n"+launch[end:]
launch=launch.replace('pursuit_window_trace_v2_','rear_latch_review_v1_').replace('latest_pursuit_trace','latest_rear_latch_review').replace('offline_pursuit_trace','offline_rear_latch_review')
(ROOT/'diagnostics/rear_latch_review_guardian.py').write_text(head+worker+launch,encoding='utf8')
print('Prepared bounded review guardian; not launched')
