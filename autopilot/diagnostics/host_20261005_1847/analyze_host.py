"""Read-only Host CSV diagnosis; does not import or change flight controllers."""
from pathlib import Path
import csv
import hashlib
import json
import math
import re

import numpy as np

ROOT = Path(__file__).resolve().parent
BASE = Path(r"E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test")
HOST = BASE / "D.比賽用主辦方連線程式_驗證是否符合能正確連線"
CSV = HOST / "飛行競賽Host端Record_20261005_1847.csv"
HZ = 60.0
FT_TO_M = 0.3048


def intervals(mask, times):
    indexes = np.flatnonzero(mask)
    if not len(indexes):
        return []
    groups = np.split(indexes, np.flatnonzero(np.diff(indexes) > 1) + 1)
    return [{"start_s": float(times[g[0]]), "last_sample_s": float(times[g[-1]]),
             "ticks": len(g), "seconds_at_60hz": len(g) / HZ} for g in groups]


def main():
    with CSV.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    data = {key: np.array([float(row[key]) for row in rows]) for key in rows[0]}
    assert all(np.isfinite(value).all() for value in data.values())
    assert np.all(np.diff(data["time"]) > 0)
    times = data["time"]
    lat1 = np.radians(data["player1_lat_deg"])
    lat2 = np.radians(data["player2_lat_deg"])
    lon1 = np.radians(data["player1_lon_deg"])
    lon2 = np.radians(data["player2_lon_deg"])
    # Match the current local judge's short-range tangent-plane convention.
    # The official Host distance algorithm is not available; these are diagnostics.
    north = (lat2 - lat1) * 6378137.0
    east = (lon2 - lon1) * 6378137.0 * np.cos((lat1 + lat2) / 2)
    down = -(data["player2_alt_ft"] - data["player1_alt_ft"]) * FT_TO_M
    relative = np.column_stack([north, east, down])
    distance = np.linalg.norm(relative, axis=1)
    angles = {}
    for number, sign in [(1, 1), (2, -1)]:
        yaw = np.radians(data[f"player{number}_yaw_deg"])
        pitch = np.radians(data[f"player{number}_pitch_deg"])
        nose = np.column_stack([np.cos(pitch) * np.cos(yaw),
                                np.cos(pitch) * np.sin(yaw), -np.sin(pitch)])
        cosine = np.sum(nose * (sign * relative), axis=1) / np.maximum(distance, 1e-9)
        angles[number] = np.degrees(np.arccos(np.clip(cosine, -1, 1)))
    range_ok = (distance >= 500 * FT_TO_M) & (distance <= 3000 * FT_TO_M)
    summary = {
        "source_csv": str(CSV), "source_sha256": hashlib.sha256(CSV.read_bytes()).hexdigest(),
        "rows": len(rows), "first_time_s": float(times[0]), "last_time_s": float(times[-1]),
        "time_remaining_final": float(data["system_time_remaining"][-1]),
        "winner_code_final": float(data["system_Final_whoiswinner"][-1]),
        "winner_code_mapping": "Not verified from official documentation; do not infer a named winner from this field alone.",
        "initial": {
            "range_ft_tangent_plane": float(distance[0] / FT_TO_M),
            "range_method": "short-range tangent plane, radius 6378137m, mean-latitude cosine; not the unavailable official Host distance implementation",
            "p1_to_p2_bearing_deg": math.degrees(math.atan2(east[0], north[0])) % 360,
            "p1_yaw_deg": float(data["player1_yaw_deg"][0]),
            "p2_yaw_deg": float(data["player2_yaw_deg"][0]),
            "p1_nose_angle_deg": float(angles[1][0]),
            "p2_nose_angle_deg": float(angles[2][0]),
            "p1_altitude_ft": float(data["player1_alt_ft"][0]),
            "p2_altitude_ft": float(data["player2_alt_ft"][0]),
            "p1_ias_kts": float(data["player1_ias_kts"][0]),
            "p2_ias_kts": float(data["player2_ias_kts"][0]),
        },
        "range_window_s_at_60hz": int(range_ok.sum()) / HZ,
        "players": {},
    }
    for number, enemy in [(1, 2), (2, 1)]:
        hp = data[f"player{number}_Score_RemainingHP"]
        enemy_hp = data[f"player{enemy}_Score_RemainingHP"]
        loss = -np.diff(enemy_hp, prepend=enemy_hp[0])
        score = data[f"player{number}_Score_Kills"]
        damage = loss > 0
        effective = range_ok & (angles[number] <= 2)
        for key in ["Score_RemainingHP", "Score_Kills", "Score_GForceOverload"]:
            assert np.isfinite(data[f"player{number}_{key}"]).all()
        summary["players"][str(number)] = {
            "hp_initial": float(hp[0]), "hp_final": float(hp[-1]),
            "damage_inflicted_ticks": float(loss[loss > 0].sum()),
            "official_score_kills_field_final": float(score[-1]),
            "damage_equivalent_seconds": float((enemy_hp[0] - enemy_hp[-1]) / HZ),
            "score_equals_hp_damage_div_60_max_error": float(np.max(np.abs(score - (enemy_hp[0] - enemy_hp) / HZ))),
            "seconds_short_of_3s_damage_threshold": max(0.0, float(enemy_hp[-1] / HZ)),
            "observed_damage_intervals": intervals(damage, times),
            "geometry_attack_s_at_60hz_diagnostic": int(effective.sum()) / HZ,
            "geometry_vs_damage_mask_disagreements": int(np.count_nonzero(effective != damage)),
            "angle_le_5deg_in_range_s": int((range_ok & (angles[number] <= 5)).sum()) / HZ,
            "angle_le_10deg_in_range_s": int((range_ok & (angles[number] <= 10)).sum()) / HZ,
            "median_nose_error_deg_in_range": float(np.median(angles[number][range_ok])),
            "min_altitude_ft": float(data[f"player{number}_alt_ft"].min()),
            "max_abs_bank_deg": float(np.abs(data[f"player{number}_roll_deg"]).max()),
            "yaw_unwrapped_travel_deg": float(np.abs(np.diff(np.unwrap(np.radians(data[f"player{number}_yaw_deg"])))).sum() * 180 / math.pi),
            "final_advantage_field": float(data[f"player{number}_Score_FinalAdvantage"][-1]),
            "gforce_overload_field_final": float(data[f"player{number}_Score_GForceOverload"][-1]),
        }
        checks = {}
        for threshold in [0.5, 1.0, 1.5, 2.0, 5.0]:
            prediction = range_ok & (angles[number] <= threshold)
            checks[str(threshold)] = {
                "geometry_seconds": int(prediction.sum()) / HZ,
                "disagreements_with_actual_damage": int(np.count_nonzero(prediction != damage)),
                "actual_damage_outside_prediction": int(np.count_nonzero(damage & ~prediction)),
            }
        summary["players"][str(number)]["threshold_checks_deg"] = checks
    p2_log = (HOST / "player2_runtime.log").read_text(encoding="utf-8", errors="replace")
    summary["p2_log"] = {
        "random_level_flight_pid_boot_message_present": "Random level-flight PID controller ready (SAC disabled)" in p2_log,
        "observed_modes": sorted(set(re.findall(r"Mode: ([^,\r\n]+)", p2_log))),
    }
    (ROOT / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    # Store per-tick derived data separately from the immutable original Host record.
    with (ROOT / "geometry_diagnostic.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "range_ft_approx", "p1_nose_error_deg_approx", "p2_nose_error_deg_approx", "p1_hp", "p2_hp"])
        for i in range(len(rows)):
            writer.writerow([times[i], distance[i] / FT_TO_M, angles[1][i], angles[2][i],
                             data["player1_Score_RemainingHP"][i], data["player2_Score_RemainingHP"][i]])
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Microsoft JhengHei", "DejaVu Sans"]
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True, constrained_layout=True)
    axes[0].plot(times, data["player1_Score_RemainingHP"], color="#1976d2", label="藍方 P1（你）")
    axes[0].plot(times, data["player2_Score_RemainingHP"], color="#d32f2f", label="紅方 P2")
    axes[0].set_ylabel("Host 剩餘 HP")
    axes[0].set_ylim(0, 190)
    axes[0].legend(loc="lower left")
    axes[0].set_title("官方 Host 2026-10-05 18:47：有命中，累積時間仍不足擊落")
    axes[1].plot(times, angles[1], color="#1976d2", linewidth=1)
    axes[1].axhline(1, color="#d32f2f", linestyle="--", label="1°：本場與扣血完全吻合")
    axes[1].axhline(2, color="#7b1fa2", linestyle=":", label="2°：目前本地裁判門檻")
    axes[1].set_ylim(0, 8)
    axes[1].set_ylabel("機鼻偏差估計（度）")
    axes[1].legend(loc="upper left", fontsize=9)
    axes[2].plot(times, distance / FT_TO_M, color="#455a64", linewidth=1)
    axes[2].axhspan(500, 3000, color="#388e3c", alpha=0.15, label="500–3000 呎")
    axes[2].set_ylabel("兩機距離估計（呎）")
    axes[2].set_xlabel("模擬時間（秒）")
    axes[2].legend(loc="upper right")
    for axis in axes:
        axis.grid(alpha=0.2)
        axis.set_xlim(0, 300)
    fig.savefig(ROOT / "host_attack_diagnosis.png", dpi=160)
    plt.close(fig)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
