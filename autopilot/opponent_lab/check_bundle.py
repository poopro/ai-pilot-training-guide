"""Reload a saved local bundle, verify hashes, counters and finite parameters/replay."""
import json
from pathlib import Path
import sys
import numpy as np
import torch
from stable_baselines3 import SAC
from overnight import valid_bundle

torch.set_num_threads(1)
folder = Path(sys.argv[1])
manifest = valid_bundle(folder)
model = SAC.load(str(folder / 'model.zip'), device='cpu')
model.load_replay_buffer(str(folder / 'replay.pkl'))
assert model.num_timesteps == manifest['timesteps']
assert model._n_updates == manifest['n_updates']
assert all(torch.isfinite(p).all() for p in model.policy.parameters())
buffer = model.replay_buffer
count = buffer.size()
assert count == manifest['replay_size']
for array in [buffer.observations, buffer.next_observations, buffer.actions, buffer.rewards, buffer.dones]:
    assert np.isfinite(array[:count]).all()
print(json.dumps({'bundle': str(folder), 'timesteps': model.num_timesteps, 'updates': model._n_updates,
                  'replay_size': count, 'reload_and_finite_check': True}))
