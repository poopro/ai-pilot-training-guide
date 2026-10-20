"""Recompute the 216 matched saved cases. No simulation or model is executed."""
from collections import Counter
import json
from pathlib import Path
import argparse


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1],help='Repo or restored workspace')
    args=parser.parse_args()
    def read(relative):
        return [json.loads(line) for line in (args.root/relative).read_text('utf-8-sig').splitlines() if line.strip()]
    ridge=read('flybrain/runs/c1_feat1/results.jsonl')
    mlp=read('flybrain/runs/c3_mlp4/results.jsonl')
    key=lambda x:(x['seed'],x['red'])
    baseline=[x for x in ridge if x['policy']=='tuned']
    keys=set(map(key,baseline))
    if len(baseline)!=216 or len(keys)!=216:
        raise ValueError('Unexpected baseline sample or duplicate cases')
    arms={'tuned':baseline,'ridge_v1_tuned':[x for x in ridge if x['policy']=='fly_tuned'],'mlp_v4_tuned':[x for x in mlp if key(x) in keys]}
    fields=['seed','red','distance_ft','side','altitude_ft']
    reference={key(x):[x[f] for f in fields] for x in baseline}
    result={}
    for name,rows in arms.items():
        if len(rows)!=216 or len(set(map(key,rows)))!=216 or any([x[f] for f in fields]!=reference[key(x)] for x in rows):
            raise ValueError('Unmatched or duplicated case: '+name)
        result[name]={'games':len(rows),'winners':dict(Counter(x['winner'] for x in rows)),'events':dict(Counter(x['event'] for x in rows)),'blue_over9G_ticks':sum(x['overg_b'] for x in rows),'blue_attack_ticks':sum(x['atk_b'] for x in rows),'red_attack_ticks':sum(x['atk_r'] for x in rows)}
    print(json.dumps({'scope':'saved-row aggregation, not full trajectory/initial-SHA audit','matched_initial_fields':fields,'mlp_extra_rows_not_used':len(mlp)-216,'results':result},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
