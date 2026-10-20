"""Stream saved Host CSV: pure maths, no simulator/model/network imports.

Geometry is the same local spherical-NED approximation used by the packet
controller. This audits empirical behavior, not official rules certification.
"""
from pathlib import Path
import csv,json,math,time,hashlib,datetime

ROOT=Path(r'E:\ai_pilot\campaign_2026')
RUN=ROOT/'diagnostics/portable_host_v3/runs/portable_20261016_082436_fe5a8fee'
OUT=ROOT/'diagnostics/HOST_RULES_AUDIT_20261016.json'

def geometry(row):
    lat1,lat2=[math.radians(float(row[f'player{i}_lat_deg'])) for i in (1,2)]
    n=(lat2-lat1)*6378137.
    e=math.radians(float(row['player2_lon_deg'])-float(row['player1_lon_deg']))*6378137.*math.cos((lat1+lat2)/2)
    down=-(float(row['player2_alt_ft'])-float(row['player1_alt_ft']))*.3048
    distance=math.sqrt(n*n+e*e+down*down)
    angles=[]
    for i,sign in ((1,1),(2,-1)):
        theta=math.radians(float(row[f'player{i}_pitch_deg']));psi=math.radians(float(row[f'player{i}_yaw_deg']))
        dot=sign*(math.cos(theta)*math.cos(psi)*n+math.cos(theta)*math.sin(psi)*e-math.sin(theta)*down)
        angles.append(math.degrees(math.acos(max(-1.,min(1.,dot/max(distance,1e-9))))))
    return distance,angles

def distance_factor(d):
    return .1 if d<150 else 1.2 if d<500 else 1. if d<1500 else .5 if d<=3000 else .1

def main():
    began=time.monotonic();result=json.loads((RUN/'portable_result.json').read_text(encoding='utf8'))
    source=RUN/Path(result['source_csv']).name
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest!=result['csv_sha256']:raise ValueError('Saved CSV bytes changed')
    stats=[{'actor':i,'rows':0,'damage_ticks':0,'predicted_1deg':0,'predicted_2deg':0,
        'cone_mismatch':{'1deg_current':0,'2deg_current':0,'1deg_previous':0,'2deg_previous':0},
        'attack_index_error_max':0.,'attack_rangeweighted_error_max':0.,'tail90_rangeweighted_error_max':0.,'tail180_rangeweighted_error_max':0.,'tail180_rangeweighted_error_sum':0.,'legacy_Pt_error_sum':0.,'tail90_error_max':0.,'tail180_error_max':0.,
        'tail90_error_sum':0.,'tail180_error_sum':0.,
        'score_delta_error_unweighted_max':0.,'score_delta_error_rangeweighted_max':0.,
        'damage_vs_scoreKills_seconds_error_max':0.,'over9G_ticks':0} for i in (1,2)]
    previous=None;previous_cones=None;first=None;last=None;count=0
    with source.open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            if time.monotonic()-began>25:raise TimeoutError('Original25second analysis limit')
            count+=1;d,angles=geometry(row);factor=distance_factor(d);cones=[]
            for index,i in enumerate((1,2)):
                s=stats[index];s['rows']+=1;ta=angles[index];aa=180.-angles[1-index]
                attack=max(0.,(90.-ta)/90.)
                tail90=max(0.,(90.-aa)/90.);tail180=max(0.,(180.-aa)/180.)
                host_attack=float(row[f'player{i}_Score_AttackAdvantage']);host_tail=float(row[f'player{i}_Score_PositionAdvantage'])
                s['attack_index_error_max']=max(s['attack_index_error_max'],abs(attack-host_attack))
                s['attack_rangeweighted_error_max']=max(s['attack_rangeweighted_error_max'],abs(attack*factor-host_attack))
                s['tail90_rangeweighted_error_max']=max(s['tail90_rangeweighted_error_max'],abs(tail90*factor-host_tail))
                s['tail180_rangeweighted_error_max']=max(s['tail180_rangeweighted_error_max'],abs(tail180*factor-host_tail))
                s['tail180_rangeweighted_error_sum']+=abs(tail180*factor-host_tail)
                s['legacy_Pt_error_sum']+=abs((attack+tail90)*factor-(host_attack+host_tail))
                for name,prediction in (('tail90',tail90),('tail180',tail180)):
                    error=abs(prediction-host_tail);s[name+'_error_max']=max(s[name+'_error_max'],error);s[name+'_error_sum']+=error
                cone=[500*.3048<=d<=3000*.3048 and ta<=angle for angle in (1,2)];cones.append(cone)
                s['predicted_1deg']+=cone[0];s['predicted_2deg']+=cone[1];s['over9G_ticks']+=abs(float(row[f'player{i}_g_acc']))>9
                if previous is not None:
                    opponent=3-i
                    damage=float(previous[f'player{opponent}_Score_RemainingHP'])-float(row[f'player{opponent}_Score_RemainingHP'])
                    observed=damage>0;s['damage_ticks']+=damage
                    for j,label in enumerate(('1deg','2deg')):
                        s['cone_mismatch'][label+'_current']+=bool(cone[j])!=observed
                        s['cone_mismatch'][label+'_previous']+=bool(previous_cones[index][j])!=observed
                    delta_score=float(row[f'player{i}_Score_FinalAdvantage'])-float(previous[f'player{i}_Score_FinalAdvantage'])
                    delta_kills=float(row[f'player{i}_Score_Kills'])-float(previous[f'player{i}_Score_Kills'])
                    delta_g=float(row[f'player{i}_Score_GForceOverload'])-float(previous[f'player{i}_Score_GForceOverload'])
                    s['damage_vs_scoreKills_seconds_error_max']=max(s['damage_vs_scoreKills_seconds_error_max'],abs(damage-60*delta_kills))
                    for label,f in (('unweighted',1.),('rangeweighted',factor)):
                        predicted=10000*delta_kills-100*delta_g+(host_attack+host_tail)*f
                        key='score_delta_error_'+label+'_max';s[key]=max(s[key],abs(delta_score-predicted))
                else:first={f'player{i}_initial_final_score':float(row[f'player{i}_Score_FinalAdvantage']) for i in (1,2)}
            previous=row;previous_cones=cones;last=row
    for s in stats:
        for label in ('tail90','tail180','tail180_rangeweighted'):s[label+'_mean_abs_error']=s.pop(label+'_error_sum')/count
    report={'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_run':str(RUN),'source_csv_sha256':digest,
        'source_package_round_ineligible_collector2_guard2':True,'row_count':count,'first_row_time':float(last['time']) if count==1 else .033,
        'initial_scores':first,'actors':stats,'actual_wall_seconds':time.monotonic()-began,'additional_hypothesis':'Separate angle-index and distancefactor to test tail denominator90vs180; initial unweighted probe retained separately',
        'geometry':'local spherical NED, bodyX from pitch/yaw; enemy trueattitude used only in private audit',
        'limitations':['Observed one installed publishedHost binary and one saved trace only','Approximate geometry may differ near boundaries','G penalty coefficient not identifiable if no overload events','Nonzero initial cumulative score does not identify cause','No changes to frozen judge/controller/reward/model or old result eligibility','New training/critic/replay contract required if scoring implementation changes'],
        'new_Host_rounds':0,'new_FDM_ticks':0,'formal_rules_certified':False}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
