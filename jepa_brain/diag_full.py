"""Check candidates on the FULL tune4 training plan (incl. advfin2) on new seeds -- does the fin2 fix hurt elsewhere?
  python diag_full.py --cands F4,B86N94,B86N96 --workers 2
"""
import argparse, json, time
import numpy as np
import tune4, diag_fin2
from common import HERE

CANDS = dict(diag_fin2.CANDS)
CANDS['B86N96'] = dict(CANDS['F4'], bank_cap=86., n_cap=9.6, turn_cas=320.)
CANDS['B80N90'] = dict(CANDS['F4'], bank_cap=80., n_cap=9.0, turn_cas=330.)
# rec_v2 = corner-speed G at idle in ground recovery (dcsvet_core.LiftPilot, 2026-10-27)
for _k in ('F4', 'B86N94', 'B80N90'):
    CANDS[_k + 'R'] = dict(CANDS[_k], rec_v2=1.)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cands', default='F4,B86N94')
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--seed0', type=int, default=7710000)
    ap.add_argument('--out', default='runs/diag_full.json')
    a = ap.parse_args()
    import multiprocessing as mp
    pool = mp.get_context('spawn').Pool(a.workers, maxtasksperchild=40)
    names = a.cands.split(',')
    t0 = time.time()
    fit, fam, raw = tune4.evaluate(pool, [n[4:] if n.startswith('arm:') else CANDS[n] for n in names], a.seed0, plan=tune4.PLAN_FIN12)
    pool.terminate()
    rep = {}
    for n, f, fm, rr in zip(names, fit, fam, raw):
        rep[n] = dict(fit=round(f, 3), fam=fm, W=sum(r['winner'] == 'blue' for r in rr), L=sum(r['winner'] == 'red' for r in rr),
                      kills=sum(r['event'] == 'blue_kill' for r in rr),
                      died=sum(r['event'] in ('red_kill', 'blue_crash') or (r['event'] == 'collision' and r['winner'] != 'blue') for r in rr),
                      coll=sum(r['event'] == 'collision' for r in rr), n=len(rr))
        print(n, rep[n], flush=True)
    (HERE / a.out).write_text(json.dumps(dict(rep=rep, raw=dict(zip(names, raw)), cfg={n: CANDS.get(n, n) for n in names}), indent=1))
    print('done in %.1f min' % ((time.time() - t0) / 60), flush=True)


if __name__ == '__main__':
    main()
