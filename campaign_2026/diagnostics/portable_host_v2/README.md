# portable公告Host獨立驗證

使用既有2115檔repair_guide可攜套件的Python與Player；所有觀察工具、receipt、active pointer與本地psutil副本放在此新分支。原ZIP、manifest、Player、控制器與公告Host輸入均不改；不用Conda執行路徑。舊環境六回合完成資料不匯入此profile；可攜套件六回合需求獨立計算。

先用包內執行時核對來源、原Host四檔、可用資源、UDP擁有者、STOP與compute工作。用量與每日6h只列警告，實際啟動仍預留720秒於原日期ledger，保留歷史。共享campaign OS lock讓單一監督工作持有；每回合重啟套件Player。

```powershell
$py='E:\ai_pilot\campaign_2026\deployment\repair_guide_portable_20261012\runtime\python.exe'
$tool='E:\ai_pilot\campaign_2026\diagnostics\portable_host_v2\portable_host.py'
& $py -I -S -B -X utf8 $tool check --out 'E:\ai_pilot\campaign_2026\diagnostics\portable_host_v2\PREFLIGHT.json'
& $py -I -S -B -X utf8 $tool arm --deadline-seconds 720
```

`arm`僅啟動獨立watchdog，由watchdog完成真實包內runtime self_check、啟動原公告Host與包內Player，留下ui_ready.json後回傳run資料夾。guard從intent起以monotonic與wall clock兩個期限較早者控制；START等待也算在720秒。WinError5存檔有界重試；receipt仍失敗時guard保存錯誤並完成自己的程序清理，不能用檔案錯誤跳過cleanup。

ui_ready出現後、INIT／START前，另開一個有實際process handle的退出觀察器。它先核對guard_spawn的PID／建立時間／命令／執行檔，再取得Windows wait handle；等待與GetExitCode得到真正退出0才留下watchdog_exit_observed.json。程序已消失或無法取得handle時不能補0，該回合不計入packaged六場gate。

```powershell
& $py -I -S -B -X utf8 $tool observe-watchdog --folder '<arm回傳的run絕對路徑>'
```

觀察器需保持執行，可在工具回傳session後同時操作UI。先確認watchdog_wait_attached.json已產生，才按INIT／START。

仍需要Computer Use／操作者在**這個新Host視窗**按INIT，等雙方READY／GO，再記錄界線並按START：

```powershell
& $py -I -S -B -X utf8 $tool mark-start --folder '<arm回傳的run絕對路徑>'
```

新鮮、屬於該Host子孫的P2 STOPPED log、唯一新CSV與已轉換且穩定ACMI都出現後，watchdog自動呼叫同一包內Python collector，保存其真實wait退出碼，再依PID／建立時間／命令／執行檔精確清理。沒有terminal證據、collector逾時、receipt失敗或未知程序身分都不當作成功。

`portable_result.json`與watchdog_receipt.json屬新profile。只有新增可攜套件回合可以透過`aggregate --report ...`計入單獨六回合gate；舊六回合永遠計0。公告版本機Host的完成依然不等於正式賽事認證或可靠競賽勝率。

本分支目前完成靜態／preflight測試。是否真正Host完成，以新run的原始CSV、ACMI、P2 receipt、collector實際退出及watchdog cleanup為準。
