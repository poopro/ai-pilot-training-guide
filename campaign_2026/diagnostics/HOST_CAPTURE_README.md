# 官方 Host 自動收證入口

10/14 已用舊環境的 repair_guide 完成六個獨立新回合，HOST_AUDIT eligible=true，六場門檻6/6。此門檻不包含 portable 套件；新套件彩排使用獨立 profile 與證據，不為舊門檻重啟 Host。

1. 先核對STOP、其他研究/Host程序、來源/設定SHA、資源與每日帳目。
2. 用 F16_ai Python 的 `-B -X utf8 diagnostics/arm_host_watchdog.py --deadline-seconds 720` 啟動。它先武裝獨立watchdog，再啟Host與Player1。
3. Computer Use按INIT，確定雙方READY/GO後執行 `diagnostics/collect_host_recorded.py mark-start`，再按START，觀察RUNNING与倒數下降。
4. watchdog會在新的P2 STOPPED log、完整新CSV及穩定且同終態ACMI均核對後，自動呼叫collector。它取得真實退出碼、保存audit，再清理自己精確識別的Host/Player1/P2子孫，不依賴聊天守候。
5. 只在HOST_AUDIT eligible=true、auto_collector_exit0、watchdog receipt清理完成時算有效回合。CSV勝負或completed flag不足以計數。原有GAME OVER log路徑保留；P2替代收據須啟動前stat/hash、同token與childPID/祖先、初始位置/CSV、保存hash等全部一致。

保存來源快照、Host/Setting、CSV/ACMI/log、P2 receipt、collector process/exit與watchdog receipt。舊缺receipt回合維持不合格，不回填。每回合從零啟動並固定來源/設定；六回合不是正式競賽認證或未知對手勝率。

離線測試：`python -B -X utf8 -m unittest test_p2_terminal_evidence test_host_watchdog -v`，9項通过，包括拒絕舊資料/錯PID/不完整CSV/遺失ACMI/竄改snapshot與mock collector timeout。實際正向證據見host_gate_latest.json。
