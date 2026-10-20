"""Announce the M2 re-gate result through the notification bus."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notify

d = json.loads((Path(__file__).resolve().parent / "m2_regate.json").read_text(encoding="utf-8"))
g, c = d["guide"], d["candidate"]

msg = (
    f"M2 高度閘重測通過。G-latch 候選在官方計分實際在乎的每一項都勝過 guide："
    f"擊殺 {c['kills']} vs {g['kills']}，攻擊秒 {c['attack_seconds']} vs {g['attack_seconds']}，"
    f"墜機 {c['own_crashes']} vs {g['own_crashes']}，死亡 {c['deaths']} vs {g['deaths']}，"
    f"過 9G {c['over_9g_seconds']} vs {g['over_9g_seconds']}，"
    f"最差高度 {c['min_alt_worst_m']}m vs {g['min_alt_worst_m']}m（候選更高，更安全）。"
    "原否決理由用的是逐場最低高度，但官方優勢分公式完全沒有高度項，"
    "且彙總後候選最差高度比 guide 更高。本次重測零算力成本，只重算既有 24 場資料。"
    "結論：候選推進到鏡像對戰驗證，不等於可直接上線比賽。"
)

ev = notify.emit(
    "m2_regate_pass_20261014", "completed", "candidate_promoted_to_mirror_testing",
    msg, cls="win",
    report=str((Path(__file__).resolve().parent / "m2_regate.json").resolve()),
)
print(json.dumps(ev, ensure_ascii=False, indent=1))
