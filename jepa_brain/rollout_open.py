"""Opening-book experiments (separate file: does not touch the modules a running job imports).

  python rollout_open.py eval --arms tuned,topen:break_out:6:side=-1 --n 48 --side -1 --seed0 960000 --opponents sac:25600000 --out runs/open1
Arm 'topen:<tactic>:<secs>[:side=+-1][:param=value]' = tuned pursuit, but for the first <secs> seconds fly <tactic>
(pursue|lead|lag|in|out|hy|ly|extend); only when the enemy starts on that side if side= is given.
"""
import argparse, json, sys, time
import numpy as np
import rollout, rollout_bfm
from common import HERE
from combat_v3.interface import validate_observation, geometry_from_observation
from bfm import ParamPilot, FixedTactic
from tactics import TacticalPilot, PURSUE, LEAD, LAG, BREAK_IN, BREAK_OUT, HIGH_YOYO, LOW_YOYO, EXTEND

TACT = dict(pursue=PURSUE, lead=LEAD, lag=LAG, ind=BREAK_IN, inn=BREAK_IN, out=BREAK_OUT, hy=HIGH_YOYO, ly=LOW_YOYO, extend=EXTEND,
            break_in=BREAK_IN, break_out=BREAK_OUT)
TIGHT3 = rollout_bfm.TIGHT3


class OpenPilot(ParamPilot):
    def __init__(self, params=None, shield=None, tactic=BREAK_OUT, secs=6., only_side=0):
        super().__init__(params, shield)
        self.o_tactic, self.o_ticks, self.only_side = tactic, int(secs * 60), int(only_side)
        self.k = 0
        self.side = None
        self.n_def_ticks = 0

    def act(self, observation, residual=None, started=True):
        if not started:
            return np.array([0., 0., 0., .8]), False
        self.k += 1
        if self.side is None:
            geo = geometry_from_observation(validate_observation(observation))
            self.side = 1 if geo['blue_az_deg'] >= 0 else -1
        if self.k <= self.o_ticks and self.o_tactic != PURSUE and (self.only_side == 0 or self.side == self.only_side):
            self.n_def_ticks += 1
            TacticalPilot.set_tactic(self, self.o_tactic)
            return TacticalPilot.act(self, observation)
        return super().act(observation)


_orig_make_arm = rollout_bfm.make_arm


def make_arm(name):
    if isinstance(name, str) and name.startswith('topen:'):
        parts = name.split(':')[1:]
        best = json.loads((HERE / 'runs' / 'tune01' / 'best.json').read_text(encoding='utf-8'))['params']
        params, side = dict(best), 0
        for kv in parts[2:]:
            k, v = kv.split('=')
            if k == 'side':
                side = int(float(v))
            else:
                params[k] = float(v)
        return OpenPilot(params, shield=TIGHT3, tactic=TACT[parts[0]], secs=float(parts[1]), only_side=side), FixedTactic()
    if name == 'tuned2':      # round-2 tuned parameters (runs/tune02/best.json) + shield v3
        best2 = json.loads((HERE / 'runs' / 'tune02' / 'best.json').read_text(encoding='utf-8'))['params']
        return ParamPilot(best2, shield=TIGHT3), FixedTactic()
    return _orig_make_arm(name)


rollout_bfm.make_arm = make_arm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['eval'])
    ap.add_argument('--arms', required=True)
    ap.add_argument('--n', type=int, default=24)
    ap.add_argument('--side', type=int, default=0, help='only play games whose start side equals this (+1 / -1); 0 = both')
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--seed0', type=int, default=960000)
    ap.add_argument('--opponents', default='sac:25600000')
    ap.add_argument('--out', default='runs/open1')
    ap.add_argument('--max-ticks', type=int, default=18000)
    a = ap.parse_args()
    arms = [x for x in a.arms.split(',') if x]
    opps = [x for x in a.opponents.split(',') if x]
    tasks = []
    for red in opps:
        for i in range(a.n):
            cfg = dict(rollout.game_config(i, a.seed0, red, a.max_ticks), host_fidelity=True)
            if a.side and cfg['side'] != a.side:
                continue
            for arm in arms:
                tasks.append((cfg, arm))
    out = HERE / a.out
    out.mkdir(parents=True, exist_ok=True)
    sink = (out / 'results.jsonl').open('a', encoding='utf-8')
    done = 0
    import multiprocessing as mp
    with mp.get_context('spawn').Pool(a.workers, maxtasksperchild=6) as pool:
        for res in pool.imap_unordered(rollout_bfm._task, tasks):
            done += 1
            sink.write(json.dumps(res, ensure_ascii=False) + '\n'); sink.flush()
            tag = res.get('error', '')[-300:] if 'error' in res else '%s/%s %s winner=%s margin %s' % (res['policy'], res['red'], res['event'], res['winner'], res['margin'])
            print('[%d/%d] %s' % (done, len(tasks), tag), flush=True)
    sink.close()


if __name__ == '__main__':
    main()
