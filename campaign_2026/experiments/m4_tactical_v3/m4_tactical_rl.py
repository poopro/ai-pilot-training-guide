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
CAMPAIGN = HERE.parents[1]
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
from judge_adapter import RuleJudgeAdapter, RESEARCH_RULE_PROFILE

BAND_LO_M, BAND_HI_M = 500 * 0.3048, 3000 * 0.3048
KILL_TICKS = 180
DECISION_EVERY = 20          # 20 physics frames @60 Hz = 3 Hz decision rate
N_TACTICAL = 13              # tactical observation size
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


def tactical_obs(o: np.ndarray, geo: dict, ticks: int, guard: bool, elapsed_ticks: int = 0) -> np.ndarray:
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
        max(0., 1. - elapsed_ticks / 18000.),
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
        self._last_guard = False
        self._mirror_p2 = None
        self.over9g = 0
        self.min_alt = 1e9
        self.judge = RuleJudgeAdapter(self, RESEARCH_RULE_PROFILE)
        info = self._info()
        info.update(rules_profile=vars(RESEARCH_RULE_PROFILE), official_validation=False)
        return obs, info

    def step(self, tactical_action):
        """One call = DECISION_EVERY physics frames."""
        raw = np.asarray(tactical_action, dtype=np.float32)
        if raw.shape != (N_DECISION,) or not np.isfinite(raw).all():
            raise ValueError("Three finite tactical values required")
        self.act_buf = np.clip(raw, -1, 1)
        before_advantage = self.judge.advantages()
        total = 0.0
        term = trunc = False
        info = {}
        guard = self._last_guard
        for _ in range(DECISION_EVERY):
            if self.current_step >= self.max_steps:
                trunc = True
                break
            # Parent accepts FOUR RESIDUALS, not finished surface commands.
            # Install goals only; parent calls StationController.act exactly once.
            self.packet_controller.set_tactical(*(float(x) for x in self.act_buf))
            previous_ticks = int(self.blue_frames)
            _, _, term, trunc, info = super().step(np.zeros(4, dtype=np.float32))
            self._frame += 1
            post = simulator_observation(self.fdm1, self.fdm2)
            self.ticks = int(self.blue_frames)
            delta = self.ticks - previous_ticks
            if delta < 0:
                raise RuntimeError("Judge counter decreased within an episode")
            self._last_guard = guard = bool(info["guard_active"])
            g = abs(float(post[14]))
            self.over9g += int(g > 9.0)
            alt = float(post[2]) * .3048
            self.min_alt = min(self.min_alt, alt)
            # Explicit diagnostic reward contract: post-step judge ticks plus
            # penalties below; no inherited shaping reward is silently added.
            total += float(delta) - OVER_9G_PENALTY * int(g > 9.0)
            total -= 0.05 * int(alt < NEAR_GROUND_M)
            if term or trunc:
                break
        if self.current_step >= self.max_steps and not term:
            trunc = True
        snapshot = self.judge.core.snapshot()
        after_advantage = snapshot["advantage"]
        #1attack tick =1reward unit. G and positional terms retain published
        #relative weights. Explicit terminal victory/loss bonus includes timeout.
        total = ((after_advantage[0]-after_advantage[1]) -
                 (before_advantage[0]-before_advantage[1])) / (10000. / 60.)
        terminal_round = snapshot["event"] != "ongoing"
        if terminal_round and snapshot["winner"] is None:
            raise RuntimeError("Unresolved winner; cannot create a learning target")
        if terminal_round:
            total += 180. if snapshot["winner"] == "blue" else (-180. if snapshot["winner"] == "red" else 0.)
        info = dict(info)
        info.update(attack_ticks=self.ticks, over9g=self.over9g,
                    min_alt=self.min_alt, guard=bool(guard), opponent=self.opponent_kind,
                    rules_profile=vars(RESEARCH_RULE_PROFILE), judge_snapshot=snapshot,
                    official_validation=False, rules_contract="publication_LINE_local_v1_not_Host_certified",
                    reward_contract="delta_advantage_gap_per166.6667_plus_terminal180",
                    parent_diagnostic_time_limit=bool(trunc and not terminal_round))
        if term or trunc:
            info["won"] = terminal_round and snapshot["winner"] == "blue"
            info["crashed"] = snapshot["event"] in ("blue_crash", "mutual_crash")
            info["local_win"] = int(info["won"])
        #The actual300s competition horizon is a terminal game event. A shorter
        #diagnostic cutoff remains truncation with no invented round winner.
        return self.tactical_obs_only(), total, term, trunc, info

    def tactical_obs_only(self) -> np.ndarray:
        blue_obs = simulator_observation(self.fdm1, self.fdm2)
        geo = geometry_from_observation(blue_obs)
        guard = bool(getattr(self, "_last_guard", False))
        return tactical_obs(blue_obs, geo, self.ticks, guard, elapsed_ticks=self.current_step)

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
            self.p2_guard = bool(guard)
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
        self.opponents = tuple(opponent.split(",")) if isinstance(opponent, str) else tuple(opponent)
        if not self.opponents or any(p not in ("mirror", "rule", "rl") for p in self.opponents):
            raise ValueError("Unknown or empty opponent pool")
        self.opponent = None
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
        selected = str(self.np_random.choice(self.opponents))
        if self.env is not None and selected != self.opponent:
            self.close()
        self.opponent = selected
        e = self._ensure(seed)
        _, info = e.reset(seed=seed)
        info = dict(info)
        info.update(opponent=selected, official_validation=False)
        return e.tactical_obs_only(), info

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
        infos = self.locals.get("infos", [])
        for done, info in zip(self.locals.get("dones", []), infos):
            if done:
                self.ep += 1
                ticks = int(info.get("attack_ticks", 0) or 0)
                self.model._best_ticks = max(ticks, int(getattr(self.model, "_best_ticks", 0)))
        if self.num_timesteps % 2000 == 0:
            self.path.write_text(json.dumps({
                "timesteps": self.num_timesteps,
                "elapsed_s": round(time.time() - self.t0, 1),
                "episodes": self.ep,
                "best_ticks": int(getattr(self.model, "_best_ticks", 0)),
                "last_opponents": [i.get("opponent") for i in infos],
                "official_validation": False,
            }), encoding="utf-8")
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=400_000)
    ap.add_argument("--opponents", default="mirror,rule,rl")
    ap.add_argument("--out", type=Path, default=HERE / "requires_unique_guarded_job")
    ap.add_argument("--seed", type=int, default=20261110)
    ap.add_argument("--learning-starts", type=int, default=5_000)
    ap.add_argument("--buffer", type=int, default=200_000)
    a = ap.parse_args()

    torch.set_num_threads(1)
    a.out.mkdir(parents=True, exist_ok=True)
    opps = [x.strip() for x in a.opponents.split(",") if x.strip()]

    def make_env():
        gym_env = TacticalGym(opps)
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
    raise SystemExit("Preparation only: a frozen job, independent watchdog, source/seed/resource gates and FDM verification are required before training.")