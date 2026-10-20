#!/usr/bin/env python3
"""Short, local-only LAG compatibility test used by the dashboard.

This deliberately exercises flight control and the no-weapon posture task.
It does not launch or evaluate weapons.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def run_case(label: str, env_cls, config: str) -> dict:
    env = env_cls(config)
    try:
        obs = env.reset()
        steps = 0
        for _ in range(5):
            action = np.asarray([env.action_space.sample() for _ in range(env.num_agents)])
            obs, reward, done, info = env.step(action)
            steps += 1
        return {
            "name": label,
            "config": config,
            "agents": int(env.num_agents),
            "observation_shape": list(np.asarray(obs).shape),
            "steps": steps,
            "ok": True,
        }
    finally:
        env.close()


def main() -> int:
    try:
        from envs.JSBSim.envs import OfficialCombatEnv, SingleCombatEnv, SingleControlEnv

        results = [
            run_case("single_control", SingleControlEnv, "1/heading"),
            run_case("single_combat_no_weapon", SingleCombatEnv, "1v1/NoWeapon/HierarchySelfplay"),
            run_case("official_1v1", OfficialCombatEnv, "1v1/Official/Official1v1"),
        ]
        print(json.dumps({"ok": True, "cases": results}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
