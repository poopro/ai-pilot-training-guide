import sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
for p in (str(HERE.parent / 'jepa_brain'), str(HERE)):
    sys.path.insert(0, p)
import numpy as np
import fly_bfm, rollout, rollout_bfm as RB

ro, red, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
idx = seed - 1010000
cfg = dict(rollout.game_config(idx, 1010000, red, 18000), host_fidelity=True)
spec = dict(opt=str(Path(ro).resolve()), prune_cache=None, backend=None, hold=None, zone=None, tau=None, cooldown=3, only=None)
LOG = []
orig = RB.make_arm


class Wrap:
    needs_feat = True

    def __init__(self):
        self.inner = fly_bfm.FlyArm(spec)

    def reset(self, c):
        self.inner.reset(c)

    def decide(self, feat, ob, arena):
        t = self.inner.decide(feat, ob, arena)
        g = arena.geo
        LOG.append((arena.tick, g['distance_m'], g.get('closing_mps', 0.), g['blue_angle_deg'], g['red_angle_deg'], int(t)))
        return t


def patched(name):
    if name == 'fly_tuned':
        return fly_bfm.make_tuned_tactical(), Wrap()
    if name == 'fly_t3':
        p = RB.ShieldedTacticalPilot(shield=False); p.enable_shield(RB.TIGHT3)
        return p, Wrap()
    return orig(name)
RB.make_arm = patched
arm = sys.argv[4] if len(sys.argv) > 4 else 'fly_tuned'
r = RB.play_game(cfg, arm)
print({k: r[k] for k in ('event', 'winner', 'margin', 'pos_b', 'pos_r', 'ticks', 'tactics', 'shield_ticks')})
names = ['PUR', 'LEAD', 'LAG', 'BIN', 'BOUT', 'HY', 'LY', 'EXT']
for t, d, c, ba, ra, tac in LOG[-30:]:
    print('tick %5d range %6.0f closing %6.1f ata_b %6.1f ata_r %6.1f  -> %s' % (t, d, c, ba, ra, names[tac]))
