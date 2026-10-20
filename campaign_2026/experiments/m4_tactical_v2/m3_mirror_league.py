"""M3 ??mirror league: the first genuine self-play measurement.

Every opponent trained or evaluated so far has FAILED to attack:
`enemy_attack_seconds` is 0.0 across every historical run. The Host's built-in
Player2 is literally "Random level-flight PID controller (SAC disabled)".

So the project has never actually fought anything. This runner adds a MIRROR
opponent: Player2 flies the same RepairController, reading only its legal
OWN20+ENEMY6 observation. It attacks, it turns, it defends. That is what makes
the measurement a self-play measurement.

It subclasses the frozen env; it does not modify repair_v1 or any SHA-bound file.

Actors
    guide      frozen RepairController
    latch      GGuardLatchBank80 (bank 80 + 8.5G/8.0G latch)

Opponents
    rule       original RuleFighter (maneuvers, rarely kills)
    rl         frozen 148,682-step SAC residual (survives, never attacks)
    mirror     RepairController ??the fighting opponent

Usage:
    python m3_mirror_league.py --out OUTDIR [--per-cell 3] [--seed 2026110100]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

CAMPAIGN = Path(r"E:\ai_pilot\campaign_2026")
REPAIR = CAMPAIGN / "repair_v1"
GLATCH = CAMPAIGN / "experiments" / "g_latch_development"
NEARBANK = CAMPAIGN / "experiments" / "near_bank80"   # supplies candidate.Bank80Controller
for p in (str(REPAIR), str(GLATCH), str(NEARBANK)):
    sys.path.insert(0, p)

import torch
torch.set_num_threads(1)

from env import RepairDuel, simulator_observation          # noqa: E402
from controller import RepairController                     # noqa: E402
from combat_v3.interface import geometry_from_observation   # noqa: E402
from artifacts import load_policy                          # noqa: E402
from env import DEFAULT_BUNDLE                             # noqa: E402

_KILL_TICKS = 180          # 3.0 s at 60 Hz, confirmed on the official Host

KILL_TICKS = 180          # 3.0 s at 60 Hz, confirmed on the official Host
OPPONENTS = ("rule", "rl", "mirror")
ACTORS = ("guide", "latch")
HERE = Path(__file__).resolve().parent
DISTANCES = (3000, 6000, 9000)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class MirrorDuel(RepairDuel):
    """Adds a fighting Player2. Frozen behaviour is untouched for rule/rl.

    PERTURBED mode exists because a byte-identical mirror DEADLOCKS: measured
    median separation 4019 m with blue nose angle median 89.8 deg and minimum
    30.4 deg over 3000 samples. Two identical deterministic controllers in a
    merge both turn inside and settle into a mutual perpendicular standoff
    ~4 km apart -- neither can ever satisfy (nose <= 1 deg AND range 500-3000 ft).

    Symmetry is therefore useless as a sparring partner. The perturbation
    below breaks it cheaply and stays inside the legal observation contract:
      * different gains on the P2 controller
      * a sinusoidal aim-point bias, so P2 periodically commits to a gun solution
        instead of mirroring blue's manoeuvre
      * P2 prefers inside energy, which is what actually wins merges
    """

    P2_GAIN_SCALE = 0.72          # P2 turns more slowly: blue gets the inside
    P2_AIM_BIAS_DEG = 6.0         # P2 aims off-axis, so blue is never symmetric
    P2_COMMIT_PERIOD_S = 9.0      # P2 periodically drives straight at blue

    def reset(self, **kw):
        if kw.get("p2") == "mirror":
            self.requested_p2 = "mirror"
        obs, info = super().reset(**kw)
        self.p2_type = "mirror"
        self._mirror = RepairController(self.settings, "repair")
        self._mirror_p2 = MirrorP2Controller(
            self.settings, self.P2_GAIN_SCALE,
            self.P2_AIM_BIAS_DEG, self.P2_COMMIT_PERIOD_S)
        self.p2_mode = "mirror_idle"
        return obs, info

    def _red_action(self):
        if getattr(self, "p2_type", None) != "mirror":
            return super()._red_action()
        obs = simulator_observation(self.fdm2, self.fdm1)   # legal: OWN20+ENEMY6 only
        try:
            cmd, guard = self._mirror_p2.act(obs, self.current_step)
            self.p2_mode = "mirror_" + str(self._mirror_p2.mode)
            self.p2_guard = guard
            return np.asarray(cmd, dtype=np.float32)
        except Exception:                                    # never let P2 crash the round
            self.p2_mode = "mirror_fallback"
            return np.array([0., 0., 0., 0.8], dtype=np.float32)


class MirrorP2Controller(RepairController):
    """RepairController with an asymmetric doctrine, so blue can actually fight."""

    def __init__(self, settings, gain_scale, bias_deg, commit_period_s):
        super().__init__(settings, "repair")
        self.gain_scale = float(gain_scale)
        self.bias_deg = float(bias_deg)
        self.commit_period_s = float(commit_period_s)

    def act(self, observation, step, residual=None, started=True):   # noqa: D102
        if not started:
            return np.array([0., 0., 0., .8]), False
        o = observation
        geo = geometry_from_observation(o)
        d = geo["distance_m"]
        phase = (step / 60.0 / self.commit_period_s) % 1.0
        commit = phase < 0.55                     # 55% of the time, drive the solution
        near = d < 1100
        self.mode = "track" if near else "intercept"

        bearing = geo["bearing_deg"]
        if commit:
            # Shorten the lead: commit to the gun solution instead of mirroring.
            lead_delta = float(np.clip(
                ((geo["lead_bearing_deg"] - bearing + 180) % 360) - 180, -20, 20))
            bearing += lead_delta * (0.85 if near else 0.35)
        else:
            # Break away: swing wide so blue cannot settle into a mirrored turn.
            bearing += self.bias_deg * (1 if int(step / 180) % 2 == 0 else -1)

        heading_error = ((bearing - o[5] + 180) % 360) - 180
        bank = float(np.clip(self.gain_scale * 2.4 * heading_error, -70, 70))

        altitude, enemy_altitude = o[2] * .3048, o[22] * .3048
        downward = o[8] * .3048
        if near and geo["blue_angle_deg"] < 45:
            pitch = geo["elevation_deg"]
        else:
            pitch = o[18] + float(np.clip((enemy_altitude - altitude) * .012
                                          + downward * .16, -8, 12))
        speed = float(np.clip(
            geo["enemy_equivalent_cas_kts"]
            + float(np.clip((d - 600) * .07, -30, 65)) * 1.9438444924 * geo["cas_ratio"],
            260, 450))
        return self.command(o, bank, float(np.clip(pitch, -18, 25)), speed, 0.)


class ActorDuel(MirrorDuel):
    """Installs the requested BLUE controller and keeps it installed.

    RepairDuel.reset() unconditionally rebuilds packet_controller from a plain
    RepairController (env.py:69), so anything assigned before reset is silently
    discarded. That made every earlier actor comparison a no-op: 'latch' and
    'guide' were literally the same object, and their differing kill counts
    were just different seeds. This subclass re-installs after every reset.
    """

    def __init__(self, *args, actor: str = "guide", **kw):
        self._actor = actor
        super().__init__(*args, **kw)

    def _build_actor(self):
        if self._actor == "latch":
            from safe_candidate import GGuardLatchBank80
            return GGuardLatchBank80(self.settings, "repair")
        if self._actor == "station":
            from m1_station import StationController
            return StationController(self.settings, "station")
        if self._actor == "station_latch":
            from safe_candidate import GGuardLatchBank80
            from m1_station import StationController

            class StationLatch(StationController):
                """M1 doctrine layered on the M2-proven G latch limiter."""
                def command(self, obs, roll_target, pitch_target, speed_target,
                            rudder=0., safety=True):
                    return GGuardLatchBank80.command(
                        self, obs, roll_target, pitch_target, speed_target,
                        rudder, safety)

            return StationLatch(self.settings, "station")
        return RepairController(self.settings, "repair")

    def reset(self, **kw):
        obs, info = super().reset(**kw)
        self.packet_controller = self._build_actor()
        self.controller_variant = self._actor
        info["controller_variant"] = self._actor
        return obs, info


def make_env(actor: str, opponent: str, distance_ft: int, mirror_ok: bool):
    cls = ActorDuel if mirror_ok else RepairDuel
    if mirror_ok:
        env = ActorDuel(p2=opponent, distance_ft=distance_ft, attack_angle=1.0,
                        max_steps=18000, actor=actor)
    else:
        env = cls(p2=opponent, policy=None, controller="repair",
                  distance_ft=distance_ft, attack_angle=1.0, max_steps=18000)
    if opponent == "rl":
        # RepairDuel refuses p2_type='rl' without the frozen residual policy.
        env.frozen_policy = load_policy(DEFAULT_BUNDLE)
    if not mirror_ok and actor != "guide":
        env._actor = actor
        env._original_reset = env.reset

        def reset_with_actor(**k):
            obs, info = env._original_reset(**k)
            env.packet_controller = ActorDuel._build_actor(env)
            env.controller_variant = actor
            info["controller_variant"] = actor
            return obs, info

        env.reset = reset_with_actor
    return env


def run_case(actor, opponent, distance_ft, seed, out_dir: Path, acmi: bool,
             max_steps: int = 18000):
    env = make_env(actor, opponent, distance_ft, opponent == "mirror")
    env.max_steps = max_steps
    obs, info = env.reset(seed=seed)
    initial = simulator_observation(env.fdm1, env.fdm2).tolist()

    rows, modes = [], {}
    total, ticks, max_g, attack_ticks_seen = 0.0, 0, 0.0, 0
    term = trunc = False
    start = time.monotonic()

    folder = out_dir / f"{actor}__{opponent}__{distance_ft}__{seed}"
    folder.mkdir(parents=True, exist_ok=True)
    acmi_path = folder / "duel.acmi"
    stream = acmi_path.open("w", encoding="utf-8") if acmi else None
    if stream:
        stream.write("FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime="
                     + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n")
        stream.write("1,Type=Air+FixedWing,Name=F16,CallSign=P1 " + actor + ",Color=Blue\n")
        stream.write("2,Type=Air+FixedWing,Name=F16,CallSign=P2 " + opponent + ",Color=Red\n")
        env.write_frame(stream)

    action = np.zeros(4, dtype=np.float32)
    try:
        for step in range(max_steps):
            obs, reward, term, trunc, info = env.step(action)
            total += float(reward)
            ticks += 1
            max_g = max(max_g, float(info.get("load_factor", 0.0)))
            modes[info.get("p2_mode", "?")] = modes.get(info.get("p2_mode", "?"), 0) + 1
            attack_ticks_seen = max(attack_ticks_seen, int(round(info["attack_seconds"] * 60)))
            if stream and (ticks % 6 == 0 or term or trunc):
                env.write_frame(stream)
            if ticks % 6 == 0 or term or trunc:
                rows.append({
                    "t": round(ticks / 60, 3),
                    "distance": info.get("distance"),
                    "blue_angle_deg": info.get("blue_angle_deg"),
                    "red_angle_deg": info.get("red_angle_deg"),
                    "altitude_m": info.get("altitude_m"),
                    "load_factor": info.get("load_factor"),
                    "attack_seconds": info.get("attack_seconds"),
                    "enemy_attack_seconds": info.get("enemy_attack_seconds"),
                })
            if term or trunc:
                break
    finally:
        env.close()
        if stream:
            stream.close()

    if rows:
        with (folder / "telemetry.csv").open("w", encoding="utf-8", newline="") as s:
            w = csv.DictWriter(s, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    f = info
    item = {
        "actor": actor, "opponent": opponent, "distance_ft": distance_ft, "seed": seed,
        "steps": ticks, "wall_seconds": round(time.monotonic() - start, 2),
        "full_round_completed": bool(term or (trunc and ticks == max_steps)),
        "outcome": f.get("outcome"), "is_kill": int(f.get("is_kill", 0)),
        "was_hit": int(f.get("was_hit", 0)), "survived": int(f.get("survived", 0)),
        "own_crash": int(f.get("own_crash", 0)), "enemy_crash": int(f.get("enemy_crash", 0)),
        "attack_seconds": round(float(f.get("attack_seconds", 0.0)), 4),
        "attack_ticks": int(round(float(f.get("attack_seconds", 0.0)) * 60)),
        "kill_ticks_needed": KILL_TICKS,
        "enemy_attack_seconds": round(float(f.get("enemy_attack_seconds", 0.0)), 4),
        "over_9g_seconds": round(float(f.get("over_9g_seconds", 0.0)), 4),
        "min_altitude_m": round(float(f.get("min_altitude_m", 0.0)), 1),
        "max_g": round(max_g, 3),
        "p2_mode_ticks": modes, "local_reward": round(total, 3),
        "initial_obs26": initial, "acmi": str(acmi_path) if acmi else None,
    }
    (folder / "result.json").write_text(json.dumps(item, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    return item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--per-cell", type=int, default=3,
                    help="episodes per (actor, opponent, distance) cell")
    ap.add_argument("--seed", type=int, default=2026110100)
    ap.add_argument("--acmi", action="store_true")
    ap.add_argument("--opponents", default="rule,rl,mirror",
                    help="comma separated subset of rule,rl,mirror")
    ap.add_argument("--actors", default=",".join(ACTORS),
                    help="comma separated subset of guide,latch,station,station_latch")
    a = ap.parse_args()

    opponents = tuple(x.strip() for x in a.opponents.split(",") if x.strip())
    for o in opponents:
        if o not in OPPONENTS:
            ap.error(f"unknown opponent {o}; choose from {OPPONENTS}")
    actors = tuple(x.strip() for x in a.actors.split(",") if x.strip())
    for x in actors:
        if x not in ("guide", "latch", "station", "station_latch"):
            ap.error(f"unknown actor {x}")

    out = a.out
    out.mkdir(parents=True, exist_ok=False)
    srcs = {f"{p.parent.name}/{p.name}": sha(p)
            for p in [REPAIR / "env.py", REPAIR / "controller.py", GLATCH / "safe_candidate.py"]}
    report = {"format": "m3_mirror_league_v1", "status": "running",
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "official_validation": False, "deployment_allowed": False,
              "seed_role": "fresh_development_not_holdout",
              "attack_angle_deg": 1.0, "kill_ticks": KILL_TICKS,
              "opponents": list(opponents), "actors": list(actors),
              "distances_ft": list(DISTANCES), "per_cell": a.per_cell,
              "planned_cases": len(actors) * len(opponents) * len(DISTANCES) * a.per_cell,
              "source_sha256": srcs, "cases": []}
    rp = out / "report.json"

    def flush():
        rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    flush()
    try:
        for actor in actors:
            for opponent in opponents:
                for dist in DISTANCES:
                    for k in range(a.per_cell):
                        seed = a.seed + len(report["cases"])
                        item = run_case(actor, opponent, dist, seed, out, a.acmi)
                        report["cases"].append(item)
                        flush()
                        print(f"[{len(report['cases']):>3}/{report['planned_cases']}] "
                              f"{actor:<5} vs {opponent:<6} {dist:>4}ft seed={seed} "
                              f"-> {item['outcome']:<8} atk={item['attack_seconds']:.3f}s "
                              f"({item['attack_ticks']}/{KILL_TICKS}) "
                              f"enemyAtk={item['enemy_attack_seconds']:.3f}s", flush=True)
                        if not item["full_round_completed"]:
                            raise RuntimeError(f"incomplete case {item['seed']}")

        cells = {}
        for actor in actors:
            for opponent in opponents:
                rows = [c for c in report["cases"]
                        if c["actor"] == actor and c["opponent"] == opponent]
                cells[f"{actor}|{opponent}"] = {
                    "n": len(rows),
                    "kills": sum(c["is_kill"] for c in rows),
                    "survived": sum(c["survived"] for c in rows),
                    "own_crashes": sum(c["own_crash"] for c in rows),
                    "was_hit": sum(c["was_hit"] for c in rows),
                    "attack_seconds": round(sum(c["attack_seconds"] for c in rows), 3),
                    "best_attack_ticks": max((c["attack_ticks"] for c in rows), default=0),
                    "enemy_attack_seconds": round(sum(c["enemy_attack_seconds"] for c in rows), 3),
                    "over_9g_seconds": round(sum(c["over_9g_seconds"] for c in rows), 4),
                    "min_altitude_m": round(min(c["min_altitude_m"] for c in rows), 1),
                }
        report["cells"] = cells
        report["status"] = "completed"
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        flush()
        print("\n=== mirror league ===")
        for k, v in cells.items():
            print(f"{k:<22} n={v['n']:<3} kills={v['kills']:<2} atk={v['attack_seconds']:>7.2f}s "
                  f"best={v['best_attack_ticks']:>3}/{KILL_TICKS} "
                  f"enemyAtk={v['enemy_attack_seconds']:.2f}s crash={v['own_crashes']} "
                  f"hit={v['was_hit']}")
    except BaseException as e:                      # noqa: BLE001
        report.update(status="failed", error=repr(e))
        flush()
        raise


if __name__ == "__main__":
    main()
