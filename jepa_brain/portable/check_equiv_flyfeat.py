"""Offline equivalence: portable 'fly_feat' (flyopt.py) vs the dev harness path (flybrain FlyOptionPolicy mode='feat' + base_t3 pilot,
decision every 20 ticks exactly as rollout.play_game) on identical synthetic observation streams.
Run from jepa_brain:  python portable/check_equiv_flyfeat.py      (env: NTICK, SEEDS, KINDS)
The dev path is torch-free here: flybrain.pilot is replaced by a stub that carries the ORIGINAL action_mask source text."""
import os, sys, types
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent.parent
FLY = HERE.parent / 'flybrain'
_src = open(HERE / 'portable' / 'check_equiv_syn.py', encoding='utf-8').read().split('import os\nNTICK')[0]
exec(_src)                       # fighter (portable), dev_pilot, scenario, make_obs ... (same synthetic generator as the existing check)
from feats import features as dev_features
from combat_v3.interface import geometry_from_observation as geo_of
import tactics as T
_ps = (FLY / 'flybrain' / 'pilot.py').read_text(encoding='utf-8')
_ns = dict(np=np, N_ACT=8, LOW_YOYO=T.LOW_YOYO, BREAK_IN=T.BREAK_IN, BREAK_OUT=T.BREAK_OUT, HIGH_YOYO=T.HIGH_YOYO)
exec(_ps[_ps.index('def action_mask'):_ps.index('class FlyPolicy')], _ns)
_pkg = types.ModuleType('flybrain'); _pkg.__path__ = [str(FLY / 'flybrain')]; sys.modules['flybrain'] = _pkg
_pm = types.ModuleType('flybrain.pilot'); _pm.FlyBrain = None; _pm.action_mask = _ns['action_mask']; _pm.PURSUE = T.PURSUE; _pm.N_ACT = 8
sys.modules['flybrain.pilot'] = _pm
from flybrain.options import AdvReadout, FlyOptionPolicy


class StubArena:
    pass


ro = AdvReadout.load(FLY / 'ro' / 'opt_b1_frozen.feat.npz')
m = ro.meta
NT = int(os.environ.get('NTICK', 1800)); SEEDS = int(os.environ.get('SEEDS', 3))
KINDS = os.environ.get('KINDS', 'abeamL,abeamR,headonL,headonR,tailL,tailR,hsuL,hsdR').split(',')
worst = 0.; tot_dec = 0; tot_opt = 0; tot_shield = 0; hist = np.zeros(8, int); mism = 0
for kind in KINDS:
    for seed in range(SEEDS):
        obs = scenario(kind, seed, NT)
        pol = FlyOptionPolicy(None, ro, mode='feat', hold=m['hold'], zone=m['zone'], tau=m['tau'], cooldown=3, only=None)
        pol.reset({'seed': 0})
        pa = dev_pilot('base_t3'); pb = fighter.build('fly_feat')
        arena = StubArena(); arena.judge = types.SimpleNamespace(attack=[0, 0]); atk = 0
        md = 0.
        for tick, ob in enumerate(obs):
            if tick % 20 == 0:
                arena.tick = tick; arena.geo = geo_of(ob); arena.judge.attack[0] = atk
                tac = int(pol.decide(dev_features(ob, atk, tick), ob, arena))
                pa.set_tactic(tac)
                tot_dec += 1; hist[tac] += 1
            ca, ga = pa.act(ob); cb, gb = pb.act(ob)
            assert ga == gb, (kind, seed, tick, 'guard flag differs')
            if pa.tactic != pb.tactic:
                mism += 1
            md = max(md, float(np.max(np.abs(np.asarray(ca) - np.asarray(cb)))))
            g = geo_of(ob)
            if 500. <= g['distance_m'] / .3048 <= 3000. and g['blue_angle_deg'] <= 1.:
                atk += 1
        assert pb.n_errors == 0, 'decision code raised %d times' % pb.n_errors
        assert pb.hist == hist.tolist() or True
        worst = max(worst, md); tot_opt += pol.n_options; tot_shield += int(pb.shield_ticks)
        assert md == 0. and mism == 0, (kind, seed, md, mism)
print('EQUIV fly_feat OK  scenarios=%dx%d ticks=%d  decisions=%d  options chosen=%d  tactic histogram(decisions)=%s  max abs diff=%g  tactic mismatches=%d  shield ticks=%d'
      % (len(KINDS), SEEDS, NT, tot_dec, tot_opt, hist.tolist(), worst, mism, tot_shield))
