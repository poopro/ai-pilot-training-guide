# 凍結學習對手六場比較 v2

唯一修復是執行與驗證分工：v1首場已保存18000步，但重做整段60Hz控制器重播時超過原90秒，worker真1、guardian真2，原600秒與兩seed保留、不重新分類成功。v2用新seed2026310200/201與新輸出；實際控制、物理、每幀sendAction核對路徑和原v1逐字一致，6項離線測試通過。

每場仍18000步／90秒，整批仍600秒。藍方零戰術StationController／old5000／transfer10000，紅方固定sac5000；兩開局三者同完整initialSHA。零戰術不是pure repair_guide。左右使用不同新seed，不能把左右差異做單因素歸因。

每60Hz實際送出命令仍需等於唯一controller.act輸出，act/send/physics/judge各一次，合法packet與自身counter/clock/guard仍逐幀核對；模型只在3Hz決策，獨立verifier重新計算每一次藍紅模型輸出與持續動作、全分數事件、安全與common-exposure高度。原1200步真FDM已有完整controller重播證據，不重跑。

worker先保存PHYSICS_COMPLETE.json，再核對固定來源／模型。完成六場且guardian真0後，在原600秒期限內用`verify.py --guarded RUN 0`，子verifier最多60秒、實際wait退出保存。僅完整六場／真exit0／source紅方model與initialSHA公平／CSV與JSONL及ACMI／逐幀score事件／所有實際3Hz模型決策獨立重算通過才verified_comparison=true。不新增訓練、不自動部署，不把兩開局當穩定勝率。
