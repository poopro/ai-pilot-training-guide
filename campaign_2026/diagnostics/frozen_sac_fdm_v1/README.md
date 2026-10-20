# 凍結SAC紅方真FDM短測

`probe.py`是獨立guardian兼launcher，持有campaign OS lock並監督唯一worker。原硬限240秒，STOP／精確PID建立時間命令exe父子／資源／模型及XML來源閘門。新seed先登記、預留不退。此一次批次已完成，禁止重跑來湊數。

結果：`run_20261017_063110_af2e25/VERIFICATION.json`，verified_FDM_packet_timing=true，errors=[]。父程序實際退出0由工具session 74217／eb2570觀察；worker0；verifier0由工具d708f9觀察。不是新訓練、完整聯賽或勝率證據。

兩模型各2次重設，每次300步，共1200真60Hz步。紅方指令在完成n步後以OWN20+ENEMY6計算，接下來只send／physics一次；tick0不累積，0/20/...3Hz決策。末態300另外產生一個未送出的pending command，用來核對最後完成步計數，不能把301次command當301次physics。

完整JSONL保存前／後packet、實際命令、逐幀計數與sim time；ACMI每次reset分檔，避免時間倒退。同種子初始／終態／命令及遙測SHA精確相符；另用新模型／控制器物件重播已保存packet，實際command精確相符。

限制：四段都沒有命中，不代表已測通非零attack累積；兩model使用不同新seed，不能從這批推論哪個較強。冷首推論36.53ms，暖推論此批最大約2.26ms；離線FDM不等於網路硬實時延遲保證。正式repair_guide與所有來源模型未變。
