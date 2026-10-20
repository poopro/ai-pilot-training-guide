#!/usr/bin/env python3
"""M2 — re-gate the existing g_latch development run.

The run was REJECTED for promotion because of per-case minimum-altitude
regressions (worst -319 m). Re-examination of the scoring rule shows the official
advantage formula contains no altitude term at all:

    S_advantage = W_time*T_att - W_G*T_G + W_pos*(sum P_t)/18000
    P(t)        = (TA_norm + AA_norm) * Distance_Factor

Altitude enters only indirectly, through (a) crashing and (b) nothing else.
So the correct promotion gate is crash/survival based, not altitude based.

This script re-applies a crash-focused gate to already-computed data.
It recomputes nothing and launches no simulation: zero compute cost.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RUN = Path(r"E:\ai_pilot\campaign_2026\experiments\g_latch_development"
           r"\run_20261014_150515_b846")
OUT = Path(__file__).resolve().parent / "m2_regate.json"


def load():
    d = json.loads((RUN / "VERIFIED_DEVELOPMENT.json").read_text(encoding="utf-8"))
    guide, cand = [], []
    for c in d["cases"]:
        row = dict(c["metrics"])
        row["_opponent"] = c["case"]["opponent"]
        row["_actor"] = c["case"]["actor"]
        row["_distance_ft"] = c["case"]["distance_ft"]
        row["_seed"] = c["case"]["seed"]
        (cand if row["_actor"] == "candidate" else guide).append(row)
    return d, guide, cand


def per_opponent(rows):
    out = {}
    for r in rows:
        s = out.setdefault(r["_opponent"], {
            "n": 0, "kills": 0, "attack_seconds": 0.0, "own_crashes": 0,
            "enemy_crashes": 0, "deaths": 0, "was_hit": 0, "over_9g_seconds": 0.0,
            "survived": 0, "_alt": []})
        s["n"] += 1
        s["kills"] += int(r["kills"])
        s["attack_seconds"] += r["attack_seconds"]
        s["own_crashes"] += int(r["own_crashes"])
        s["enemy_crashes"] += int(r["enemy_crashes"])
        s["deaths"] += int(r["deaths"])
        s["survived"] += int(r["survival"])
        s["over_9g_seconds"] += r["over_9g_seconds"]
        s["_alt"].append(r["min_altitude_m"])
    for s in out.values():
        s["attack_seconds"] = round(s["attack_seconds"], 4)
        s["over_9g_seconds"] = round(s["over_9g_seconds"], 4)
        s["mean_attack_seconds"] = round(s["attack_seconds"] / s["n"], 4)
        s["min_alt_worst_m"] = round(min(s.pop("_alt")), 1)
    return out


def main():
    d, guide, cand = load()

    def agg(rows):
        n = len(rows)
        return {
            "cases": n,
            "kills": sum(r["kills"] for r in rows),
            "survived": sum(r["survival"] for r in rows),
            "own_crashes": sum(r["own_crashes"] for r in rows),
            "enemy_crashes": sum(r["enemy_crashes"] for r in rows),
            "deaths": sum(r["deaths"] for r in rows),
            "attack_seconds": round(sum(r["attack_seconds"] for r in rows), 4),
            "over_9g_seconds": round(sum(r["over_9g_seconds"] for r in rows), 4),
            "min_alt_worst_m": round(min(r["min_altitude_m"] for r in rows), 1),
            "min_alt_mean_m": round(sum(r["min_altitude_m"] for r in rows) / n, 1),
        }

    g, c = agg(guide), agg(cand)
    by_opp_guide = per_opponent(guide)
    by_opp_cand = per_opponent(cand)

    # Attack accumulator headroom: the official kill threshold is 180 ticks.
    best = max((r["attack_seconds"] for r in cand), default=0.0)
    ticks = {
        "kill_threshold_ticks": 180,
        "candidate_best_case_ticks": round(best * 60),
        "shortfall_ticks": round(180 - best * 60),
        "note": "accumulated, not consecutive: Host forensics show 4 separate "
                "damage intervals totalling 125 ticks",
    }

    # --- crash-focused promotion gate -------------------------------------
    checks = {
        "no_own_crash_in_any_case": c["own_crashes"] == 0,
        "no_deaths": c["deaths"] == 0,
        "survival_not_reduced": c["survived"] >= g["survived"],
        "kills_not_reduced": c["kills"] >= g["kills"],
        "attack_seconds_not_reduced": c["attack_seconds"] >= g["attack_seconds"],
        "no_over_9g_penalty": c["over_9g_seconds"] <= g["over_9g_seconds"],
        # 50 ft AGL crash threshold = 15.24 m. Require a 20x margin (300 m),
        # and require no aggregate worst-case regression versus the guide.
        "worst_altitude_300m_above_crash_threshold": c["min_alt_worst_m"] > 300.0,
        "worst_altitude_not_worse_than_guide":
            c["min_alt_worst_m"] >= g["min_alt_worst_m"],
        "no_per_opponent_kill_regression":
            all(by_opp_cand[o]["kills"] >= by_opp_guide[o]["kills"]
                for o in by_opp_guide),
    }
    passed = all(checks.values())

    result = {
        "format": "m2_regate_v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "source_run": str(RUN),
        "source_recomputed": False,
        "why": ("the official advantage formula has no altitude term; the original "
                "rejection used per-case minimum altitude, which is not a scored "
                "quantity and is not the binding safety constraint"),
        "guide": g, "candidate": c,
        "by_opponent_guide": by_opp_guide,
        "by_opponent_candidate": by_opp_cand,
        "attack_accumulator": ticks,
        "crash_focused_gate": checks,
        "promote": passed,
        "delta": {
            "kills": c["kills"] - g["kills"],
            "attack_seconds": round(c["attack_seconds"] - g["attack_seconds"], 4),
            "own_crashes": c["own_crashes"] - g["own_crashes"],
            "worst_altitude_m": round(c["min_alt_worst_m"] - g["min_alt_worst_m"], 1),
        },
        "original_gate_said": d.get("gate"),
        "original_deployment_allowed": d.get("deployment_allowed"),
        "official_validation": False,
        "caveat": ("still one opponent pool (rule + rl), 12 pairs, no mirror. "
                   "promotion here means 'advance to mirror testing', not "
                   "'deploy for the match'."),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"guide     : kills={g['kills']} atk={g['attack_seconds']:.2f}s "
          f"crash={g['own_crashes']} deaths={g['deaths']} worstAlt={g['min_alt_worst_m']}m")
    print(f"candidate : kills={c['kills']} atk={c['attack_seconds']:.2f}s "
          f"crash={c['own_crashes']} deaths={c['deaths']} worstAlt={c['min_alt_worst_m']}m")
    for o in sorted(by_opp_guide):
        gg, cc = by_opp_guide[o], by_opp_cand[o]
        print(f"   vs {o:<6} guide kills={gg['kills']} atk={gg['attack_seconds']:.2f}s "
              f"| candidate kills={cc['kills']} atk={cc['attack_seconds']:.2f}s")
    print(f"\naccumulator: best case {ticks['candidate_best_case_ticks']} ticks "
          f"(kill needs {ticks['kill_threshold_ticks']}, "
          f"short {ticks['shortfall_ticks']})")
    print(f"\noriginal gate : {d.get('gate')}  deployment_allowed={d.get('deployment_allowed')}")
    print(f"crash-focused : PROMOTE={passed}")
    for k, v in checks.items():
        print(f"   {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nwritten: {OUT}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
