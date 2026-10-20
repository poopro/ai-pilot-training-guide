# 原引導器可攜套件：待官方Host驗證

這是原repair_guide的回退套件，沒有新版bank80、SAC、replay或訓練。攜帶Windows64位Python與NumPy，來源檔SHA可核對。控制器僅改匯入路徑，RepairController類別AST不變；通訊RoundState AST不變。

雙擊「啟動Player.cmd」。先做檔案與依賴檢查，再開Player；每回合重新啟動。預設localhost，接官方Host若不同電腦，依主辦提供的IP與port修改network.json。network.json為可改設定，程式與runtime不可任意修改。

Player使用208-byte OWN20+ENEMY6封包，回傳30-byte合法四操縱與狀態、PLAYER_CMD。初始化不推進控制器，重複觀測保留原命令，最多60Hz；沒有新OBS時不自行發包。

官方公告Host必須從自己的原資料夾開啟，INIT後等待雙方READY/GO，再START；不要重複開內建Player2。這個可攜Player尚待官方Host重新實測，封裝/loopback通過不能當作Host通過或勝率。

套件包含僅供本Windows64位Player使用的Python/NumPy執行時；不是完整科研Conda環境，也不提供JSBSim/訓練/GUI工具。Python與NumPy授權保存在licenses及runtime/Lib/site-packages/numpy-1.26.4.dist-info。

## 本機驗證已完成

搬移到含中文/空白的另一個路徑後，以刻意錯誤的PYTHONHOME/PYTHONPATH與僅Windows系統PATH啟動；自我檢查確認模組與DLL未取用原Conda環境。兩個真正Player程序分別實際退出0，120個有狀態指令與原引導器一致（float32回傳誤差<=1e-6），初始化、READY、重複/無效觀測、缺資料恢復與重啟皆通過。沒有新FDM。

這證明本機搬移後的Player與封包流程；尚未證明另一台電腦、正式LAN、防火牆或官方Host多回合連線。下一階段需在比賽電腦從零啟動、檢查主辦IP/port並保存官方Host實測證據。
