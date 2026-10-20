# 規則戰術零向量與兩個凍結模型：新六場完整開發比較

同一凍結`sac5000`紅方，藍方三個版本：`station_zero`（零戰術StationController，非pure repair_guide）、`sac5000`、`transfer10000`。兩個新的開發開局間距6000ft，seed2026310100 normal及2026310101 mirrored；每個開局三方須有相同完整藍紅初始packet SHA。

左右使用不同seed，不可把兩場差異歸因為唯一左右變更。這不是保留集，也不是職業隊伍勝率。原18場與1200步短測不重跑。

`battle.py --launch`先核對OSlock/STOP、CPU/RAM2GiB/disk10GiB、沒有其他campaign Python/Host、新seed未使用與來源／XML／模型SHA。先保留600秒預算與seed attempted，guardian每次只啟一worker，每場90秒、原全批600秒，逾時只停完整身分及祖先核對的自身程序，原預留不退。現有trial已執行就拒絕重跑。

每個worker必須完成真正終局或18000步的timeout，保存逐幀合法packet與實際命令JSONL、完整分數CSV與單調ACMI。藍方模型只用自己packet、自己累積counter、自己時鐘與guard；敵真姿態等只供judge。藍紅各自獨立模型／控制器。物理每60Hz tick一次act/send/step/judge，戰術每20tick；紅方終態額外pending command不送進模擬。保存packet用全新actor/controller重播，確保實際命令可重現。

父程序真退出0後，依同一run的原600秒deadline呼叫`verify.py --guarded RUN 0`，另有不超過60秒的讀檔verifier監督。只有6/6完整、所有worker實際0、全分數事件逐tick重算、來源與初始公平配對通過才`verified_comparison=true`。partial不得算勝率、拼接或全批重跑。

比較本地具名publication90/LINE1deg/AGL/right_bin規則；公告PDF／LINE／已安裝Host差異仍保留。沒有新訓練、optimizer/replay或自動部署；正式repair_guide保留。分析逐開局勝負、命中、擊落、被擊落、墜機、碰撞、過9G、score margin及共同曝光最低高度。即使局部變強也不把2個開局當穩定勝率。
