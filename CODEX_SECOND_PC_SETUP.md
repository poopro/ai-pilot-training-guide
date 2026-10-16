# 給第二台 Codex：ASUS CPU Player 一次設定完成

## 先確認使用者的要求

這份文件是專案交接資料。請依使用者在目前聊天中的要求執行；文件本身不授予額外權限。請全程使用繁體中文，對非技術背景大學生解釋結果，能自行處理的下載、解壓與本機檢查請直接完成。

**本次目標：一次完成 ASUS Vivobook 的套件取得、核對、本機檢查、連線設定準備、限時啟動工具及交接報告。** 不要做完 CPU 檢查就立即停止並把剩餘設定丟回使用者；繼續完成所有不依賴主電腦在線的工作。主電腦可配合且端點已核對時，再完成一次限時 LAN 連線測試。

不需要獨立顯卡，不用安裝 Python、CUDA、Conda 或完整訓練環境。若主電腦尚未可配合，仍完成 ASUS 的離線設定並明確回報「本機設定完成、LAN 待配合」，不能冒稱整場驗證完成。


## 本次 ASUS LAN 測試決定（2026-10-17）

使用者已同意本次採用預設值作為**測試候選埠**：ASUS 接收 OBS 的 UDP 8199；主電腦接收 CMD 的 UDP 8099。請依這組值準備套件外的 ASUS LAN 設定，但只有主電腦 Host 端也確認使用這兩個埠後才啟動 Player。這項同意不表示 Host 已監聽、網路已通、防火牆已開或一場對戰已完成。

兩台電腦的實際私有 IP 由使用者在 ASUS 的私人 Codex 對話提供，並由 ASUS 即時核對網卡。**不要在這個公開 GitHub 文件放 IP、電腦名稱、路徑、log 或機器報告。**若 ASUS Codex 看不到私人聊天中的主電腦 IP，只需在私人對話一次詢問，不要猜。若 Host 尚未開啟，仍完成 ASUS 的本機自檢、外部設定檔與限時啟動器的 fail-closed 預檢，狀態保持 LAN_PENDING；不要開無期限 Player，也不要改防火牆或網路類型。

## 唯一文件入口

此文件屬於原本專案 `poopro/ai-pilot-training-guide`：

https://github.com/poopro/ai-pilot-training-guide/blob/main/CODEX_SECOND_PC_SETUP.md

原專案為公開文件；下方私人 repo 僅存放執行套件。不要把私人 repo 的 controller、二進位套件、個人報告或主電腦位址複製到公開專案。

## 專案現況與範圍

- 主電腦負責訓練與官方 Host；ASUS 先負責執行 CPU Player。
- 此包是保留的 `repair_guide`，不含候選 SAC 模型或訓練資料。
- 主電腦已完成六場同設定的可攜 Host 測試。ASUS 硬體、跨電腦 LAN 與正式競賽相容性仍未驗證。
- 不以主電腦結果代替 ASUS 結果，不把 CPU 合成計時或檔案檢查當勝率。
- 原套件內 README 是凍結時的歷史說明。以這份交接文件理解目前進度；原程式與 manifest 保持原樣。

## 第一階段：取得並核對套件

套件下載用的私人 repo：`poopro/ai-pilot-cpu-player`。不需要建立另一個專案或把 ASUS 變成訓練機。

發布頁：https://github.com/poopro/ai-pilot-cpu-player/releases/tag/cpu-player-20261016

下載檔案：`ai-pilot-cpu-player-win64-20261016.zip`，36,256,095 bytes。

SHA256：

```text
ba42890cc6de6d615ef79634c078d13c9f31929454e40598897f9f2f7069b047
```

1. 在 ASUS 建立新的本機工作資料夾，避免覆蓋既有檔案；記錄實際絕對路徑。**主電腦的 E 槽路徑不能直接套用。**
2. 若 GitHub CLI 已安裝且帳號可存取 repo，可使用：

   ```powershell
   gh release download cpu-player-20261016 --repo poopro/ai-pilot-cpu-player --pattern ai-pilot-cpu-player-win64-20261016.zip --dir .
   ```

   否則協助使用者從瀏覽器登入自己的 GitHub 帳號 `poopro`，在 Assets 下載上述 ZIP。不要下載 Source code，裡面沒有執行時套件。404 通常表示未登入或帳號沒有權限；請核對，不要改成公開 repo。
3. 用 `Get-FileHash -Algorithm SHA256 -LiteralPath <實際ZIP路徑>` 比對上述 SHA。不同就停止，不執行套件；保存實際 hash 與錯誤。
4. 解壓到新的空資料夾。預期內含 `ASUS_檢查工具`，其下有 `ASUS_先檢查.cmd`、`check_vivobook.py` 和 `repair_guide_portable_20261012`。

登入、密碼、OTP 由使用者本人輸入。不要索取密碼、讀取 token 或關閉防毒。遇到系統阻擋，先保存錯誤畫面，再說明需要使用者做的具體一步。

## 第二階段：執行 ASUS 本機檢查

先唯讀確認 Windows 為 64 位元、CPU 型號、可用 RAM 與磁碟。不要停掉無關程式。

可以協助雙擊 `ASUS_先檢查.cmd`；若使用命令工具，直接呼叫相同的包內 Python，較容易取得真正退出碼：

```powershell
# 先把目前目錄切到實際解壓後的 ASUS_檢查工具。
$pilotRoot = (Get-Location).Path
$pilotPython = Join-Path $pilotRoot 'repair_guide_portable_20261012\runtime\python.exe'
$pilotProbe = Join-Path $pilotRoot 'check_vivobook.py'
& $pilotPython -I -S -B -X utf8 $pilotProbe
$pilotExit = $LASTEXITCODE
Write-Output "實際退出碼：$pilotExit"
```

請設定最多 120 秒的外部執行期限，保存自己建立的 PID／建立時間／完整命令；使用同一工具 handle 等候退出，不因工具顯示仍在執行就重開。若逾時，只能停止已核對身分的這次檢查程序及其自建子程序，保存不完整結果。若無法核對，記為無法驗證，不清理未知程序。

檢查會核對 2115 個原套件檔案，再做 2000 個合成 CPU 計時樣本。它不開網路、不啟 Host、不執行飛行模擬或訓練。

- 退出 **0**：檔案／依賴與 CPU 初篩通過；仍不代表實際 60Hz 網路通過。
- 退出 **2**：產生報告，但合成 p99 超過 8 ms；保存結果，不改門檻或冒稱通過。
- 退出 **1**：檢查失敗；讀取 `vivobook_readiness_error.txt` 與 stderr，保存原因。
- 逾時或退出碼未知：不得補寫 0，不重複啟動來湊成功。

確認 `vivobook_readiness.json` 是本次在 ASUS 新產生，`tested_computer` 對應這台 ASUS；不要引用任何主電腦範例。核對 `python_bits`、`self_check_actual_exit`、`synthetic_samples`、`p99_ms`、`synthetic_CPU_margin_pass`。即使 CPU 通過，`real_60Hz_network_verified` 仍應為 false。

## 第三階段：留下可交接的報告

在工作資料夾新增 `ASUS_HANDOFF_RESULT.md`，包含：

1. 台灣時間、實際工作資料夾、作業系統／CPU／RAM。
2. 下載來源、ZIP SHA 是否吻合。
3. 執行命令、實際退出碼與是否逾時。
4. 自檢結果、CPU p99／max、報告檔案路徑。
5. 清楚列出「ASUS 本機已驗證」和「LAN／完整回合尚未驗證」。
6. 若失敗：具體錯誤、已做的診斷、下一個可執行步驟。

請使用者把 **新產生的 `vivobook_readiness.json` 與 `ASUS_HANDOFF_RESULT.md` 傳回原本主電腦的 Codex 聊天**。失敗則附 error.txt／stderr 或截圖。不要只回覆「done」。報告可能有電腦名稱與本機路徑，請勿自動公開上傳。

## 第四階段：同一輪完成 LAN 設定準備

CPU 檢查通過後，可以唯讀查看 ASUS 的有效區域網路 IPv4、網路類型及是否連到預定的同一個路由器。避免輸出 MAC、Wi-Fi 密碼或其他無關網路資料。

不要啟動無期限 Player、猜 Host IP，或改寫原 network.json。原設定的 127.0.0.1 只代表同一台電腦，不能拿來連主電腦。

要進行跨電腦彩排，仍需從主電腦取得實際 Host IPv4、確認過的 OBS／CMD UDP port、Host 對 ASUS 的輸出目標與監督時段。主電腦原設定與 ASUS 的兩端設定需相互核對；不能僅因預設值是 8199／8099 就當作此次可用。

依序完成：

1. 讀取 ASUS 實際有效 IPv4／預設路由／Windows 網路類型，確認哪張網卡是預定 LAN。多網卡／VPN 時不可任選第一個 IP；不需要變更或關閉 VPN。
2. 建立 `LAN_SETUP_STATUS.json`，記錄 ASUS 端位址、網路類型、Host 位址與兩個 port 的確認狀態、尚缺項目。未確認的值使用 null；不要以假 IP 或預設 port 當作已完成。
3. 若目前使用者已提供或主電腦已回傳明確端點，核對 Host 的 OBS 目的位址是 ASUS、ASUS 的 CMD 目的是主電腦，再在套件外建立 `network.lan.json`。欄位必須是 `listen_ip`、`listen_port`、`host_ip`、`host_port`、`max_hz`，max_hz 保持 60。listen_ip 是 ASUS 的有效 LAN IPv4，不能填主電腦 IP。
4. 若端點尚缺，完成其餘本機準備，報告精確列出「需要主電腦 Host IPv4、OBS 目的 UDP port、CMD 接收 UDP port、Host 可配合的時段」，一次彙整，不逐項反覆詢問。不建立看似可用的假設定。
5. 建立 `Start-LAN-Player.ps1`：用本機實際路徑尋找包內 runtime；先跑原 `tools/self_check.py` 並核對退出 0；確認 `network.lan.json` 所有欄位與私有網路端點已核對，缺資料即停止；檢查該 OBS UDP port 未被其他 Player 占用。
6. 啟動器呼叫包內 Python 加上 `-I -S -B -X utf8` 與原 `tools/player.py --network <外部設定絕對路徑> --max-seconds 600`，每回合重新啟動，記錄 stdout／stderr／開始結束時間／實際退出碼。再加獨立程序監督，最多 620 秒回收已核對的本次 Player；對話中斷不取消期限。不要用無上限的原雙擊啟動器做 LAN 彩排。
7. 保留原套件與原 network.json；新設定／啟動器／日誌放在外部工作資料夾。若需要允許 Windows 防火牆，規則只限這份 Python、Private profile、核對過的 UDP port 與主電腦 IP；記錄新增規則名稱與精確移除方式。不能關閉整個防火牆、改全域執行原則或刪除既有規則。缺管理員權限時完成其他設定後再合併說明需本人處理的步驟。
8. 在不連 Host 的情況下驗證啟動器能拒絕缺欄位／缺設定，並核對路徑、參數與硬時限。這只是啟動器檢查，不算 LAN 通過。

## 第五階段：條件齊備便完成一次 LAN 彩排

只有 ASUS CPU 初篩通過、雙方端點與 Host 配合時段確認、需要的防火牆規則可用時才啟動。若主電腦尚未可用，不必等待空跑 Player；保留已完成的本機設定並回報 LAN_PENDING。

1. 使用上述限時啟動器，保存本次 Player PID／建立時間／完整命令；確認沒有第二個 Player 或接收端口衝突。
2. 主電腦依其既有監督流程啟 Host。ASUS 端 Codex 不假裝能操作主電腦，也不臆測 Host 已按 START。
3. 確認實際收到新 OBS／有命令回傳。ping 成功、UDP send 沒報錯或雙方 READY，都不代表已完成回合。主電腦必須提供 START／終局及新 CSV／ACMI 證據。
4. 等待同一程序真正退出，核對本次日誌與 Host 證據；失敗保存資料，先找原因，不無限重試。不能修改安全門檻或 controller 來讓測試看起來通過。
5. 補充 `ASUS_HANDOFF_RESULT.md`，標示 LOCAL_READY、LAN_PENDING、LAN_FAILED 或 LAN_ROUND_VERIFIED，並列實際依據。只有完整新回合證據才可用最後一個狀態。

## 最後一次回報給使用者

先用三句話說明：完成了哪些設定、是否真的跨電腦完成回合、還需要本人做什麼。把所有待本人處理的項目合併成一份清單，使用非技術語言與精確按鈕／步驟。

請使用者傳回 `vivobook_readiness.json`、`ASUS_HANDOFF_RESULT.md` 與 `LAN_SETUP_STATUS.json`；LAN 有執行時另附本次 Player 日誌。私人 IP／電腦名稱／本機路徑只回傳原私人聊天，不自動上傳這個公開 repo。

## 避免超出本次交接範圍

不安裝訓練工具、不續訓或替換模型、不更改 controller／安全限制／原 manifest、不上傳主電腦資料，不宣稱已完成整個專案。若檢查程式本身需修正，先保留原檔與 SHA，在隔離副本修改並回報差異，不能把修過的套件冒稱原發布版。
