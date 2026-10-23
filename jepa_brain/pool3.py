"""Opponent pool v3 (2026-10-23): adds two opponent kinds on top of pool2, without modifying any older file.

  adv:<name>    adversarial-search opponent (adv_red.AdvRed) with parameters from adv_pool/<name>.json
  sacn:<N>      official-ladder checkpoint model/jsbsim_sac_<N>_steps.zip flown by the pure-numpy actor (sac_np.py; no torch)
  sacx:<path>   any SAC zip with the official train.py interface (e.g. an exploiter checkpoint
                runs/exp_e1/ft_2000000.zip), flown like sac_red.OfficialSacPlayer; <path> is relative to
                this folder or to the official AirCombat_Train_Test folder, or absolute.

Import this module in the MAIN script (spawned workers re-import the main module, so the patch is active there):
  python eval_pool3.py eval --arms base_t3 --opponents adv:f1_00,sacx:runs/exp_e1/ft_2000000.zip --n 24 ...
"""
import json
from pathlib import Path
import rollout
import rollout_bfm           # noqa: F401  installs rollout_sac + pool2 patches first
from common import HERE, BASE

_SAC = {}


def _resolve(p):
    p = Path(p)
    if p.is_absolute():
        return p
    return HERE / p if (HERE / p).exists() else BASE / p


def _load_sac(path):
    key = str(path)
    if key not in _SAC:
        from stable_baselines3 import SAC
        import torch
        torch.set_num_threads(1)
        _SAC[key] = SAC.load(key, device='cpu')
    return _SAC[key]


_NP = {}


class _NpModel:
    """sac_np.SacNumpy behind the SB3 predict() signature used by sac_red.OfficialSacPlayer."""
    def __init__(self, path):
        import sac_np
        key = str(path)
        if key not in _NP:
            _NP[key] = sac_np.SacNumpy(path)
        self.m = _NP[key]

    def predict(self, obs, deterministic=True):
        return self.m.predict(obs, deterministic=True), None


class _Wrap3:
    def __init__(self, kind, seed):
        self.kind = kind
        if kind.startswith('adv:'):
            import adv_red
            spec = json.loads((HERE / 'adv_pool' / (kind[4:] + '.json')).read_text(encoding='utf-8'))
            self.inner = adv_red.AdvRed(adv_red.decode(spec['x']), seed)
        elif kind.startswith('sacx:'):
            from sac_red import OfficialSacPlayer
            self.inner = OfficialSacPlayer(model=_load_sac(_resolve(kind[5:])))
        elif kind.startswith('sacn:'):           # official-ladder checkpoint <N> steps, numpy actor (no torch)
            from sac_red import OfficialSacPlayer
            self.inner = OfficialSacPlayer(model=_NpModel(BASE / 'model' / ('jsbsim_sac_%d_steps.zip' % int(kind[5:]))))
        else:
            self.inner = _Prev3(kind, seed)

    def act(self, obs, tick):
        return self.inner.act(obs, tick)


if getattr(rollout.ScriptedRed, '__name__', '') != '_Wrap3':
    _Prev3 = rollout.ScriptedRed
    rollout.ScriptedRed = _Wrap3
