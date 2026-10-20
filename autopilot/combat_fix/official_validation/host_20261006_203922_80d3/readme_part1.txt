JSBsim HOST 民眾公告版－操作說明與標準作業流程（SOP））---Part1
========================================================

一、軟體簡介
------------
這是一套提供參賽者快速驗證 Player1 連線程式的 Host 測試平台。
使用者扮演 Player1，系統會在按下 INIT 後自動啟動內建 Player2，讓 Player1
可透過既有通訊介面與 Player2 進行模擬對戰。

本公告版不需要另外啟動 Player2。請勿重複開啟多個 Host 程式，以免通訊埠衝突。


二、開始前準備
------------
1. 確認 JSB_host_GUI_publish.exe 與發布資料完整保留在原資料夾中。
2. 準備好您自己的 Player1 連線程式。
3. 若電腦的防火牆跳出網路存取詢問，請允許本程式及 Player1 連線程式通訊。
4. 建議開始新回合前，先確認上一回合已停止。


三、標準操作流程（SOP）
--------------------
Step 1：啟動您自己的 Player1 連線程式。

Step 2：開啟 JSB_host_GUI_publish.exe。
        畫面開啟後，確認 HOST STATE 顯示為 STOPPED。

Step 3：按下「INIT PLAYERS STATE」按鈕，並等待系統初始化。
        按下 INIT 後，Host 會重設本回合初始狀態，並在背景自動啟動內建 Player2。

Step 4：等待右側 Player2 初始化狀態亮起。
        顯示「Host已收到Player2／回傳初始化完成」，代表內建 Player2 已完成初始化回傳。

Step 5：等待左側 Player1 初始化狀態亮起。
        顯示「Host已收到Player1／回傳初始化完成」，代表 Host 已收到您的 Player1 初始化回傳。

Step 6：確認 Player1 與 Player2 兩個初始化狀態皆已亮起。
        畫面會顯示 P1/P2 READY 倒數；倒數結束顯示 GO 後，仍需手動按下 START。

Step 7：按下「START」按鈕開始演訓。
        HOST STATE 會切換為 RUNNING，計時器開始運作。

Step 8：演訓進行中可依需求使用「FREEZE／RESUME」或「STOP」。
        若啟用倒數計時器，時間歸零時系統會自動停止本回合。

Step 9：本回合停止後，等待系統完成資料存檔與 ACMI 轉換。
        轉換完成時，程式會印出完成訊息；Tacview 回放檔存放於 output_acmi 資料夾。

Step 10：若要進行下一回合，確認 HOST STATE 已回到 STOPPED，再重新由 Step 1 或
         Step 3 開始。建議確認 Player1 連線程式仍正常運作後，再按下 INIT。


