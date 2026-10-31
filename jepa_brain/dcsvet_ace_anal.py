"""How do DCS AI fights end?  Geometry at the first gun hit, and what the low-going jet was doing before softdeck.
Usage: python dcsvet_ace_anal.py OUT.json LINES.log bucket1.csv.gz [...]"""
import sys, json, math
from collections import defaultdict
import numpy as np
import dcsvet_data as D


def parse(lines):
    st, en, hits = {}, {}, defaultdict(list)
    for line in open(lines, encoding='utf-8', errors='replace'):
        i = line.find('DCSVET|')
        if i < 0:
            continue
        p = line[i:].strip().split('|')
        if p[1] not in ('START', 'END', 'HIT'):
            continue
        idx = int(p[2])
        kv = dict(x.split('=', 1) for x in p[3:] if '=' in x)
        if p[1] == 'START':
            st[idx] = kv
        elif p[1] == 'END':
            en[idx] = kv
        else:
            hits[idx].append((p[3], p[4], float(kv.get('t', 0))))
    return st, en, hits


def state(tr, t):
    """position NED (m), velocity (m/s), bank/pitch (deg) at absolute time t, by local fit."""
    tt = tr['t']
    j = int(np.clip(np.searchsorted(tt, t), 2, len(tt) - 3))
    sl = slice(j - 2, j + 3)
    P = np.array([np.interp(t, tt, tr[k]) for k in ('n', 'e', 'd')])
    V = np.array([np.polyfit(tt[sl] - t, tr[k][sl], 1)[0] for k in ('n', 'e', 'd')])
    return P, V, math.degrees(np.interp(t, tt, tr['bank'])), math.degrees(np.interp(t, tt, tr['pitch']))


def geom(own, en):
    Po, Vo, bo, po = own
    Pe, Ve, be, pe = en
    rel = Pe - Po
    r = np.linalg.norm(rel)
    ata = math.degrees(math.acos(np.clip(np.dot(Vo, rel) / (np.linalg.norm(Vo) * r + 1e-9), -1, 1)))
    aa = math.degrees(math.acos(np.clip(np.dot(Ve, rel) / (np.linalg.norm(Ve) * r + 1e-9), -1, 1)))  # 0 = target fleeing straight away (tail)
    hca = math.degrees(math.acos(np.clip(np.dot(Vo, Ve) / (np.linalg.norm(Vo) * np.linalg.norm(Ve) + 1e-9), -1, 1)))
    clos = -np.dot(rel, Ve - Vo) / r
    return dict(range_m=float(r), ata=ata, aa=aa, hca=hca, closure=float(clos),
                v_own=float(np.linalg.norm(Vo)), v_en=float(np.linalg.norm(Ve)),
                alt_own=float(-Po[2]), alt_en=float(-Pe[2]), dalt=float(-Po[2] + Pe[2]),
                bank_own=bo, pitch_own=po, bank_en=be, pitch_en=pe,
                gamma_own=math.degrees(math.asin(np.clip(-Vo[2] / max(np.linalg.norm(Vo), 1), -1, 1))))


def main(argv):
    out, lines, files = argv[0], argv[1], argv[2:]
    st, en, hits = parse(lines)
    hit_rows, low_rows = [], []
    for f in files:
        fights = D.pair_fights(D.load_csv(f))
        for (seed, idx, _), fr in fights.items():
            if idx not in en:
                continue
            e, s = en[idx], st.get(idx, {})
            t0 = max(fr['B']['t'][0], fr['R']['t'][0])
            tl = min(fr['B']['t'][-1], fr['R']['t'][-1])
            base = dict(idx=idx, reason=e.get('reason'), loser=e.get('loser'), skillR=s.get('skillR'),
                        dist_ft=s.get('dist_ft'), alt0_ft=s.get('alt_ft'))
            h = hits.get(idx)
            if h:
                sh, tg, th = h[0]
                ss, ts = sh.split('_')[1], tg.split('_')[1]
                ta = t0 + th
                if t0 + 1 < ta < tl - .2:
                    g = geom(state(fr[ss], ta), state(fr[ts], ta))
                    # what the shooter did in the 10 s before the hit
                    g10 = geom(state(fr[ss], max(ta - 10, t0 + .5)), state(fr[ts], max(ta - 10, t0 + .5)))
                    hit_rows.append(dict(base, shooter=ss, n_hits=len(h), t_hit=th, kill=e.get('reason') == 'S_EVENT_UNIT_LOST',
                                         shooter_won=(e.get('loser') or '').split('_')[1:2] == [ts] if e.get('loser') else False,
                                         at=g, before10=g10))
            if e.get('reason') == 'softdeck' and e.get('loser'):
                ls = e['loser'].split('_')[1]
                os_ = 'R' if ls == 'B' else 'B'
                tr = fr[ls]
                below = np.nonzero(-tr['d'] < 1000)[0]
                if len(below):
                    tb = tr['t'][below[0]]
                    for dt in (0, 10, 30):
                        tq = max(tb - dt, t0 + .5)
                        g = geom(state(fr[ls], tq), state(fr[os_], tq))
                        low_rows.append(dict(base, dt_before=dt, t_low=float(tb - t0), at=g))
    json.dump(dict(hits=hit_rows, low=low_rows), open(out, 'w'))
    print('hit rows', len(hit_rows), 'low rows', len(low_rows))


if __name__ == '__main__':
    main(sys.argv[1:])
