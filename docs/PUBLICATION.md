# 公開範圍、來源與去重

## 本次包含

- Claude 的 `flybrain` 研究、反事實標籤、決策頭、可攜選項程式與結果。
- `jepa_brain` 規則／BFM／預測網路研究與 portable fighter。
- campaign 的修復控制器、實驗、前測、監督、核對器、成功與失敗收據。
- 較早的 autopilot／trainer／穩定飛行原型，以及本地 Host 測試的研究輸出。
- 研究者產生的權重、標籤、回放與逐幀模擬資料；較大項目放同一 GitHub repo 的 Release。

## 不公開的項目

憑證、帳號／用量／通知資料、報名與身分、私人通訊、網路設定與端點、個人主機識別；主辦方原始套件、Host／Python 執行檔、DLL、套件快取、第三方 vendor、重複封裝 ZIP、暫存／編輯器備份、隔離 quarantine。逐檔篩選到的排除分類與數量在 manifest 的 `excluded_counts`；整個第三方／runtime 資料夾直接略過，不逐檔列出。因此這是可公開的研究交接，不是硬碟完整備份。

原 repo 曾有名為 `LAN_ENDPOINTS_PRIVATE.md` 的舊檔，本次只在目前版本遮蔽其端點並註明停用。沒有重寫 Git 歷史；先前 commit 仍可能包含舊內容，不把本次清理說成歷史刪除。

## 防止重複上傳

`manifests/snapshot.json` 為每個邏輯路徑保留來源 SHA-256、公開 SHA-256 與大小。內容完全相同時只存一份，其餘使用 `alias_of` 指向同一份；`tools/snapshot.py restore` 會恢復原路徑結構。

大型內容也只按 SHA 儲存一次在 Release 壓縮包內的 `objects/<sha256>`，並分卷供下載；不再上傳包含相同資料的整包 ZIP、執行環境或備份。原始來源未改動；公開文字有個資／網路遮蔽、帳號欄位移除或 UTF-8 正規化時，`public_copy_changed=true`，不能用公開副本冒充原凍結 SHA。

## 署名與第三方

這個 repo 整合使用者指導下的 Codex 工程／核對與 Claude 研究分支。資料夾名稱只描述歷史來源，不代表任一方法已證實更強。歷史作者 README 保留其原說法，由具名原始證據與最新交接註記界定適用範圍。

未替整個 repo 套用新的寬鬆授權。主辦方程式、JSBSim、LAG、FlyWire／連結體與相關論文有各自的來源與授權；請從原來源取得第三方依賴，不因這份交接推定有權再散布全部官方資產。
