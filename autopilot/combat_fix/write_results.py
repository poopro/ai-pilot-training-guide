"""Publish verified complete evaluations, never rolling training success claims."""
from pathlib import Path
import json
from artifacts import ROOT,atomic_json,contract_sources,file_hash
from score_estimates import estimates

def main():
    paired=json.loads((ROOT/'evaluations/paired_guide_vs_night/report.json').read_text(encoding='utf-8'))
    guide=json.loads((ROOT/'evaluations/guide_new20/report.json').read_text(encoding='utf-8'))
    candidate=json.loads((ROOT/'evaluations/model_vs_guide/report.json').read_text(encoding='utf-8'))
    latest=json.loads((ROOT/'latest_train.json').read_text(encoding='utf-8'))
    trained=json.loads((Path(latest['run_dir'])/'result.json').read_text(encoding='utf-8'))
    verified=json.loads((ROOT/'validation/final_reload.json').read_text(encoding='utf-8'))
    udp=json.loads((ROOT/'validation/repair_udp_retry/report.json').read_text(encoding='utf-8'))
    model_udp=json.loads((ROOT/'validation/repair_model_udp/report.json').read_text(encoding='utf-8'))
    tests=json.loads((ROOT/'diagnostics/test_repair_report.json').read_text(encoding='utf-8'))
    host=None
    host_session_path=ROOT/'active_host_test.json'
    if host_session_path.exists():
        hs=json.loads(host_session_path.read_text(encoding='utf-8-sig'))
        if hs.get('status')=='completed' and hs.get('result'):
            candidate_host=json.loads(Path(hs['result']).read_text(encoding='utf-8'))
            saved_csv=Path(hs['folder'])/Path(candidate_host['source_csv']).name
            if (candidate_host.get('published_host_round_completed')
                    and candidate_host.get('host_game_over_logged')
                    and hs['source_sha256']==contract_sources()
                    and file_hash(saved_csv)==candidate_host['csv_sha256']):
                host=candidate_host
    for r in (paired,guide,candidate):
        if r['status']!='completed' or len(r['cases'])!=r['expected_cases'] or not all(x['full_round_completed'] for x in r['cases']):
            raise ValueError('Incomplete evaluation; refused final success report')
    if not verified['passed'] or not udp['passed'] or not model_udp['passed'] or tests['status']!='passed':raise ValueError('Verification failed')
    if guide['source_sha256']!=contract_sources():raise ValueError('Evaluation source no longer matches')
    for r in (paired,guide,candidate):
        for case in r['cases']:
            case['score_estimates']=estimates(case['final'],case['steps'])
    atomic_json(ROOT/'results.json',{'paired_before_after':paired,'guide_new20':guide,'short_training':trained,
        'model_vs_guide':candidate,'reload':verified,'udp':udp,'model_udp':model_udp,
        'official_validation':host is not None,
        'official_validation_scope':'unchanged published Host; one repair_guide round' if host else 'none',
        'competition_certification':False,'published_host_result':host,
        'local_default':'repair_guide',
        'official_default':('original unchanged; repair entry passed one published Host round' if host else
                            'original unchanged; repair entry available for manual validation')})
    lines=['# AI空戰修正結果','',
        ('修正版純引導器已完成一場官方公告版 Host 實測，Host 裁決 Player1 勝；正式賽事認證與其他對手表現仍未驗證。' if host else
         '已修正飛控、瞄準及訓練流程，並接上可直接使用的入口。修正版是改善中的本地候選，尚未完成官方 Host 驗證。'),'',
        '## 原因與修正','',
        '舊引導器在大坡度轉彎時高度補償不足，俯仰阻尼也使用了 body q；飛機反覆降低高度，SAC 小修正量無法補救。新版改為 Euler 俯仰速率、完整轉彎升力補償、有上限的積分控制，以及近距離視線速度前饋。','',
        '新訓練提供連續瞄準獎勵、由易到難的課程、新 critic 暖身、完整保存與停止入口。舊模型、舊 replay 和原官方部署保留。','',
        '## 同開局比較：原兩百萬步模型 vs 修正版純引導器','',
        '| 控制器／對手 | 完整場數 | 擊落 | 存活 | 平均攻擊秒數 | 最低高度m |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for key,s in paired['summary'].items():
        name=key.replace('baseline','舊2M模型').replace('candidate','修正版純引導器')
        lines.append(f'| {name} | {s["n"]} | {s["kills"]} | {s["survived"]} | {s["mean_attack_seconds"]:.3f} | {s["minimum_altitude_m"]:.0f} |')
    lines+=['','## 修正版純引導器：另外20場完整測試','',
        '使用另一組固定種子，評分後沒有調整控制器。每個對手10場，距離輪替3000／6000／9000呎。','',
        '| 對手 | 完整場數 | 擊落 | 存活 | 墜機 | 平均攻擊秒數 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for key,s in guide['summary'].items():lines.append(f'| {key} | {s["n"]} | {s["kills"]} | {s["survived"]} | {s["crashes"]} | {s["mean_attack_seconds"]:.3f} |')
    lines+=['','這是有限樣本的本地測試；凍結SAC對手不等於強對手，更不能代表參賽選手。Timeout不算擊落成功。','',
        '## 已實際完成短程訓練與保存','',
        f'新增 {trained["decision_steps"]:,} 次15Hz策略決策、{trained["physics_ticks"]:,} 個60Hz模擬tick；critic更新 {trained["critic_updates"]:,} 次，actor更新 {trained["actor_updates"]:,} 次。結束狀態：{trained["status"]}。',
        f'完整存檔：[model、replay、manifest](<{Path(trained["final_bundle"]).as_posix()}>)。SHA校驗、實際重新載入、replay抽樣及動作有限值檢查通過。','',
        '這是新設定的小規模試跑，沒有把舊兩百萬步重標成新訓練成果。模型仍須與純引導器比較：','',
        '| 控制器／對手 | 完整場數 | 擊落 | 存活 | 平均攻擊秒數 |',
        '| --- | ---: | ---: | ---: | ---: |']
    for key,s in candidate['summary'].items():
        name=key.replace('baseline','修正版純引導器').replace('candidate','短程SAC模型')
        lines.append(f'| {name} | {s["n"]} | {s["kills"]} | {s["survived"]} | {s["mean_attack_seconds"]:.3f} |')
    lines+=['','目前觀看／新版Host入口預設純引導器；最新訓練模型只登錄為候選，沒有自動替換部署。先解決對凍結SAC對手的持續追蹤，再增加訓練預算；不要只因保存完成或loss下降就宣稱模型更強。','',
        '## 規則與官方驗證','',
        '資料輸入仍是官方20+6項；四個飛控量合法，控制器60Hz。完整評估回合五分鐘。公告攻擊門檻2°，本輪採較嚴的1°診斷，500–3000呎、累積180tick才判定擊落，沒有放寬門檻。','',
        f'新版純引導器實際UDP loopback通過，p99={udp["network_latency_p99_ms"]:.3f}ms。這只能證明本機協議和處理延遲，不能證明官方Host實戰通過。','',
        f'新訓練模型同樣通過UDP loopback，p99={model_udp["network_latency_p99_ms"]:.3f}ms；模型推理每四個有效tick一次，底層飛控仍60Hz。','',
        '表四原圖已核對，公尺單位與1.2因子正確；攻擊距離用呎是另一項規則。位置分平均／18000與舊累加值已分開記錄。Host公式、邊界、碰撞判定仍未驗證，不能用舊位置估計宣稱勝負。','',
        '原始info的estimated_winner／local_win／failure_reason沿用舊累加分估計，不能當作正式勝率。這份報告以is_kill、survived、own_crash及outcome判定；timeout即未完成擊落，不因failure_reason為none就算成功。','',
        '## 現在怎麼做','',
        '先雙擊 [觀看修正版對戰.cmd](<E:/ai_pilot/autopilot/combat_fix/觀看修正版對戰.cmd>)，藍色是你、紅色是對手；會先模擬再開Tacview回放。',
        '之後依 [修正版入口](<E:/ai_pilot/修正版入口.md>) 操作開始、停止保存、評估或接續訓練。詳細限制在 [使用說明](<E:/ai_pilot/autopilot/combat_fix/使用說明.md>)。','',
        '[20場逐場報告與ACMI](<E:/ai_pilot/autopilot/combat_fix/evaluations/guide_new20/report.json>)；[新模型公平比較](<E:/ai_pilot/autopilot/combat_fix/evaluations/model_vs_guide/report.json>)；[完整核對資料](<E:/ai_pilot/autopilot/combat_fix/results.json>)。']
    if host:
        p1,p2=host['players']['1'],host['players']['2']
        host_lines=['## 官方公告版 Host：已實測一場','',
            f"使用 repair_guide，不帶 RL。原始 Host 與設定未修改；{host['rows']:,} 列、{host['sim_seconds']:.2f} 模擬秒後 Host 自動提前裁決。沒有硬跑到五分鐘或改裁判。",'',
            '| Host 原始欄位 | 我方 Player1 | 內建 Player2 |',
            '| --- | ---: | ---: |']
        for key in ('hp','score_kills','advantage'):
            host_lines.append(f'| {key} | {p1[key]:.3f} | {p2[key]:.3f} |')
        host_lines+=['',"Host CSV winner=1，stdout 的 [GAME OVER] 同樣宣告 Player1。score_kills=3 是原始欄位，不說成擊落三架。",
            f"我方最低高度 {p1['min_altitude_m']:.0f} 公尺，GForceOverload={p1['gforce_overload']:.0f}。",'',
            f"[Host 原始結果、CSV、ACMI與診斷](<{(Path(hs['folder'])/'官方Host結果.md').as_posix()}>)。",'',
            '第一次啟動時工作目錄落在 Codex 安裝目錄，START 後通訊停止；第二次改從官方資料夾啟動後正常完成。新增「啟動官方Host.cmd」固定工作目錄並保存 log。', '',
            '這證明本機公告版 Host 接線與這一場實戰可用；不代表強對手勝率、全部規則邊界測試或正式比賽認證。24k SAC 沒有替換純引導器，原全域部署入口仍保留。','']
        lines[4:4]=host_lines
    content='\n'.join(lines)+'\n'
    (ROOT/'修正結果.md').write_text(content,encoding='utf-8')
    (ROOT.parent/'最新結果.md').write_text(content,encoding='utf-8')
    print(str(ROOT.parent/'最新結果.md'))

if __name__=='__main__':main()
