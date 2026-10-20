> 2026-10-03：本文件保留舊流程紀錄；提到的舊啟動檔已封存，下面的舊啟動步驟須先還原檔案才可使用。現在訓練／評估請使用第二版入口：E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test。完整操作說明位於 combat_v2\README_第二版操作.md；封存與還原說明位於 E:\ai_pilot\_archive\launchers_20261003\README_封存與還原.md。

# LAG 輔助環境

`E:\ai_pilot\lag` 是從 [liuqh16/LAG](https://github.com/liuqh16/LAG) 分開下載的研究副本，保留 GPL-3.0 授權檔案。它不會取代官方競賽環境，也不會把官方 UDP／模型介面改掉。

目前已做的相容性修正：

- 補齊 LAG 的 JSBSim data submodule。
- 讓 LAG 的 property catalog 同時支援舊版 JSBSim 回傳 list，以及目前 1.3.1 回傳的換行文字。
- 新增 `lag_smoke.py`，只測飛行控制與 `1v1/NoWeapon`，每個情境跑 5 步，不包含武器發射。
- dashboard 的「LAG 輔助環境」區塊會顯示依賴、模型資料是否齊全，並可一鍵執行 smoke test。

使用方式：執行 `START_DASHBOARD.bat`，在瀏覽器按「執行 LAG Smoke Test」。看到兩個案例都是 `ok: true` 才代表環境能啟動；這不是競賽成績，也不是完整訓練。

目前 LAG 的舊 PPO 長訓練尚未接到「開始訓練」按鈕，先用 smoke test 把環境穩定下來，再決定是否以獨立設定接入短訓練。官方競賽訓練仍使用 `E:\ai_pilot\work` 的訓練腳本。
