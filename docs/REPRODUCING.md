# 取得與核對快照

## 只閱讀程式與報告

```powershell
git clone https://github.com/poopro/ai-pilot-training-guide.git
cd ai-pilot-training-guide
python -B tools/snapshot.py verify
```

這個核對只讀檔、計算雜湊，不會載入模型、啟動 Player、Host、FDM 或訓練。

## 取得大型模型／逐幀紀錄並還原重複路徑

在 [handoff-20261021 Release](https://github.com/poopro/ai-pilot-training-guide/releases/tag/handoff-20261021) 下載所有 `research-artifacts-20261021.tar.gz.part*` 分卷，或使用：

```powershell
gh release download handoff-20261021 --repo poopro/ai-pilot-training-guide --pattern 'research-artifacts-20261021.tar.gz.part*' --dir downloads
python -B tools/snapshot.py join --parts downloads --archive downloads/research-artifacts-20261021.tar.gz
python -B tools/snapshot.py verify --archive downloads/research-artifacts-20261021.tar.gz
python -B tools/snapshot.py restore --archive downloads/research-artifacts-20261021.tar.gz --output workspace
```

`workspace` 必須是新的或空的資料夾。工具不覆寫現有工作、不執行快照內的任何程式。它會重建因去重而未重複提交的路徑，並逐檔比對公開 SHA。

`join` 先檢查每個分卷 SHA，再合成壓縮檔並檢查整包 SHA；分卷是同一包資料的不同段，沒有再上傳一份相同的完整包。

## 執行研究程式前的依賴

- 原研究使用 Windows Python 環境 `F16_ai`；套件版本摘錄見 `manifests/environment.json`。這是環境紀錄，不是完整跨平台 lockfile。
- 需要自行從主辦方取得符合版本的 `AirCombat_Train_Test`／`combat_v3`／FDM XML 與資產。這些第三方原始套件未放入公開 repo。
- Linux 的反事實分支標籤會使用 `os.fork`，不能假設在原生 Windows 直接可跑；見 Claude README 的平台與資料取得說明。
- 果蠅完整資料由 `flybrain/fetch_data.py` 的固定來源下載，保留上游論文與授權。原始連結體不重複打包。
- 歷史腳本常以 `E:\ai_pilot` 為根目錄，少數 Python 路徑已遮蔽使用者名稱。還原完成只保證檔案／模型／紀錄的完整性，不保證換機可直接訓練或連線。先在獨立工作副本設定路徑、檢查依賴，不能直接覆寫原凍結來源。
- SB3 zip／PyTorch checkpoint／replay pickle 只作研究資產保存，不由快照工具反序列化。實際使用前要核對模型介面與套件版本。

## 不要重做已完成實驗

run 名稱、seed registry、失敗退出與 watchdog 契約都已保留。新的對戰／訓練必須另立有界契約；不能直接重新執行 `guard.py`，把已使用種子當新證據。
