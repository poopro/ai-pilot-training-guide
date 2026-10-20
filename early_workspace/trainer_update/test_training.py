"""Regression checks using a small deterministic Gymnasium fixture, not flight scores."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import gymnasium as gym
import numpy as np
from stable_baselines3 import SAC
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

ROOT = Path(__file__).resolve().parent
os.environ["AI_PILOT_ENV_SOURCE"] = "E:/ai_pilot/work"
sys.path.insert(0, str(ROOT / "work"))
from train_local import TrainingMetrics
from training_store import candidates, read_json, save_bundle


class Fixture(gym.Env):
    observation_space = gym.spaces.Box(-1, 1, (3,), dtype=np.float32)
    action_space = gym.spaces.Box(-1, 1, (1,), dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.t = 0
        return np.zeros(3, dtype=np.float32), {}

    def step(self, action):
        self.t += 1
        return np.zeros(3, dtype=np.float32), 2., self.t == 4, False, {}


class TrainingTests(unittest.TestCase):
    def test_roundtrip_reward_optimizer_replay_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            run = Path(temp) / "runs" / "test"
            run.mkdir(parents=True)
            env = DummyVecEnv([lambda: Monitor(Fixture())])
            try:
                model = SAC("MlpPolicy", env, buffer_size=100, batch_size=4, learning_starts=4,
                            policy_kwargs={"net_arch":[8,8]}, tensorboard_log=str(run / "logs"), device="cpu")
                callback = TrainingMetrics(run, 12, 8, run / "stop.request")
                model.learn(12, callback=callback, log_interval=1)
                callback.publish("saving")
                saved = save_bundle(model, run, "finished")
                callback.publish("finished", checkpoint=saved["path"])
                metrics = read_json(run / "live_metrics.json")
                self.assertEqual(metrics["mean_reward"], 8.)
                self.assertEqual(metrics["mean_episode_length"], 4.)
                self.assertEqual(metrics["episodes_completed"], 3)
                self.assertEqual(len((run / "episodes.csv").read_text().splitlines()), 4)
                events = next((run / "logs").rglob("events.out.tfevents*"))
                acc = EventAccumulator(str(events)); acc.Reload()
                self.assertEqual(acc.Scalars("rollout/ep_rew_mean")[-1].value, 8.)
                fingerprint = hashlib.sha256(Path(saved["path"]).read_bytes()).hexdigest()
                loaded = SAC.load(saved["path"], env=env, device="cpu")
                loaded.load_replay_buffer(str(Path(saved["path"]).with_name("replay.pkl")))
                self.assertEqual(loaded.num_timesteps, 12)
                self.assertEqual(loaded.replay_buffer.size(), 12)
                self.assertTrue(loaded.actor.optimizer.state_dict()["state"])
                run2 = Path(temp) / "runs" / "resume"
                run2.mkdir()
                callback2 = TrainingMetrics(run2, 20, 100, run2 / "stop.request", saved["path"])
                loaded.learn(8, callback=callback2, reset_num_timesteps=False)
                saved2 = save_bundle(loaded, run2, "finished")
                callback2.publish("finished", checkpoint=saved2["path"])
                self.assertEqual(loaded.num_timesteps, 20)
                self.assertEqual(loaded.replay_buffer.size(), 20)
                self.assertEqual(read_json(run2 / "live_metrics.json")["session_steps"], 8)
                self.assertEqual(hashlib.sha256(Path(saved["path"]).read_bytes()).hexdigest(), fingerprint)
                self.assertEqual(candidates([temp])[-1]["steps"], 20)
                partial = run2 / "checkpoints" / "partial"
                partial.mkdir()
                (partial / "model.zip").write_bytes(b"partial")
                self.assertEqual(candidates([temp])[-1]["steps"], 20)
                (run2 / "stop.request").touch()
                stopping = TrainingMetrics(run2, 30, 100, run2 / "stop.request")
                loaded.learn(10, callback=stopping, reset_num_timesteps=False)
                self.assertTrue(stopping.stopped)
                self.assertLess(loaded.num_timesteps, 30)
            finally:
                env.close()

    def test_legacy_selection_uses_mtime_and_internal_steps(self):
        import zipfile
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            models = Path(temp) / "model"; models.mkdir()
            for name, steps, stamp in [("jsbsim_sac_314400000_steps.zip",314400000,1),
                                       ("jsbsim_sac_1100000_steps.zip",1100000,2)]:
                file = models/name
                with zipfile.ZipFile(file, "w") as archive:
                    archive.writestr("data", json.dumps(dict(num_timesteps=steps)))
                os.utime(file, (stamp,stamp))
            (models/"jsbsim_sac_broken.zip").write_bytes(b"broken")
            self.assertEqual(candidates([temp])[-1]["steps"], 1100000)


if __name__ == "__main__":
    unittest.main()
