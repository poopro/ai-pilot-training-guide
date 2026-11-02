"""Play arena games and write Tacview ACMI 2.2 files (open with Tacview; drag the file in).

  python acmi_export.py OUTDIR --blue tuned2 --reds guide,lag,defender,pp2,jink --games 6
Writes one .acmi per game plus index.json (winner, event, kill time, attack ticks).
"""
import sys, json, math, argparse, datetime
from pathlib import Path
import numpy as np
import pool3  # noqa: F401  adv:/sacn: opponents
import dcsvet_pool as P            # registers all red kinds (pool2, sac, dcsvet)
import rollout
from arena import Arena

FT = .3048


def play_record(cfg, blue, red_kind, weights=None, every=2):
    from opponents import DECISION_TICKS
    arena = Arena(cfg['seed'], cfg['distance_ft'], cfg['side'], cfg['altitude_ft'], host_fidelity=True)
    pilot, pol = P.make_blue(blue, weights)
    if pol is not None and hasattr(pol, 'reset'):
        pol.reset(cfg)
    red = rollout.ScriptedRed(red_kind, cfg['seed'] + 1)
    frames, events = [], []
    done = False
    prev_atk = [0, 0]
    while not done and arena.tick < cfg['max_ticks']:
        ob = arena.obs_blue(); orr = arena.obs_red()
        if pol is not None and arena.tick % DECISION_TICKS == 0:
            pilot.set_tactic(int(pol.decide(None, ob, arena)))
        bcmd, _ = pilot.act(ob)
        done = arena.step(bcmd, red.act(orr, arena.tick))
        j = arena.judge
        for k, nm in ((0, 'BLUE'), (1, 'RED')):
            a = j.attack[k]
            if a > 0 and prev_atk[k] == 0:
                events.append((arena.tick / 60., '%s nose-on (1 deg cone, 500-3000 ft)' % nm))
            for m in (60, 120):
                if a >= m > prev_atk[k]:
                    events.append((arena.tick / 60., '%s attack %d/180 frames' % (nm, m)))
            prev_atk[k] = a
        if arena.tick % every == 0 or done:
            frames.append((arena.tick / 60., ob.copy(), orr.copy(), arena.geo['distance_m']))
    snap = arena.judge.snapshot()
    events.append((arena.tick / 60., 'END %s winner=%s' % (snap['event'], snap['winner'])))
    return frames, events, snap


def write_acmi(path, frames, events, title, blue_name, red_name, winner):
    ref = datetime.datetime(2026, 11, 7, 9, 0, 0)
    L = ['FileType=text/acmi/tacview', 'FileVersion=2.2',
         '0,ReferenceTime=%sZ' % ref.strftime('%Y-%m-%dT%H:%M:%S'),
         '0,Title=%s' % title, '0,Author=Nailong Aerospace Research Group (JSBSim arena)',
         '0,Comments=%s' % title]
    L.append('#0')
    L.append('101,Name=F-16C,Type=Air+FixedWing,Color=Blue,Coalition=Blue,Pilot=%s,CallSign=BLUE' % blue_name)
    L.append('102,Name=F-16C,Type=Air+FixedWing,Color=Red,Coalition=Red,Pilot=%s,CallSign=RED' % red_name)
    ev = sorted(events)
    ei = 0
    for t, ob, orr, d in frames:
        L.append('#%.3f' % t)
        while ei < len(ev) and ev[ei][0] <= t + 1e-9:
            L.append('0,Event=Message|101|%s' % ev[ei][1].replace(',', ';'))
            ei += 1
        for oid, o in ((101, ob), (102, orr)):
            L.append('%d,T=%.7f|%.7f|%.1f|%.1f|%.1f|%.1f,IAS=%.1f,AOA=%.1f' %
                     (oid, o[1], o[0], o[2] * FT, o[3], o[4], o[5], o[12] * FT, o[18]))
    if winner in ('blue', 'red'):
        loser = 102 if winner == 'blue' else 101
        L.append('0,Event=Destroyed|%d|' % loser)
    Path(path).write_text('\n'.join(L) + '\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--blue', default='tuned2')
    ap.add_argument('--reds', default='guide,lag,defender,pp2,jink')
    ap.add_argument('--games', type=int, default=6)
    ap.add_argument('--seed', type=int, default=990000)
    ap.add_argument('--weights', default=None)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    idx = []
    for red in a.reds.split(','):
        for i in range(a.games):
            cfg = P.game_cfg(a.seed + i, i)
            frames, events, snap = play_record(cfg, a.blue, red, a.weights)
            name = '%s_vs_%s_%dft_side%+d_s%d.acmi' % (a.blue.replace(':', '-').replace('/', '-'), red.replace(':', '-').replace('/', '-')[:40], cfg['distance_ft'], cfg['side'], cfg['seed'])
            title = '%s (blue) vs %s (red), %d ft abeam side %+d, %s -> %s' % (a.blue, red, cfg['distance_ft'], cfg['side'],
                                                                            snap['event'], snap['winner'])
            write_acmi(out / name, frames, events, title, a.blue, red, snap['winner'])
            ts = snap['total_score'] or snap['advantage']
            row = dict(file=name, red=red, distance_ft=cfg['distance_ft'], side=cfg['side'], event=snap['event'],
                       winner=snap['winner'], t_end=round(snap['ticks'] / 60., 1), atk_b=snap['attack_ticks'][0],
                       atk_r=snap['attack_ticks'][1], margin=round(ts[0] - ts[1], 1))
            idx.append(row)
            print(row, flush=True)
    (out / 'index.json').write_text(json.dumps(idx, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
