"""rollout.py plus the official 314.4M SAC red opponent ('sac314'), without touching rollout.py.

  python rollout_sac.py smoke_sac
  python rollout_sac.py eval --opponents sac314 --n 12 --seed0 900000 --out runs/eval_baseline_sac [--model brain_v1.pt]
  python rollout_sac.py collect --opponents sac314,mix,lead --games 240 --seed0 700000 --out runs/collect02
Spawned pool workers re-import this file, so the patch below is active in every process.
"""
import sys, json, time
import rollout
from sac_red import OfficialSacPlayer

_Original = rollout.ScriptedRed


class _Wrap:
    def __init__(self, kind, seed):
        self.kind = kind
        self.inner = OfficialSacPlayer() if kind == 'sac314' else _Original(kind, seed)

    def act(self, obs, tick):
        return self.inner.act(obs, tick)


rollout.ScriptedRed = _Wrap

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'smoke_sac':
        t0 = time.time()
        cfg = dict(rollout.game_config(0, 1, 'sac314', 3600), host_fidelity=True)
        res = rollout.play_game(cfg, {'type': 'baseline'})
        print(json.dumps(res, ensure_ascii=False, indent=1))
        print('SMOKE_SAC OK in %.1fs' % (time.time() - t0))
    else:
        rollout.main()
