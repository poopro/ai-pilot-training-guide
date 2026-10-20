#!/usr/bin/env python3
"""Executable verification for the official 1v1 task."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from envs.JSBSim.envs import OfficialCombatEnv
    from envs.JSBSim.core.catalog import Catalog as c
    from envs.JSBSim.utils.utils import NEU2LLA

    env = OfficialCombatEnv("1v1/Official/Official1v1")
    try:
        env.seed(20260920)
        obs = env.reset()
        assert obs.shape == (2, 26), obs.shape
        assert env.action_space.shape == (4,)
        assert env.sim_freq == 60
        assert env.agent_interaction_steps == 1
        assert env.max_steps == 18_000
        initial = env.last_initial_condition
        assert initial["distance_ft"] in (3_000.0, 6_000.0, 9_000.0)
        assert 10_000.0 <= initial["altitude_ft"] <= 20_000.0
        assert initial["speed_kts"] == 340.0
        sims = list(env.agents.values())
        actual_distance_ft = float(np.linalg.norm(sims[0].get_position() - sims[1].get_position()) / 0.3048)
        actual_speeds_kts = [sim.get_property_value(c.velocities_vc_fps) / 1.687809857 for sim in sims]
        assert abs(actual_distance_ft - initial["distance_ft"]) < 0.1
        assert all(abs(speed - 340.0) < 0.1 for speed in actual_speeds_kts)

        actions = np.array([[0.0, 0.0, 0.0, 0.8], [0.0, 0.0, 0.0, 0.8]], dtype=np.float32)
        for _ in range(5):
            obs, rewards, dones, info = env.step(actions)
        assert obs.shape == (2, 26)
        assert rewards.shape == (2, 1)
        assert dones.shape == (2, 1)
        assert "official_rules" in info
        assert set(info["official_rules"]["agents"]) == set(env.agents)

        assert env.task._distance_factor(100.0) == 0.1
        assert env.task._distance_factor(200.0) == 1.2
        assert env.task._distance_factor(1_000.0) == 1.0
        assert env.task._distance_factor(2_000.0) == 0.5
        assert env.task._distance_factor(4_000.0) == 0.1
        assert env.task._angle_deg([1, 0, 0], [1, 0, 0]) < 1e-6

        # Deterministic rule check: A is 1,000 ft behind B and both point north.
        # A must receive a kill only after exactly 180 valid 60 Hz frames.
        ids = list(env.agents)
        altitude_ft = 15_000.0
        half_distance_m = 1_000.0 * 0.3048 / 2.0
        for uid, north_m in zip(ids, (-half_distance_m, half_distance_m)):
            lon, lat, _ = NEU2LLA(
                north_m,
                0.0,
                altitude_ft * 0.3048,
                env.center_lon,
                env.center_lat,
                env.center_alt,
            )
            env.agents[uid].reload(
                {
                    "ic_long_gc_deg": float(lon),
                    "ic_lat_geod_deg": float(lat),
                    "ic_h_sl_ft": altitude_ft,
                    "ic_psi_true_deg": 0.0,
                    "ic_vc_kts": 340.0,
                }
            )
        env.current_step = 0
        env.task.reset(env)
        for frame in range(1, 180):
            env.current_step = frame
            env.task.step(env)
            assert not env.task._done
        env.current_step = 180
        env.task.step(env)
        assert env.task._done
        assert env.task._results[ids[0]] == "win_kill"
        assert env.task._results[ids[1]] == "loss_killed"
        assert env.task.stats[ids[0]]["attack_frames"] == 180

        clipped = env.task.normalize_action(env, ids[0], [2.0, -2.0, 4.0, -1.0])
        assert np.allclose(clipped, [1.0, -1.0, 1.0, 0.0])
        previous = clipped.copy()
        fallback = env.task.normalize_action(env, ids[0], [np.nan, 0.0, 0.0, 0.5])
        assert np.allclose(fallback, previous)
        assert env.task.stats[ids[0]]["invalid_action_count"] == 1

        result = {
            "ok": True,
            "observation_shape": list(obs.shape),
            "action_shape": list(env.action_space.shape),
            "sim_freq": env.sim_freq,
            "control_interval_frames": env.agent_interaction_steps,
            "episode_frames": env.max_steps,
            "initial": initial,
            "metric_keys": sorted(info["official_rules"]["agents"][env.task.agent_ids[0]].keys()),
            "rule_checks": {
                "kill_after_frames": 180,
                "winner": env.task._results[ids[0]],
                "loser": env.task._results[ids[1]],
                "action_clipping": True,
                "invalid_action_fallback": True,
            },
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0
    finally:
        env.close()


if __name__ == "__main__":
    raise SystemExit(main())
