"""test_precision_math.py — precision_math.analyze 的幾何意義測試。

執行：python -m unittest test_precision_math -v
（需與 precision_math.py 放在同一目錄）
"""

import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from precision_math import analyze  # noqa: E402

D2R = math.pi / 180.0

EXPECTED_KEYS = {
    "range_m",
    "horizontal_los_deg",
    "vertical_los_deg",
    "nose_error_deg",
    "body_azimuth_deg",
    "body_elevation_deg",
    "closing_mps",
    "cpa_time_s",
    "cpa_range_m",
    "overshoot_time_s",
}


class TestDeadAhead(unittest.TestCase):
    """yaw=0/pitch=0/roll=0，目標在正北。"""

    def test_straight_ahead_north(self):
        res = analyze([700.0, 0.0, 0.0], [-20.0, 0.0, 0.0], 0.0, 0.0, 0.0)
        self.assertEqual(set(res.keys()), EXPECTED_KEYS)
        self.assertAlmostEqual(res["range_m"], 700.0, places=6)
        self.assertAlmostEqual(res["horizontal_los_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["vertical_los_deg"], 0.0, places=6)
        # 完全共線：dot 為 1.0，acos 得 0
        self.assertAlmostEqual(res["nose_error_deg"], 0.0, places=4)
        self.assertAlmostEqual(res["body_azimuth_deg"], 0.0, places=4)
        self.assertAlmostEqual(res["body_elevation_deg"], 0.0, places=4)
        self.assertAlmostEqual(res["closing_mps"], 20.0, places=6)
        # 對頭相撞：700 m / 20 m/s
        self.assertAlmostEqual(res["cpa_time_s"], 35.0, places=6)
        self.assertAlmostEqual(res["cpa_range_m"], 0.0, places=4)
        self.assertAlmostEqual(res["overshoot_time_s"], 5.0, places=6)

    def test_straight_ahead_east(self):
        """yaw=90 時正東就是正前方。"""
        res = analyze([0.0, 500.0, 0.0], [0.0, -20.0, 0.0], 0.0, 0.0, 90.0)
        self.assertAlmostEqual(res["horizontal_los_deg"], 0.0, places=4)
        self.assertAlmostEqual(res["vertical_los_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["nose_error_deg"], 0.0, places=4)
        self.assertAlmostEqual(res["body_azimuth_deg"], 0.0, places=4)
        self.assertAlmostEqual(res["body_elevation_deg"], 0.0, places=4)
        self.assertAlmostEqual(res["closing_mps"], 20.0, places=6)

    def test_negative_relative_bearing_equals_nose_error(self):
        """yaw=37、目標在正北 → 目標偏左 37 度，無 roll/pitch 時與 nose_error 同值。"""
        res = analyze([100.0, 0.0, 0.0], [0.0, 0.0, 0.0], 0.0, 0.0, 37.0)
        self.assertAlmostEqual(res["horizontal_los_deg"], -37.0, places=6)
        self.assertAlmostEqual(res["nose_error_deg"], 37.0, places=4)
        self.assertAlmostEqual(res["body_azimuth_deg"], -37.0, places=4)


class TestRightAndVertical(unittest.TestCase):
    def test_dead_right(self):
        """目標正東、相對速度 [10, -20, 0]。"""
        res = analyze([0.0, 800.0, 0.0], [10.0, -20.0, 0.0], 0.0, 0.0, 0.0)
        self.assertAlmostEqual(res["range_m"], 800.0, places=6)
        self.assertAlmostEqual(res["horizontal_los_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["vertical_los_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["nose_error_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["body_azimuth_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["body_elevation_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["closing_mps"], 20.0, places=6)
        # t = 16000/500 = 32；CPA 點 = [320, 160, 0]
        self.assertAlmostEqual(res["cpa_time_s"], 32.0, places=6)
        self.assertAlmostEqual(res["cpa_range_m"], math.sqrt(128000.0), delta=1e-6)
        self.assertAlmostEqual(res["cpa_range_m"], 357.770876, places=3)
        # (800 - 600)/20
        self.assertAlmostEqual(res["overshoot_time_s"], 10.0, places=6)

    def test_directly_overhead(self):
        """純上方：horizontal/body azimuth 不可定義，但3D 角仍正常。"""
        res = analyze([0.0, 0.0, -500.0], [0.0, 0.0, 5.0], 0.0, 0.0, 0.0)
        self.assertAlmostEqual(res["range_m"], 500.0, places=6)
        self.assertIsNone(res["horizontal_los_deg"])
        self.assertIsNone(res["body_azimuth_deg"])
        self.assertAlmostEqual(res["vertical_los_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["nose_error_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["body_elevation_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["closing_mps"], 5.0, places=6)
        self.assertAlmostEqual(res["cpa_time_s"], 100.0, places=6)
        self.assertAlmostEqual(res["cpa_range_m"], 0.0, places=4)
        # 已在600m內且繼續靠近，沒有未來由外向內跨越600m
        self.assertIsNone(res["overshoot_time_s"])

    def test_directly_below(self):
        """純下方。"""
        res = analyze([0.0, 0.0, 300.0], [3.0, 0.0, -2.0], 0.0, 0.0, 0.0)
        self.assertAlmostEqual(res["range_m"], 300.0, places=6)
        self.assertIsNone(res["horizontal_los_deg"])
        self.assertIsNone(res["body_azimuth_deg"])
        self.assertAlmostEqual(res["vertical_los_deg"], -90.0, places=6)
        self.assertAlmostEqual(res["nose_error_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["body_elevation_deg"], -90.0, places=6)
        self.assertAlmostEqual(res["closing_mps"], 2.0, places=6)
        # t = 600/13，CPA 點 = [138.4615, 0, 207.6923]
        self.assertAlmostEqual(res["cpa_time_s"], 600.0 / 13.0, places=9)
        self.assertAlmostEqual(res["cpa_range_m"], 249.615, delta=1e-2)
        # 已在 desired_range 內，線性外推為負 → 沒有未來跨越
        self.assertIsNone(res["overshoot_time_s"])

    def test_near_zero_horizontal_is_degenerate(self):
        """水平分量 1e-12 m（遠低於 1e-9 m 門檻）視同純垂直。"""
        res = analyze([1e-12, 0.0, -500.0], [0.0, 0.0, 0.0], 0.0, 0.0, 0.0)
        self.assertIsNone(res["horizontal_los_deg"])
        self.assertAlmostEqual(res["vertical_los_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["range_m"], 500.0, places=6)


class TestPitch(unittest.TestCase):
    def test_pitch30_upward_los_on_nose(self):
        """pitch=30、LOS 沿機首 → vertical_los=30、nose_error=0、機身角=0。"""
        rel_p = [
            600.0 * math.cos(30.0 * D2R),
            0.0,
            -600.0 * math.sin(30.0 * D2R),
        ]
        rel_v = [
            -20.0 * math.cos(30.0 * D2R),
            5.0,
            20.0 * math.sin(30.0 * D2R),
        ]
        res = analyze(rel_p, rel_v, 0.0, 30.0, 0.0, desired_range_m=500.0)
        self.assertAlmostEqual(res["range_m"], 600.0, delta=1e-6)
        self.assertAlmostEqual(res["horizontal_los_deg"], 0.0, delta=1e-4)
        self.assertAlmostEqual(res["vertical_los_deg"], 30.0, delta=1e-4)
        # acos 對共線向量數值敏感（sqrt(eps)），用絕對值門檻
        self.assertLess(abs(res["nose_error_deg"]), 1e-4)
        self.assertLess(abs(res["body_azimuth_deg"]), 1e-4)
        self.assertLess(abs(res["body_elevation_deg"]), 1e-4)
        self.assertAlmostEqual(res["closing_mps"], 20.0, delta=1e-6)
        self.assertAlmostEqual(res["cpa_time_s"], 12000.0 / 425.0, places=9)
        self.assertAlmostEqual(res["cpa_range_m"], 145.52, delta=1e-2)
        # (600 - 500)/20
        self.assertAlmostEqual(res["overshoot_time_s"], 5.0, delta=1e-9)

    def test_pitch30_level_target(self):
        """抬頭30度看水平目標，目標在機首下方：body elevation=-30。"""
        res = analyze([600.0, 0.0, 0.0], [0.0, 0.0, 0.0], 0.0, 30.0, 0.0)
        self.assertAlmostEqual(res["horizontal_los_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["vertical_los_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["nose_error_deg"], 30.0, delta=1e-6)
        self.assertAlmostEqual(res["body_azimuth_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["body_elevation_deg"], -30.0, delta=1e-6)

    def test_pitch30_heading45(self):
        """抬頭 30 度、航向 45 度，LOS 仍在機首上 → 兩個相對角皆 0。"""
        rel_p = [
            400.0 * math.cos(30.0 * D2R) * math.cos(45.0 * D2R),
            400.0 * math.cos(30.0 * D2R) * math.sin(45.0 * D2R),
            -400.0 * math.sin(30.0 * D2R),
        ]
        res = analyze(rel_p, [0.0, 0.0, 0.0], 0.0, 30.0, 45.0)
        self.assertAlmostEqual(res["range_m"], 400.0, delta=1e-6)
        self.assertLess(abs(res["horizontal_los_deg"]), 1e-4)
        self.assertAlmostEqual(res["vertical_los_deg"], 30.0, delta=1e-4)
        self.assertLess(abs(res["nose_error_deg"]), 1e-4)


class TestRoll(unittest.TestCase):
    def test_roll90_dead_ahead_unchanged(self):
        """右翼下傾 90 度，目標仍在正北 → 機身角不受影響。"""
        res = analyze([600.0, 0.0, 0.0], [0.0, 0.0, 0.0], 90.0, 0.0, 0.0)
        self.assertAlmostEqual(res["horizontal_los_deg"], 0.0, places=4)
        self.assertAlmostEqual(res["nose_error_deg"], 0.0, places=4)
        self.assertAlmostEqual(res["body_azimuth_deg"], 0.0, places=4)
        self.assertAlmostEqual(res["body_elevation_deg"], 0.0, places=4)

    def test_roll90_overhead_becomes_body_left(self):
        """roll=90 時機身右軸指向正下方：正上方的目標變成機身左方 90 度。"""
        res = analyze([0.0, 0.0, -300.0], [0.0, 0.0, 5.0], 90.0, 0.0, 0.0)
        self.assertIsNone(res["horizontal_los_deg"])
        self.assertAlmostEqual(res["vertical_los_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["nose_error_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["body_azimuth_deg"], -90.0, places=6)
        self.assertAlmostEqual(res["body_elevation_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["closing_mps"], 5.0, places=6)
        self.assertAlmostEqual(res["cpa_time_s"], 60.0, places=6)
        self.assertAlmostEqual(res["cpa_range_m"], 0.0, places=4)

    def test_roll90_east_target_becomes_body_overhead(self):
        """roll=90 時機身下軸指向正西：正東目標變成機身上方 90 度。"""
        res = analyze([0.0, 600.0, 0.0], [0.0, -20.0, 0.0], 90.0, 0.0, 0.0)
        self.assertAlmostEqual(res["horizontal_los_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["vertical_los_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["nose_error_deg"], 90.0, places=6)
        self.assertIsNone(res["body_azimuth_deg"])
        self.assertAlmostEqual(res["body_elevation_deg"], 90.0, places=6)
        self.assertAlmostEqual(res["closing_mps"], 20.0, places=6)
        self.assertAlmostEqual(res["cpa_time_s"], 30.0, places=6)
        self.assertAlmostEqual(res["cpa_range_m"], 0.0, places=4)
        self.assertAlmostEqual(res["overshoot_time_s"], 0.0, places=9)

    def test_roll_minus90_is_mirror(self):
        """roll=-90時機身下軸指向正東，正東目標在機身正下方。"""
        res = analyze([0.0, 600.0, 0.0], [0.0, 0.0, 0.0], -90.0, 0.0, 0.0)
        self.assertIsNone(res["body_azimuth_deg"])
        self.assertAlmostEqual(res["body_elevation_deg"], -90.0, places=6)


class TestHeadingWrap(unittest.TestCase):
    def test_heading170_los190(self):
        """跨 180 度：yaw=170、LOS bearing=190 → 相對 +20 度。"""
        los = 190.0 * D2R
        rel_p = [600.0 * math.cos(los), 600.0 * math.sin(los), 0.0]
        rel_v = [-20.0 * math.cos(los), -20.0 * math.sin(los), 4.0]
        res = analyze(rel_p, rel_v, 0.0, 0.0, 170.0)
        self.assertAlmostEqual(res["horizontal_los_deg"], 20.0, places=6)
        self.assertAlmostEqual(res["vertical_los_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["nose_error_deg"], 20.0, delta=1e-6)
        self.assertAlmostEqual(res["body_azimuth_deg"], 20.0, delta=1e-6)
        self.assertAlmostEqual(res["body_elevation_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["closing_mps"], 20.0, delta=1e-6)
        # t = 12000/416        self.assertAlmostEqual(res["cpa_time_s"], 12000.0 / 416.0, places=9)
        self.assertAlmostEqual(res["cpa_range_m"], 117.670, delta=1e-2)
        self.assertAlmostEqual(res["overshoot_time_s"], 0.0, places=9)

    def test_heading350_los10(self):
        """反向跨界：yaw=350、LOS=10 → 相對 +20 度（不是 -340）。"""
        los = 10.0 * D2R
        rel_p = [600.0 * math.cos(los), 600.0 * math.sin(los), 0.0]
        # 純垂直速度：閉合率為 0，CPA 就是現在
        res = analyze(rel_p, [0.0, 0.0, 3.0], 0.0, 0.0, 350.0)
        self.assertAlmostEqual(res["horizontal_los_deg"], 20.0, places=6)
        self.assertAlmostEqual(res["nose_error_deg"], 20.0, delta=1e-6)
        self.assertAlmostEqual(res["closing_mps"], 0.0, delta=1e-9)
        self.assertAlmostEqual(res["cpa_time_s"], 0.0, places=9)
        self.assertAlmostEqual(res["cpa_range_m"], 600.0, delta=1e-6)
        self.assertIsNone(res["overshoot_time_s"])

    def test_heading350_los170(self):
        """yaw=350、LOS=170 → 折進 [-180,180) 得 -180。"""
        los = 170.0 * D2R
        rel_p = [600.0 * math.cos(los), 600.0 * math.sin(los), 0.0]
        res = analyze(rel_p, [0.0, 0.0, 0.0], 0.0, 0.0, 350.0)
        self.assertAlmostEqual(res["horizontal_los_deg"], -180.0, places=9)
        self.assertLessEqual(res["horizontal_los_deg"], 180.0)
        self.assertGreaterEqual(res["horizontal_los_deg"], -180.0)


class TestRelativeMotion(unittest.TestCase):
    def test_zero_relative_velocity(self):
        """零相對速度：CPA 時間 0、CPA 距離即目前距離、無跨越。"""
        res = analyze([600.0, 0.0, 0.0], [0.0, 0.0, 0.0], 0.0, 0.0, 0.0)
        self.assertAlmostEqual(res["closing_mps"], 0.0, places=9)
        self.assertEqual(res["cpa_time_s"], 0.0)
        self.assertAlmostEqual(res["cpa_range_m"], 600.0, delta=1e-9)
        self.assertIsNone(res["overshoot_time_s"])

    def test_opening(self):
        """遠離：閉合率為負、CPA 裁到 0、沒有跨越時間。"""
        res = analyze([600.0, 0.0, 0.0], [30.0, 0.0, 0.0], 0.0, 0.0, 0.0)
        self.assertAlmostEqual(res["closing_mps"], -30.0, places=9)
        self.assertEqual(res["cpa_time_s"], 0.0)
        self.assertAlmostEqual(res["cpa_range_m"], 600.0, delta=1e-9)
        self.assertIsNone(res["overshoot_time_s"])

    def test_receding_past_desired_range(self):
        """已在 desired_range 外側且遠離 → 無未來跨越。"""
        res = analyze(
            [900.0, 0.0, 0.0], [20.0, 0.0, 0.0], 0.0, 0.0, 0.0, desired_range_m=600.0
        )
        self.assertAlmostEqual(res["closing_mps"], -20.0, places=9)
        self.assertIsNone(res["overshoot_time_s"])

    def test_near_miss_cpa(self):
        """擦身而過：目標從 50 m 側方通過。"""
        res = analyze([500.0, 50.0, 0.0], [-20.0, 0.0, 0.0], 0.0, 0.0, 0.0)
        self.assertAlmostEqual(res["range_m"], math.sqrt(252500.0), delta=1e-9)
        # atan(50/500) = 5.710593...
        self.assertAlmostEqual(res["horizontal_los_deg"], 5.710593, places=5)
        self.assertAlmostEqual(res["vertical_los_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["nose_error_deg"], 5.710593, delta=1e-5)
        self.assertAlmostEqual(res["body_azimuth_deg"], 5.710593, places=5)
        self.assertAlmostEqual(res["body_elevation_deg"], 0.0, places=6)
        self.assertAlmostEqual(res["closing_mps"], 19.900744, places=5)
        self.assertAlmostEqual(res["cpa_time_s"], 25.0, places=9)
        # CPA 點 = [0, 50, 0]
        self.assertAlmostEqual(res["cpa_range_m"], 50.0, delta=1e-6)
        # 已在600 m 內 → 無未來跨越
        self.assertIsNone(res["overshoot_time_s"])

    def test_overshoot_custom_desired_range(self):
        res = analyze([1000.0, 0.0, 0.0], [-25.0, 0.0, 0.0], 0.0, 0.0, 0.0,
                      desired_range_m=400.0)
        self.assertAlmostEqual(res["closing_mps"], 25.0, places=9)
        self.assertAlmostEqual(res["overshoot_time_s"], 24.0, places=6)


class TestInvalidInput(unittest.TestCase):
    def test_near_zero_position(self):
        for pos in ([0.0, 0.0, 0.0], [1e-7, 0.0, 0.0], [9.9e-7, 0.0, 0.0],
                    [0.0, 1e-9, 0.0], [1e-12, 0.0, 1e-12]):
            with self.subTest(pos=pos):
                with self.assertRaises(ValueError):
                    analyze(pos, [0.0, 0.0, 0.0], 0.0, 0.0, 0.0)

    def test_exact_floor_is_allowed(self):
        """長度剛好等於 1e-6 m 不算近零，不應丟錯。"""
        res = analyze([1e-6, 0.0, 0.0], [0.0, 0.0, 0.0], 0.0, 0.0, 0.0)
        self.assertAlmostEqual(res["range_m"], 1e-6, places=9)

    def test_non_finite_values(self):
        cases = [
            ([float("nan"), 0.0, 0.0], [0.0, 0.0, 0.0], 0.0, 0.0, 0.0),
            ([600.0, float("inf"), 0.0], [0.0, 0.0, 0.0], 0.0, 0.0, 0.0),
            ([600.0, 0.0, 0.0], [float("-inf"), 0.0, 0.0], 0.0, 0.0, 0.0),
            ([600.0, 0.0, 0.0], [0.0, 0.0, 0.0], float("nan"), 0.0, 0.0),
            ([600.0, 0.0, 0.0], [0.0, 0.0, 0.0], 0.0, float("nan"), 0.0),
            ([600.0, 0.0, 0.0], [0.0, 0.0, 0.0], 0.0, 0.0, float("inf")),
            ([600.0, 0.0, 0.0], [0.0, 0.0, 0.0], 0.0, 0.0, 0.0, float("nan")),
        ]
        for args in cases:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    analyze(*args)

    def test_bad_shapes(self):
        for pos in ([1.0, 2.0], [1.0, 2.0, 3.0, 4.0], [[1.0, 2.0, 3.0]],
                    [[1.0], [2.0], [3.0]], "abc", None, 600.0):
            with self.subTest(pos=pos):
                with self.assertRaises(ValueError):
                    analyze(pos, [0.0, 0.0, 0.0], 0.0, 0.0, 0.0)
        for vel in ([1.0, 2.0], [[0.0, 0.0, 0.0]], "abc", None):
            with self.subTest(vel=vel):
                with self.assertRaises(ValueError):
                    analyze([600.0, 0.0, 0.0], vel, 0.0, 0.0, 0.0)

    def test_non_positive_desired_range(self):
        for desired in (0.0, -1.0, -600.0):
            with self.subTest(desired=desired):
                with self.assertRaises(ValueError):
                    analyze([700.0, 0.0, 0.0], [-20.0, 0.0, 0.0], 0.0, 0.0, 0.0,
                            desired_range_m=desired)

    def test_bad_angles(self):
        for bad in ("north", None, [0.0]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    analyze([600.0, 0.0, 0.0], [0.0, 0.0, 0.0], bad, 0.0, 0.0)


class TestInvariants(unittest.TestCase):
    def test_rotation_matrix_is_orthonormal_and_deterministic(self):
        """間接受驗旋轉矩陣：用多組姿態檢查 analyze 的角度輸出互相一致。"""
        rng = np.random.default_rng(20261012)
        for _ in range(200):
            roll = float(rng.uniform(-180.0, 180.0))
            pitch = float(rng.uniform(-89.0, 89.0))
            yaw = float(rng.uniform(-180.0, 360.0))
            vec = rng.normal(size=3)
            vec = vec / np.linalg.norm(vec)
            # 將任意機身向量旋轉到NED，結果應還原該向量的機身角。
            phi, theta, psi = (
                roll * D2R, pitch * D2R, yaw * D2R,
            )
            Rz = np.array([[np.cos(psi), -np.sin(psi), 0.0],
                           [np.sin(psi), np.cos(psi), 0.0],
                           [0.0, 0.0, 1.0]])
            Ry = np.array([[np.cos(theta), 0.0, np.sin(theta)],
                           [0.0, 1.0, 0.0],
                           [-np.sin(theta), 0.0, np.cos(theta)]])
            Rx = np.array([[1.0, 0.0, 0.0],
                           [0.0, np.cos(phi), -np.sin(phi)],
                           [0.0, np.sin(phi), np.cos(phi)]])
            R = Rz @ Ry @ Rx
            rel_p = (R @ vec) * 500.0
            res = analyze(rel_p.tolist(), [0.0, 0.0, 0.0], roll, pitch, yaw)
            self.assertAlmostEqual(res["range_m"], 500.0, delta=1e-6)
            expected_nose=math.degrees(math.acos(float(np.clip(vec[0],-1,1))))
            expected_elevation=math.degrees(math.atan2(-vec[2],math.hypot(vec[0],vec[1])))
            self.assertAlmostEqual(res["nose_error_deg"], expected_nose, delta=1e-4)
            self.assertAlmostEqual(res["body_elevation_deg"], expected_elevation, delta=1e-6)
            if res["body_azimuth_deg"] is not None:
                expected_azimuth=math.degrees(math.atan2(vec[1],vec[0]))
                self.assertAlmostEqual(res["body_azimuth_deg"], expected_azimuth, delta=1e-4)

    def test_nose_error_bounds_and_types(self):
        """輸出為純 Python類型，且角度落在定義域內。"""
        res = analyze([700.0, 300.0, -400.0], [-15.0, 7.0, 2.0], 20.0, 10.0, 123.0)
        self.assertIs(type(res), dict)
        for key, value in res.items():
            self.assertIn(type(value), (float, type(None)), msg=key)
        self.assertGreaterEqual(res["nose_error_deg"], 0.0)
        self.assertLessEqual(res["nose_error_deg"], 180.0)
        self.assertGreaterEqual(res["vertical_los_deg"], -90.0)
        self.assertLessEqual(res["vertical_los_deg"], 90.0)
        self.assertGreaterEqual(res["body_elevation_deg"], -90.0)
        self.assertLessEqual(res["body_elevation_deg"], 90.0)
        self.assertGreater(res["cpa_time_s"], 0.0)
        # range = sqrt(700^2 + 300^2 + 400^2) = sqrt(740000)
        self.assertAlmostEqual(res["range_m"], math.sqrt(740000.0), delta=1e-6)


if __name__ == "__main__":
    unittest.main()
