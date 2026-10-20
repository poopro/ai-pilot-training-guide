JSBsim HOST 民眾公告版－操作說明與標準作業流程（SOP）---Part2
========================================================

四、GUI 按鈕功能
---------------

【INIT PLAYERS STATE】
重設回合初始狀態並開始等待 Player1、Player2 初始化回傳。
本公告版會在此時自動啟動內建 Player2，不需要另外執行 Player2 程式。
僅可在 HOST STATE 為 STOPPED 時使用。

【START】
開始本回合演訓。請先完成 INIT，並確認 Player1、Player2 初始化狀態皆已亮起。
按下後 HOST STATE 會變成 RUNNING。

【FREEZE】
暫停正在進行的演訓。暫停後按鈕文字會變成 RESUME。

【RESUME】
從暫停位置繼續演訓。按下後按鈕文字會恢復為 FREEZE。

【STOP】
立即結束目前回合。系統會停止內建 Player2、清除兩個初始化狀態，並執行本回合的
存檔與 ACMI 轉換流程。完成後可再次按下 INIT 開始下一回合。

【倒數計時器】
點擊可切換啟用或停用。預設為啟用，預設倒數時間為 5 分鐘。
啟用時顯示剩餘時間，時間歸零會自動執行 STOP；停用時則顯示正向累計時間，
需要由使用者手動按下 STOP 結束回合。

【Player1／Player2 初始化狀態】
位於 INIT 下方的兩個矩形狀態顯示區，不是操作按鈕，點擊不會執行功能。
預設為灰色；Host 正確收到對應 Player 回傳的初始化完成數值後會亮起。
STOP 後會自動恢復灰色，等待下一次 INIT。


五、回合結束與輸出檔案
--------------------
1. 手動按下 STOP、5 分鐘倒數結束或系統完成仲裁，都會結束本回合。
2. 回合結束時會自動儲存本次演訓資料。
3. 系統會自動將本次 CSV 轉換為 Tacview 可讀取的 ACMI 檔案。
4. ACMI 檔案會存放在 output_acmi 資料夾；若資料夾不存在，系統會自動建立。
5. Player1 與 Player2 在 Tacview 回放中均以 F-16 顯示。
6. 轉換完成後，程式會印出一行完成訊息。


六、常見狀況
------------
1. Player1 初始化狀態未亮起：
   請確認 Player1 連線程式已啟動、IP／Port 設定正確，且未被防火牆阻擋。

2. Player2 初始化狀態未亮起：
   請先按下 STOP，再重新按下 INIT。若程式顯示 Player2 啟動失敗，請檢查
   player2_runtime.log 的錯誤訊息。

3. START 無法使用：
   請確認目前 HOST STATE 為 STOPPED，並先執行 INIT 等待雙方完成初始化。

4. 要進行下一回合：
   等待 HOST STATE 回到 STOPPED，確認上一回合檔案已完成轉換，再重新按下 INIT。

5. 程式異常關閉或數值異常：
   請重新啟動 Host 與 Player1 連線程式，再依完整 SOP 建立新回合。
