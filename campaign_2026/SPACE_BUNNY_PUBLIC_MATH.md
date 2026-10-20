# 公開數學程式實作

本題只包含一般公開的三維向量、航空姿態與相對運動數學，不包含任何私有專案程式或數據。請直接使用這段規格，不呼叫工具、不讀檔或執行 shell。回答繁體中文。

請產生兩份完整可執行的 Python 原始碼（只用標準函式庫和 Numpy），各自放在一個有檔名的程式碼區塊中：

1. `precision_math.py`：函式 `analyze(relative_ned_m, relative_velocity_ned_mps, roll_deg, pitch_deg, yaw_deg, desired_range_m=600.0)`。
 NED 是北、東、下為正。航空歐拉角定義：yaw0正北、yaw90正東；pitch為正抬頭；roll為正右側下傾。輸入只含相對位置、相對速度、己機姿態，沒有敵機姿態。
 輸出純 Python dict：range_m、horizontal_los_deg（yaw相對LOS，wrap到[-180,180)）、vertical_los_deg（世界水平面上方為正）、nose_error_deg（機身前向量與相對位置的3D夾角）、body_azimuth_deg（機身右方為正）、body_elevation_deg（機身上方為正）、closing_mps（靠近為正）、cpa_time_s（等速最近接近的未來時間，負值裁到0）、cpa_range_m、overshoot_time_s（以線性徑向閉合推估跨越desired_range的時間，沒有跨越時為None）。不用聲稱這是可飛行的控制器，只是純診斷。
 規則：非有限數、錯誤形狀、非正desired_range應ValueError；相對位置長度<1e-6應ValueError（無法定義瞄準方向）；零相對速度時CPA時間0。水平位置為零時水平LOS應為None，不可憑空定義bearing。僅有上方或下方時3D nose和body角仍正常。

2. `test_precision_math.py`：用unittest測試上述幾何意義，至少包含正前、正右、正上方、pitch30對正上升LOS、roll90導致身體右/下軸轉換、heading跨180度、零相對速度、遠離、CPA擦身而過、near-zero位置與NaN。測試要給具體預期數字。

所有角度要明確是degree，位置m，速度m/s。使用穩定clip處理arccos。說明 overshoot 只是直線等速風險指標，不預測飛機會如何轉向。
