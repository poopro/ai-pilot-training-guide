"""產生一般穩定飛行遙測資料，不包含對戰、瞄準或攻擊邏輯。"""

from __future__ import annotations

import argparse
import csv
import math
import os
import random
import sys
from pathlib import Path


DEFAULT_OFFICIAL_DIR = Path(
    r"E:\ai_pilot\2026 AI 飛行員  相關資料"
    r"\AI空戰競賽系統安裝及測試指引"
    r"\AI空戰競賽系統安裝及測試指引"
    r"\AirCombat_Train_Test"
)
DEFAULT_OUTPUT = (
    Path(os.environ.get("LOCALAPPDATA", Path.home()))
    / "ai-pilot"
    / "data"
    / "flight_stability.csv"
)

FIELDS = [
    "episode",
    "step",
    "time_s",
    "latitude_deg",
    "longitude_deg",
    "altitude_ft",
    "heading_deg",
    "pitch_deg",
    "roll_deg",
    "calibrated_airspeed_kts",
    "mach",
    "alpha_deg",
    "beta_deg",
    "aileron_cmd",
    "elevator_cmd",
    "rudder_cmd",
    "throttle_cmd",
    "target_altitude_ft",
    "target_speed_kts",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=12)
    parser.add_argument("--steps", type=int, default=1800)
    parser.add_argument("--seed", type=int, default=20260918)
    parser.add_argument("--official-dir", type=Path, default=DEFAULT_OFFICIAL_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.episodes < 1 or args.steps < 1:
        raise SystemExit("episodes 與 steps 必須大於 0。")

    official_dir = args.official_dir.resolve()
    if not (official_dir / "envs" / "jsbsimEnv" / "jsbsimFdm.py").is_file():
        raise SystemExit(f"找不到官方環境：{official_dir}")

    sys.path.insert(0, str(official_dir))
    previous_cwd = Path.cwd()
    os.chdir(official_dir)
    try:
        from envs.jsbsimEnv.jsbsimFdm import JsbsimFdm

        rng = random.Random(args.seed)
        args.output.parent.mkdir(parents=True, exist_ok=True)

        row_count = 0
        with args.output.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()

            for episode in range(args.episodes):
                initial_altitude = rng.randint(5_000, 20_000)
                initial_speed = rng.randint(320, 420)
                initial_heading = rng.randint(0, 359)

                fdm = JsbsimFdm(
                    fdm_aircraft="f16",
                    fdm_ic_h=initial_altitude,
                    fdm_ic_v=initial_speed,
                    fdm_ic_psi=initial_heading,
                )

                for step in range(args.steps):
                    fdm.auto_run()
                    fdm.step()

                    altitude_ft = float(fdm.fdm["position/h-sl-ft"])
                    speed_kts = float(fdm.fdm["velocities/vc-kts"])
                    values = [
                        altitude_ft,
                        speed_kts,
                        float(fdm.fdm["attitude/psi-deg"]),
                        float(fdm.fdm["attitude/theta-deg"]),
                        float(fdm.fdm["attitude/phi-deg"]),
                    ]
                    if not all(math.isfinite(value) for value in values):
                        raise RuntimeError(
                            f"episode={episode} step={step} 出現非有限數值"
                        )

                    writer.writerow(
                        {
                            "episode": episode,
                            "step": step,
                            "time_s": f"{step / 60.0:.4f}",
                            "latitude_deg": f"{fdm.fdm['position/lat-gc-deg']:.8f}",
                            "longitude_deg": f"{fdm.fdm['position/long-gc-deg']:.8f}",
                            "altitude_ft": f"{altitude_ft:.4f}",
                            "heading_deg": f"{fdm.fdm['attitude/psi-deg']:.4f}",
                            "pitch_deg": f"{fdm.fdm['attitude/theta-deg']:.4f}",
                            "roll_deg": f"{fdm.fdm['attitude/phi-deg']:.4f}",
                            "calibrated_airspeed_kts": f"{speed_kts:.4f}",
                            "mach": f"{fdm.fdm['velocities/mach']:.6f}",
                            "alpha_deg": f"{fdm.fdm['aero/alpha-deg']:.4f}",
                            "beta_deg": f"{fdm.fdm['aero/beta-deg']:.4f}",
                            "aileron_cmd": f"{fdm.fdm['fcs/aileron-cmd-norm']:.6f}",
                            "elevator_cmd": f"{fdm.fdm['fcs/elevator-cmd-norm']:.6f}",
                            "rudder_cmd": f"{fdm.fdm['fcs/rudder-cmd-norm']:.6f}",
                            "throttle_cmd": f"{fdm.fdm['fcs/throttle-cmd-norm']:.6f}",
                            "target_altitude_ft": initial_altitude,
                            "target_speed_kts": initial_speed,
                        }
                    )
                    row_count += 1
    finally:
        os.chdir(previous_cwd)

    print(f"dataset={args.output}")
    print(f"rows={row_count}")
    print(f"episodes={args.episodes} steps_per_episode={args.steps}")


if __name__ == "__main__":
    main()

