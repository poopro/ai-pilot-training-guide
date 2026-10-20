"""Replay only fields actually present in saved real60Hz telemetry.

No red60Hz attitude/G/altitude is available here. Do not invent it or claim a
complete new winner/S_advantage from this blue-only counter audit.
"""
import csv
import hashlib
import json
from pathlib import Path
from judge import RuleProfile, attack_window

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'experiments'/'g_latch_development'/'run_20261014_150515_b846'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    known=SOURCE/'cases'/'r000_rl_9000_mirrored_2026101412_candidate'
    kill_case=None
    for folder in sorted((SOURCE/'cases').glob('*rule*candidate')):
        result=read(folder/'result.json')
        if result['metrics']['kills']==1:
            kill_case=folder
            break
    if kill_case is None:raise RuntimeError('No saved kill case found; do not substitute a fabricated trace')
    output=[]
    for folder in (known,kill_case):
        result=read(folder/'result.json')
        path=folder/'telemetry_60hz.csv'
        original_hash=sha(path)
        with (folder/'telemetry.csv').open(encoding='utf-8-sig',newline='') as stream:
            checkpoints={int(row['tick']):int(round(float(row['attack_seconds'])*60)) for row in csv.DictReader(stream)}
        profiles=[RuleProfile('line_20261014_1deg','AGL','right_bin'),RuleProfile('pdf_20261008_2deg','AGL','right_bin')]
        counts=[0,0];first180=[None,None];bursts=[];burst=None;rows=0;checked=0
        with path.open(encoding='utf-8-sig',newline='') as stream:
            for row in csv.DictReader(stream):
                rows+=1
                tick=int(row['tick'])
                if tick!=rows:raise RuntimeError('60Hz trace not contiguous')
                distance=float(row['distance_m']);angle=float(row['blue_angle_deg_judge_only'])
                hits=[attack_window(distance,angle,p) for p in profiles]
                for i,hit in enumerate(hits):
                    counts[i]+=int(hit)
                    if counts[i]>=180 and first180[i] is None:first180[i]=tick
                if hits[0]:
                    if burst is None:burst={'start_tick':tick,'ticks':0}
                    burst['ticks']+=1
                elif burst is not None:
                    bursts.append(burst);burst=None
                if tick in checkpoints:
                    if counts[0]!=checkpoints[tick]:raise RuntimeError('Saved per-second counter mismatch')
                    checked+=1
        if burst is not None:bursts.append(burst)
        expected=int(round(result['metrics']['attack_seconds']*60))
        if rows!=result['steps'] or counts[0]!=expected or sha(path)!=original_hash:
            raise RuntimeError('Final steps/counter/source mismatch')
        if counts[0]<=0:raise RuntimeError('Expected nonzero actual-flight trace')
        output.append({'case_id':folder.name,'source_60hz_sha256':original_hash,'source_result_sha256':sha(folder/'result.json'),
                       'saved_real_FDM_rows':rows,'line1deg_attack_ticks':counts[0],
                       'source_counter_ticks':expected,'checkpoints_matched':checked,'nonconsecutive_bursts':bursts,
                       'pdf2deg_attack_ticks_on_same_saved_trace':counts[1],
                       'first180tick_line1deg':first180[0],'first180tick_pdf2deg':first180[1],
                       'full_new_winner_verified':False,'reason':'Red60Hz/G/altitude are absent;2deg may truncate earlier, so raw prefix thresholds are not counterfactual full battles.'})
    report={'verified_saved_real_FDM_blue_counter':True,'cases':output,'new_FDM_ticks':0,
            'source_unchanged':True,'new_training_steps':0,'official_Host_conformance_verified':False,
            'deployment_allowed':False,'full_S_advantage_recomputed':False}
    (HERE/'NONZERO_COUNTER_REPLAY.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
