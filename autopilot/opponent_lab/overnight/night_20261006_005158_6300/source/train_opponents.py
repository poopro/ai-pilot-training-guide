"""Actor transfer into the new P2 lab, or exact-compatible full lab checkpoint resume.

Never loads an old v3 replay/critic into changed scenario/reward dynamics.
One learner, frozen opponents, immutable complete bundles and cooperative stop.
"""
import argparse
from collections import deque
from datetime import datetime, timezone, timedelta
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import sys
import time
import uuid

import numpy as np
import torch
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from duel_lab import BASE, DEFAULT_BUNDLE, DuelLab, file_hash, load_policy

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "latest_training.json"
torch.set_num_threads(1)


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp_" + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def compatible_sources():
    return {
        "base": {name: file_hash(BASE / "combat_v3" / name) for name in
                 ("env.py", "controller.py", "interface.py", "fdm.py", "rules.py", "config.json")},
        "original_fdm": file_hash(BASE / "envs" / "jsbsimEnv" / "jsbsimFdm.py"),
        "lab": file_hash(ROOT / "duel_lab.py"), "trainer": file_hash(Path(__file__)),
    }


class WarmActorSAC(SAC):
    def _sample_action(self, learning_starts, action_noise=None, n_envs=1):
        if self.num_timesteps < learning_starts:
            # Fill the new replay with the retained policy instead of random sticks.
            action = self.predict(self._last_obs, deterministic=True)[0]
            return action, self.policy.scale_action(action)
        return super()._sample_action(learning_starts, action_noise, n_envs)


class TrainingDuel(DuelLab):
    def __init__(self, pool, opponent_policy, angle):
        super().__init__(p2="rule", policy=opponent_policy, attack_angle=angle)
        self.pool = pool
        self.schedule_rng = np.random.default_rng(0)

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self.schedule_rng = np.random.default_rng(seed)
        self.distance_ft = int(self.schedule_rng.choice([3000, 6000, 9000]))
        observation, info = super().reset(seed=seed, options=options)
        self.p2_type = (str(self.schedule_rng.choice(["rule", "rl"], p=[.75, .25]))
                        if self.pool == "mixed" else self.pool)
        info["opponent"] = self.p2_type
        return observation, info

    def step(self, action):
        result = super().step(action)
        result[4]["opponent"] = self.p2_type
        return result


def save_bundle(model, folder, config, label):
    destination = folder / f"{label}_{model.num_timesteps:010d}"
    if destination.exists():
        raise ValueError(f"完整存檔已存在，不覆蓋：{destination}")
    staging = folder / (".saving_" + uuid.uuid4().hex)
    staging.mkdir()
    model.save(str(staging / "model.zip"))
    model.save_replay_buffer(str(staging / "replay.pkl"))
    manifest = {"format": "opponent_lab_sac_v1", "timesteps": model.num_timesteps,
                "n_updates": model._n_updates, "replay_size": model.replay_buffer.size(),
                "model_sha256": file_hash(staging / "model.zip"),
                "replay_sha256": file_hash(staging / "replay.pkl"), "config": config,
                "official_validation": False}
    atomic_json(staging / "manifest.json", manifest)
    staging.rename(destination)
    print(f"已完整儲存：{destination}", flush=True)
    return destination


class ProgressAndSave(BaseCallback):
    def __init__(self, folder, config, period, checkpoint_seconds, deadline, stop_file, publish):
        super().__init__()
        self.folder, self.config, self.period = folder, config, period
        self.seconds, self.deadline, self.stop_file = checkpoint_seconds, deadline, stop_file
        self.publish = publish
        self.episodes = deque(maxlen=100)
        self.last_heartbeat = 0
        self.last_save = time.monotonic()
        self.reason = "completed"

    def _on_training_start(self):
        self.next_save = self.model.num_timesteps + self.period

    def write_progress(self, phase):
        progress = {"status": phase, "run_dir": str(self.folder), "pid": os.getpid(),
                    "timesteps": self.model.num_timesteps, "target": self.model._total_timesteps,
                    "updates": self.model._n_updates, "heartbeat_epoch": time.time(),
                    "stop_file": str(self.stop_file), "episode_samples": len(self.episodes)}
        atomic_json(self.folder / "progress.json", progress)
        if self.publish:
            atomic_json(STATE, progress)

    def _on_step(self):
        now = time.monotonic()
        if now - self.last_heartbeat >= 5:
            self.write_progress("training")
            print(f"新環境進度 {self.model.num_timesteps}/{self.model._total_timesteps}；更新 {self.model._n_updates}", flush=True)
            self.last_heartbeat = now
        for info in self.locals.get("infos", []):
            if "episode" not in info:
                continue
            episode = {**info["episode"], "p2": info["p2_type"],
                       "distance_ft": info["spawn_distance_ft"],
                       "outcome": info["outcome"], "attack_seconds": info["attack_seconds"],
                       "enemy_attack_seconds": info["enemy_attack_seconds"],
                       "survived": info["survived"], "is_kill": info["is_kill"],
                       "own_crash": info["own_crash"]}
            self.episodes.append(episode)
            with (self.folder / "episodes.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(episode, ensure_ascii=False) + "\n")
            print("回合結果：" + json.dumps(episode, ensure_ascii=False), flush=True)
            self.logger.record("episode/sample_count", len(self.episodes))
            for key in ["is_kill", "survived", "own_crash", "attack_seconds", "enemy_attack_seconds"]:
                self.logger.record("episode/" + key + "_last100", float(np.mean([e[key] for e in self.episodes])))
        if self.model.num_timesteps >= self.next_save or now - self.last_save >= self.seconds:
            self.write_progress("saving")
            save_bundle(self.model, self.folder, self.config, "checkpoint")
            self.next_save = self.model.num_timesteps + self.period
            self.last_save = time.monotonic()
        if self.stop_file.exists():
            self.reason = "stopped_by_user"
            return False
        if now >= self.deadline:
            self.reason = "time_limit"
            return False
        return self.model.num_timesteps < self.model._total_timesteps


def main():
    parser = argparse.ArgumentParser(description="沿用第三版策略，對新 P2 學習；改環境時不混用舊 replay／critic")
    parser.add_argument("--steps", type=int, default=100000, help="本次新增步數")
    parser.add_argument("--p2", choices=["rule", "rl", "mixed"], default="mixed")
    parser.add_argument("--actor-from", type=Path, help="僅移植策略；預設使用已驗證的 148682 步第三版")
    parser.add_argument("--fresh-guide", action="store_true", help="消融基準：不沿用舊策略，從零修正開始")
    parser.add_argument("--resume", type=Path, help="同設定接續新對手實驗的完整存檔")
    parser.add_argument("--resume-latest", action="store_true")
    parser.add_argument("--red-bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--attack-angle", choices=[1., 2.], type=float, default=1.)
    parser.add_argument("--learning-starts", type=int, default=5000)
    parser.add_argument("--buffer-size", type=int, default=50000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--checkpoint-steps", type=int, default=20000)
    parser.add_argument("--checkpoint-seconds", type=float, default=300)
    parser.add_argument("--max-minutes", type=float, default=60)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--seed", type=int, default=20266000)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--stop-file", type=Path)
    parser.add_argument("--no-publish", action="store_true", help="驗證用：不改使用者的最新訓練入口")
    args = parser.parse_args()
    if args.resume and args.resume_latest:
        parser.error("resume 和 resume-latest 擇一")
    if (args.resume or args.resume_latest) and (args.actor_from or args.fresh_guide):
        parser.error("完整續跑和策略移植／全新基準擇一")
    if args.actor_from and args.fresh_guide:
        parser.error("actor-from 和 fresh-guide 擇一")
    if min(args.steps, args.buffer_size, args.batch_size, args.checkpoint_steps,
           args.checkpoint_seconds, args.max_minutes) <= 0 or args.learning_starts < 0:
        parser.error("步數、容量、間隔、時間須為正數")
    if args.resume_latest:
        candidates = list((ROOT / "training").glob("run_*/*/manifest.json"))
        candidates = [p for p in candidates if p.parent.name.startswith(("final_", "checkpoint_"))
                      and json.loads(p.read_text(encoding="utf-8"))["format"] == "opponent_lab_sac_v1"]
        if not candidates:
            parser.error("尚無新對手訓練存檔；先使用沿用舊策略的入口")
        args.resume = max(candidates, key=lambda p: p.stat().st_mtime).parent
    actor_source = args.actor_from or DEFAULT_BUNDLE
    sources = compatible_sources()
    red_hash = file_hash(args.red_bundle / "model.zip") if args.p2 != "rule" else None
    signature_data = {"sources": sources, "p2_pool": args.p2, "red_model_sha256": red_hash,
                      "attack_angle": args.attack_angle, "distance_schedule": [3000, 6000, 9000],
                      "mixed_probabilities": [.75, .25], "action_semantics": "v3_bounded_residual"}
    fingerprint = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
    if args.resume:
        previous = json.loads((args.resume / "manifest.json").read_text(encoding="utf-8"))
        if previous["format"] != "opponent_lab_sac_v1" or previous["config"]["environment_fingerprint"] != fingerprint:
            parser.error("這不是相同設定的新對手完整存檔；改設定請改用 actor-from")
        for label, extension in [("model", "zip"), ("replay", "pkl")]:
            if file_hash(args.resume / f"{label}.{extension}") != previous[label + "_sha256"]:
                parser.error("完整存檔校驗失敗")
    taipei = timezone(timedelta(hours=8))
    folder = args.run_dir or ROOT / "training" / (
        "run_" + datetime.now(taipei).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:4])
    if folder.exists():
        parser.error("run-dir 已存在，不覆蓋")
    # Windows releases this file lock if the process exits, including after a crash.
    ROOT.mkdir(parents=True, exist_ok=True)
    lock = (ROOT / "learner.lock").open("a+b")
    lock.seek(0, 2)
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        lock.close()
        parser.error("已有新對手 learner 執行，不重複啟動")
    folder.mkdir(parents=True)
    stop_file = args.stop_file or folder / "STOP"
    config = {"environment_fingerprint": fingerprint, "environment": signature_data,
              "base_source_sha256": sources["base"], "actor_from": None if args.fresh_guide else str(actor_source),
              "resume_parent": str(args.resume) if args.resume else None,
              "red_bundle": str(args.red_bundle) if args.p2 != "rule" else None,
              "new_requested_steps": args.steps, "run_status": "initializing",
              "max_minutes": args.max_minutes, "seed": args.seed,
              "official_validation": False, "critic_reused": bool(args.resume),
              "old_v3_replay_reused": False, "resume_replay_reused": bool(args.resume)}
    atomic_json(folder / "config.json", config)
    if not args.no_publish:
        atomic_json(STATE, {"status": "initializing", "run_dir": str(folder), "pid": os.getpid(),
                            "stop_file": str(stop_file), "heartbeat_epoch": time.time()})
    snapshot = folder / "source"
    snapshot.mkdir()
    for path in [Path(__file__), ROOT / "duel_lab.py"]:
        (snapshot / path.name).write_bytes(path.read_bytes())
    base_snapshot = snapshot / "combat_v3"
    base_snapshot.mkdir()
    for name in sources["base"]:
        (base_snapshot / name).write_bytes((BASE / "combat_v3" / name).read_bytes())
    deadline = time.monotonic() + args.max_minutes * 60
    environment = model = callback = None
    exit_error = None
    try:
        opponent = load_policy(args.red_bundle) if args.p2 != "rule" else None
        environment = DummyVecEnv([lambda: Monitor(TrainingDuel(args.p2, opponent, args.attack_angle),
                                                       str(folder / "monitor"))])
        if args.resume:
            model = WarmActorSAC.load(str(args.resume / "model.zip"), env=environment, device=args.device)
            model.load_replay_buffer(str(args.resume / "replay.pkl"))
            model.tensorboard_log = str(folder / "tensorboard")
            config["transfer_checks"] = previous["config"].get("transfer_checks")
            config["actor_from"] = previous["config"].get("actor_from")
        else:
            model = WarmActorSAC("MlpPolicy", environment, learning_rate=5e-5,
                                 buffer_size=args.buffer_size, learning_starts=args.learning_starts,
                                 batch_size=args.batch_size, gamma=.999, train_freq=8, gradient_steps=1,
                                 ent_coef=.001, policy_kwargs={"net_arch": [128, 128]},
                                 tensorboard_log=str(folder / "tensorboard"), device=args.device,
                                 seed=args.seed, verbose=1)
            if args.fresh_guide:
                with torch.no_grad():
                    model.actor.mu.weight.zero_(); model.actor.mu.bias.zero_()
                    model.actor.log_std.weight.zero_(); model.actor.log_std.bias.fill_(-2)
            else:
                old = opponent if opponent is not None and args.red_bundle.resolve() == actor_source.resolve() else load_policy(actor_source)
                if old.observation_space.shape != model.observation_space.shape or old.action_space.shape != model.action_space.shape:
                    raise ValueError("舊策略輸入／動作維度不符")
                model.actor.load_state_dict(old.actor.state_dict())
                exact = all(torch.equal(value.detach().cpu(), model.actor.state_dict()[name].detach().cpu())
                            for name, value in old.actor.state_dict().items())
                checks = {"actor_weights_exactly_copied": exact,
                          "new_replay_empty": model.replay_buffer.size() == 0,
                          "new_actor_optimizer_empty": len(model.actor.optimizer.state) == 0,
                          "new_critic_optimizer_empty": len(model.critic.optimizer.state) == 0,
                          "new_update_count_zero": model._n_updates == 0,
                          "old_model_timesteps": old.num_timesteps,
                          "new_model_timesteps": model.num_timesteps}
                if not all(checks[key] for key in ["actor_weights_exactly_copied", "new_replay_empty",
                                                   "new_actor_optimizer_empty", "new_critic_optimizer_empty", "new_update_count_zero"]):
                    raise ValueError("策略移植初始化驗證失敗")
                config["transfer_checks"] = checks
                print("已沿用舊策略；critic、optimizer 和 replay 重新建立。", flush=True)
            model.set_random_seed(args.seed)
        config.update(start_timesteps=model.num_timesteps, run_status="training", device=str(model.device),
                      learning_starts=model.learning_starts, buffer_size=model.buffer_size, batch_size=model.batch_size,
                      seed=model.seed)
        atomic_json(folder / "config.json", config)
        callback = ProgressAndSave(folder, config, args.checkpoint_steps, args.checkpoint_seconds,
                                   deadline, stop_file, not args.no_publish)
        model.learn(total_timesteps=args.steps, callback=callback, reset_num_timesteps=not bool(args.resume), log_interval=1)
        config["run_status"] = callback.reason
    except KeyboardInterrupt:
        config["run_status"] = "interrupted"
        print("收到 Ctrl+C，正在保存；請等完整儲存完成。", flush=True)
    except Exception as error:
        config["run_status"] = "failed"
        config["error"] = repr(error)
        exit_error = error
    finally:
        try:
            if model is not None:
                if callback is not None:
                    callback.write_progress("saving_final")
                try:
                    final = save_bundle(model, folder, config, "final")
                    config["final_bundle"] = str(final)
                except Exception as save_error:
                    config["run_status"] = "save_failed"
                    config["save_error"] = repr(save_error)
                    exit_error = save_error
            atomic_json(folder / "config.json", config)
            result = {"status": config["run_status"], "run_dir": str(folder),
                      "final_bundle": config.get("final_bundle"), "pid": os.getpid(),
                      "timesteps": model.num_timesteps if model is not None else 0,
                      "updates": model._n_updates if model is not None else 0,
                      "stop_file": str(stop_file), "heartbeat_epoch": time.time(),
                      "official_validation": False}
            atomic_json(folder / "result.json", result)
            if not args.no_publish:
                atomic_json(STATE, result)
            print("訓練結果：" + str(folder / "result.json"), flush=True)
        finally:
            if environment is not None:
                environment.close()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            lock.close()
    if exit_error is not None:
        raise exit_error


if __name__ == "__main__":
    main()
