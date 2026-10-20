# 獨立終態補稽核

`post_audit.py`不屬於149個凍結來源；沒有改動正在執行的launcher、candidate、manifest或原verifier。它只讀完成資料與實際檔案SHA，不啟FDM、learner或新對戰。

要求supervisor與guardian已不存在、state completed、guardian親自Popen.wait取得parent真0，24worker皆有真0/完整命令/PID建立時間/正確父程序receipt。每場必須1–18000整數tick、full_round_completed=true；短回合只接受kill/shot_down/own_crash/enemy_crash/mutual_crash/simultaneous_hit合法终態。兩側回合長度可以不同。

獨立重算全部60Hz：前一tick實際G決定候選latch、abs_g=abs(signed_g)、exact overload counter、合法有限四控制、無缺tick、metric overG seconds與tick精確一致。對1Hz CSV核對最後attack/enemy attack/overG；ACMI核對最後模擬時間。逐pair initial SHA必须相同，對手model/manifest實際重新hash；來源與launch固定149項一致。

最低高度保留judge的AGL數值；CSV altitude為HSL，两者可有毫米等級差異，不能拿HSL最低值替換AGL最低值。每pair的AGL退步仍進安全review。任何新增候選over9G皆拒絕；不自動部署、不宣稱正式勝率。

7項初版反例與原smoke正向測試已過；另加入partial/live終態拒絕反例後共8項。原smoke完整正向CLI實際exit0；新24完成後正向CLI實際exit0，24場/12pair，gate=metric_pass_safety_review_pending。這表示完整證據一致，仍需檢討最低高度退步。

## 最小獨立finisher設計（未實作或啟動）

新增放diagnostics的監督腳本，絕不改149項來源。以最新guardian的PID/建立時間/完整命令核對，30秒輪詢到它退出；最多等launch固定deadline加60秒。持有該job的finish.lock去重，拒绝不同job/新pointer覆蓋。

確認真parent+24worker receipt後，親自Popen原verify並保存wait真exit；再Popen post_audit並保存wait真exit。任一失敗都只存阻塞證據。只有兩個真0和post_audit passed，才將本job的latest/pointer更新為verified与其review gate；若root pointer已指向另一job，只記本job歷史，不蓋掉新的運行狀態。marker使用run path+launch SHA+來源SHA去重，永不部署、不開FDM、不呼叫API。
