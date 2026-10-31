"""Quick diagnostic (2026-10-27): can simple finisher/base changes fix the points losses of F4 against the
adversarial turn-fighters adv:fin2_* (found by runs/adv_fin2; all games timeouts decided on POSITION points)?

  python diag_fin2.py --workers 2 --n 6
"""
import argparse, json, time
import numpy as np
import tune4
from common import HERE

F4 = tune4.to_cfg(tune4.X0)
TF1 = dict(F4, k_ang=2.036, k_ff=.9958, hold_m=517.8, turn_cas=301.4, n_cap=7.94, enter_m=3474., merge_off_m=301.7,
           k_spd=.09971, tcpa_s=3.373, miss_m=100., exit_m=3974.)
CANDS = {'F4': F4, 'B86': dict(F4, bank_cap=86.), 'N94': dict(F4, n_cap=9.4, turn_cas=320.),
         'B86N94': dict(F4, bank_cap=86., n_cap=9.4, turn_cas=320.), 'TF1': TF1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--n', type=int, default=6)
    ap.add_argument('--opps', default='adv:fin2_03,adv:fin2_04,adv:fin2_05')
    ap.add_argument('--cands', default=','.join(CANDS))
    ap.add_argument('--seed0', type=int, default=7700000)
    ap.add_argument('--out', default='runs/diag_fin2.json')
    a = ap.parse_args()
    import multiprocessing as mp
    pool = mp.get_context('spawn').Pool(a.workers, maxtasksperchild=40)
    names = a.cands.split(',')
    plan = (('fin2', tuple(a.opps.split(',')), a.n, 1.),)
    t0 = time.time()
    fit, fam, raw = tune4.evaluate(pool, [CANDS[n] for n in names], a.seed0, plan=plan)
    pool.terminate()
    rep = {}
    for n, f, rr in zip(names, fit, raw):
        rep[n] = dict(fit=round(f, 3), W=sum(r['winner'] == 'blue' for r in rr), L=sum(r['winner'] == 'red' for r in rr),
                      kills=sum(r['event'] == 'blue_kill' for r in rr), died=sum(r['event'] in ('red_kill', 'blue_crash', 'collision') for r in rr),
                      med_margin=round(float(np.median([r['margin'] for r in rr])), 0),
                      atk_b=round(float(np.mean([r['atk_b'] or 0 for r in rr])), 1), atk_r=round(float(np.mean([r['atk_r'] or 0 for r in rr])), 1))
        print(n, rep[n], flush=True)
    (HERE / a.out).write_text(json.dumps(dict(rep=rep, raw=dict(zip(names, raw)), minutes=round((time.time() - t0) / 60, 1)), indent=1))
    print('done in %.1f min' % ((time.time() - t0) / 60), flush=True)


if __name__ == '__main__':
    main()
