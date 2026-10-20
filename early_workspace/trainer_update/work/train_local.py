"""Resumable SAC baseline with Monitor episode statistics and graceful stop."""
from __future__ import annotations
import argparse
from collections import deque
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import uuid
import numpy as np
import torch as th
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.append(os.environ.get("AI_PILOT_ENV_SOURCE", str(Path(__file__).resolve().parent)))
from training_store import candidates, read_json, save_bundle, write_json
from envs.jsbsimEnv import JsbsimEnv


def make_env(rank, logs):
    def init_env():
        return Monitor(JsbsimEnv(config={"rank": rank}), str(Path(logs) / f"env-{rank}"))
    return init_env


def create_envs(count, logs):
    factories = [make_env(i, logs) for i in range(count)]
    return DummyVecEnv(factories) if count == 1 or os.environ.get("USE_DUMMY") == "1" else SubprocVecEnv(factories)


class TrainingMetrics(BaseCallback):
    def __init__(self, run, target, interval, stop_file, resumed_from=None):
        super().__init__()
        self.run, self.target = Path(run), target
        self.interval, self.stop_file = interval, Path(stop_file)
        self.resumed_from = resumed_from
        self.episodes = deque(maxlen=100)
        self.history = deque(maxlen=300)
        self.episode_count = 0
        self.stopped = False
        self.last_write = 0
        self.last_checkpoint = 0
        self.state = "starting"

    def _on_training_start(self):
        self.started = time.monotonic()
        self.start_step = int(self.model.num_timesteps)
        self.last_checkpoint = self.start_step
        self.returns = np.zeros(self.training_env.num_envs)
        self.lengths = np.zeros(self.training_env.num_envs, dtype=int)
        self.state = "running"
        self.publish()

    def _on_step(self):
        self.returns += self.locals["rewards"]
        self.lengths += 1
        for i, info in enumerate(self.locals["infos"]):
            episode = info.get("episode")
            if episode is not None:
                self.episode_count += 1
                record = dict(episode=self.episode_count, step=int(self.model.num_timesteps),
                              reward=float(episode["r"]), length=int(episode["l"]), env=i)
                self.episodes.append(record)
                path = self.run / "episodes.csv"
                with path.open("a", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(record))
                    if stream.tell() == 0:
                        writer.writeheader()
                    writer.writerow(record)
            if self.locals["dones"][i]:
                self.returns[i] = 0
                self.lengths[i] = 0
        if time.monotonic() - self.last_write >= 3:
            self.publish()
        if self.stop_file.exists():
            self.stopped = True
            return False
        return True

    def _on_rollout_end(self):
        # SB3 has stored transitions by this point.
        if self.model.num_timesteps - self.last_checkpoint >= self.interval:
            self.publish("saving")
            saved = save_bundle(self.model, self.run, "periodic")
            self.last_checkpoint = saved["steps"]
            self.publish("running")

    def publish(self, state=None, checkpoint=None, error=None):
        if state:
            self.state = state
        self.last_write = time.monotonic()
        elapsed = max(.001, self.last_write - self.started)
        step = int(self.model.num_timesteps)
        mean = lambda key: sum(x[key] for x in self.episodes) / len(self.episodes) if self.episodes else None
        payload = dict(run_id=self.run.name, step=step, total_steps=self.target,
                       start_step=self.start_step, session_steps=step-self.start_step,
                       progress=min(1., step/self.target), fps=(step-self.start_step)/elapsed,
                       elapsed_seconds=elapsed, updated_epoch=time.time(),
                       updated_at=datetime.now(timezone.utc).isoformat(), state=self.state,
                       mean_reward=mean("reward"), mean_episode_length=mean("length"),
                       episodes_completed=self.episode_count, reward_window=len(self.episodes),
                       current_episode_rewards=self.returns.tolist(),
                       current_episode_lengths=self.lengths.tolist(),
                       resumed_from=self.resumed_from, checkpoint=checkpoint, error=error, losses={})
        for key, value in self.model.logger.name_to_value.items():
            if "loss" in key or "ent_coef" in key:
                try:
                    number = float(value)
                    if np.isfinite(number):
                        payload["losses"][key] = number
                except (TypeError, ValueError):
                    pass
        if self.episodes:
            self.history.append(dict(step=step, reward=payload["mean_reward"]))
        payload["reward_history"] = list(self.history)
        write_json(self.run / "live_metrics.json", payload)
        print("METRIC " + json.dumps({k:v for k,v in payload.items() if k != "reward_history"}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=2000000, help="Cumulative target, not additional steps")
    parser.add_argument("--envs", type=int, default=2)
    parser.add_argument("--checkpoint-steps", type=int, default=100000)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--run-dir")
    parser.add_argument("--resume")
    parser.add_argument("--new", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if min(args.steps, args.envs, args.checkpoint_steps) < 1:
        parser.error("steps, envs and checkpoint-steps must be positive")
    if args.new and args.resume:
        parser.error("--new and --resume are mutually exclusive")
    if args.smoke:
        env = JsbsimEnv()
        try:
            env.reset()
            for _ in range(60):
                _, _, terminated, truncated, _ = env.step(env.action_space.sample())
                if terminated or truncated:
                    env.reset()
        finally:
            env.close()
        print("SMOKE_OK")
        return
    root = Path(os.environ.get("AI_PILOT_OUTPUT_ROOT", str(Path(__file__).resolve().parent)))
    source = args.resume
    if not source and not args.new:
        saved = candidates([root])
        source = saved[-1]["path"] if saved else None
    run = Path(args.run_dir) if args.run_dir else root / "runs" / (datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=True)
    if (run / "run.json").exists():
        raise RuntimeError("Refusing to overwrite an existing run")
    logs = run / "logs"
    logs.mkdir()
    write_json(run / "run.json", dict(target_steps=args.steps, resume=source, envs=args.envs, created_epoch=time.time()))
    env = None
    metrics = None
    try:
        env = create_envs(args.envs, logs)
        device = "cuda" if args.device == "auto" and th.cuda.is_available() else args.device
        if device == "auto":
            device = "cpu"
        if source:
            model = SAC.load(source, env=env, device=device, tensorboard_log=str(logs))
            replay = Path(source).with_name("replay.pkl")
            if replay.is_file():
                model.load_replay_buffer(str(replay))
                if model.replay_buffer.n_envs != env.num_envs:
                    raise ValueError("Replay buffer environment count differs; use the original environment count")
                # The simulator resets on resume. Break unfinished replay episodes
                # at this boundary rather than bootstrapping into an unrelated reset.
                rb = model.replay_buffer
                if rb.size():
                    rb.dones[(rb.pos - 1) % rb.buffer_size] = 1
                    rb.timeouts[(rb.pos - 1) % rb.buffer_size] = 0
                print("RESUME_FULL: model, optimizer and replay buffer restored", flush=True)
            else:
                model.learning_starts = int(model.num_timesteps) + 20000
                print("RESUME_LEGACY: model/optimizer restored; no old replay buffer. Collect 20000 new steps before updates.", flush=True)
        else:
            model = SAC("MlpPolicy", env, learning_rate=.0002, buffer_size=300000,
                        batch_size=256, tau=.005, gamma=.99,
                        learning_starts=min(20000, max(1000, args.steps//10)),
                        target_entropy="auto", policy_kwargs={"activation_fn":th.nn.Tanh, "net_arch":[256,256], "use_sde":True, "log_std_init":-2},
                        verbose=1, tensorboard_log=str(logs), device=device)
        remaining = args.steps - int(model.num_timesteps)
        if remaining <= 0:
            raise ValueError("Checkpoint already reached the cumulative target; increase target or explicitly start new")
        metrics = TrainingMetrics(run, args.steps, args.checkpoint_steps, run / "stop.request", source)
        model.learn(total_timesteps=remaining, callback=metrics, reset_num_timesteps=False, log_interval=1)
        metrics.publish("saving")
        saved = save_bundle(model, run, "stopped" if metrics.stopped else "finished")
        metrics.publish("stopped" if metrics.stopped else "finished", checkpoint=saved["path"])
        print("TRAINING_SAVED: " + saved["path"], flush=True)
    except BaseException as exc:
        write_json(run / "error.json", dict(error=f"{type(exc).__name__}: {exc}"))
        if metrics and hasattr(metrics, "started"):
            metrics.publish("error", error=str(exc))
        raise
    finally:
        if env is not None:
            env.close()


if __name__ == "__main__":
    main()
