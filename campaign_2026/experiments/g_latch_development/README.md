# 固定G latch候選：新24場開發比較

此次baseline是**真正的純repair_guide**，`guide`不是bank80別名。固定candidate為已小試的bank80＋G latch；safe_candidate.py与驗證小試來源byte-identical。比較rule／凍結RL ×3000/6000/9000呎 ×左右，共12公平pairs、24場；沒有learner、holdout或重跑原診斷。

固定新的seedbase2026101400；六個seed先核對observed/trials/holdout，再登錄prepared_not_run。start之後登錄attempted，即使失敗也不重複使用這份新開局宣稱fresh。

**假設限制：**原小試的首次指令分歧早在158.4167秒恢復模式，並非244秒才直接消除那個tick。單因素候選整場過G從1tick變0，但攻擊時間下降26.44%、最低高度下降0.6002m；新開發比較要檢查安全是否能保留，並量測相對純guide的戰鬥代價。

```powershell
$py='C:\Users\USER\anaconda3\envs\F16_ai\python.exe'
$tool='E:\ai_pilot\campaign_2026\experiments\g_latch_development\launch_development.py'
& $py -B -X utf8 $tool --check-only
```

check-only只檢查固定manifest、來源／model XML／red bundle、seed權利和程序；不建立JSBSim模擬器。每個新pair的初始SHA公平必須在實際模擬後核對，準備階段不能宣稱已生成新的初始狀態。

```powershell
# Host/其他研究終態之後，正式有時限執行：
& $py -B -X utf8 $tool start
# guardian與24worker終態後：
& $py -B -X utf8 $tool verify --job 'E:\ai_pilot\campaign_2026\experiments\g_latch_development\run_...'
```

獨立guardian亲自Popen supervisor並保存真正wait退出receipt；沿用已實測的OSlock、STOP、精確PID/建立時間/命令、資源與Host並行阻擋。固定總deadline40分鐘，單場300秒。用量與每天6小時只警告；仍保守預留40分鐘並禁止無上限運算。

驗證要求24完整場、12相同初始SHA配對、來源与對手不變、真實parent/worker退出0、合法有限60Hz逐tick指令、CSV/ACMI保存。分rule/RL比較擊落、攻擊、死亡、墜機、過G與最低高度；候選新增1tick過G或單對手kills退步都拒絕，逐對最低高度退步會列明安全review，不以全體平均掩蓋。通過只標review_pending，永不自動部署或宣稱奪冠機率。
