# AI 飛行員：程式、研究與新成員交接

> 2026-10-21：本 repo 已從早期指南擴充為 Claude 與 Codex 工作的共同公開交接入口。以下先讀新版；原指南保存在 [歷史指南](docs/history/training-guide-20261016.md)。本地結果不等於官方認證或對其他隊伍的勝率。

## 新成員從這裡開始

1. **[先讀我](docs/START_HERE.md)**：專案在做什麼、閱讀順序與下一個具體缺口。
2. **[目前狀態](docs/STATUS_20261021.md)**：候選、保留基準、已否決方案，以及六場已完成但核對逾時的實驗。
3. **[架構對照](docs/ARCHITECTURE.md)**：`campaign_2026`、`jepa_brain`、Claude 的 `flybrain` 及較早期工作。
4. **[下載／還原與核對](docs/REPRODUCING.md)**：程式在 Git；大型模型、replay 與逐幀資料在同一 repo 的 [Release](https://github.com/poopro/ai-pilot-training-guide/releases/tag/handoff-20261021)。
5. **[公開範圍與去重](docs/PUBLICATION.md)**：相同內容只存一份，以 SHA-256 和別名還原原目錄，不重複上傳整包備份。

## 現況摘要

- 保留已驗證的規則控制基準與原模型，不自動部署新候選。
- Claude 的 ridge／MLP 選項戰術員有值得追蹤的本地配對結果，但各對手的強弱與 Host 接線範圍要分開看。
- 新 bank17 SAC pilot 已完成訓練機制核對；六場凍結模型比較的原 verifier 逾時，戰力結論仍待獨立保存資料審查。
- 本次只發布現有程式、模型與證據，沒有新增訓練或對戰。

快速核對（只讀檔，不執行研究程式）：

```powershell
python -B tools/snapshot.py verify
```

完整檔案、來源／公開 SHA 及重複對照：[`manifests/snapshot.json`](manifests/snapshot.json)。實際數量與 Release 雜湊：[`manifests/export-summary.json`](manifests/export-summary.json)。

## 舊指南與備存事項

- [原訓練指南](docs/history/training-guide-20261016.md)
- [ASUS 第二台電腦設定指南](CODEX_SECOND_PC_SETUP.md)（備存；不是目前模型研究前置）
- [既有公開進度報告](reports/progress-2026-10-21.md)（需配合新版狀態看其適用範圍）
