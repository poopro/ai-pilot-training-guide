"""Offline equivalence: portable/fighter.py profiles vs the dev pilots on identical synthetic observation streams.
Run from jepa_brain:  python portable/check_equiv_syn.py"""
import sys, types, math, json, importlib.util
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
exec(open(HERE / 'syn_pool2_test.py', encoding='utf-8').read().split('import pool2')[0])   # make_obs, state, ll
_ARGV = list(sys.argv); sys.argv = [sys.argv[0]]
import common                                               # dev env (frozen repair controller, AirCombat_Train_Test on sys.path)
shim = types.ModuleType('controller'); shim.RepairController = common.repair.RepairController
sys.modules['controller'] = shim
spec = importlib.util.spec_from_file_location('fighter', str(HERE / 'portable' / 'fighter.py'))
fighter = importlib.util.module_from_spec(spec); sys.modules['fighter'] = fighter; spec.loader.exec_module(fighter)
# heavy modules (torch/SB3) are stubbed: OpenPilot only needs ParamPilot + geometry
for _n in ('rollout', 'rollout_bfm'):
    _m = types.ModuleType(_n); sys.modules[_n] = _m
sys.modules['rollout_bfm'].TIGHT3 = dict(tcpa_s=2.0, miss_m=60., range_m=1000.)
sys.modules['rollout_bfm'].make_arm = lambda name: None
import rollout_open
rollout_bfm = sys.modules['rollout_bfm']
from bfm import ParamPilot, ShieldedTacticalPilot
from tactics import BREAK_OUT
TIGHT3 = rollout_bfm.TIGHT3
best = json.loads((HERE / 'runs' / 'tune01' / 'best.json').read_text(encoding='utf-8'))['params']
best2 = json.loads((HERE / 'runs' / 'tune02' / 'best.json').read_text(encoding='utf-8'))['params']

def dev_pilot(name):
    if name == 'base':
        return ShieldedTacticalPilot(shield=False)
    if name == 'base_t3':
        p = ShieldedTacticalPilot(shield=False); p.enable_shield(TIGHT3); return p
    if name == 'tuned':
        return ParamPilot(best, shield=TIGHT3)
    if name == 'tuned2':
        return ParamPilot(best2, shield=TIGHT3)
    if name.startswith('tuned_open'):
        return rollout_open.OpenPilot(best, shield=TIGHT3, tactic=BREAK_OUT, secs=float(name.split(':')[1]), only_side=-1)

def scenario(kind, seed, n):
    r = np.random.default_rng(seed)
    side = -1 if kind.endswith('L') else 1
    if kind.startswith('abeam'):
        own = state(0, 0, 4500, 175, 0); en = state(0, side * r.choice([914, 1829, 2743]), 4500, 175, 180)
    elif kind.startswith('hs'):     # straight head-on, small offset, enemy slightly above/below -> exercises the shield
        own = state(0, 0, 4500, 175, 0); en = state(2200, side * 25., 4500 + (20. if kind[2] == 'u' else -20.), 175, 180)
    elif kind.startswith('headon'):
        own = state(0, 0, 4500, 175, 0); en = state(2200, side * 40., 4500, 175, 180)
    else:   # tail
        own = state(0, 0, 4500, 175, 0); en = state(-700, side * 60., 4500, 190, 0)
    phi_t = [0., 0.]; out = []
    for k in range(n):
        if k % 90 == 0 and not kind.startswith('hs'):
            phi_t = [math.radians(r.uniform(-70, 70)), math.radians(r.uniform(-70, 70))]
        for S, pt in ((own, phi_t[0]), (en, phi_t[1])):
            S['phi'] += np.clip(pt - S['phi'], -.02, .02)
            S['psi'] += 9.81 * math.tan(S['phi']) / S['V'] / 60.
            S['gam'] = float(np.clip(S['gam'] + r.normal(0, .002), -.15, .15))
            S['h'] = float(np.clip(S['h'] + S['V'] * math.sin(S['gam']) / 60., 1500, 9000))
            S['x'] += S['V'] * math.cos(S['psi']) / 60.; S['y'] += S['V'] * math.sin(S['psi']) / 60.
        out.append(make_obs(own, en))
    return out

import os
NTICK = int(os.environ.get('NTICK', 600)); SEED0 = int(os.environ.get('SEED0', 0))
KINDS = os.environ.get('KINDS', 'abeamL,abeamR,headonL,headonR,tailL,tailR').split(',')
worst = 0.; n_shield = 0; n_open = 0
for prof in ('base', 'base_t3', 'tuned', 'tuned2', 'tuned_open:6', 'tuned_open:3'):
    for kind in KINDS:
        for seed in range(SEED0, SEED0 + 1):
            obs = scenario(kind, seed, NTICK)
            a, b = dev_pilot(prof), fighter.build(prof)
            md = 0.
            for ob in obs:
                ca, ga = a.act(ob); cb, gb = b.act(ob)
                md = max(md, float(np.max(np.abs(np.asarray(ca) - np.asarray(cb)))))
                assert ga == gb, (prof, kind, seed, 'guard flag differs')
            worst = max(worst, md)
            n_shield += int(getattr(b, 'shield_ticks', 0)); n_open += int(getattr(b, 'n_def_ticks', 0))
            assert md == 0., (prof, kind, seed, md)
print('EQUIV OK  profiles=6 scenarios=6x1 seed=%d ticks=%d  max abs diff = %g  shield ticks seen = %d  opening ticks seen = %d' % (SEED0, NTICK, worst, n_shield, n_open))
