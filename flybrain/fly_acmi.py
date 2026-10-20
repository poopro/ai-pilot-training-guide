"""Record ONE closed-loop game of the fly pilot (or of your base_t3, for comparison) as a Tacview file (.acmi).

The game is played by exactly the same code path as fly_bfm.py / rollout_bfm.play_game (same Arena, same frozen
repair_guide controller + collision shield v3, same scripted red); the only addition is that the two aircraft's
poses are written out, in the same layout your own envs/jsbsimEnv/jsbsimEnv.py render() uses (lon|lat|alt|roll|pitch|yaw
from fdm.getProperty('pose')).  The fly's tactic switches are written as Tacview messages, so you see WHEN the brain
changed its mind while you watch the flight.

  python fly_acmi.py --readout ro\\dn_g99.npz --prune-cache cache480 --backend numba --pursue-bonus 0.5 ^
         --red lag --index 0 --seed0 950000 --out fly_lag_950000.acmi
  python fly_acmi.py --arm base_t3 --red lag --index 0 --seed0 950000 --out base_lag_950000.acmi     (same game, no fly)

Nothing under jepa_brain/ or campaign_2026/ is modified.
"""
import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
JEPA = ROOT / 'jepa_brain'
for p in (str(JEPA), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

A_ID, B_ID = 'A0001', 'B0001'
DT = 1.0 / 60.0                 # one physics tick


def pose_line(obj_id, fdm, first=None):
    p = fdm.getProperty('pose')                     # same indices as jsbsimEnv.render(): lon=1, lat(geod)=7, alt=2, roll=5, pitch=4, yaw=3
    t = 'T=%.8f|%.8f|%.2f|%.2f|%.2f|%.2f' % (p[1], p[7], p[2], p[5], p[4], p[3])
    return '%s,%s%s' % (obj_id, t, (',' + first) if first else '')


def record(cfg, arm, spec, out_path, every=3, title=None, telemetry=None):
    import numpy as np
    import rollout, rollout_bfm as RB
    from arena import Arena
    from opponents import DECISION_TICKS
    from tactics import N_TACTICS, NAMES
    from feats import features

    t0 = time.time()
    arena = Arena(cfg['seed'], cfg['distance_ft'], cfg['side'], cfg['altitude_ft'], host_fidelity=cfg.get('host_fidelity', True))
    if arm.startswith('fly_t3'):
        import fly_bfm as FB
        pilot = RB.ShieldedTacticalPilot(shield=False)
        pilot.enable_shield(RB.TIGHT3)
        policy = FB.FlyArm(spec)
        blue_name = 'Blue FlyWire fly brain (%s) + shield v3' % ('option tactician' if spec.get('opt') else 'pursue bias %.2f' % spec.get('pursue_bonus', 0.0))
    else:
        pilot, policy = RB.make_arm(arm)
        blue_name = 'Blue ' + arm
    red = rollout.ScriptedRed(cfg['red'], cfg['seed'] + 1)
    if policy is not None:
        policy.reset(cfg)

    frames = {}                                     # tick -> list of lines (events first, then poses)
    rows = []                                       # per-frame telemetry for --telemetry
    def put(tick, line):
        frames.setdefault(tick, []).append(line)

    put(0, pose_line(A_ID, arena.fdm1, 'Type=Air+FixedWing,Name=F-16C,Color=Blue,Pilot=%s' % blue_name))
    put(0, pose_line(B_ID, arena.fdm2, 'Type=Air+FixedWing,Name=F-16C,Color=Red,Pilot=Red %s (scripted)' % cfg['red']))
    put(0, '0,Event=Message|%s|%s vs Red %s, start distance %d ft, altitude %d ft, seed %d' % (
        A_ID, blue_name, cfg['red'], cfg['distance_ft'], round(cfg['altitude_ft']), cfg['seed']))

    hist = np.zeros(N_TACTICS, dtype=int)
    prev = None
    done = False
    min_agl = 1e9
    while not done and arena.tick < cfg['max_ticks']:
        ob = arena.obs_blue()
        if policy is not None and arena.tick % DECISION_TICKS == 0:
            feat = features(ob, arena.judge.attack[0], arena.tick) if getattr(policy, 'needs_feat', False) else None
            tac = int(policy.decide(feat, ob, arena))
            pilot.set_tactic(tac)
            hist[tac] += 1
            if prev is not None and tac != prev:
                put(arena.tick, '0,Event=Message|%s|tactic %s -> %s' % (A_ID, NAMES[prev].upper(), NAMES[tac].upper()))
            prev = tac
        bcmd, _ = pilot.act(ob)
        done = arena.step(bcmd, red.act(arena.obs_red(), arena.tick))
        min_agl = min(min_agl, arena.agl_blue_m())
        if arena.tick % every == 0 or done:
            if telemetry:
                g = arena.geo
                rows.append([arena.tick * DT, g['distance_m'], g['blue_angle_deg'], g['red_angle_deg'],
                             float(arena.fdm1.fdm['accelerations/n-pilot-z-norm']), float(arena.fdm2.fdm['accelerations/n-pilot-z-norm']),
                             float(arena.fdm1.fdm['velocities/vt-fps']) * .3048, float(arena.fdm2.fdm['velocities/vt-fps']) * .3048,
                             float(arena.fdm1.fdm['position/h-sl-ft']) * .3048, float(arena.fdm2.fdm['position/h-sl-ft']) * .3048,
                             float(arena.fdm1.fdm['attitude/theta-deg']), float(arena.fdm1.fdm['attitude/phi-deg']),
                             arena.judge.position[0], arena.judge.position[1], arena.judge.attack[0], arena.judge.attack[1],
                             -1 if prev is None else prev])
            put(arena.tick, pose_line(A_ID, arena.fdm1))
            put(arena.tick, pose_line(B_ID, arena.fdm2))
    snap = arena.judge.snapshot()
    ts = snap['total_score'] or snap['advantage']
    margin = ts[0] - ts[1]
    end = 'END %s, winner %s, blue-red score margin %+.1f, attack ticks blue/red %d/%d, min AGL %.0f m' % (
        snap['event'], snap['winner'], margin, snap['attack_ticks'][0], snap['attack_ticks'][1], min_agl)
    put(arena.tick, '0,Event=Message|%s|%s' % (A_ID, end))
    if snap['event'] in ('blue_kill',):
        put(arena.tick, '0,Event=Destroyed|%s|' % B_ID)
    elif snap['event'] in ('red_kill',):
        put(arena.tick, '0,Event=Destroyed|%s|' % A_ID)

    title = title or '%s vs %s seed %d' % (blue_name, cfg['red'], cfg['seed'])
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', encoding='utf-8-sig', newline='\n') as f:
        f.write('FileType=text/acmi/tacview\nFileVersion=2.1\n')
        f.write('0,ReferenceTime=2026-10-17T00:00:00Z,Title=%s,DataSource=flybrain/fly_acmi.py,DataRecorder=Claude\n' % title.replace(',', ';'))
        f.write('0,Comments=%s\n' % ('; '.join([end, 'tactic decisions ' + ' '.join('%s:%d' % (NAMES[i], hist[i]) for i in range(N_TACTICS))]).replace(',', ';')))
        for tick in sorted(frames):
            f.write('#%.3f\n' % (tick * DT))
            for line in frames[tick]:
                f.write(line + '\n')
    if telemetry:
        import numpy as np
        np.savetxt(telemetry, np.array(rows), delimiter=',', fmt='%.4f',
                   header='t,dist_m,blue_ata,red_ata,g_blue,g_red,tas_blue,tas_red,alt_blue,alt_red,pitch_blue,roll_blue,pos_blue,pos_red,atk_blue,atk_red,tactic', comments='')
    info = dict(seed=cfg['seed'], red=cfg['red'], arm=arm, event=snap['event'], winner=snap['winner'], margin=round(float(margin), 1),
                ticks=arena.tick, atk_b=snap['attack_ticks'][0], atk_r=snap['attack_ticks'][1], min_agl_m=round(float(min_agl), 1),
                tactics=hist.tolist(), frames=len(frames), file=str(out), wall_s=round(time.time() - t0, 1))
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='fly_t3', help='fly_t3 (default) or any rollout_bfm arm, e.g. base_t3')
    ap.add_argument('--readout', default=None)
    ap.add_argument('--opt', default=None, help='option readout from train_branch.py (fly_opt arm; see fly_bfm.py)')
    ap.add_argument('--hold', type=int, default=None); ap.add_argument('--zone', type=float, default=None)
    ap.add_argument('--tau', type=float, default=None); ap.add_argument('--cooldown', type=int, default=3)
    ap.add_argument('--only', default=None)
    ap.add_argument('--prune-cache', default=None)
    ap.add_argument('--backend', default='auto')
    ap.add_argument('--margin', type=float, default=0.01)
    ap.add_argument('--pursue-bonus', type=float, default=0.0)
    ap.add_argument('--feat', action='store_true')
    ap.add_argument('--dt', type=float, default=1.0)
    ap.add_argument('--red', default='lag')
    ap.add_argument('--index', type=int, default=0, help='game index within the opponent (decides distance / side / altitude, seed = seed0 + index)')
    ap.add_argument('--seed0', type=int, default=950000)
    ap.add_argument('--max-ticks', type=int, default=18000)
    ap.add_argument('--every', type=int, default=3, help='write a frame every N physics ticks (3 = 20 Hz, like your combat_v3 evaluate.py)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--telemetry', default=None, help='also write a per-frame CSV (range, nose-to-LOS angles, G, speed, altitude, tactic ...)')
    a = ap.parse_args()
    import rollout
    spec = {}
    if a.arm.startswith('fly_t3'):
        if not a.readout and not a.opt:
            ap.error('--readout or --opt is required for the fly arm')
        spec = dict(readout=str(Path(a.readout).resolve()) if a.readout else None, opt=str(Path(a.opt).resolve()) if a.opt else None,
                    hold=a.hold, zone=a.zone, tau=a.tau, cooldown=a.cooldown, only=[int(x) for x in a.only.split(',')] if a.only else None,
                    prune_cache=str(Path(a.prune_cache).resolve()) if a.prune_cache else None,
                    backend=a.backend, margin=a.margin, pursue_bonus=a.pursue_bonus, passive=False, feat=a.feat, dt=a.dt)
    cfg = dict(rollout.game_config(a.index, a.seed0, a.red, a.max_ticks), host_fidelity=True)
    info = record(cfg, a.arm, spec, a.out, every=a.every, telemetry=a.telemetry)
    print(json.dumps(info, ensure_ascii=False))


if __name__ == '__main__':
    main()
