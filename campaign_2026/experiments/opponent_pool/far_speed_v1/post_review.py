"""Saved full-game review; called inside preplanned verifier120s deadline."""
import csv,json,statistics
from pathlib import Path
def run(out,comparison):
    results=[];commands={}
    for item in comparison['results']:
        folder=out/'cases'/item['case']['id'];rows=list(csv.DictReader((folder/'telemetry.csv').open(encoding='utf8',newline='')))
        r=dict(item);r.update(inside_range_ticks=sum(152.4<=float(x['distance_m'])<=914.4 for x in rows),front_in_range_ticks=sum(152.4<=float(x['distance_m'])<=914.4 and float(x['blue_angle_deg'])<=90 for x in rows),closest_distance_m=min(float(x['distance_m']) for x in rows),blue_kills=int(item['event']=='blue_kill'),blue_deaths=int(item['event']=='red_kill'),blue_crashes=int(item['event'] in ('blue_crash','mutual_crash')),collisions=int(item['event']=='collision'))
        cmds=[];changed=0;speeds=[];prefix_packets=[]
        with (folder/'telemetry.jsonl').open(encoding='utf8') as f:
            for line in f:
                row=json.loads(line);g=row['blue_guidance'];changed+=int(g['applied'][2]!=g['requested'][2]);speeds.append(g['applied'][2]);cmds.append(row['blue_command'])
        r.update(speed_goal_changed_ticks=changed,median_speed_goal_kts=statistics.median(speeds));results.append(r);commands[r['case']['id']]=cmds
    pairs=[]
    for trade in comparison['paired_tradeoffs']:
        base=next(r for r in results if r['case']['opening']==trade['opening'] and r['case']['actor']=='station_zero');cand=next(r for r in results if r['case']['opening']==trade['opening'] and r['case']['actor']=='far_speed_unclipped')
        diff=next((i+1 for i,(a,z) in enumerate(zip(commands[base['case']['id']],commands[cand['case']['id']])) if a!=z),None)
        pairs.append(dict(**trade,baseline_margin=base['score_margin'],candidate_margin=cand['score_margin'],baseline_attacks=base['attack_ticks'],candidate_attacks=cand['attack_ticks'],baseline_in_range=base['inside_range_ticks'],candidate_in_range=cand['inside_range_ticks'],baseline_front_in_range=base['front_in_range_ticks'],candidate_front_in_range=cand['front_in_range_ticks'],first_actual_command_difference_tick=diff,candidate_over9G=cand['over9G']))
    candidate=[r for r in results if r['case']['actor']=='far_speed_unclipped']
    unsafe=any(r['over9G'][0] or r['blue_deaths'] or r['blue_crashes'] or r['collisions'] for r in candidate)
    lost_win=any(p['baseline_winner']=='blue' and p['candidate_winner']!='blue' for p in pairs)
    if unsafe:gate='reject_candidate_safety_or_death'
    elif lost_win or all(p['candidate_margin']<=p['baseline_margin'] for p in pairs):gate='reject_position_score_regression'
    elif all(p['candidate_margin']>p['baseline_margin'] for p in pairs):gate='promising_development_safety_review_required_no_promotion'
    else:gate='mixed_development_not_promoted'
    value=dict(status='completed_saved_full_game_review',gate=gate,results=results,pairs=pairs,unsafe=bool(unsafe),hypothesis='Only remove290kt ceiling when far and heading error>45; original72 unlatched, zero tactical blue',complete_games=4,matched_pairs=2,new_FDM_ticks=comparison['new_FDM_ticks'],actual_worker_exits=comparison['actual_worker_exits'],formal_deployment='repair_guide',training_started=False,deployment_allowed=False,holdout=False,scope='Two new development openings against fixed frozen sac5000. Not professional-team win rate or pure repair_guide comparison.')
    (out/'SAFETY_REVIEW.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
