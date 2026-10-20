# 凍結對手池與左右鏡像自我對戰：先檢查介面

既有 `POOL_FREEZE.json`、`PREPARATION.json` 與144場 `launch_pool.py` 保持原樣。近距bank80在新開局已被 `reject_promotion`，原launcher所要求的成功與安全前置並未通過，因此不能直接拿它當新分支入口。原launcher的Codex剩餘35%／每日6h硬擋也與最新記錄的「只提醒」政策不同，執行器更新時須保留實際用量紀錄與獨立硬期限。

最小池沿用四個已凍結來源：原規則追擊、既有SAC殘差、原repair引導器、遠距bank60規則變體。前三者是三種控制方法；bank60是參數變體，不聲稱是第四種獨立方法。對手強度尚未驗證。

第一步規劃 **24個短回合**：四對手 × 3000／6000／9000ft × 左右開局，每場只有300個60Hz tick（5秒）；藍方都使用目前repair引導器。當紅方也是repair引導器時，共有6個左右自我對戰case。每個控制器的積分、上一幀狀態與恢復狀態須各自獨立。所有策略只收OWN20+ENEMY6；紅機真實姿態僅供裁判與稽核。

左右鏡像以紅方為中心反射藍方初始位置，保留双方heading／高度／CAS；驗證cross-track符號相反、初始距離誤差小於1%、紅方狀態不變、同一幾何對的紅方RNG一致。左右鏡像的初始SHA理應不同；不能用「SHA相同」當左右幾何成立的條件。相同SHA只用於同一side下的guide／candidate公平比較。

短回合只驗證初始化、合法有限4維控制、穩定更新、STOP、期限與產物保存。每場最多30秒、整批15分鐘；在首次嘗試前登記12個開發種子，保留集不得混入。父程序與worker實際退出必須記錄。未完成、逾時或缺資料不列介面通過，更不列勝率。即使提前合法終止，300tick規劃仍永遠 `score_eligible=false`。

目前只實作**無模擬的準備工具**，沒有新smoke執行器；不得繞過原private worker的擁有者／預算／bank80前置檢查。離線檢查用6筆既有合法觀測核對24個對手控制輸出、guide自我對戰與原控制器一致，並攔截FGFDMExec建立飛機的呼叫。這些結果不代表時間演化、戰鬥表現或正式Host驗證。

```powershell
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\prepare_smoke.py' --check-only --out 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\SMOKE_PREPARATION.json'
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 -m unittest discover -s 'E:\ai_pilot\campaign_2026\experiments\opponent_pool' -p test_smoke_preparation.py -v
```

短smoke通過後，才凍結一個有新理由的候選進行48場完整開發比較（四對手×三距離×兩側×guide/candidate）。以逐對手最差表現、擊殺／死亡／墜機、攻擊秒數、9G與最低高度判斷；同controller自我對戰結果不得轉成競賽勝率。候選穩定後才擴展三種子144場與未見保留集、正式Host及現場彩排。
