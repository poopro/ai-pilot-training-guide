"""League tables for blue arms x pool-v2 opponents (+ head-to-head 'ctl:<arm>' reds).

  python league.py runs/league_a runs/league_b ...            (REF=base_t3 default reference arm)
Writes runs/league_report.md:  1) win-rate matrix  2) head-to-head matrix  3) Bradley-Terry / Elo
4) paired difference vs REF per opponent (flags opponent classes where an arm is worse than REF).
"""
import json, os, sys, math
from collections import defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REF = os.environ.get('REF', 'base_t3')
CTL = 'ctl:'
rows = {}
for d in sys.argv[1:]:
    p = HERE / d / 'results.jsonl'
    if not p.exists():
        continue
    for line in p.read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        if 'error' in r:
            continue
        rows[(r['policy'], r['red'], r['seed'])] = r          # later runs override earlier duplicates
rows = list(rows.values())
if not rows:
    sys.exit('no results')


def score(r):
    return 1. if r['winner'] == 'blue' else (0. if r['winner'] == 'red' else .5)


def wilson(w, n, z=1.96):
    if n == 0:
        return (0., 1.)
    p = w / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0., c - h), min(1., c + h))


arms = sorted({r['policy'] for r in rows}, key=lambda a: (a != REF, a))
pool = sorted({r['red'] for r in rows if not r['red'].startswith(CTL)})
ctl = sorted({r['red'] for r in rows if r['red'].startswith(CTL)})
cell = defaultdict(list)
for r in rows:
    cell[(r['policy'], r['red'])].append(r)


def fmt(rs):
    if not rs:
        return '-'
    w = sum(r['winner'] == 'blue' for r in rs); l = sum(r['winner'] == 'red' for r in rs)
    return '%d-%d (%+.0f)' % (w, l, np.mean([r['margin'] for r in rs]))


out = ['# League report', '', 'Reference arm: **%s**.  Cell = 藍方勝-負 (平均 margin);n 見各格。' % REF, '']
# ---------------- 1. pool matrix
out += ['## 1. 藍方 arm × 對手池 v2', '', '| 對手 | ' + ' | '.join(arms) + ' |', '|---|' + '---|' * len(arms)]
for o in pool:
    out.append('| %s | ' % o + ' | '.join(fmt(cell[(a, o)]) for a in arms) + ' |')
out.append('| **合計勝率** | ' + ' | '.join(
    '%.0f%% [%.0f–%.0f] n=%d' % (100 * np.mean([score(r) for o in pool for r in cell[(a, o)]]) if any(cell[(a, o)] for o in pool) else 0,
                                 100 * wilson(sum(score(r) for o in pool for r in cell[(a, o)]), sum(len(cell[(a, o)]) for o in pool))[0],
                                 100 * wilson(sum(score(r) for o in pool for r in cell[(a, o)]), sum(len(cell[(a, o)]) for o in pool))[1],
                                 sum(len(cell[(a, o)]) for o in pool)) for a in arms) + ' |')
# ---------------- 2. head to head
if ctl:
    out += ['', '## 2. 對戰矩陣(列=藍方,欄=紅方控制器)', '', '| 藍＼紅 | ' + ' | '.join(c[len(CTL):] for c in ctl) + ' |', '|---|' + '---|' * len(ctl)]
    for a in arms:
        if any(cell[(a, c)] for c in ctl):
            out.append('| %s | ' % a + ' | '.join(fmt(cell[(a, c)]) for c in ctl) + ' |')
# ---------------- 3. Bradley-Terry / Elo
games = []
for r in rows:
    i = 'A:' + r['policy']
    j = ('A:' + r['red'][len(CTL):]) if r['red'].startswith(CTL) else ('O:' + r['red'])
    games.append((i, j, score(r)))
players = sorted({g[0] for g in games} | {g[1] for g in games})
idx = {p: k for k, p in enumerate(players)}
gam = np.ones(len(players))
for _ in range(500):
    new = gam.copy()
    for p, k in idx.items():
        wsum, den = .5, 1. / (gam[k] + 1.)               # pseudo game vs an average player (regulariser)
        for i, j, s in games:
            if i == p:
                wsum += s; den += 1. / (gam[k] + gam[idx[j]])
            elif j == p:
                wsum += 1. - s; den += 1. / (gam[k] + gam[idx[i]])
        new[k] = wsum / den
    new /= np.exp(np.mean(np.log(new)))
    if np.max(np.abs(np.log(new / gam))) < 1e-7:
        gam = new; break
    gam = new
ref_k = idx.get('A:' + REF, 0)
elo = 1500 + 400 * np.log10(gam / gam[ref_k])
out += ['', '## 3. Bradley-Terry / Elo(以 %s = 1500;對手池與我方 arm 同表,僅供相對比較;n 小時誤差很大)' % REF, '', '| 選手 | Elo | 局數 |', '|---|---|---|']
cnt = defaultdict(int)
for i, j, s in games:
    cnt[i] += 1; cnt[j] += 1
for k in np.argsort(-elo):
    out.append('| %s | %.0f | %d |' % (players[k], elo[k], cnt[players[k]]))
# ---------------- 4. paired vs REF
out += ['', '## 4. 相對 %s 的配對差(同 seed;Δ勝率分 = 勝1/和.5/負0,Δmargin;"✗" = 該類對手比 REF 差)' % REF, '',
        '| 對手 | arm | n配對 | Δ得分 | Δmargin | 旗標 |', '|---|---|---|---|---|---|']
bad = defaultdict(list)
for o in pool + ctl:
    ref = {r['seed']: r for r in cell[(REF, o)]}
    for a in arms:
        if a == REF:
            continue
        pr = [(r, ref[r['seed']]) for r in cell[(a, o)] if r['seed'] in ref]
        if not pr:
            continue
        ds = np.array([score(r) - score(b) for r, b in pr]); dm = np.array([r['margin'] - b['margin'] for r, b in pr])
        flag = '✗' if ds.mean() < -0.1 else ('✓' if ds.mean() > 0.1 else '')
        if flag == '✗':
            bad[a].append(o)
        out.append('| %s | %s | %d | %+.2f | %+.0f | %s |' % (o, a, len(pr), ds.mean(), dm.mean(), flag))
out += ['', '### 比 REF 差的對手類別']
for a in arms:
    if a != REF:
        out.append('- %s: %s' % (a, ', '.join(bad[a]) if bad[a] else '無'))
# ---------------- 5. failure modes
out += ['', '## 5. 事件分布(藍方 arm × event)', '', '| arm | ' + ' | '.join(sorted({r['event'] for r in rows})) + ' |', '|---|' + '---|' * len({r['event'] for r in rows})]
evs = sorted({r['event'] for r in rows})
for a in arms:
    rs = [r for r in rows if r['policy'] == a]
    out.append('| %s | ' % a + ' | '.join(str(sum(r['event'] == e for r in rs)) for e in evs) + ' |')
(HERE / 'runs' / 'league_report.md').write_text('\n'.join(out), encoding='utf-8')
print('\n'.join(out))
