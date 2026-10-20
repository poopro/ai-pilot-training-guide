"""Paired benchmark of the user's idea (U) and the military-style planner (M) against the same
seeds / opponents as runs/eval_baseline. rollout.py is NOT modified.

  python rollout_bfm.py smoke_bfm
  python rollout_bfm.py eval --arms user,user_s --n 12 --seed0 900000 --opponents guide,lead,lag,mix,breaker,level,sac314 --out runs/bfm_user
Arms: base_s (frozen pursue + shield) | user | user_s | mil | mil_s
"""
import argparse, json, sys, time, traceback
from pathlib import Path
import numpy as np
import rollout
import rollout_sac            # patches rollout.ScriptedRed so that kind 'sac314' is the official 314.4M SAC
import pool2                  # chains more kinds on top: weave/jink/vosc/hturn/defender, pp0..5, sac:<N>, sacc:<N>, ctl:<arm>
from common import HERE
from opponents import DECISION_TICKS
from bfm import UserPilot, ShieldedTacticalPilot, MilPolicy, FixedTactic, ParamPilot, DefPilot, DEF_DEFAULT
from tactics import N_TACTICS
from feats import features

ARMS = ('base_s', 'user', 'user_s', 'mil', 'mil_s', 'base_t', 'user_t', 'mil_t', 'user_nz', 'user_nz_t', 'base', 'base_t2', 'base_t3', 'brain_t3', 'brain_t3_m1', 'brain_t3_m3', 'tuned')
TIGHT2 = dict(tcpa_s=1.2, miss_m=35., range_m=700.)
TIGHT3 = dict(tcpa_s=2.0, miss_m=60., range_m=1000.)
TIGHT = dict(tcpa_s=1.5, miss_m=45., range_m=800.)   # shield v2: only a real imminent collision course
ALL_OPP = 'guide,lead,lag,mix,breaker,level,sac314'


class BrainArm:
    """JEPA brain tactician (rollout.BrainPolicy) with explicit plan() settings."""
    needs_feat = True
    def __init__(self, **plan):
        from brain import load_brain
        self.inner = rollout.BrainPolicy(load_brain(str(HERE / 'brain_v1.pt')), **plan)
        self.name = 'brain'
    def reset(self, cfg):
        self.inner.reset(cfg)
    def decide(self, feat, ob, arena):
        return self.inner.decide(feat, ob, arena)


def make_arm(name):
    if isinstance(name, dict):     # {'params': {...}, 'shield': {...}} -> tuned frozen-pursuit law
        return ParamPilot(name.get('params'), shield=name.get('shield', TIGHT3)), FixedTactic()
    if name == 'base_s':
        return ShieldedTacticalPilot(shield=True), FixedTactic()
    if name == 'user':
        return UserPilot(shield=False), None
    if name == 'user_s':
        return UserPilot(shield=True), None
    if name == 'mil':
        return ShieldedTacticalPilot(shield=False), MilPolicy()
    if name == 'mil_s':
        return ShieldedTacticalPilot(shield=True), MilPolicy()
    if name == 'base':           # frozen repair_guide pursuit, no shield (identical to runs/eval_baseline 'baseline')
        return ShieldedTacticalPilot(shield=False), FixedTactic()
    if name in ('base_t2', 'base_t3'):
        p = ShieldedTacticalPilot(shield=False); p.enable_shield(TIGHT2 if name == 'base_t2' else TIGHT3)
        return p, FixedTactic()
    if name in ('brain_t3', 'brain_t3_m1', 'brain_t3_m3'):
        p = ShieldedTacticalPilot(shield=False); p.enable_shield(TIGHT3)
        return p, BrainArm(margin={'brain_t3': .02, 'brain_t3_m1': .1, 'brain_t3_m3': .3}[name])
    if isinstance(name, str) and name.startswith('tdef:'):     # tuned pursuit + tail-chase defence, e.g. tdef:break:hold_s=3:turn_cap=380
        parts = name.split(':')[1:]
        best = json.loads((HERE / 'runs' / 'tune01' / 'best.json').read_text(encoding='utf-8'))['params']
        params, dfn = dict(best), {'mode': parts[0]}
        for kv in parts[1:]:
            k, v = kv.split('=')
            (dfn if k in DEF_DEFAULT else params)[k] = float(v)
        return DefPilot(params, shield=TIGHT3, defense=dfn), FixedTactic()
    if name == 'tuned':          # best parameters found by tune.py
        best = json.loads((HERE / 'runs' / 'tune01' / 'best.json').read_text(encoding='utf-8'))['params']
        return ParamPilot(best, shield=TIGHT3), FixedTactic()
    if name == 'user_nz':        # user's law, boom-and-zoom disabled (pure nose-on + short lead)
        return UserPilot(zoom=False, shield=False), None
    if name == 'user_nz_t':
        p = UserPilot(zoom=False, shield=False); p.enable_shield(TIGHT)
        return p, None
    if name == 'base_t':
        p = ShieldedTacticalPilot(shield=False); p.enable_shield(TIGHT)
        return p, FixedTactic()
    if name == 'user_t':
        p = UserPilot(shield=False); p.enable_shield(TIGHT)
        return p, None
    if name == 'mil_t':
        p = ShieldedTacticalPilot(shield=False); p.enable_shield(TIGHT)
        return p, MilPolicy()
    raise ValueError(name)


def play_game(cfg, arm):
    from arena import Arena
    t0 = time.time()
    arena = Arena(cfg['seed'], cfg['distance_ft'], cfg['side'], cfg['altitude_ft'], host_fidelity=cfg.get('host_fidelity', True))
    pilot, policy = make_arm(arm)
    red = rollout.ScriptedRed(cfg['red'], cfg['seed'] + 1)
    if policy is not None:
        policy.reset(cfg)
    hist = np.zeros(N_TACTICS, dtype=int)
    min_agl = 1e9
    done = False
    while not done and arena.tick < cfg['max_ticks']:
        ob = arena.obs_blue()
        if policy is not None and arena.tick % DECISION_TICKS == 0:
            feat = features(ob, arena.judge.attack[0], arena.tick) if getattr(policy, 'needs_feat', False) else None
            tac = int(policy.decide(feat, ob, arena))
            pilot.set_tactic(tac)
            hist[tac] += 1
        bcmd, _ = pilot.act(ob)
        done = arena.step(bcmd, red.act(arena.obs_red(), arena.tick))
        min_agl = min(min_agl, arena.agl_blue_m())
    snap = arena.judge.snapshot()
    ts = snap['total_score'] or snap['advantage']
    plan_ms = getattr(policy, 'plan_ms', None)
    return dict(seed=cfg['seed'], red=cfg['red'], distance_ft=cfg['distance_ft'], side=cfg['side'],
                altitude_ft=round(cfg['altitude_ft'], 1), policy=(arm if isinstance(arm, str) else 'param'), event=snap['event'], winner=snap['winner'],
                ticks=snap['ticks'], atk_b=snap['attack_ticks'][0], atk_r=snap['attack_ticks'][1],
                pos_b=round(snap['position_sum'][0], 1), pos_r=round(snap['position_sum'][1], 1),
                overg_b=snap['over_g_ticks'][0], margin=round(ts[0] - ts[1], 1), min_agl_m=round(float(min_agl), 1),
                tactics=hist.tolist(), shield_ticks=int(getattr(pilot, 'shield_ticks', 0)), zooms=int(getattr(pilot, 'n_zoom', 0)), def_ticks=int(getattr(pilot, 'n_def_ticks', 0)), def_entries=int(getattr(pilot, 'n_def_entries', 0)),
                plan_ms_mean=round(float(np.mean(plan_ms)), 1) if plan_ms else None,
                plan_ms_max=round(float(np.max(plan_ms)), 1) if plan_ms else None,
                wall_s=round(time.time() - t0, 1), fidelity=arena.fidelity_applied)


def _task(args):
    cfg, arm = args
    try:
        return play_game(cfg, arm)
    except Exception:
        return dict(seed=cfg['seed'], red=cfg['red'], policy=arm, error=traceback.format_exc())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['smoke_bfm', 'eval'])
    ap.add_argument('--arms', default=','.join(ARMS))
    ap.add_argument('--n', type=int, default=12)
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--seed0', type=int, default=900000)
    ap.add_argument('--opponents', default=ALL_OPP)
    ap.add_argument('--out', default='runs/bfm')
    ap.add_argument('--max-ticks', type=int, default=18000)
    a = ap.parse_args()
    if a.mode == 'smoke_bfm':
        for arm in ARMS:
            for red in ('mix', 'sac314'):
                cfg = dict(rollout.game_config(1, 1, red, 1800), host_fidelity=True)
                t0 = time.time()
                r = play_game(cfg, arm)
                print('%-7s vs %-7s %-9s atk %d/%d margin %.1f minAGL %.0f shield %d zoom %d plan_ms %s wall %.1fs tactics %s' % (
                    arm, red, r['event'], r['atk_b'], r['atk_r'], r['margin'], r['min_agl_m'], r['shield_ticks'], r['zooms'], r['plan_ms_mean'], time.time() - t0, r['tactics']), flush=True)
        print('SMOKE_BFM OK')
        return
    arms = [x for x in a.arms.split(',') if x]
    opps = [x for x in a.opponents.split(',') if x]
    tasks = []
    for red in opps:
        for i in range(a.n):
            for arm in arms:
                tasks.append((dict(rollout.game_config(i, a.seed0, red, a.max_ticks), host_fidelity=True), arm))
    out = HERE / a.out
    out.mkdir(parents=True, exist_ok=True)
    results = []
    sink = (out / 'results.jsonl').open('a', encoding='utf-8')
    def handle(res):
        results.append(res)
        sink.write(json.dumps(res, ensure_ascii=False) + '\n'); sink.flush()
        tag = res.get('error', '')[-400:] if 'error' in res else '%s/%s %s winner=%s atk %s/%s margin %s' % (res['policy'], res['red'], res['event'], res['winner'], res['atk_b'], res['atk_r'], res['margin'])
        print('[%d/%d] %s' % (len(results), len(tasks), tag), flush=True)
    if a.workers <= 1:
        for t in tasks:
            handle(_task(t))
    else:
        import multiprocessing as mp
        with mp.get_context('spawn').Pool(a.workers, maxtasksperchild=6) as pool:
            for res in pool.imap_unordered(_task, tasks):
                handle(res)
    sink.close()
    rollout.summarize(results)


if __name__ == '__main__':
    main()
