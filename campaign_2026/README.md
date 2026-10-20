# AI 飛行員競賽工作目錄

本目錄由 2026/10/11 的接手對話管理，實際路徑 `E:/ai_pilot/campaign_2026`。

- 完整路線：ROADMAP.md
- 最新進度：LATEST_RESULT.md；機器狀態：pipeline_latest.json
- 實驗檢討：REVIEW_LOG.md
- 凍結的原始來源及初始存檔校驗：BASELINE.json
- 各輪訓練、評估、進度、完整存檔與紀錄：jobs/

PowerShell：

```powershell
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -X utf8 'E:\ai_pilot\campaign_2026\runner.py' status
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -X utf8 'E:\ai_pilot\campaign_2026\runner.py' stop
```

`stop` 會先要求保存；結果確認已收尾前勿直接關視窗或電腦。

本機 pipeline 有固定預算，完成後每日 Codex 檢討才決定下一個方法；同一個已完成工作不會為湊時間重啟。只有真的改進並經過對戰驗證，才能更新正式版本。

Codex 排程：00:30、06:30、12:30、18:30 低頻監督；20:30 每日檢討。時間皆 Asia/Taipei。正常運行保持安靜；新成果、失敗或需協助時通知。排程使用本對話既有上下文，額度不足時縮小工作。


報名狀態（10/12更正）：尚未正式報名；主辦已確認接受單人參賽。10/21前要完成報名。

OpenCode執行與權限：OPENCODE.md。排程需要電腦及Codex開著；本機訓練不使用Codex API。若狀態檢查因權限不足無法讀取程序，不能把它當作停止訓練。
