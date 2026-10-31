"""Common held-out judgement of finisher candidates (2026-10-27).

Every candidate plays the SAME new seeds against opponents that no tuning run trained on:
  fin1_ho  : adv:fin1_01/02/05/07          (round-1 adversaries vs F4, held out of tune4)
  fin2_ho  : adv:fin2_02/04/07             (round-2 adversaries vs F4, held out of tune4 --advfin fin12)
  fin3     : adv:fin3_*  (if present)      (round-3 adversaries, server)
  f2w80, sac_ho, script_ho, self_ho        (as tune4 --heldout)
Reported but NOT in the fitness: fin2_tr = adv:fin2_01/03/05 (trained on by --advfin fin12 runs).

  python judge4.py --cands F4,runs/tune04_desk,runs/tune04 --workers 6 --out runs/judge4_1028
Candidate: F4 | F4R | TF1 (runs/tune_fin1 best) | B86N94 / B80N90 / ...R (diag_full.py) | <spec>+R (rec_v2 on) | <run dir with best.json> | name=<json cfg>
Fitness = 0.5 * mean family utility + 0.5 * min family utility (tune4.utility).
"""
import argparse, json, time
from pathlib import Path
import numpy as np
import tune4
from common import HERE


def families():
    fams = [('fin1_ho', tuple('adv:' + n for n in tune4.FIN1_HO)), ('fin2_ho', tuple('adv:' + n for n in tune4.FIN2_HO))]
    fin3 = sorted(p.stem for p in (HERE / 'adv_pool').glob('fin3_*.json'))
    if fin3:
        fams.append(('fin3', tuple('adv:' + n for n in fin3)))
    fams += [f for f in tune4.HELDOUT if f[0] != 'fin1_ho']
    new = tuple('adv:' + n for n in tune4.NEW_HO if (HERE / 'adv_pool' / (n + '.json')).exists())
    if new:
        fams.append(('new_ho', new))          # 2026-10-28: finisher / vertical reds found against T17 (held out of tune05)
    fams.append(('fin2_tr', tuple('adv:' + n for n in tune4.FIN2_TRAIN)))
    return fams


def load_cand(spec):
    if spec.endswith('+R'):                          # same candidate with finisher ground recovery v2 switched on
        name, cfg = load_cand(spec[:-2])
        return name + '+R', dict(cfg, rec_v2=1.)
    if spec.startswith('arm:'):                      # any blue arm string, e.g. arm:dcsv2fr:runs/bc_v2b_all.npz
        a = spec[4:]
        return a.split(':')[0] + ':' + Path(a.split(':', 1)[-1]).stem if a.startswith('dcsv2') else a, a
    if spec == 'F4':
        return 'F4', tune4.to_cfg(tune4.X0)
    if spec == 'TF1':
        import diag_fin2
        return 'TF1', dict(diag_fin2.TF1)
    import diag_full
    if spec in diag_full.CANDS:                      # B86N94, B80N90, ...
        return spec, dict(diag_full.CANDS[spec])
    if '=' in spec and spec.split('=', 1)[1].lstrip().startswith('{'):
        n, js = spec.split('=', 1)
        return n, json.loads(js)
    d = json.loads((HERE / spec / 'best.json').read_text())
    return Path(spec).name + '@g%s' % d.get('gen'), d['cfg']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cands', default='F4')
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--n', type=int, default=12)
    ap.add_argument('--seed0', type=int, default=7900000)
    ap.add_argument('--out', default='runs/judge4')
    ap.add_argument('--max-ticks', type=int, default=18000, help='smoke test only (official round = 18000)')
    a = ap.parse_args()
    cands = [load_cand(s) for s in a.cands.split(',')]
    fams = families()
    plan = tuple((n, o, a.n, 1.) for n, o in fams)
    print('candidates', [c[0] for c in cands], 'families', {n: len(o) for n, o in fams}, flush=True)
    import multiprocessing as mp
    pool = mp.get_context('spawn').Pool(a.workers, maxtasksperchild=40)
    t0 = time.time()
    _, fam_u, raw = tune4.evaluate(pool, [c[1] for c in cands], a.seed0, plan=plan, max_ticks=a.max_ticks)
    pool.terminate()
    # per-family W/L/kills/deaths, using the evaluate() task order
    order = [n for n, o in fams for _ in o for _ in range(a.n)]
    rep = {}
    for (name, cfg), fu, rr in zip(cands, fam_u, raw):
        scored = {k: v for k, v in fu.items() if k != 'fin2_tr'}
        fit = .5 * float(np.mean(list(scored.values()))) + .5 * min(scored.values())
        per = {}
        for fam, r in zip(order, rr):
            d = per.setdefault(fam, dict(W=0, L=0, D=0, kills=0, died=0, n=0))
            d['n'] += 1
            d['W' if r['winner'] == 'blue' else ('L' if r['winner'] == 'red' else 'D')] += 1
            d['kills'] += r['event'] == 'blue_kill'
            d['died'] += r['event'] in ('red_kill', 'blue_crash') or (r['event'] == 'collision' and r['winner'] != 'blue')
        tot = {k: sum(p[k] for f, p in per.items() if f != 'fin2_tr') for k in ('W', 'L', 'D', 'kills', 'died', 'n')}
        rep[name] = dict(fit=round(fit, 4), fam_u=fu, per=per, total=tot, cfg=cfg)
        print(name, 'fit %.3f' % fit, 'total', tot, flush=True)
    out = HERE / a.out
    out.mkdir(parents=True, exist_ok=True)
    (out / 'judge.json').write_text(json.dumps(dict(rep=rep, raw={c[0]: r for c, r in zip(cands, raw)}, n=a.n, seed0=a.seed0,
                                                    minutes=round((time.time() - t0) / 60, 1)), indent=1))
    fam_names = [n for n, _ in fams]
    lines = ['# judge4 共同留出判定（%s，每對手 %d 局，種子 %d 起）' % (time.strftime('%F %H:%M'), a.n, a.seed0), '',
             '| 候選 | fitness | 總勝-敗-和 | 擊落 | 被擊落/墜機 | ' + ' | '.join(fam_names) + ' |',
             '|---|---|---|---|---|' + '---|' * len(fam_names)]
    for name, r in rep.items():
        t = r['total']
        cells = ['%d-%d (%.2f)' % (r['per'][f]['W'], r['per'][f]['L'], r['fam_u'][f]) for f in fam_names]
        lines.append('| %s | %.3f | %d-%d-%d | %d | %d | %s |' % (name, r['fit'], t['W'], t['L'], t['D'], t['kills'], t['died'], ' | '.join(cells)))
    lines += ['', 'fin2_tr 不計入 fitness（--advfin fin12 的執行有拿它訓練）。換上新參數的條件：fitness 高於 F4、被擊落不增加，並通過完整門檻。']
    (out / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines), flush=True)
    print('done in %.1f min' % ((time.time() - t0) / 60), flush=True)


if __name__ == '__main__':
    main()
