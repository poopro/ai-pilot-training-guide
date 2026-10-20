"""Per-second trace of a few games: python diag_game.py <arm> <red> <seed0> <idx,idx,...> [max_ticks]
Writes runs/diag/<arm>__<red>__<seed>.jsonl and prints a 5-second table + tail-chase statistics."""
import sys, json, time, math
import numpy as np
import rollout
import rollout_bfm
from common import HERE
from combat_v3.interface import geometry_from_observation, validate_observation
from arena import Arena
from opponents import DECISION_TICKS


def trace(cfg, arm):
    arena = Arena(cfg['seed'], cfg['distance_ft'], cfg['side'], cfg['altitude_ft'], host_fidelity=True)
    pilot, policy = rollout_bfm.make_arm(arm)
    red = rollout.ScriptedRed(cfg['red'], cfg['seed'] + 1)
    if policy is not None:
        policy.reset(cfg)
    rows = []
    done = False
    while not done and arena.tick < cfg['max_ticks']:
        ob = arena.obs_blue()
        if policy is not None and arena.tick % DECISION_TICKS == 0:
            pilot.set_tactic(int(policy.decide(None, ob, arena)))
        if arena.tick % 60 == 0:
            g = arena.geo
            gg = geometry_from_observation(validate_observation(ob))
            ore = arena.obs_red()
            rows.append(dict(t=arena.tick // 60, d=round(g['distance_m']), ba=round(g['blue_angle_deg'], 1), ra=round(g['red_angle_deg'], 1),
                             asp=round(gg['aspect_proxy_deg'], 1), clos=round(gg['closing_mps'], 1),
                             cas_b=round(float(ob[12]) / 1.6878, 0), cas_r=round(float(ore[12]) / 1.6878, 0),
                             agl_b=round(float(ob[2]) * .3048), agl_r=round(float(ore[2]) * .3048),
                             bank_b=round(float(ob[3])), bank_r=round(float(ore[3])),
                             pos_b=round(arena.judge.position[0]), pos_r=round(arena.judge.position[1])))
        bcmd, _ = pilot.act(ob)
        done = arena.step(bcmd, red.act(arena.obs_red(), arena.tick))
    snap = arena.judge.snapshot()
    return rows, snap


def main():
    arm, red_kind, seed0 = sys.argv[1], sys.argv[2], int(sys.argv[3])
    idxs = [int(x) for x in sys.argv[4].split(',')]
    max_ticks = int(sys.argv[5]) if len(sys.argv) > 5 else 18000
    out = HERE / 'runs' / 'diag'
    out.mkdir(parents=True, exist_ok=True)
    for i in idxs:
        cfg = dict(rollout.game_config(i, seed0, red_kind, max_ticks), host_fidelity=True)
        t0 = time.time()
        rows, snap = trace(cfg, arm)
        safe = red_kind.replace(':', '_')
        (out / ('%s__%s__%d.jsonl' % (arm, safe, cfg['seed']))).write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
        n = len(rows)
        # tail-chase stats: red nose within 30 deg of us, our nose > 90 deg off, range < 1500 m
        tail = sum(1 for r in rows if r['ra'] < 30 and r['ba'] > 90 and r['d'] < 1500)
        mine = sum(1 for r in rows if r['ba'] < 30 and r['ra'] > 90 and r['d'] < 1500)
        nose_on_us = sum(1 for r in rows if r['ra'] < 30 and r['d'] < 1500)
        print('== seed %d idx %d dist %d side %d  event %s winner %s  ticks %d  secs=%d' % (cfg['seed'], i, cfg['distance_ft'], cfg['side'], snap['event'], snap['winner'], snap['ticks'], n))
        print('   red-on-our-tail %d s | we-on-his-tail %d s | red nose on us <30deg & <1500m: %d s | pos %s' % (tail, mine, nose_on_us, [round(x) for x in snap['position_sum']]))
        print('   t    d   ba   ra  asp  clos casB casR aglB aglR bankB bankR  posB  posR')
        for r in rows[::5][:60]:
            print('%4d %5d %4.0f %4.0f %4.0f %5.0f %4.0f %4.0f %4d %4d %4d %4d %5d %5d' % (r['t'], r['d'], r['ba'], r['ra'], r['asp'], r['clos'], r['cas_b'], r['cas_r'], r['agl_b'], r['agl_r'], r['bank_b'], r['bank_r'], r['pos_b'], r['pos_r']), flush=True)
        print('   wall %.1fs' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
