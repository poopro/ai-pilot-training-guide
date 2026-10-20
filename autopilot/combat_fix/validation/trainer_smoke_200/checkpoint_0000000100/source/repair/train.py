"""Bounded 15-Hz SAC training with 60-Hz flight control.

Compatible resume retains training state, then starts a fresh episode. It does
not claim to resume a simulator pose or reproduce a previous RNG stream.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import time
import uuid

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from artifacts import (ROOT, BASE, FORMAT, DECISION_REPEAT, PHYSICS_HZ, DECISION_HZ,
                       atomic_json, contract_sources, contract_fingerprint,
                       file_hash, load_policy, read_manifest, save_bundle, snapshot_sources)

GAMMA = .999
REWARD_GAMMA = GAMMA ** (1 / DECISION_REPEAT)
torch.set_num_threads(1)


class BurnInSAC(SAC):
    """Keep actor weights/optimizer untouched while a fresh critic warms up."""
    critic_burnin_updates = 500

    def _sample_action(self, learning_starts, action_noise=None, n_envs=1):
        if self.num_timesteps < learning_starts:
            action = self.predict(self._last_obs, deterministic=True)[0]
            return action, self.policy.scale_action(action)
        return super()._sample_action(learning_starts, action_noise, n_envs)

    def train(self, gradient_steps, batch_size=64):
        burn = min(gradient_steps, max(0, self.critic_burnin_updates - self._n_updates))
        if burn:
            original_step = self.actor.optimizer.step
            self.actor.optimizer.step = lambda closure=None: None
            try:
                super().train(burn, batch_size)
            finally:
                self.actor.optimizer.step = original_step
        if gradient_steps > burn:
            super().train(gradient_steps - burn, batch_size)


class DecisionHold(gym.Wrapper):
    """Four fresh-OBS physics ticks per held residual; stage changes at resets."""
    def __init__(self, factory, seed, rear_decisions=8000, maneuver_decisions=8000,
                 counters=None, curriculum=True):
        self.factory = factory
        self.seed_rng = np.random.default_rng(seed)
        self.rear_decisions, self.maneuver_decisions = rear_decisions, maneuver_decisions
        self.curriculum = curriculum
        self.counters = counters or {'decision_steps': 0, 'physics_ticks': 0, 'episodes': 0, 'stages': {}}
        self.active_stage = self.stage_for(self.counters['decision_steps'])
        super().__init__(factory(self.active_stage))

    def stage_for(self, decisions):
        if not self.curriculum:
            return 'official'
        if decisions < self.rear_decisions:
            return 'rear'
        if decisions < self.rear_decisions + self.maneuver_decisions:
            return 'maneuver'
        return 'official'

    def reset(self, *, seed=None, options=None):
        desired = self.stage_for(self.counters['decision_steps'])
        if desired != self.active_stage:
            self.env.close()
            self.env = self.factory(desired)
            self.active_stage = desired
        actual_seed = seed if seed is not None else int(self.seed_rng.integers(0, 2**31 - 1))
        # Random official 3/6/9-kft entry; curriculum replaces geometry itself.
        self.env.distance_ft = int(self.seed_rng.choice([3000, 6000, 9000]))
        obs, info = self.env.reset(seed=actual_seed, options=options)
        info['training_stage'] = self.active_stage
        return obs, info

    def step(self, action):
        reward_total, ticks = 0., 0
        for index in range(DECISION_REPEAT):
            obs, reward, terminated, truncated, info = self.env.step(action)
            reward_total += REWARD_GAMMA ** index * reward
            ticks += 1
            if terminated or truncated:
                break
        self.counters['decision_steps'] += 1
        self.counters['physics_ticks'] += ticks
        stage_counts = self.counters['stages'].setdefault(self.active_stage, {'decisions': 0, 'physics_ticks': 0})
        stage_counts['decisions'] += 1
        stage_counts['physics_ticks'] += ticks
        self.counters['episodes'] += int(terminated or truncated)
        info.update(training_stage=self.active_stage, decision_repeat=DECISION_REPEAT,
                    physics_ticks_this_decision=ticks)
        return obs, reward_total, terminated, truncated, info


def initialize_actor(model, old=None):
    if old is None:
        with torch.no_grad():
            model.actor.mu.weight.zero_()
            model.actor.mu.bias.zero_()
            model.actor.log_std.weight.zero_()
            model.actor.log_std.bias.fill_(-2)
    else:
        if old.observation_space.shape != model.observation_space.shape or old.action_space.shape != model.action_space.shape:
            raise ValueError('舊 actor 輸入／輸出維度不相容')
        model.actor.load_state_dict(old.actor.state_dict(), strict=True)
    checks = {'actor_source': 'zero' if old is None else 'actor_only_warm_start',
              'new_replay_empty': model.replay_buffer.size() == 0,
              'new_actor_optimizer_empty': not model.actor.optimizer.state,
              'new_critic_optimizer_empty': not model.critic.optimizer.state,
              'new_update_count_zero': model._n_updates == 0, 'new_timesteps_zero': model.num_timesteps == 0,
              'critic_reused': False, 'old_replay_reused': False}
    if old is not None:
        checks['actor_weights_exactly_copied'] = all(torch.equal(value.detach().cpu(),
            model.actor.state_dict()[name].detach().cpu()) for name, value in old.actor.state_dict().items())
    required = [key for key in checks if key.startswith('new_')]
    if not all(checks[key] for key in required) or checks.get('actor_weights_exactly_copied') is False:
        raise ValueError('actor-only 初始化驗證失敗')
    return checks


class ProgressAndSave(BaseCallback):
    def __init__(self, folder, config, held_env, deadline, stop_file, checkpoint_decisions, checkpoint_seconds):
        super().__init__()
        self.folder, self.config, self.held_env = folder, config, held_env
        self.deadline, self.stop_file = deadline, stop_file
        self.period, self.seconds = checkpoint_decisions, checkpoint_seconds
        self.last_heartbeat = 0.
        self.last_save = time.monotonic()
        self.reason = 'completed'

    def _on_training_start(self):
        self.next_save = self.model.num_timesteps + self.period

    def write_progress(self, phase):
        atomic_json(self.folder / 'progress.json', {'status': phase, 'pid': os.getpid(),
                    'decision_steps': int(self.model.num_timesteps), 'target_decisions': int(self.model._total_timesteps),
                    'physics_ticks': self.held_env.counters['physics_ticks'],
                    'critic_updates': self.model._n_updates,
                    'actor_updates': max(0, self.model._n_updates - self.model.critic_burnin_updates),
                    'training_stage': self.held_env.active_stage, 'stop_file': str(self.stop_file),
                    'heartbeat_epoch': time.time(), 'official_validation': False})

    def _on_step(self):
        now = time.monotonic()
        if now - self.last_heartbeat >= 15:
            self.write_progress('training')
            print(f'修復訓練 decision {self.model.num_timesteps}/{self.model._total_timesteps}；'
                  f'critic更新 {self.model._n_updates}；stage {self.held_env.active_stage}', flush=True)
            self.last_heartbeat = now
        for info in self.locals.get('infos', []):
            if 'episode' in info:
                episode = {**info['episode'], **{key: info.get(key) for key in
                           ('outcome', 'attack_seconds', 'enemy_attack_seconds', 'survived', 'is_kill',
                            'training_stage', 'p2_type', 'spawn_distance_ft')}}
                with (self.folder / 'episodes.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(episode, ensure_ascii=False) + '\n')
        if self.stop_file.exists():
            self.reason = 'stopped_by_user'
            return False
        if now >= self.deadline:
            self.reason = 'time_limit'
            return False
        if self.model.num_timesteps >= self.next_save or now - self.last_save >= self.seconds:
            self.write_progress('saving')
            save_bundle(self.model, self.folder, self.config, self.held_env.counters)
            self.next_save = self.model.num_timesteps + self.period
            self.last_save = time.monotonic()
        return True


def parser():
    cli = argparse.ArgumentParser(description='修復版 SAC：15Hz決策／60Hz飛控，有時間上限和完整存檔')
    cli.add_argument('--decisions', '--steps', dest='decisions', type=int, default=30000,
                     help='本次新增 decision 數；每個 decision 至多4個60Hz tick')
    cli.add_argument('--max-minutes', type=float, default=15.)
    cli.add_argument('--actor-from', type=Path, help='只移植 actor；控制器已改，僅作 warm start')
    cli.add_argument('--resume', type=Path, help='僅接續相同新契約的修復版完整存檔')
    cli.add_argument('--p2', choices=['rule', 'rl', 'mixed'], default='mixed')
    cli.add_argument('--red-bundle', type=Path)
    cli.add_argument('--rear-decisions', type=int, default=8000)
    cli.add_argument('--maneuver-decisions', type=int, default=8000)
    cli.add_argument('--no-curriculum', action='store_true')
    cli.add_argument('--learning-starts', type=int, default=1000)
    cli.add_argument('--critic-burnin-updates', type=int, default=500)
    cli.add_argument('--buffer-size', type=int, default=50000)
    cli.add_argument('--batch-size', type=int, default=128)
    cli.add_argument('--episode-physics-ticks', type=int, default=18000,
                     help='訓練回合上限；短程驗證可設200，正式完整回合為18000')
    cli.add_argument('--checkpoint-decisions', '--checkpoint-steps', dest='checkpoint_decisions', type=int, default=5000)
    cli.add_argument('--checkpoint-seconds', type=float, default=300.)
    cli.add_argument('--device', choices=['cuda', 'cpu', 'auto'], default='cuda')
    cli.add_argument('--seed', type=int, default=20266000)
    cli.add_argument('--run-dir', type=Path)
    cli.add_argument('--stop-file', type=Path)
    return cli


def main():
    cli = parser()
    args = cli.parse_args()
    if args.resume and args.actor_from:
        cli.error('完整新契約續跑與 actor-only 移植擇一')
    if min(args.decisions, args.max_minutes, args.buffer_size, args.batch_size,
           args.checkpoint_decisions, args.checkpoint_seconds) <= 0:
        cli.error('步數、時間、容量與儲存間隔須為正數')
    if min(args.rear_decisions, args.maneuver_decisions, args.learning_starts, args.critic_burnin_updates) < 0:
        cli.error('課程與暖身數不可為負數')
    if not 1 <= args.episode_physics_ticks <= 18000:
        cli.error('episode-physics-ticks 須為1到18000')
    if args.device == 'cuda' and not torch.cuda.is_available():
        cli.error('CUDA 不可用；診斷可指定 --device cpu')
    from env import RepairDuel, DEFAULT_BUNDLE, REWARD_CONFIG
    red_bundle = args.red_bundle or DEFAULT_BUNDLE
    contract = {'source_sha256': contract_sources(), 'controller': 'repair', 'reward_profile': 'precision',
                'reward_gamma': REWARD_GAMMA, 'gamma': GAMMA, 'decision_repeat': DECISION_REPEAT,
                'physics_hz': PHYSICS_HZ, 'decision_hz': DECISION_HZ, 'attack_angle_deg': 1.,
                'observation_shape': [20], 'action_shape': [4], 'p2_pool': args.p2,
                'red_model_sha256': file_hash(red_bundle / 'model.zip') if args.p2 != 'rule' else None,
                'curriculum': not args.no_curriculum, 'stage_boundaries': [args.rear_decisions,
                    args.rear_decisions + args.maneuver_decisions], 'stage_transition': 'next_episode_reset',
                'mixed_probabilities': [.75, .25], 'rear_maneuver_p2': 'rule',
                'distance_schedule_ft': [3000, 6000, 9000],
                'episode_physics_ticks': args.episode_physics_ticks,
                'base_config': json.loads((BASE / 'combat_v3/config.json').read_text(encoding='utf-8')),
                'reward_config': dict(REWARD_CONFIG),
                'actor_semantics': 'repair_bounded_residual_hold4', 'net_arch': [128, 128],
                'learning_rate': 5e-5, 'train_freq': 4, 'gradient_steps': 1, 'ent_coef': .001,
                'buffer_size': args.buffer_size, 'batch_size': args.batch_size,
                'learning_starts': args.learning_starts, 'critic_burnin_updates': args.critic_burnin_updates}
    fingerprint = contract_fingerprint(contract)
    previous = None
    if args.resume:
        previous = read_manifest(args.resume, verify_replay=True)
        if previous['environment_fingerprint'] != fingerprint or previous['contract'] != contract:
            cli.error('只能續跑完全相同的新契約；改設定請使用 actor-from')
    folder = args.run_dir or ROOT / 'training' / ('run_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4])
    if folder.exists():
        cli.error('run-dir 已存在，不覆蓋')
    folder.mkdir(parents=True)
    stop_file = args.stop_file or folder / 'STOP'
    config = {'contract': contract, 'environment_fingerprint': fingerprint, 'format': FORMAT,
              'actor_from': str(args.actor_from) if args.actor_from else None,
              'resume_parent': str(args.resume) if args.resume else None,
              'red_bundle': str(red_bundle) if args.p2 != 'rule' else None,
              'requested_decisions': args.decisions, 'max_minutes': args.max_minutes, 'seed': args.seed,
              'decision_repeat': DECISION_REPEAT, 'physics_hz': PHYSICS_HZ, 'decision_hz': DECISION_HZ,
              'stop_file': str(stop_file), 'run_status': 'initializing', 'official_validation': False,
              'old_critic_reused': False, 'old_replay_reused': False,
              'new_contract_critic_reused': bool(args.resume), 'new_contract_replay_reused': bool(args.resume)}
    atomic_json(folder / 'config.json', config)
    snapshot_sources(folder / 'source')
    started = time.monotonic()
    model = vector_env = held_env = callback = None
    failure = None
    try:
        red = load_policy(red_bundle) if args.p2 != 'rule' else None
        def factory(stage):
            return RepairDuel(controller='repair', reward_profile='precision', stage=stage,
                              reward_gamma=REWARD_GAMMA, p2=args.p2 if stage == 'official' else 'rule',
                              policy=red, attack_angle=1., max_steps=args.episode_physics_ticks)
        counters = previous['counters'] if previous else None
        held_env = DecisionHold(factory, args.seed, args.rear_decisions, args.maneuver_decisions,
                                counters, not args.no_curriculum)
        vector_env = DummyVecEnv([lambda: Monitor(held_env, str(folder / 'monitor'))])
        if args.resume:
            model = BurnInSAC.load(str(args.resume / 'model.zip'), env=vector_env, device=args.device)
            model.load_replay_buffer(str(args.resume / 'replay.pkl'))
            config['transfer_checks'] = previous['config'].get('transfer_checks')
        else:
            model = BurnInSAC('MlpPolicy', vector_env, learning_rate=5e-5,
                             buffer_size=args.buffer_size, learning_starts=args.learning_starts,
                             batch_size=args.batch_size, gamma=GAMMA, train_freq=4, gradient_steps=1,
                             ent_coef=.001, policy_kwargs={'net_arch': [128, 128]},
                             device=args.device, seed=args.seed, verbose=1)
            model.critic_burnin_updates = args.critic_burnin_updates
            old = load_policy(args.actor_from) if args.actor_from else None
            config['transfer_checks'] = initialize_actor(model, old)
        config.update(run_status='training', start_decisions=int(model.num_timesteps), device=str(model.device))
        atomic_json(folder / 'config.json', config)
        callback = ProgressAndSave(folder, config, held_env, started + args.max_minutes * 60,
                                   stop_file, args.checkpoint_decisions, args.checkpoint_seconds)
        model.learn(total_timesteps=args.decisions, callback=callback, reset_num_timesteps=not bool(args.resume), log_interval=1)
        config['run_status'] = callback.reason
    except KeyboardInterrupt:
        config['run_status'] = 'interrupted'
        print('收到 Ctrl+C，正在保存完整模型與 replay。', flush=True)
    except Exception as error:
        config['run_status'] = 'failed'
        config['error'] = repr(error)
        failure = error
    finally:
        if model is not None:
            try:
                if callback is not None:
                    callback.write_progress('saving_final')
                final = save_bundle(model, folder, config, held_env.counters, 'final')
                config['final_bundle'] = str(final)
            except Exception as error:
                config['run_status'] = 'save_failed'
                config['save_error'] = repr(error)
                failure = error
        config['wall_seconds'] = time.monotonic() - started
        atomic_json(folder / 'config.json', config)
        result = {'status': config['run_status'], 'run_dir': str(folder),
                  'final_bundle': config.get('final_bundle'), 'decision_repeat': DECISION_REPEAT,
                  'decision_steps': int(model.num_timesteps) if model else 0,
                  'physics_ticks': held_env.counters['physics_ticks'] if held_env else 0,
                  'critic_updates': model._n_updates if model else 0,
                  'actor_updates': max(0, model._n_updates - model.critic_burnin_updates) if model else 0,
                  'stop_file': str(stop_file), 'wall_seconds': config['wall_seconds'], 'official_validation': False}
        atomic_json(folder / 'result.json', result)
        if vector_env is not None:
            vector_env.close()
        print(json.dumps(result, ensure_ascii=False), flush=True)
    if failure is not None:
        raise failure


if __name__ == '__main__':
    main()
