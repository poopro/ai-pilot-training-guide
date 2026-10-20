"""Evaluate a saved SAC checkpoint without changing the running trainer.

Run after stopping the official training program. The current training environment
has no kill event, so this reports attack geometry as a proxy, never as a win.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean

import numpy as np


OFFICIAL_DIR = Path(
    r"E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引"
    r"\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test"
)


def latest_checkpoint() -> Path:
    files = list((OFFICIAL_DIR / "model").glob("jsbsim_sac_*_steps.zip"))
    files += list((OFFICIAL_DIR / "models").glob("jsbsim_sac.zip"))
    if not files:
        raise FileNotFoundError("找不到已儲存的模型檔。")
    return max(files, key=lambda item: item.stat().st_mtime)


def run() -> None:
    parser = argparse.ArgumentParser(description="評估官方範例 SAC 模型")
    parser.add_argument("--checkpoint", type=Path, help="指定模型 .zip；省略時使用最新檔")
    parser.add_argument("--episodes", type=int, default=5, help="評估回合數，預設 5")
    parser.add_argument("--max-steps", type=int, default=18000, help="每回合最多步數；正式評估用 18000")
    parser.add_argument("--seed", type=int, default=20261002)
    parser.add_argument("--output-dir", type=Path, default=OFFICIAL_DIR / "eval_reports")
    parser.add_argument("--acmi", action="store_true", help="另存 Tacview 回放，記錄兩架飛機")
    parser.add_argument("--no-save", action="store_true", help="只印結果，不寫檔")
    args = parser.parse_args()
    if args.episodes < 1 or args.max_steps < 1:
        parser.error("episodes 和 max-steps 必須大於零")

    checkpoint = args.checkpoint or latest_checkpoint()
    if not checkpoint.is_file():
        parser.error(f"找不到模型：{checkpoint}")

    # The official environment uses relative paths for its aircraft assets.
    os.chdir(OFFICIAL_DIR)
    sys.path.insert(0, str(OFFICIAL_DIR))
    if not args.no_save or args.acmi:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    from stable_baselines3 import SAC
    from envs.jsbsimEnv import JsbsimEnv

    model = SAC.load(str(checkpoint), device="cpu")
    env = JsbsimEnv(render_modes="txt" if args.acmi else None)
    rows: list[dict[str, object]] = []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"模型：{checkpoint}", flush=True)
    try:
        for episode in range(1, args.episodes + 1):
            seed = args.seed + episode - 1
            random.seed(seed)
            np.random.seed(seed)
            observation, _ = env.reset(seed=seed)
            acmi_path = args.output_dir / f"fight_{stamp}_episode_{episode}.acmi"
            if args.acmi:
                env.record_file = str(acmi_path)
                env._record_created = False
                env.render()
            total_reward = 0.0
            attack_steps = 0
            terminated = truncated = False
            own_altitude_ft = float("nan")
            enemy_altitude_ft = float("nan")
            for step in range(1, args.max_steps + 1):
                action, _ = model.predict(observation, deterministic=True)
                observation, reward, terminated, truncated, info = env.step(action)
                total_reward += float(reward)
                if args.acmi:
                    env.render()
                own_altitude_ft = float(observation[11]) * 5000.0
                enemy_altitude_ft = (float(observation[1]) + float(observation[11])) * 5000.0
                distance_ft = float(info["distance"]) / 0.3048
                nose_angle_deg = float(env._last_own_3d_angle)
                if 500.0 <= distance_ft <= 3000.0 and nose_angle_deg <= 2.0:
                    attack_steps += 1
                if terminated or truncated:
                    break

            if terminated and own_altitude_ft <= 50:
                reason = "我方墜機"
            elif terminated and enemy_altitude_ft <= 50:
                reason = "敵機自行墜機"
            elif truncated:
                reason = "五分鐘到時"
            else:
                reason = "評估提早截止"

            completed = bool(terminated or truncated)
            survived = own_altitude_ft > 50
            row = {
                "episode": episode,
                "seed": seed,
                "steps": step,
                "completed": completed,
                "episode_reward": round(total_reward, 3),
                "survived": bool(survived),
                "attack_window_seconds": round(attack_steps / 60.0, 3),
                "attack_3s_proxy": attack_steps >= 180,
                "end_reason": reason,
                "failure_reason": reason if reason in {"我方墜機", "評估提早截止"} else "無",
                "official_kill": "無法從此環境判定",
            }
            if args.acmi:
                row["acmi_file"] = str(acmi_path)
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        env.close()

    finished = [row for row in rows if row["completed"]]
    summary = {
        "checkpoint": str(checkpoint),
        "episodes_requested": args.episodes,
        "episodes_completed": len(finished),
        "mean_episode_reward": round(mean(float(row["episode_reward"]) for row in finished), 3) if finished else None,
        "survival_rate": round(mean(float(row["survived"]) for row in finished), 3) if finished else None,
        "mean_attack_window_seconds": round(mean(float(row["attack_window_seconds"]) for row in finished), 3) if finished else None,
        "attack_3s_proxy_rate": round(mean(float(row["attack_3s_proxy"]) for row in finished), 3) if finished else None,
        "official_kill_rate": None,
        "note": "攻擊窗口與 3 秒門檻只是幾何代理值；官方擊殺率須用官方 Host 對戰紀錄計算。",
    }
    print("總結：" + json.dumps(summary, ensure_ascii=False), flush=True)
    if not args.no_save:
        csv_path = args.output_dir / f"evaluation_{stamp}.csv"
        json_path = args.output_dir / f"evaluation_{stamp}.json"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"回合紀錄：{csv_path}\n總結：{json_path}", flush=True)


if __name__ == "__main__":
    run()
