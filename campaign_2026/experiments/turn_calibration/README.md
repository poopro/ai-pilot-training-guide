# 轉彎校準工具準備狀態

這個資料夾尚未執行 FDM 校準，沒有模型訓練或勝率結果。

- Space Bunny 第一次max草稿只有說明、缺程式碼，已保存DELIVERY拒絕結果。一次針對缺漏的重試成功交付243行草稿，實際session確認max/cost0；不再重試。
- 本地核對並修正：錯誤Euler yaw公式、暖機CSV漏記、每tick恢復track模式以符合原act行為、嚴格形狀/舵面界線、Euler奇異與非有限JSON拒絕、目標值分為requested/effective、trim分母與原式一致、完成時STOP/150s再核對。原控制器/環境/ICD來源均未修改。
- 六項mock adapter測試通過，涵蓋body q在bank時對yaw影響、奇異/形狀拒絕、2100列含900暖機與1200測試、guard不剔除、controller歷史保留、非法舵面不advance、STOP/時間界線、獨立案例初始/暖機SHA一致。這些不證明真實FDM飛控穩定、負載定義或真實舵面符號。
- calibration_adapter.py 是本地介接草稿，使用原runtime及兩個原FDM；每tick own與bank0/path-hold reference各step一次，沒有裁判或learner。JSBSim類別確有get_delta_t方法，實際建構仍待校準時驗證。

## 尚需完成後才能執行

實作父層CLI/supervisor：新worker process每個case各建立同initial adapter/controller；7case，bank0 baseline及30/50/70乘nose0/path_alpha。150s每case硬限、600s全輪硬限；STOP與owned PID/create/cmd、OS實驗鎖、來源/SHA初始化前後、原3檔不變、完整2100行CSV與result退出碼核對。原reviewed worker未驗parent流程，不能直接宣稱ready_to_execute。注意model輸出的243行原draft超出220行要求，不把長度合規當成功證據。

待即時用量>=35%後，讀tracking_analysis/CALIBRATION_PLAN.json。總只預留10分鐘，日研究預留4.917h<6h。runtime查核/不可达要回報unknown，不能restart舊已結束SAC。完整短校準也固定combat_score_eligible=False，通過後才設計單一控制改動及24場完整戰鬥配對。


## 10/12 已完成的真實執行

父層calibrate.py、adapter與原FDM已實際驗證，原7案例完整完成；calibrate80.py追加3案例亦完整完成。詳見calibration_draft_latest.json與各run的ANALYSIS.json。最初prepared/mock狀態已由這些實際報告更新。不要重跑7案例，也不要再次請OpenCode生成草稿；兩次模型嘗試已用盡。後續先讀research_latest.json與near_bank80的配對結果。
