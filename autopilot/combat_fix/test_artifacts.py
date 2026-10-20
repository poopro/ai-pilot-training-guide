"""Focused tests for action timing, actor isolation and artifact rejection."""
import json
from pathlib import Path
import tempfile
import unittest

import gymnasium as gym
from gymnasium.spaces import Box
import numpy as np
import torch

import artifacts
from train import BurnInSAC, DecisionHold, REWARD_GAMMA, initialize_actor


class TinyEnv(gym.Env):
    observation_space = Box(-500., 500., shape=(20,), dtype=np.float32)
    action_space = Box(-1., 1., shape=(4,), dtype=np.float32)

    def __init__(self, stage='rear', terminate_at=None):
        self.stage, self.terminate_at = stage, terminate_at
        self.tick = 0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.tick = 0
        return np.zeros(20, dtype=np.float32), {}

    def step(self, action):
        self.tick += 1
        return np.full(20, self.tick / 100, dtype=np.float32), 1., self.tick == self.terminate_at, False, {}


class RepairTests(unittest.TestCase):
    def test_actor_transfer_never_reuses_critic_or_replay(self):
        kwargs = dict(buffer_size=100, device='cpu', ent_coef=.001,
                      policy_kwargs={'net_arch': [128, 128]})
        old = BurnInSAC('MlpPolicy', TinyEnv(), seed=1, **kwargs)
        new = BurnInSAC('MlpPolicy', TinyEnv(), seed=2, **kwargs)
        with torch.no_grad():
            for value in old.critic.parameters():
                value.fill_(123.)
        old.replay_buffer.add(np.zeros((1, 20), dtype=np.float32), np.zeros((1, 20), dtype=np.float32),
                              np.zeros((1, 4), dtype=np.float32), np.array([1.]), np.array([False]), [{}])
        checks = initialize_actor(new, old)
        self.assertTrue(checks['actor_weights_exactly_copied'])
        self.assertEqual(new.replay_buffer.size(), 0)
        self.assertTrue(any(not torch.equal(value, new.critic.state_dict()[name])
                            for name, value in old.critic.state_dict().items()))
        self.assertNotIn('repair/train.py', artifacts.contract_sources())

    def test_hold_and_early_terminal_tick_count(self):
        held = DecisionHold(lambda stage: TinyEnv(stage), seed=10)
        held.reset(seed=10)
        _, reward, term, trunc, info = held.step(np.zeros(4))
        self.assertAlmostEqual(reward, sum(REWARD_GAMMA**index for index in range(4)))
        self.assertFalse(term or trunc)
        self.assertEqual(info['physics_ticks_this_decision'], 4)
        short = DecisionHold(lambda stage: TinyEnv(stage, terminate_at=2), seed=10)
        short.reset(seed=10)
        _, reward, term, _, _ = short.step(np.zeros(4))
        self.assertTrue(term)
        self.assertAlmostEqual(reward, 1 + REWARD_GAMMA)
        self.assertEqual(short.counters['physics_ticks'], 2)

    def test_stage_changes_only_at_reset(self):
        stages = []
        def factory(stage):
            stages.append(stage)
            return TinyEnv(stage)
        held = DecisionHold(factory, seed=10, rear_decisions=1, maneuver_decisions=1)
        held.reset()
        held.step(np.zeros(4))
        self.assertEqual(held.active_stage, 'rear')
        held.reset()
        self.assertEqual(held.active_stage, 'maneuver')
        held.step(np.zeros(4))
        held.reset()
        self.assertEqual(stages, ['rear', 'maneuver', 'official'])

    def test_fresh_critic_burnin_and_complete_bundle(self):
        model = BurnInSAC('MlpPolicy', TinyEnv(), buffer_size=100, batch_size=8,
                         learning_starts=0, ent_coef=.001, device='cpu',
                         policy_kwargs={'net_arch': [128, 128]}, seed=17)
        model.critic_burnin_updates = 500
        initialize_actor(model)
        before_actor = {name: value.clone() for name, value in model.actor.state_dict().items()}
        before_critic = {name: value.clone() for name, value in model.critic.state_dict().items()}
        for tick in range(32):
            obs = np.full((1, 20), tick / 100, dtype=np.float32)
            model.replay_buffer.add(obs, obs + .01, np.zeros((1, 4), dtype=np.float32),
                                    np.array([.2]), np.array([False]), [{}])
        model._logger = __import__('stable_baselines3.common.logger', fromlist=['configure']).configure(format_strings=[])
        model._current_progress_remaining = 1.
        model.train(500, batch_size=8)
        self.assertEqual(model._n_updates, 500)
        self.assertTrue(all(torch.equal(before_actor[name], value) for name, value in model.actor.state_dict().items()))
        self.assertFalse(model.actor.optimizer.state)
        self.assertTrue(any(not torch.equal(before_critic[name], value) for name, value in model.critic.state_dict().items()))
        model.train(1, batch_size=8)
        self.assertTrue(model.actor.optimizer.state)
        self.assertTrue(any(not torch.equal(before_actor[name], value) for name, value in model.actor.state_dict().items()))
        sources = artifacts.contract_sources()
        contract = {'source_sha256': sources}
        config = {'contract': contract, 'environment_fingerprint': artifacts.contract_fingerprint(contract)}
        counters = {'decision_steps': 0, 'physics_ticks': 0, 'episodes': 0, 'stages': {}}
        with tempfile.TemporaryDirectory() as temporary:
            bundle = artifacts.save_bundle(model, temporary, config, counters, 'test')
            manifest = artifacts.read_manifest(bundle, verify_replay=True)
            self.assertEqual(manifest['decision_repeat'], 4)
            self.assertEqual(manifest['actor_updates'], 1)
            loaded = artifacts.load_policy(bundle)
            self.assertEqual(loaded.combat_fix_manifest['format'], artifacts.FORMAT)
            # A changed environment contract must be refused before model load.
            altered = dict(manifest)
            altered['source_sha256'] = dict(sources)
            altered['source_sha256']['repair/controller.py'] = '0' * 64
            artifacts.atomic_json(bundle / 'manifest.json', altered)
            with self.assertRaises(ValueError):
                artifacts.read_manifest(bundle)
            artifacts.atomic_json(bundle / 'manifest.json', manifest)
            with (bundle / 'replay.pkl').open('ab') as stream:
                stream.write(b'damaged')
            with self.assertRaises(ValueError):
                artifacts.read_manifest(bundle, verify_replay=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
