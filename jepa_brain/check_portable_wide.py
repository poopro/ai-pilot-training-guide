"""Full-game equivalence: portable/fighter.py profiles vs the research pilots (2026-10-23).
  python check_portable_wide.py
For each case the SAME game (seed, geometry, opponent) is flown twice, once with the research pilot and once with
portable fighter.build(profile); every scored quantity must be identical.
Cases: tuned2 (regression: the generator change must not alter it) and tuned2w:80 vs wide_pilot.make_wide(80).
"""
import sys, types, importlib.util
import common
import pool3  # noqa: F401  (adv:<name> opponents)
import rollout, rollout_bfm
import wide_pilot
from bfm import FixedTactic

shim = types.ModuleType('controller'); shim.RepairController = common.repair.RepairController
sys.modules['controller'] = shim
spec = importlib.util.spec_from_file_location('fighter', str(common.HERE / 'portable' / 'fighter.py'))
fighter = importlib.util.module_from_spec(spec); sys.modules['fighter'] = fighter; spec.loader.exec_module(fighter)

KEYS = ('event', 'winner', 'ticks', 'atk_b', 'atk_r', 'pos_b', 'pos_r', 'overg_b', 'margin', 'min_agl_m', 'shield_ticks')
orig = rollout_bfm.make_arm


def arm(name):
    if name == 'dev:tuned2':
        return orig({'params': wide_pilot.tuned2_params()})
    if name.startswith('dev:tuned2w:'):
        return wide_pilot.make_wide(float(name.split(':')[2]))
    if name.startswith('port:'):
        return fighter.build(name[5:]), FixedTactic()
    return orig(name)


rollout_bfm.make_arm = arm
ok = True
for dev, port in (('dev:tuned2', 'port:tuned2'), ('dev:tuned2w:80', 'port:tuned2w:80')):
    for i, red in ((0, 'guide'), (4, 'lag'), (2, 'adv:f1s_2'), (5, 'adv:f1s_0'), (1, 'pp2')):
        cfg = dict(rollout.game_config(i, 7100000, red, 18000), host_fidelity=True)
        a = rollout_bfm.play_game(cfg, dev)
        b = rollout_bfm.play_game(cfg, port)
        same = all(a[k] == b[k] for k in KEYS)
        ok &= same
        print('%-16s %-10s %s  margin %s / %s' % (port, red, 'IDENTICAL' if same else 'DIFFERENT', a['margin'], b['margin']), flush=True)
print('ALL IDENTICAL' if ok else 'MISMATCH FOUND')
