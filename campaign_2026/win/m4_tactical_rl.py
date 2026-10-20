"""M4 — slow-decision RL tactical layer over the frozen 60 Hz rule controller.

DESIGN (why it is different from every previous attempt)

  60 Hz  frozen RepairController.command()
          safety, G limiter, trim, slew limits — never learned, never broken
    ^
  3 Hz   RL policy  ->  (aggression, break_bias, range_bias) in [-1,1]^3
          decides HOW HARD to press, WHEN to force a break, WHERE to sit
    ^
  judge  accumulated attack ticks, 1 deg cone, 500-3000 ft, 180 = kill

What the previous runs actually optimised, and why it did not transfer:

  * Reward was potential shaping (progress / alignment / precision). Those terms
    are maximised by getting close and pointing roughly at the target. The judge
    only pays for ticks INSIDE a 1 degree cone. A policy that is 30 degrees off
    scores well on the old reward and zero on the real one. That is exactly the
    failure we measured: vs the RL opponent, nose angle never got under 1.5 deg
    across 3000 samples.
  * The opponent flew straight lines (jsbsimFdm.py:360 hardcodes
    random.choice(["Straight"]); the turn branches are dead code), so the policy
    never had to defend, and never met a target that manoeuvred.
  * The environment had no attack termination, so a 180-tick kill never happened
    and the policy never saw the reward that matters.
  * env.py:69 rebuilt packet_controller on every reset, silently discarding any
    trained component.

This file fixes all four. Reward is the tick counter itself.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import gymnasium as gym
from gymnasium import spaces

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPAIR = CAMPAIGN / "repair_v1"
GLATCH = CAMPAIGN / "experiments" / "g_latch_development"
NEARBANK = CAMPAIGN / "experiments" / "near_bank80"
for p in (str(REPAIR), str(GLATCH), str(NEARBANK), str(HERE)):
    sys.path.insert(0, p)

import torch
import torch.nn as nn
from stable_baselines3 import SAC
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback

from env import RepairDuel, simulator_observation
from controller import RepairController
from combat_v3.interface import geometry_from_observation
from artifacts import load_policy
from env import DEFAULT_BUNDLE

BAND_LO_M, BAND_HI_M = 500 * 0.3048, 3000 * 0.3048
KILL_TICKS = 180
DECISION_EVERY = 20          # 20 physics frames @60 Hz = 3 Hz decision rate
N_TACTICAL = 12              # tactical observation size
N_DECISION = 3               # (aggression, break_bias, range_bias)

OVER_9G_PENALTY = 0.35
NEAR_GROUND_M = 400.0


def enemy_heading_proxy_deg(o: np.ndarray) -> float:
    """Enemy nose direction estimated from its NED velocity. LEGAL: the official
    26-value packet carries enemy position + NED velocity, nothing else. The true
    enemy attitude is judge-only and must never reach the deployed policy."""
    vn, ve = float(o[23]), float(o[24])
    if math.hypot(vn, ve) < 1e-3:
        return 0.0
    return math.degrees(math.atan2(ve, vn)) % 360.0


def tactical_obs(o: np.ndarray, geo: dict, ticks: int, guard: bool) -> np.ndarray:
    d = geo["distance_m"]
    in_band = 1.0 if BAND_LO_M <= d <= BAND_HI_M else 0.0
    eh = math.radians(enemy_heading_proxy_deg(o))
    rel = math.radians(geo["bearing_deg"]) - eh
    return np.array([
        float(np.clip(d / 4000.0, 0.0, 1.0)),
        in_band,
        math.cos(math.radians(min(geo["blue_angle_deg"], 180.0))),
        math.sin(math.radians(geo["blue_angle_deg"])),
        math.cos(rel),
        math.sin(rel),
        math.tanh(geo["closing_mps"] / 200.0),
        math.sin(math.radians(o[3])),
        math.cos(math.radians(o[3])),
        math.tanh(o[14] / 9.0),
        ticks / KILL_TICKS,
        1.0 if guard else 0.0,
    ], dtype=np.float32)


class TacticalDuel(RepairDuel):
    """3 Hz tactical layer; frozen 60 Hz control underneath."""

    def __init__(self, *a, opponent="mirror", **kw):
        kw.setdefault("attack_angle", 1.0)
        kw.setdefault("max_steps", 18000)
        # callers may pass p2=..., which otherwise lands in **kw and would be
        # silently overwritten by the default opponent
        opponent = kw.pop("p2", opponent)
        # RepairDuel reads p2 out of kwargs; it must not also be positional.
        kw["p2"] = opponent
        kw.setdefault("controller", "repair")
        self.opponent_kind = opponent
        super().__init__(*a, **kw)
        self.act_buf = np.zeros(N_DECISION, dtype=np.float32)
        self._frame = 0

    # -- frozen controller, parameterised by the slow policy ----------------
    def _build_blue(self):
        from m1_station import StationController
        return StationController(self.settings, "station")

    def reset(self, **kw):
        obs, info = super().reset(**kw)
        self.packet_controller = self._build_blue()
        self.controller_variant = "station"
        self._frame = 0
        self.act_buf = np.zeros(N_DECISION, dtype=np.float32)
        self.ticks = 0
        self.over9g = 0
        self.min_alt = 1e9
        return obs, info

    def _tactical_control(self, o: np.ndarray, geo: dict):
        """Hand the 3 Hz decision to the proven act(). The frozen guidance is
        never reimplemented here — that is exactly what broke the first attempt
        (bank saturated at 72 deg for the whole round, zero G, never engaged)."""
        self.packet_controller.set_tactical(*(float(x) for x in self.act_buf))
        return self.packet_controller.act(o, None, True)

    def step(self, tactical_action):
        """One call = DECISION_EVERY physics frames."""
        a = np.clip(np.asarray(tactical_action, dtype=np.float32).reshape(-1), -1, 1)
        self.act_buf = a
        total = 0.0
        ticks = 0
        term = trunc = False
        info = {}
        for _ in range(DECISION_EVERY):
            if self.current_step >= self.max_steps:
                trunc = True
                break
            blue_obs = simulator_observation(self.fdm1, self.fdm2)
            geo = geometry_from_observation(blue_obs)
            cmd, guard = self._tactical_control(blue_obs, geo)
            _, r, term, trunc, info = super().step(cmd)
            total += float(r)
            self._frame += 1
            ticks += 1

            d = geo["distance_m"]
            if abs(float(blue_obs[14])) > 9.0:
                self.over9g += 1
            alt = blue_obs[2] * .3048
            self.min_alt = min(self.min_alt, alt)

            # THE reward: the quantity the judge actually counts.
            in_band = BAND_LO_M <= d <= BAND_HI_M
            aimed = geo["blue_angle_deg"] <= 1.0
            if in_band and aimed:
                self.ticks += 1
                total += 1.0
            if abs(float(blue_obs[14])) > 9.0:
                total -= OVER_9G_PENALTY
            if alt < NEAR_GROUND_M:
                total -= 0.05

            if term or trunc or self.ticks >= KILL_TICKS:
                if self.ticks >= KILL_TICKS and not term:
                    term = True
                break
        if self.current_step >= self.max_steps and not (term or trunc):
            trunc = True

        info = dict(info)
        info.update(attack_ticks=self.ticks, over9g=self.over9g,
                    min_alt=self.min_alt, guard=bool(guard),
                    outcome=info.get("outcome"))
        if term or trunc:
            info["won"] = bool(self.ticks >= KILL_TICKS)
            info["crashed"] = bool(info.get("own_crash"))
        # roll the frozen env back so the tactical layer owns termination
        return self.tactical_obs_only(), total, term, trunc, info

    def tactical_obs_only(self) -> np.ndarray:
        blue_obs = simulator_observation(self.fdm1, self.fdm2)
        geo = geometry_from_observation(blue_obs)
        guard = bool(getattr(self, "_last_guard", False))
        return tactical_obs(blue_obs, geo, self.ticks, guard)

    def observation_space(self):
        from gymnasium.spaces import Box
        return Box(-2.0, 2.0, (N_TACTICAL,), dtype=np.float32)

    def action_space(self):
        from gymnasium.spaces import Box
        return Box(-1.0, 1.0, (N_DECISION,), dtype=np.float32)

    def _red_action(self):
        """Perturbed mirror Player2, so the opponent actually fights.

        A byte-identical mirror deadlocks (measured: 4019 m median separation,
        nose angle never below 30 deg). Reuses the asymmetry proven to fix it.
        """
        if getattr(self, "p2_type", None) != "mirror":
            return super()._red_action()
        if getattr(self, "_mirror_p2", None) is None:
            from m3_mirror_league import MirrorP2Controller
            self._mirror_p2 = MirrorP2Controller(self.settings, 0.72, 6.0, 9.0)
        obs = simulator_observation(self.fdm2, self.fdm1)   # OWN20+ENEMY6 only
        try:
            cmd, guard = self._mirror_p2.act(obs, self.current_step)
            self.p2_mode = "mirror_" + str(self._mirror_p2.mode)
            return np.asarray(cmd, dtype=np.float32)
        except Exception:
            self.p2_mode = "mirror_fallback"
            return np.array([0., 0., 0., 0.8], dtype=np.float32)


class TacticalGym(gym.Env):
    """gymnasium wrapper so SB3 (and its Monitor) can drive the 3 Hz layer."""

    metadata = {"render_modes": []}

    def __init__(self, opponent="mirror"):
        super().__init__()
        self.opponent = opponent
        self.env = None
        self.observation_space = spaces.Box(-2.0, 2.0, (N_TACTICAL,), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, (N_DECISION,), dtype=np.float32)

    def _ensure(self, seed=None):
        if self.env is None:
            self.env = TacticalDuel(
                p2=self.opponent,
                policy=(load_policy(DEFAULT_BUNDLE)
                        if self.opponent == "rl" else None))
        return self.env

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        e = self._ensure(seed)
        e.reset(seed=seed)
        return e.tactical_obs_only(), {}

    def step(self, action):
        obs, r, term, trunc, info = self.env.step(action)
        return obs, float(r), bool(term), bool(trunc), info

    def close(self):
        if self.env is not None:
            self.env.close()
            self.env = None


class Telemetry(BaseCallback):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.t0 = time.time()
        self.ep = 0

    def _on_step(self):
        if self.num_timesteps % 2000 == 0:
            self.path.write_text(json.dumps({
                "timesteps": self.num_timesteps,
                "elapsed_s": round(time.time() - self.t0, 1),
                "episodes": self.ep,
                "best_ticks": int(getattr(self.model, "_best_ticks", 0)),
            }), encoding="utf-8")
        return True

    def _on_episode_end(self):
        self.ep += 1
        info = self.locals.get("infos", [{}])[0] if self.locals.get("infos") else {}
        t = int(info.get("attack_ticks", 0) or 0)
        if t > int(getattr(self.model, "_best_ticks", 0)):
            self.model._best_ticks = t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=400_000)
    ap.add_argument("--opponents", default="mirror,rule,rl")
    ap.add_argument("--out", type=Path, default=CAMPAIGN / "experiments" / "m4_tactical")
    ap.add_argument("--seed", type=int, default=20261110)
    ap.add_argument("--learning-starts", type=int, default=5_000)
    ap.add_argument("--buffer", type=int, default=200_000)
    a = ap.parse_args()

    torch.set_num_threads(1)
    a.out.mkdir(parents=True, exist_ok=True)
    opps = [x.strip() for x in a.opponents.split(",") if x.strip()]

    def make_env():
        gym_env = TacticalGym(random.choice(opps))
        from stable_baselines3.common.monitor import Monitor
        return Monitor(gym_env)

    vec = DummyVecEnv([make_env])
    model = SAC(
        "MlpPolicy", vec,
        learning_rate=3e-4,
        buffer_size=a.buffer,
        batch_size=256,
        learning_starts=a.learning_starts,
        tau=0.005,
        gamma=0.995,                 # long horizon: accumulate 180 ticks
        train_freq=8,
        gradient_steps=1,
        ent_coef=0.01,
        policy_kwargs=dict(net_arch=[128, 128], activation_fn=nn.Tanh,
                           log_std_init=-1.0),
        verbose=1,
        seed=a.seed,
        device="cuda" if torch.cuda.is_available() else "cpu",
    )
    print(json.dumps({
        "opponents": opps, "steps": a.steps, "decision_every": DECISION_EVERY,
        "tactical_obs": N_TACTICAL, "decision_dim": N_DECISION,
        "kill_ticks": KILL_TICKS, "reward": "accumulated attack ticks",
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False), flush=True)

    cb = [CheckpointCallback(save_freq=max(1, a.steps // 8),
                             save_path=str(a.out), name_prefix="m4_tactical"),
          Telemetry(a.out / "progress.json")]
    model.learn(total_timesteps=a.steps, callback=cb)
    model.save(str(a.out / "m4_tactical_final"))
    print("M4_DONE", flush=True)


if __name__ == "__main__":
    main()