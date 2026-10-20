"""Locked paired local comparison, all five-minute rounds or genuine termination."""
import argparse
from pathlib import Path
import json
import subprocess
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
OLD=Path('E:/ai_pilot/autopilot/opponent_lab/training/run_night_20261006_005158_6300_08/final_0002000000')
CASES=[(p2,20276000+i,[3000,6000,9000][i]) for p2 in ('rule','rl') for i in range(3)]

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--candidate',type=Path);p.add_argument('--baseline',choices=['night','repair_guide','old_guide'],default='night')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    report={'status':'running','official_validation':False,'seed_role':'fixed development comparison; no post-score controller tuning',
        'expected_cases':12,'cases':[],'started':datetime.now(timezone.utc).isoformat()}
    path=args.out/'report.json'
    def save(): path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    try:
        for p2,seed,distance in CASES:
            for side in ('baseline','candidate'):
                folder=args.out/f'{side}_{p2}_{seed}'
                controller='repair' if side=='candidate' or args.baseline=='repair_guide' else 'old'
                bundle=args.candidate if side=='candidate' else OLD if args.baseline=='night' else None
                cmd=[sys.executable,'-X','utf8',str(ROOT/'evaluate.py'),'--controller',controller,
                     '--p2',p2,'--seed',str(seed),'--distance-ft',str(distance),'--out',str(folder)]
                if bundle: cmd+=['--bundle',str(bundle)]
                result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=150)
                (args.out/f'{side}_{p2}_{seed}.stdout.txt').write_text(result.stdout,encoding='utf-8')
                (args.out/f'{side}_{p2}_{seed}.stderr.txt').write_text(result.stderr,encoding='utf-8')
                if result.returncode: raise RuntimeError(f'{side}/{p2}/{seed}: exit {result.returncode}')
                item=json.loads((folder/'report.json').read_text(encoding='utf-8'))
                if not item['full_round_completed']: raise RuntimeError('Incomplete round')
                report['cases'].append({'side':side,**item});save()
                print(f'{side}/{p2}/{seed}: {item["final"]["outcome"]}, attack={item["final"]["attack_seconds"]:.3f}s',flush=True)
        summary={}
        for side in ('baseline','candidate'):
            for p2 in ('rule','rl'):
                items=[x for x in report['cases'] if x['side']==side and x['p2']==p2]
                summary[f'{side}_{p2}']={'n':len(items),'kills':sum(x['final']['is_kill'] for x in items),
                    'survived':sum(x['final']['survived'] for x in items),
                    'crashes':sum(x['final']['own_crash'] for x in items),
                    'mean_attack_seconds':sum(x['final']['attack_seconds'] for x in items)/len(items),
                    'minimum_altitude_m':min(x['final']['min_altitude_m'] for x in items)}
        report['summary']=summary;report['status']='completed';save()
        print(json.dumps(summary,ensure_ascii=False),flush=True)
    except BaseException as error:
        report['status']='failed';report['error']=repr(error);save();raise

if __name__=='__main__':main()
