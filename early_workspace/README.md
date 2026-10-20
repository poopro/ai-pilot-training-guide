> 2026-10-03：本文件保留舊流程紀錄，提到的啟動檔已封存。以下舊啟動步驟須先還原檔案才可使用。現在請依 [目前啟動入口](啟動入口.md) 使用第二版。需要舊版時請看 [封存與還原說明](_archive/launchers_20261003/README_封存與還原.md)。

# AI Pilot 本機準備

這個資料夾把官方環境需求整理成可重跑的本機流程。官方提供的是 JSBSim 模擬環境，不是固定的 CSV 資料集；訓練資料會在模擬過程中逐步產生。

目前已完成：

- Python 3.10.20 隔離環境：`C:\Users\USER\AppData\Local\ai-pilot\venv`
- PyTorch 2.5.1 CUDA 12.1，已確認可使用 RTX 3060
- Stable-Baselines3 2.4.0、Gymnasium 1.0.0、JSBSim 1.3.1
- 官方 F-16 模型 600 步一般飛行健康檢查
- 一般穩定飛行遙測資料集產生器
- 使用 RTX 3060 的一般飛行穩定控制模型訓練器

## 一鍵產生資料集

在 PowerShell 進入本資料夾後執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_dataset.ps1
```

預設會產生 12 回合、每回合 1,800 步，共 21,600 筆資料：

```text
C:\Users\USER\AppData\Local\ai-pilot\data\flight_stability.csv
```

資料包含高度、速度、姿態、攻角、側滑角與四個控制輸出，可用於一般飛行穩定控制與資料品質分析。它不包含對戰、瞄準或攻擊標籤。

## 一鍵訓練穩定飛行模型

先產生資料集，再執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_training.ps1
```

模型與驗證結果會寫入：

```text
C:\Users\USER\AppData\Local\ai-pilot\models\stability_controller.pt
C:\Users\USER\AppData\Local\ai-pilot\models\stability_metrics.json
```

## 重新安裝主要套件

PyTorch 使用官方文件指定的 CUDA 12.1 套件庫：

```powershell
C:\Users\USER\AppData\Local\ai-pilot\venv\Scripts\python.exe -m pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
C:\Users\USER\AppData\Local\ai-pilot\venv\Scripts\python.exe -m pip install "stable-baselines3[extra]==2.4.0" gymnasium==1.0.0 jsbsim==1.3.1 tensorboard==2.21.0
```

## 目前的限制

官方 `train.py` 預設使用 8 個平行環境與 5 億步，對 Ryzen 3 4100 不適合作為第一次測試。先用短回合確認資料品質與運作穩定，再決定訓練時數。
