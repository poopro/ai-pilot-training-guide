from pathlib import Path
ROOT=Path(r'E:\ai_pilot\campaign_2026')
s=(ROOT/'diagnostics/saved_latch_audit_guardian_v1.py').read_text(encoding='utf8')
head=s[:s.index('def worker(out):')].replace('LIMIT=180','LIMIT=120')
head=head.replace('"""Bounded offline guidance projection over saved packets; no FDM/model call.\n\nThe frozen StationController.act and its bearing history are used unchanged.\ncommand() is a recorder: it does not replay the inner actuator controller.\nActual sent-command equality is prior independently verified evidence.\n"""','"""Bounded window extraction only; no act, FDM or model inference."""')
worker='''def worker(out):
    spec=read(out/'CONTRACT.json')
    if sha(Path(__file__))!=spec['diagnostic_source_sha256']:raise RuntimeError('Guardian source changed')
    if sha(ROOT/'diagnostics/latch_window_worker_v1.py')!=spec['analysis_worker_sha256']:raise RuntimeError('Window worker changed')
    import latch_window_worker_v1
    return latch_window_worker_v1.worker(out)

'''
launch=s[s.index('def launch():'):]
start=launch.index("        spec['failed_comparison_sha256']")
end=launch.index("        write(out/'CONTRACT.json',spec)",start)
launch=launch[:start]+"        link=read(RUN/'SAVED_DATA_AUDIT_LINK.json');spec.update(comparison_path=link['comparison'],comparison_sha256=link['comparison_sha256'],analysis_worker_sha256=sha(ROOT/'diagnostics/latch_window_worker_v1.py'),anchors={'0':3458,'1':3854},window_seconds=[-5,0,5,10,20,40])\n"+launch[end:]
launch=launch.replace('saved_latch_audit_v1_','latch_window_v1_').replace('offline_rear_latch_review','offline_latch_window').replace('latest_rear_latch_review','latest_latch_window')
(ROOT/'diagnostics/latch_window_guardian_v1.py').write_text(head+worker+launch,encoding='utf8')
print('Prepared bounded120s saved-window guardian; no FDM, source mutation or seed claims')
