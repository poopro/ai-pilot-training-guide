# OpenCode / Space Bunny 工作規則

使用者於 2026/10/12 指定用 OpenCode 的 Space Bunny 節省 Codex 用量。

- CLI：`E:\ai_pilot\campaign_2026\tools\opencode-v2\opencode.exe`，官方 @opencode/cli Windows baseline 2.0.27。套件完整性與執行檔 SHA 已保存到 tools/opencode-v2/INSTALL.json。
- 模型固定 `opencode/space-bunny-free`；small_model 也固定同一模型。沒有付費或其他模型回退。
- 每項使用 opencode_task.py，預設十分鐘、最多二十分鐘，獨立本機伺服器。指定附件快照；禁止編輯與派子代理，其餘工具要批准，沒有 --auto。以文字提出程式，由 Codex 靜態審查、隔離保存及執行必要測試。
- 不修改 repair_v1、runner.py、benchmark.py 或任何正在運行作業的凍結來源。
- 禁止把密碼、憑證、個人資料附入任務。專案原始碼外傳曾被自動核准審查拒絕，理由是需要明確同意特定檔案傳給 Space Bunny。使用者已於10/12明確同意 repair_v1/controller.py、repair_v1/env.py 與 combat_v3/interface.py 這三個檔案傳給 Space Bunny，範圍與 SHA 記錄於 delegations/20261012_194445_a586/CONSENT.json。其他內部檔案不在這次同意範圍。
- 目前公開連線測試已實際成功；授權三檔原始碼審查已完成，實際模型與成本確認為 space-bunny-free / 0，補丁經本地核對拒絕，詳見該工作 LOCAL_REVIEW.md。SPACE_BUNNY_PUBLIC_MATH.md 是一般三維向量數學實作，無私有程式或實驗數據。
- 完全 deny 工具的自訂 agent 導致免費服務 403。官方內建 plan + 工具 ask、edit/subagent deny 已成功。不能用偽造身分標頭或自製 API 繞過入口限制。
- 每項紀錄在 delegations/：state.json、REQUEST.md、附件快照、events.jsonl、stderr.log、result.md；opencode_latest.json 指向最近完成工作。
- 若 CLI 沒回傳實際成本或模型資訊，記為未知，不以模型名字代替實際費用證據。回覆內容須經驗證，不當成飛行測試或勝率。

```powershell
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 'E:\ai_pilot\campaign_2026\opencode_task.py' --request 'E:\ai_pilot\campaign_2026\SPACE_BUNNY_PUBLIC_MATH.md' --seconds 600
```

外傳授權以對話中的使用者明確答覆為準；本次只同意上述三檔，不代表其他內部資料也獲同意。


10/12 19:09更新：公開數學任務已完成；實際session確認space-bunny-free且reported cost=0。診斷模組與本地修正後測試在diagnostics/，30項通過。這不是飛行性能證明。


## 10/12 最高推理強度規則

- 使用者要求無論模型都採最高強度；目前維持 Space Bunny，未指定清楚的其他旗艦選擇已取消。
- opencode_task.py 每次讀即時 `/api/model`，確認輸入、輸出、快取價格全為0，從可排序的支援 variants 選最高檔。Space Bunny 目前為 `opencode/space-bunny-free#max`；不手填其他模型未支援的 max。
- 根 `model` 在 OpenCode V2 不保留 variant，所以同時設定 CLI selector、plan/title agent selector 與模型 settings，small_model 也維持同一個模型。設定來源：https://opencode.ai/v2/docs/models/ 。
- 沒有可調 variants 時，明確記錄 no_adjustable_effort_advertised；未知價格或不明 variant 順序拒絕請求。沒有付費/降強度備援。
- 支援 `--model opencode/已查證免費模型ID`，仍強制最高支援檔位。此功能不擴大內部資料外傳授權；預設仍使用三檔已獲同意的 Space Bunny。
- 實際探測 delegations/20261012_195711_cb9b 已完成，session metadata 確認 space-bunny-free / variant=max / cost=0；六項價格、最高檔位及拒絕測試通過。確認依實際 session，不依模型回覆自述。
- 最高強度不代表建議正確，程式補丁仍需本地審查與模擬驗證。原啟動器保留為 opencode_task.before_highest_effort_20261012.py。
