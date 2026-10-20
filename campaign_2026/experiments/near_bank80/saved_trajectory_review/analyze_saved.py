"""Read-only analysis of two completed paired trajectories; no simulator imports."""
import csv,json,pathlib,hashlib,math,datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(r'E:\ai_pilot\campaign_2026')
RUN=ROOT/'experiments/near_bank80/run_20261012_2050'
OUT=pathlib.Path(__file__).parent
PAIRS=['r000_rule_3000_mirrored_2026101100','r000_rl_6000_mirrored_2026101111']
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def wrap(x): return (x+180)%360-180
def acmi(path):
    frames={}; tick=None
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('#'):
            t=float(line[1:]); tick=round(t*60)
            assert abs(t-tick/60)<.0006
            frames.setdefault(tick,{})
        elif ',T=' in line:
            ident,values=line.split(',T=',1)
            if ident in ['1','2']:
                pose=[float(x) for x in values.split('|')[:6]]
                if ident in frames[tick]: assert frames[tick][ident]==pose, 'Conflicting repeated ACMI frame'
                frames[tick][ident]=pose
    assert all(set(v)=={'1','2'} for v in frames.values())
    return frames
comparison=json.loads((RUN/'COMPARISON.json').read_text(encoding='utf-8-sig'))
assert comparison['verified_comparison'] and comparison['actual_parent_exit_code']==0
assert sha(RUN/'report.json')==comparison['report_sha256']
expected={x['case_id']:x for x in comparison['artifact_hashes']}
inputs={}; data={}; results=[]; derived=[]
for pair in PAIRS:
    data[pair]={}
    for actor in ['guide','candidate']:
        folder=RUN/'cases'/f'{pair}_{actor}'
        for filename in ['telemetry.csv','duel.acmi','result.json']:
            inputs[str(folder/filename)]=sha(folder/filename)
        assert sha(folder/'telemetry.csv')==expected[folder.name]['telemetry_sha256']
        assert sha(folder/'duel.acmi')==expected[folder.name]['acmi_sha256']
        raw=json.loads((folder/'result.json').read_text(encoding='utf-8-sig'))
        assert raw['status']=='completed' and raw['score_eligible'] and raw['full_round_completed']
        frames=acmi(folder/'duel.acmi')
        with (folder/'telemetry.csv').open(encoding='utf-8-sig',newline='') as f: source=list(csv.DictReader(f))
        rows=[]
        assert len(source)==expected[folder.name]['csv_rows']
        for x in source:
            tick=int(x['tick']); pose=frames[tick]['1']; t=tick/60
            assert abs(t-float(x['simulation_seconds']))<1e-9
            assert abs(pose[2]-float(x['altitude_m']))<1e-7
            row={'tick':tick,'time_s':t,'range_m':float(x['distance_m']),'nose_deg':float(x['blue_angle_deg_judge_only']),
                 'altitude_m':float(x['altitude_m']),'load':float(x['load_factor']),'attack_s':float(x['attack_seconds']),
                 'mode':x['controller_mode'],'roll_deg':pose[3],'pitch_deg':pose[4],'yaw_deg':pose[5]}
            assert all(math.isfinite(v) for v in row.values() if isinstance(v,(int,float)))
            rows.append(row); derived.append({'pair':pair,'actor':actor,**row})
        passes=[]; current=[]
        for row in rows:
            if row['range_m']<1100: current.append(row)
            elif current: passes.append(current); current=[]
        if current: passes.append(current)
        close=[]
        for group in passes:
            closest=min(group,key=lambda x:x['range_m']); aligned=min(group,key=lambda x:x['nose_deg'])
            close.append({'first_logged_s':group[0]['time_s'],'last_logged_s':group[-1]['time_s'],'logged_rows':len(group),
                'closest':closest,'best_nose':aligned,'mode_counts':{m:sum(x['mode']==m for x in group) for m in sorted(set(x['mode'] for x in group))},
                'nose_under45_rows':sum(x['nose_deg']<45 for x in group),'nose_under3_rows':sum(x['nose_deg']<3 for x in group),
                'attack_increase_between_first_last_logged_s':group[-1]['attack_s']-group[0]['attack_s']})
        positives=[]; previous=0.
        for row in rows:
            if row['attack_s']>previous+1e-8: positives.append({**row,'increase_since_previous_logged_s':row['attack_s']-previous})
            previous=row['attack_s']
        recover=[x for x in rows if x['mode']=='recover']
        data[pair][actor]={'attack_increase_intervals':positives,'first_logged_recover':recover[0] if recover else None,'rows':rows,'frames':frames,'initial_sha':raw['initial_sha256'],'metrics':raw['metrics'],
                            'steps':raw['steps'],'close_passes':close,'terminal_sample':rows[-1]}
    g=data[pair]['guide']; c=data[pair]['candidate']; assert g['initial_sha']==c['initial_sha']
    assert g['frames'][0]==c['frames'][0]
    common=min(g['steps'],c['steps'])/60
    shared=sorted(set(g['frames'])&set(c['frames']))
    first=None
    for tick in shared:
        pg=g['frames'][tick]['1']; pc=c['frames'][tick]['1']
        delta={'roll_deg':pc[3]-pg[3],'pitch_deg':pc[4]-pg[4],'yaw_deg':wrap(pc[5]-pg[5]),'altitude_m':pc[2]-pg[2]}
        if max(abs(delta[k]) for k in ['roll_deg','pitch_deg','yaw_deg'])>.1:
            first={'time_s':tick/60,'candidate_minus_guide':delta}; break
    lookup={a:{x['tick']:x for x in data[pair][a]['rows']} for a in ['guide','candidate']}
    common_ticks=sorted(set(lookup['guide'])&set(lookup['candidate']))
    examples=[{'time_s':tick/60,'guide':lookup['guide'][tick],'candidate':lookup['candidate'][tick]} for tick in common_ticks if tick/60 in ([1,2,10,20,100,180,205,210,220,229] if pair==PAIRS[0] else [1,2,10,20,100,170,180,183,184])]
    results.append({'pair':pair,'same_initial_sha':g['initial_sha'],'common_window_s':common,'first_observed_attitude_divergence_over0p1deg':first,
        'arms':{a:{k:data[pair][a][k] for k in ['metrics','steps','close_passes','terminal_sample','attack_increase_intervals','first_logged_recover']} for a in ['guide','candidate']},'aligned_examples':examples})
with (OUT/'aligned_samples.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(derived[0])); w.writeheader(); w.writerows(derived)
for early in [False,True]:
    fig,axes=plt.subplots(4,2,figsize=(13,11),sharex='col')
    for col,pair in enumerate(PAIRS):
        horizon=20 if early else min(data[pair]['guide']['steps'],data[pair]['candidate']['steps'])/60
        for actor,color in [('guide','#2d6cdf'),('candidate','#de7130')]:
            rows=[x for x in data[pair][actor]['rows'] if x['time_s']<=horizon]
            for i,(field,label) in enumerate([('range_m','Range (m)'),('nose_deg','Nose error (deg)'),('roll_deg','Observed bank (deg)'),('altitude_m','Altitude (m)')]):
                axes[i,col].plot([x['time_s'] for x in rows],[x[field] for x in rows],label=actor,color=color)
                axes[i,col].set_ylabel(label); axes[i,col].grid(alpha=.25)
        axes[0,col].set_title('Lost rule kill' if col==0 else 'Gained RL kill')
        axes[0,col].axhline(1100,color='gray',ls='--',lw=.8)
        axes[1,col].axhline(45,color='gray',ls='--',lw=.8)
        axes[3,col].axhline(800,color='gray',ls='--',lw=.8)
        axes[3,col].set_xlabel('Simulation time (s)'); axes[0,col].legend()
    fig.suptitle('Saved development trajectories / aligned common horizon'+(' / first20s' if early else ''))
    fig.tight_layout(); fig.savefig(OUT/('early20s.png' if early else 'paired_trajectories.png'),dpi=150); plt.close(fig)
assert all(sha(pathlib.Path(p))==h for p,h in inputs.items())
analysis={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verified_input_comparison':str(RUN/'COMPARISON.json'),
 'comparison_sha256':sha(RUN/'COMPARISON.json'),'input_sha256':inputs,'inputs_unchanged_after_analysis':True,'new_fdm_ticks':0,'learner_started':False,
 'selected_pairs':results,'limits':['Two selected observed development pairs; not generalization or win-rate estimate.',
 'Repeated terminal ACMI timestamps are accepted only when both poses are identical.',
 'CSV about1Hz and ACMI0.5s; close-pass endpoints and first divergence are sampled, not exact onset or durations.',
 'Uses authoritative logged judge nose angle for diagnosis only; no reconstruction from geodetic latitude and no policy input change.',
 'Observed bank/pitch/yaw do not reveal actual target commands, trim or integrator state.',
 'No counterfactual proves that adding angular eligibility restores lost kill.'],
 'decision':'Keep bank80 frozen for scheduled fresh development trial. Consider only afterward a single-factor angular eligibility experiment if repeated intercept regressions persist; do not mix pitch/trim/safety changes.'}
(OUT/'ANALYSIS.json').write_text(json.dumps(analysis,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pairs':[{'pair':x['pair'],'divergence':x['first_observed_attitude_divergence_over0p1deg'],
 'passes':{a:[{'start':v['first_logged_s'],'end':v['last_logged_s'],'rows':v['logged_rows'],'min_range':v['closest']['range_m'],'min_nose':v['best_nose']['nose_deg'],'modes':v['mode_counts']} for v in x['arms'][a]['close_passes']] for a in ['guide','candidate']},
 'examples':x['aligned_examples']} for x in results],'new_fdm_ticks':0,'inputs_unchanged':True},ensure_ascii=False))


