"""precision_math.py — 公開的三維向量 / 航空姿態 / 相對運動幾何。

只使用標準函式庫與 Numpy。純診斷用途，不宣稱是任何可飛行的控制器、
瞄準律或射擊解算。

座標與角度約定
----------------
* NED：北 (+N)、東 (+E)、下 (+D) 為正；位置單位 m。
* 相對速度：目標相對於本機的速度，單位 m/s。
* 航空歐拉角（本機姿態）：
    yaw   psi  : 0 = 正北，+90 = 正東（由北往東為正）
    pitch theta: 正值為抬頭
    roll  phi  : 正值為右翼下傾
  機身軸 (body)：+x = 機首、+y = 機身右、+z = 機身下。
* 輸出角度一律為 degree。

風險聲明
--------
本模組輸出的是幾何診斷量。`overshoot_time_s` 只是「直線、等速、純徑向
閉合」的外推指標，不代表飛机会如何轉向，也不含任何姿態/操縱極限。
"""

from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np

__all__ = ["analyze"]

# |relative_ned_m| 小於此值 → 無法定義瞄準方向
_RANGE_FLOOR_M = 1e-6
# 水平投影小於此值 → 視為純垂直，bearing 回傳 None
_HORIZONTAL_EPS_M = 1e-9
# 機身座水平投影（LOS 為單位向量）門檻
_BODY_AZIMUTH_EPS = 1e-12
# 小於此速度視為零速，CPA 時間定義為 0
_ZERO_SPEED_MPS = 1e-6
# 閉合率門檻，小於等於此值不算「正在靠近」
_ZERO_CLOSING_MPS = 1e-9


def _to_vec3(value, name: str) -> np.ndarray:
    """轉成形狀 (3,) 的 float ndarray，失敗一律 ValueError。"""
    try:
        arr = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} 必須是 3 個實數組成的序列，得到 {value!r}"
        ) from exc
    if arr.shape != (3,):
        raise ValueError(f"{name} 形狀必須為 (3,)，得到 {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise ValueError(f"{name} 含 NaN 或 inf：{arr.tolist()}")
    return arr


def _to_float(value, name: str) -> float:
    """轉成有限 float，失敗一律 ValueError。"""
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必須是實數，得到 {value!r}") from exc
    if not math.isfinite(out):
        raise ValueError(f"{name} 不得為 NaN 或 inf，得到 {value!r}")
    return out


def _wrap180(deg: float) -> float:
    """折進 [-180, 180)。"""
    return (deg + 180.0) % 360.0 - 180.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)


def _body_to_ned(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    """R：機身軸 → NED，v_ned = R @ v_body。

    R = Rz(yaw) @ Ry(pitch) @ Rx(roll)，航空慣例（roll 正 = 右翼下傾）。
    """
    phi = math.radians(roll_deg)
    theta = math.radians(pitch_deg)
    psi = math.radians(yaw_deg)
    cphi, sphi = math.cos(phi), math.sin(phi)
    cth, sth = math.cos(theta), math.sin(theta)
    cpsi, spsi = math.cos(psi), math.sin(psi)
    return np.array(
        [
            [cpsi * cth, cpsi * sth * sphi - spsi * cphi, cpsi * sth * cphi + spsi * sphi],
            [spsi * cth, spsi * sth * sphi + cpsi * cphi, spsi * sth * cphi - cpsi * sphi],
            [-sth, cth * sphi, cth * cphi],
        ],
        dtype=float,
    )


def _norm3(v: np.ndarray) -> float:
    return math.sqrt(float(v[0]) ** 2 + float(v[1]) ** 2 + float(v[2]) ** 2)


def analyze(
    relative_ned_m,
    relative_velocity_ned_mps,
    roll_deg,
    pitch_deg,
    yaw_deg,
    desired_range_m: float = 600.0,
) -> Dict[str, object]:
    """把「相對位置 + 相對速度 + 己機姿態」轉成一組可解釋的幾何診斷量。

    參數
    ----
    relative_ned_m : 形狀 (3,) 的 [北, 東, 下]，單位 m，己機 → 目標。
    relative_velocity_ned_mps : 形狀 (3,) 的 [北, 東, 下]，單位 m/s，
        目標相對於本機的速度。
    roll_deg, pitch_deg, yaw_deg : 己機姿態，單位 degree，定義見模組 docstring。
    desired_range_m : 正數，overshop/overshoot 推估的參考距離，單位 m。

    回傳（純 Python dict，角度皆 degree）
    ----------------------------------
    range_m            : 目標距離（m）。
    horizontal_los_deg : yaw 相對 LOS 的水平夾角，[-180, 180)，正為右；
                         水平投影退化時為 None。
    vertical_los_deg   : 世界水平面上方為正，[-90, 90]。
    nose_error_deg     : 機首向量與相對位置的 3D 夾角，[0, 180]。
    body_azimuth_deg   : 機身右方為正；機身垂直方向退化時為 None。
    body_elevation_deg : 機身上方為正，[-90, 90]。
    closing_mps        : 徑向閉合率，靠近為正。
    cpa_time_s         : 等速最近接近的未來時間（負值裁到 0）。
    cpa_range_m        : 在 cpa_time_s 的等速最近接近距離。
    overshoot_time_s   : 以線性徑向閉合推估穿越 desired_range_m 的未來時間，
                         沒有未來跨越時為 None。

    錯誤
    ----
    非有限數、形狀不為 (3,)、desired_range_m 非正 → ValueError。
    相對位置長度 < 1e-6 m → ValueError（無法定義瞄準方向）。
    """
    rel_p = _to_vec3(relative_ned_m, "relative_ned_m")
    rel_v = _to_vec3(relative_velocity_ned_mps, "relative_velocity_ned_mps")
    roll = _to_float(roll_deg, "roll_deg")
    pitch = _to_float(pitch_deg, "pitch_deg")
    yaw = _to_float(yaw_deg, "yaw_deg")
    desired = _to_float(desired_range_m, "desired_range_m")
    if desired <= 0.0:
        raise ValueError(f"desired_range_m 必須為正數，得到 {desired!r}")

    rng = _norm3(rel_p)
    if rng < _RANGE_FLOOR_M:
        raise ValueError(
            f"relative_ned_m 長度 {rng!r} m 小於 {_RANGE_FLOOR_M} m，無法定義瞄準方向"
        )

    u = rel_p / rng  # LOS 單位向量（NED）
    R = _body_to_ned(roll, pitch, yaw)
    forward = R[:, 0]

    north = float(rel_p[0])
    east = float(rel_p[1])
    down = float(rel_p[2])
    horiz = math.hypot(north, east)

    # --- 世界系角度 ---
    horizontal_los_deg: Optional[float] = None
    if horiz > _HORIZONTAL_EPS_M:
        horizontal_los_deg = _wrap180(math.degrees(math.atan2(east, north)) - yaw)
    vertical_los_deg = math.degrees(math.atan2(-down, horiz))

    # --- 3D 機首誤差（clip 保護 acos 的浮點溢位）---
    nose_error_deg = math.degrees(
        math.acos(_clamp(float(np.dot(forward, u)), -1.0, 1.0))
    )

    # --- 機身座角度 ---
    u_body = R.T @ u
    bx, by, bz = float(u_body[0]), float(u_body[1]), float(u_body[2])
    body_horiz = math.hypot(bx, by)
    body_azimuth_deg: Optional[float] = None
    if body_horiz > _BODY_AZIMUTH_EPS:
        body_azimuth_deg = math.degrees(math.atan2(by, bx))
    body_elevation_deg = math.degrees(math.atan2(-bz, body_horiz))

    # --- 徑向閉合率與 CPA（等速直線假設）---
    dot_pv = float(np.dot(rel_p, rel_v))
    closing_mps = -dot_pv / rng

    speed_sq = float(np.dot(rel_v, rel_v))
    if speed_sq <= _ZERO_SPEED_MPS * _ZERO_SPEED_MPS:
        cpa_time_s = 0.0
    else:
        cpa_time_s = max(0.0, -dot_pv / speed_sq)
    cpa_range_m = _norm3(rel_p + rel_v * cpa_time_s)

    # --- 直線等速的 desired_range 跨越時間（純風險指標）---
    overshoot_time_s: Optional[float] = None
    if closing_mps > _ZERO_CLOSING_MPS:
        t_cross = (rng - desired) / closing_mps
        if t_cross >= 0.0:
            overshoot_time_s = t_cross

    return {
        "range_m": rng,
        "horizontal_los_deg": horizontal_los_deg,
        "vertical_los_deg": vertical_los_deg,
        "nose_error_deg": nose_error_deg,
        "body_azimuth_deg": body_azimuth_deg,
        "body_elevation_deg": body_elevation_deg,
        "closing_mps": closing_mps,
        "cpa_time_s": cpa_time_s,
        "cpa_range_m": cpa_range_m,
        "overshoot_time_s": overshoot_time_s,
    }
