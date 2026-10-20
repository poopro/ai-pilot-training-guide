from pathlib import Path
import json
ROOT=Path(r'E:\ai_pilot\campaign_2026')
folder=ROOT/'delegations'/'20261012_195711_cb9b'
state=json.loads((folder/'state.json').read_text(encoding='utf-8'))
assert state['verified_model_effort_and_zero_cost'] and state['variant']=='max'
entry=json.loads((folder/'catalog_selection.json').read_text(encoding='utf-8'))
policy={'default_model':'opencode/space-bunny-free','effort_policy':'highest_supported',
    'selection':'live catalog, strict zero input/output/cache prices, explicit provider/model#variant',
    'unknown_price_or_variant_order':'reject_before_request',
    'models_without_variants':'report no adjustable effort, never claim max',
    'verified_default_selector':state['selector'],'verification':str(folder/'model_evidence.json'),
    'verified_metadata':state['verified_model_metadata'],
    'backup':str(ROOT/'opencode_task.before_highest_effort_20261012.py'),
    'user_cancelled_unclear_flagship_selection':True,
    'private_source_scope':'Existing explicit three-file consent to Space Bunny only; no broadened file upload.'}
(ROOT/'opencode_effort_policy.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2),encoding='utf-8')
with (ROOT/'OPENCODE.md').open('a',encoding='utf-8') as f:
    f.write('''\n\n## 10/12 最高推理強度規則\n
- 使用者要求無論模型都採最高強度；目前維持 Space Bunny，未指定清楚的其他旗艦選擇已取消。
- opencode_task.py 每次讀即時 `/api/model`，確認輸入、輸出、快取價格全為0，從可排序的支援 variants 選最高檔。Space Bunny 目前為 `opencode/space-bunny-free#max`；不手填其他模型未支援的 max。
- 根 `model` 在 OpenCode V2 不保留 variant，所以同時設定 CLI selector、plan/title agent selector 與模型 settings，small_model 也維持同一個模型。設定來源：https://opencode.ai/v2/docs/models/ 。
- 沒有可調 variants 時，明確記錄 no_adjustable_effort_advertised；未知價格或不明 variant 順序拒絕請求。沒有付費/降強度備援。
- 支援 `--model opencode/已查證免費模型ID`，仍強制最高支援檔位。此功能不擴大內部資料外傳授權；預設仍使用三檔已獲同意的 Space Bunny。
- 實際探測 delegations/20261012_195711_cb9b 已完成，session metadata 確認 space-bunny-free / variant=max / cost=0；六項價格、最高檔位及拒絕測試通過。確認依實際 session，不依模型回覆自述。
- 最高強度不代表建議正確，程式補丁仍需本地審查與模擬驗證。原啟動器保留為 opencode_task.before_highest_effort_20261012.py。
''')
with (ROOT/'REVIEW_LOG.md').open('a',encoding='utf-8') as f:
    f.write('\n\n## 2026-10-12 19:58 OpenCode 最高推理設定\n- 使用者要求每個模型一律最高支援推理強度。啟動器已加入即時免費價格與 variant 解析，Space Bunny 實際使用 max，session證據確認成本0。六項必要測試通過，原版已备份；未修改訓練來源，也未採用先前錯誤補丁。模糊的其他旗艦名稱使用者答覆 nvm，維持 Space Bunny。\n')
print(json.dumps({'selector':state['selector'],'verified_zero_cost':True,'policy':str(ROOT/'opencode_effort_policy.json')},ensure_ascii=False))
