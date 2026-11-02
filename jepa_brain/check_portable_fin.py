"""Full-game equivalence: portable fighter.build('tuned2f') vs research arm tuned2f:<F4> (2026-10-26).
Same game flown twice; every scored quantity must be identical.  python check_portable_fin.py [F4R]
F4R (2026-10-27): portable 'tuned2fr' vs research arm tuned2f:<F4>:rec_v2=1, cases include turn-fighters where the
ground recovery is used a lot."""
import sys, types, importlib.util
import common
import pool3  # noqa: F401
import rollout, rollout_bfm
import dcsvet_pool as P
from bfm import FixedTactic

shim = types.ModuleType('controller'); shim.RepairController = common.repair.RepairController
sys.modules['controller'] = shim
spec = importlib.util.spec_from_file_location('fighter', str(common.HERE / 'portable' / 'fighter.py'))
fighter = importlib.util.module_from_spec(spec); sys.modules['fighter'] = fighter; spec.loader.exec_module(fighter)
F4 = (common.HERE / 'runs' / 'eval_fin' / 'F4.txt').read_text().strip()
KEYS = ('event', 'winner', 'ticks', 'atk_b', 'atk_r', 'pos_b', 'pos_r', 'overg_b', 'margin', 'min_agl_m', 'shield_ticks')
orig = rollout_bfm.make_arm


def arm(name):
    if name == 'dev:F4':
        return P.make_blue(F4)
    if name == 'dev:F4R':
        return P.make_blue(F4 + ':rec_v2=1')
    if name == 'dev:T17':
        return P.make_blue('fin4:runs/tune04_fin12d')
    if name == 'dev:V2bRS':
        return P.make_blue('dcsv2frs:runs/bc_v2b_all.npz')
    if name == 'dev:V2R':
        return P.make_blue('dcsv2fr:runs/bc_v2_intent.npz')
    if isinstance(name, str) and name.startswith('port:'):
        return fighter.build(name[5:]), FixedTactic()
    return orig(name)


rollout_bfm.make_arm = arm
ok = True
cases = ((0, 'guide'), (4, 'lag'), (2, 'adv:f1s_2'), (5, 'adv:f2w80_00'), (1, 'pp2'), (3, 'hturn'), (0, 'defender'), (2, 'sacn:25600000'))
dev, port = 'dev:F4', 'port:tuned2f'
if len(sys.argv) > 1 and sys.argv[1] == 'F4R':
    dev, port = 'dev:F4R', 'port:tuned2fr'
    cases = cases + ((1, 'adv:fin2_05'), (3, 'adv:fin2_03'), (0, 'adv:f1s_1'), (4, 'adv:fin1_06'))
if len(sys.argv) > 1 and sys.argv[1] == 'T17':
    dev, port = 'dev:T17', 'port:tuned2t'
    cases = cases + ((1, 'adv:fin2_05'), (3, 'adv:fin2_03'), (0, 'adv:f1s_1'), (4, 'adv:fin1_06'), (2, 'pp0'), (1, 'adv:f4rs_01'), (5, 'adv:fin2_02'))
if len(sys.argv) > 1 and sys.argv[1] == 'V2bRS':    # v2b + shield (portable profile dcsv2frs)
    dev, port = 'dev:V2bRS', 'port:dcsv2frs'
    cases = cases + ((1, 'adv:fin2_05'), (3, 'adv:fin2_03'), (0, 'adv:f1s_1'), (4, 'adv:fin1_06'), (2, 'pp0'), (1, 'adv:f4rs_01'))
if len(sys.argv) > 1 and sys.argv[1] == 'V2R':      # DCS v2 intent + finisher F4R (portable profile dcsv2fr)
    dev, port = 'dev:V2R', 'port:dcsv2fr'
    cases = cases + ((1, 'adv:fin2_05'), (3, 'adv:fin2_03'), (0, 'adv:f1s_1'), (4, 'adv:fin1_06'))
for i, red in cases:
    cfg = dict(rollout.game_config(i, 7200000, red, 18000), host_fidelity=True)
    a = rollout_bfm.play_game(cfg, dev)
    b = rollout_bfm.play_game(cfg, port)
    same = all(a.get(k) == b.get(k) for k in KEYS)
    ok &= same
    print('%-14s %s  event %s/%s margin %s / %s' % (red, 'IDENTICAL' if same else 'DIFFERENT', a['event'], b['event'], a['margin'], b['margin']), flush=True)
print('ALL IDENTICAL' if ok else 'MISMATCH FOUND')
