"""Read-only human campaign status. Does not launch or stop any process."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import math
import psutil

ROOT = Path(__file__).resolve().parent
TAIPEI = timezone(timedelta(hours=8))


def read(path, optional=False):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("JSON 根節點不是物件")
        return value
    except FileNotFoundError:
        if not optional:
            print(f"無法驗證：找不到 {path}")
    except (OSError, ValueError) as exc:
        print(f"無法驗證：{path}：{exc}")
    return None


def identity(record):
    if not record:
        return "未記錄程序身分"
    try:
        pid = record["pid"]
        expected = record["creation_epoch"]
        command = record["cmdline"]
        if type(pid) is not int or not isinstance(command, list) or not command:
            return "身分資料不完整；無法驗證"
        proc = psutil.Process(pid)
        creation, actual_command = proc.create_time(), proc.cmdline()
        if abs(creation - expected) < 1 and actual_command == command:
            return f"PID {pid}、建立時間、命令均吻合，仍在運行"
        return f"PID {pid} 已被不同程序使用；原身分不吻合"
    except psutil.NoSuchProcess:
        return "原記錄的 PID 已不存在"
    except psutil.AccessDenied:
        return "權限不足；無法驗證程序是否仍在運行"
    except (KeyError, TypeError, ValueError, OSError) as exc:
        return f"無法驗證程序：{exc}"


def completed_comparison(pointer, comparison):
    if not comparison or pointer.get("status") != "completed":
        return False
    n = comparison.get("eligible_cases")
    pairs = comparison.get("matched_pairs")
    try:
        totals = comparison["totals"]
        counts = [totals[k]["completed_cases"] for k in ("guide", "candidate")]
        exits = [pointer.get("actual_parent_exit_code"), comparison.get("actual_parent_exit_code")]
        return (comparison.get("verified_comparison") is True
                and all(type(e) is int and e == 0 for e in exits)
                and type(n) is int and n > 0 and type(pairs) is int
                and pairs * 2 == n == pointer.get("planned_cases")
                and all(type(c) is int and c == pairs for c in counts))
    except (KeyError, TypeError):
        return False


def main():
    now = datetime.now(TAIPEI)
    print(f"AI 飛行員競賽進度｜{now:%Y/%m/%d %H:%M:%S}（台灣時間）")
    research = read(ROOT / "research_latest.json") or {}
    training = read(ROOT / "pipeline_latest.json") or {}
    print("\n【最新研究】")
    print(f"實驗：{research.get('experiment', '無法驗證')}；記錄狀態：{research.get('status', '無法驗證')}")
    print("程序核對：" + identity(research.get("supervisor")))
    comparison = read(research["comparison"]) if research.get("comparison") else None
    if completed_comparison(research, comparison):
        print(f"完成報告：{comparison['eligible_cases']} 場／{comparison['matched_pairs']} 個配對；記錄的實際退出碼為 0。")
        for key, title in (("guide", "原引導器"), ("candidate", "候選")):
            total = comparison["totals"][key]
            print(f"{title}：{total.get('kills', '?')} 擊落、攻擊 {total.get('attack_seconds', '?')} 秒、墜機 {total.get('own_crashes', '?')}。")
        print("以上為開發集比較，不能視為正式競賽勝率。")
        print("比較閘門：" + str(comparison.get("gate", "無法驗證")))
    else:
        print("尚未核對到完整配對比較與實際退出碼；暫不顯示已驗證成績。")
    print("正式部署：" + str(research.get("retained_deployment", "無法驗證")))
    print("完整結果：" + str(ROOT / "latest_result.md"))
    print("\n【先前 SAC 訓練】")
    state = "已因改善不足停止追加，並保存" if training.get("status") == "futility_stop" else training.get("status", "無法驗證")
    print(f"{state}；新增決策 {training.get('new_decisions', '?'):,}／原上限 {training.get('decision_budget', '?'):,}。" if type(training.get('new_decisions')) is int and type(training.get('decision_budget')) is int else str(state))
    print("程序核對：" + identity(training.get("supervisor")))
    if training.get("child"):
        print("子程序核對：" + identity(training["child"]))
    print("\n【今日運算與下一次驗證】")
    ledger_path = ROOT / "compute_budgets" / f"{now:%Y-%m-%d}.json"
    ledger = read(ledger_path, optional=True)
    if ledger is None:
        print("今日預算檔尚未建立或無法讀取；啟動器仍需核對並登記預留。")
    else:
        hours, limit = ledger.get("reserved_hours"), ledger.get("daily_limit_hours")
        if all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in (hours, limit)):
            print(f"今日已預留 {hours:.3f}／{limit:g} 小時（失敗或換 run 不退回）。")
        else:
            print("今日預算資料不完整；無法驗證。")
    schedule = read(ROOT / "schedule_latest.json") or {}
    if schedule.get("new_taipei"):
        print("最近保存的驗證時段：" + str(schedule["new_taipei"]) + "（台灣時間）。")
        print("這是保存的排程，不代表已執行；請以最新研究狀態與實際程序為準。")
    print("執行前需重新核對即時額度、預算、来源與程序；本頁只讀取資料。")
    print("停止要求：" + ("根目錄 STOP 存在" if (ROOT / "STOP").exists() else "根目錄未見 STOP"))


if __name__ == "__main__":
    main()
