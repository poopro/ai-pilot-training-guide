"""Isolated local P2 opponents. No UDP, network APIs, or model training.

SAC is the existing frozen guided-residual policy, not a new trained opponent.
The configurable attack angle labels a local diagnostic profile, not official approval.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import subprocess
import sys
import time
import uuid

import numpy as np

BASE = Path(r"E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test")
sys.path.insert(0, str(BASE))
from combat_v3.env import CombatEnvV3
from combat_v3.fdm import JsbsimFdm
from combat_v3.controller import relative_geometry, wrap_deg
from combat_v3.interface import simulator_observation, geometry_from_observation, policy_state, PacketController, OwnSnapshot
from combat_v3.rules import LocalJudge, position_index, FT_TO_M, HZ

DEFAULT_BUNDLE = Path(r"E:\ai_pilot\autopilot\jobs\job_20261004_235618_984b\candidate2\candidate1_to_199000\final_0000148682")


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_policy(bundle):
    from stable_baselines3 import SAC
    import torch
    torch.set_num_threads(1)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest["format"] not in ("guided_combat_v3", "opponent_lab_sac_v1"):
        raise ValueError("需要第三版或新對手實驗的引導器＋SAC 修正量存檔")
    sources = (manifest["config"]["source_sha256"] if manifest["format"] == "guided_combat_v3"
               else manifest["config"]["base_source_sha256"])
    for name in ("controller.py", "interface.py", "config.json"):
        if file_hash(BASE / "combat_v3" / name) != sources[name]:
            raise ValueError(f"模型與控制器不相容：{name}")
    if file_hash(bundle / "model.zip") != manifest["model_sha256"]:
        raise ValueError("模型校驗不符")
    return SAC.load(str(bundle / "model.zip"), device="cpu")


class DiagnosticJudge(LocalJudge):
    def __init__(self, weights, angle_deg):
        super().__init__(weights)
        self.angle_deg = float(angle_deg)

    def window(self, distance_m, angle):
        return 500 * FT_TO_M <= distance_m <= 3000 * FT_TO_M and 0 <= angle <= self.angle_deg

    def update(self, geo, g_blue, g_red):
        d, ba, ra = geo["distance_m"], geo["blue_angle_deg"], geo["red_angle_deg"]
        self.attack[0] += int(self.window(d, ba))
        self.attack[1] += int(self.window(d, ra))
        self.over_g[0] += int(abs(g_blue) > 9)
        self.over_g[1] += int(abs(g_red) > 9)
        self.position[0] += position_index(d, ba, ra)
        self.position[1] += position_index(d, ra, ba)


class RuleFighter:
    """Pursuit/tracking and threat-triggered break turn, using OWN20+ENEMY6 only."""
    def __init__(self, settings, initial_altitude_m, rng):
        self.controller = PacketController(settings)
        self.altitude_m = initial_altitude_m
        self.rng = rng
        self.break_until = -1.0
        self.next_break_allowed = 0.0
        self.break_bank = 0.0
        self.mode = "intercept"
        self.guard = False

    def act(self, observation, elapsed_s):
        geo = geometry_from_observation(observation)
        # Enemy velocity direction is an estimate of threat, never its hidden nose.
        threatened = (geo["distance_m"] < 1300 and geo["aspect_proxy_deg"] < 18
                      and geo["blue_angle_deg"] > 65)
        if threatened and elapsed_s >= self.next_break_allowed:
            self.break_bank = float(self.rng.choice([-1, 1])) * 65
            self.break_until = elapsed_s + 2.5
            self.next_break_allowed = elapsed_s + 6.0
        if elapsed_s < self.break_until:
            self.mode = "defensive_break"
            command, self.guard = self.controller.control.level(
                OwnSnapshot(observation), self.altitude_m, self.break_bank, 410)
        else:
            if geo["distance_m"] > 1200:
                # A different, altitude-controlled pure-pursuit entry avoids both
                # planes following identical lead-intercept circles indefinitely.
                heading_error = wrap_deg(geo["bearing_deg"] - observation[5])
                bank = float(np.clip(1.8 * heading_error, -72, 72))
                own_altitude = observation[2] * FT_TO_M
                target_altitude = float(np.clip(observation[22] * FT_TO_M,
                                               max(1200, own_altitude - 600),
                                               max(1200, own_altitude + 600)))
                speed = 340 if abs(heading_error) > 45 else 400
                command, self.guard = self.controller.control.level(
                    OwnSnapshot(observation), target_altitude, bank, speed)
                self.mode = "altitude_controlled_pursuit"
            else:
                residual = np.zeros(4, dtype=np.float32)
                command, self.guard = self.controller.act(observation, residual)
                self.mode = "precision_track"
        if self.guard:
            self.mode = "recover"
        return command


class DuelLab(CombatEnvV3):
    def __init__(self, p2="rule", policy=None, attack_angle=1.0, max_steps=18000, distance_ft=6000):
        super().__init__(opponent="duel", scenario="official", max_steps=max_steps)
        self.p2_type = p2
        self.frozen_policy = policy
        self.attack_angle = attack_angle
        self.distance_ft = distance_ft
        self.p2_mode = "initializing"
        self.p2_guard = False

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed, options={"distance_ft": self.distance_ft})
        initial = simulator_observation(self.fdm2, self.fdm1)
        latitude, longitude, altitude_ft, heading = initial[0], initial[1], initial[2], initial[5]
        distance_m = self.distance_ft * FT_TO_M
        bearing = math.radians(heading - 90)
        blue_lat = latitude + math.degrees(math.cos(bearing) * distance_m / 6378137)
        blue_lon = longitude + math.degrees(math.sin(bearing) * distance_m / (6378137 * math.cos(math.radians(latitude))))
        common = {"fdm_ic_h": altitude_ft, "fdm_ic_v": 340}
        self.fdm1 = JsbsimFdm(fdm_id=1, fdm_ic_lat=blue_lat, fdm_ic_long=blue_lon,
                             fdm_ic_psi=(heading + 180) % 360, **common)
        self.fdm2 = JsbsimFdm(fdm_id=2, fdm_ic_lat=latitude, fdm_ic_long=longitude,
                             fdm_ic_psi=heading, **common)
        self.judge = DiagnosticJudge(self.settings["reference_score_weights"], self.attack_angle)
        self.red_packet_controller = PacketController(self.settings)
        self.red_fighter = RuleFighter(self.settings, altitude_ft * FT_TO_M, self.np_random)
        self.geometry = relative_geometry(self.fdm1, self.fdm2)
        self.prev_potential = self._potential(self.geometry)
        self.min_altitude_m = float(self.fdm1.fdm["position/h-agl-ft"]) * FT_TO_M
        self.p2_mode, self.p2_guard = "initializing", False
        return policy_state(simulator_observation(self.fdm1, self.fdm2)), self._info()

    def _red_action(self):
        observation = simulator_observation(self.fdm2, self.fdm1)
        if self.p2_type == "rule":
            command = self.red_fighter.act(observation, self.current_step / HZ)
            self.p2_mode, self.p2_guard = self.red_fighter.mode, self.red_fighter.guard
        else:
            residual = self.frozen_policy.predict(policy_state(observation), deterministic=True)[0]
            command, self.p2_guard = self.red_packet_controller.act(observation, residual)
            self.p2_mode = "recover" if self.p2_guard else self.red_packet_controller.control.mode
        if command.shape != (4,) or not np.isfinite(command).all():
            raise ValueError("P2 輸出無效")
        return command

    def step(self, action):
        observation, reward, terminated, truncated, info = super().step(action)
        # Parent uses its published 2-degree window in its dense reward. Correct the
        # attack component to match this lab's diagnostic judge; never change globals.
        geo = self.geometry
        d, ba, ra = geo["distance_m"], geo["blue_angle_deg"], geo["red_angle_deg"]
        old_blue = 500 * FT_TO_M <= d <= 3000 * FT_TO_M and ba <= 2
        old_red = 500 * FT_TO_M <= d <= 3000 * FT_TO_M and ra <= 2
        new_blue, new_red = self.judge.window(d, ba), self.judge.window(d, ra)
        reward += self.dt * self.settings["reward"]["attack_per_second"] * (
            int(new_blue) - int(new_red) - int(old_blue) + int(old_red))
        info.update(p2_type=self.p2_type, p2_mode=self.p2_mode,
                    p2_guard=self.p2_guard, attack_angle_deg=self.attack_angle,
                    blue_hp=max(0, 180 - self.red_frames), red_hp=max(0, 180 - self.blue_frames))
        return observation, reward, terminated, truncated, info

    def write_frame(self, stream):
        stream.write(f"#{self.current_step / HZ:.3f}\n")
        for oid, plane in [(1, self.fdm1), (2, self.fdm2)]:
            pose = plane.getProperty("pose")
            stream.write(f"{oid},T={pose[1]}|{pose[7]}|{pose[2]}|{pose[5]}|{pose[4]}|{pose[3]}\n")


def main():
    parser = argparse.ArgumentParser(description="本地對戰：規則式／現有 SAC 控制 P2；不訓練、不連官方 Host")
    parser.add_argument("--p2", choices=["rule", "rl"], default="rule")
    parser.add_argument("--blue", choices=["guide", "rl"], default="guide")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--red-bundle", type=Path, help="紅方獨立模型；省略時與 bundle 相同")
    parser.add_argument("--seed", type=int, default=20264000)
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--distance-ft", type=int, choices=[3000, 6000, 9000], default=6000)
    parser.add_argument("--attack-angle", type=float, choices=[1.0, 2.0], default=1.0)
    parser.add_argument("--max-steps", type=int, default=18000)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--open-tacview", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_steps <= 18000 or args.episodes < 1:
        parser.error("max-steps 須為 1–18000、episodes 須為正整數")
    blue_policy = load_policy(args.bundle) if args.blue == "rl" else None
    red_source = args.red_bundle or args.bundle
    red_policy = None
    if args.p2 == "rl":
        red_policy = (blue_policy if blue_policy is not None and red_source.resolve() == args.bundle.resolve()
                      else load_policy(red_source))
    output = args.out or Path(__file__).parent / "outputs" / (
        datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + args.p2 + "_" + uuid.uuid4().hex[:4])
    output.mkdir(parents=True, exist_ok=False)
    (output / "lab_source.py").write_bytes(Path(__file__).read_bytes())
    report = {"status": "running", "official_validation": False,
              "scenario": "side_by_side_opposite_headings", "attack_angle_deg": args.attack_angle,
              "collision_model": "not modeled; not official validation",
              "p2": args.p2, "blue": args.blue, "training_steps_added": 0,
              "rl_type": "existing frozen guided SAC residual; strength not guaranteed",
              "bundle": str(args.bundle) if blue_policy is not None else None,
              "red_bundle": str(red_source) if red_policy is not None else None,
              "lab_sha256": file_hash(Path(__file__)),
              "v3_sources": {name: file_hash(BASE / "combat_v3" / name) for name in
                             ["env.py", "fdm.py", "controller.py", "interface.py", "rules.py", "config.json"]},
              "episodes": []}
    save = lambda: (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    save()
    environment = DuelLab(args.p2, red_policy, args.attack_angle, args.max_steps, args.distance_ft)
    first_acmi = None
    try:
        for episode in range(args.episodes):
            seed = args.seed + episode
            obs, _ = environment.reset(seed=seed)
            p1 = simulator_observation(environment.fdm1, environment.fdm2)
            p2 = simulator_observation(environment.fdm2, environment.fdm1)
            initial = {"distance_ft": environment.geometry["distance_m"] / FT_TO_M,
                       "blue_heading": float(p1[5]), "red_heading": float(p2[5]),
                       "blue_cas_kts": float(environment.fdm1.fdm["velocities/vc-kts"]),
                       "red_cas_kts": float(environment.fdm2.fdm["velocities/vc-kts"])}
            acmi = output / f"duel_{seed}_{args.p2}.acmi"
            if first_acmi is None:
                first_acmi = acmi
            modes = {}
            total_reward = 0.0
            start = time.monotonic()
            with acmi.open("w", encoding="utf-8") as stream:
                reference = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                stream.write(f"FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime={reference}\n")
                stream.write(f"1,Type=Air+FixedWing,Name=F16,CallSign=P1 {args.blue},Color=Blue\n")
                stream.write(f"2,Type=Air+FixedWing,Name=F16,CallSign=P2 {args.p2},Color=Red\n")
                environment.write_frame(stream)
                for step in range(args.max_steps):
                    action = np.zeros(4, dtype=np.float32) if args.blue == "guide" else blue_policy.predict(obs, deterministic=True)[0]
                    obs, reward, terminated, truncated, info = environment.step(action)
                    total_reward += reward
                    modes[info["p2_mode"]] = modes.get(info["p2_mode"], 0) + 1
                    if (step + 1) % 6 == 0 or terminated or truncated:
                        environment.write_frame(stream)
                    if (step + 1) % 1800 == 0:
                        print(f"seed={seed} t={(step + 1)/HZ:.0f}s P2={info['p2_mode']} HP blue/red={info['blue_hp']}/{info['red_hp']}", flush=True)
                    if terminated or truncated:
                        break
            report["episodes"].append({"seed": seed, "initial": initial, "steps": step + 1,
                                       "full_round_completed": bool(terminated or (truncated and args.max_steps == 18000)),
                                       "local_reward": total_reward, "wall_seconds": time.monotonic() - start,
                                       "p2_mode_ticks": modes, "final": info, "acmi": str(acmi)})
            save()
        report["status"] = "completed"
    except KeyboardInterrupt:
        report["status"] = "interrupted"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = repr(error)
        raise
    finally:
        environment.close()
        save()
    print(f"本地對戰報告：{output / 'report.json'}", flush=True)
    print(f"藍色=P1（你）；紅色=P2（{args.p2}）；這是本地模擬，不是官方裁判。", flush=True)
    if report["status"] == "completed" and args.open_tacview and first_acmi:
        tacview = Path(r"C:\Program Files (x86)\Tacview\Tacview64.exe")
        if tacview.exists():
            subprocess.Popen([str(tacview), str(first_acmi)])
        else:
            print(f"請用 Tacview 開啟：{first_acmi}", flush=True)


if __name__ == "__main__":
    main()
