"""tuned2 with a wider bank limit (2026-10-23).

ParamPilot.act clips the final bank target at +-72 deg whatever bank_lim says, so tuned2 never banks past 72.
WidePilot = the same pursuit law and constants (runs/tune02/best.json) + collision shield v3, with the final
bank clip at `cap` instead. cap = 72 must reproduce tuned2 exactly (checked in check_wide()).
The frozen low-level command() still limits the pull (elevator capped once |Nz| > 8.5 G).
Arm names (eval_pool3.make_arm): 'tuned2w:<cap>', e.g. tuned2w:80.
"""
import json
from common import HERE
from bfm import ShieldMixin, FixedTactic
from adv_red import AdvPilot

TIGHT3 = dict(tcpa_s=2.0, miss_m=60., range_m=1000.)


def tuned2_params():
    return json.loads((HERE / 'runs' / 'tune02' / 'best.json').read_text(encoding='utf-8'))['params']


class WidePilot(ShieldMixin, AdvPilot):
    def __init__(self, params, shield=TIGHT3):
        super().__init__(params)
        if shield:
            self.enable_shield(shield)


def make_wide(cap, params=None):
    p = dict(params or tuned2_params())
    p['bank_cap'] = float(cap)
    return WidePilot(p), FixedTactic()


def check_wide(seed=1300000):
    """cap 72 vs tuned2 on two games: must be identical."""
    import rollout, rollout_bfm
    for i, red in ((0, 'guide'), (4, 'lag')):
        cfg = dict(rollout.game_config(i, seed, red, 18000), host_fidelity=True)
        a = rollout_bfm.play_game(cfg, {'params': tuned2_params()})
        orig = rollout_bfm.make_arm
        rollout_bfm.make_arm = lambda name: make_wide(72) if name == 'w72' else orig(name)
        try:
            b = rollout_bfm.play_game(cfg, 'w72')
        finally:
            rollout_bfm.make_arm = orig
        same = all(a[k] == b[k] for k in ('event', 'winner', 'ticks', 'atk_b', 'atk_r', 'pos_b', 'pos_r', 'margin'))
        print(red, 'tuned2', a['margin'], a['pos_b'], 'w72', b['margin'], b['pos_b'], 'IDENTICAL' if same else 'DIFFERENT', flush=True)


if __name__ == '__main__':
    check_wide()
