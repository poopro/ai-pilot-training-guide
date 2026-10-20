"""Stop the current lab learner, or evaluate its saved model against fixed opponents."""
import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent


def write_json(path, value):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def latest_bundle():
    state = ROOT / "latest_training.json"
    if state.exists():
        saved = json.loads(state.read_text(encoding="utf-8")).get("final_bundle")
        if saved and (Path(saved) / "manifest.json").exists():
            return Path(saved)
    choices = [p for p in (ROOT / "training").glob("run_*/*/manifest.json")
               if p.parent.name.startswith(("checkpoint_", "final_"))]
    if not choices:
        raise ValueError("尚未開始新的訓練，沒有可評估的新模型")
    return max(choices, key=lambda p: p.stat().st_mtime).parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["stop", "evaluate", "status", "results"])
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--rounds", type=int, default=3, help="每類對手、每個版本的場數")
    parser.add_argument("--seed", type=int, default=20267000)
    parser.add_argument("--max-minutes", type=float, default=10)
    parser.add_argument("--only-if-completed", action="store_true", help="自動入口：停止後不繼續跑評估")
    parser.add_argument("--no-publish", action="store_true", help="流程驗證：不替換使用者的最新評估入口")
    args = parser.parse_args()
    if args.rounds <= 0 or args.max_minutes <= 0:
        parser.error("rounds 和 max-minutes 須為正數")
    state_file = ROOT / "latest_training.json"
    if args.action == "results":
        result_pointer = ROOT / "latest_evaluation.json"
        if not result_pointer.exists():
            print("還沒有新的正式訓練評估；先訓練，再使用『評估新對手模型』。")
            return
        result = json.loads(result_pointer.read_text(encoding="utf-8"))
        markdown = Path(result["markdown"])
        if not markdown.is_file():
            raise ValueError("最新評估報告不存在；請查看最新評估 JSON 的路徑")
        print("評估狀態：" + result["status"])
        print("報告：" + str(markdown))
        os.startfile(str(markdown))
        return
    if args.action in ("stop", "status"):
        if not state_file.exists():
            print("尚未開始新的訓練。")
            return
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if args.action == "status":
            labels = {"initializing": "準備中", "training": "訓練中", "saving": "保存中", "saving_final": "收尾保存中",
                      "completed": "訓練已完成", "stopped_by_user": "已依要求保存並停止", "interrupted": "已中斷",
                      "time_limit": "已達時間上限", "failed": "失敗，請查看 result.json", "save_failed": "保存失敗，請保留錯誤訊息"}
            print("狀態：" + labels.get(state["status"], state["status"]))
            print(f"新環境累計步數：{state.get('timesteps', 0)}；更新次數：{state.get('updates', 0)}")
            print("本次資料夾：" + state["run_dir"])
            if state.get("final_bundle"):
                print("完整存檔：" + state["final_bundle"])
            if state["status"] in ("initializing", "training", "saving", "saving_final"):
                age = max(0, time.time() - state.get("heartbeat_epoch", 0))
                print(f"進度最後更新：{age:.0f} 秒前；本次目標：{state.get('target', '準備中')}")
                if age > 120:
                    print("進度較久未更新，請查看訓練視窗；這份舊狀態不能證明程序仍正常。")
            return
        if state["status"] not in ("initializing", "training", "saving", "saving_final"):
            print("目前訓練已結束；完整模型與結果保留。")
            return
        folder = Path(state["run_dir"]).resolve()
        if ROOT.resolve() not in folder.parents:
            raise ValueError("停止目標不在新對手實驗資料夾內")
        (folder / "STOP").write_text("stopped_by_user", encoding="utf-8")
        print("已要求保存並停止。請等訓練視窗印出『已完整儲存』再關閉。")
        return
    if args.only_if_completed:
        state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
        if state.get("status") != "completed":
            print("本次訓練已停止或尚未完成；跳過自動評估。存檔可稍後手動評估。")
            return
    bundle = args.bundle or latest_bundle()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest["format"] != "opponent_lab_sac_v1":
        raise ValueError("請評估新對手實驗存檔")
    config = manifest["config"]
    from duel_lab import DEFAULT_BUNDLE
    red_bundle = Path(config.get("red_bundle") or DEFAULT_BUNDLE)
    taipei = timezone(timedelta(hours=8))
    folder = ROOT / "evaluations" / ("eval_" + datetime.now(taipei).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:4])
    folder.mkdir(parents=True)
    verification_only = "verification_training" in bundle.parts
    report = {"status": "running", "seed_role": "development; not independent holdout",
              "verification_only": verification_only,
              "official_validation": False, "bundle": str(bundle), "red_bundle": str(red_bundle),
              "expected_cases": args.rounds * 4, "cases": [], "groups": []}
    deadline = time.monotonic() + args.max_minutes * 60
    child = None
    try:
        for index in range(args.rounds):
            for p2 in ["rule", "rl"]:
                for blue in ["guide", "rl"]:
                    if time.monotonic() >= deadline:
                        report["status"] = "time_limit"
                        raise TimeoutError("開發評估達時間上限；保存已完成場次")
                    name = f"{p2}_{blue}_{args.seed + index}"
                    output = folder / name
                    command = [sys.executable, "-X", "utf8", str(ROOT / "duel_lab.py"),
                               "--p2", p2, "--blue", blue, "--bundle", str(bundle),
                               "--red-bundle", str(red_bundle), "--seed", str(args.seed + index),
                               "--distance-ft", str([3000, 6000, 9000][index % 3]),
                               "--attack-angle", str(config["environment"]["attack_angle"]),
                               "--out", str(output)]
                    print(f"評估 {name}；藍方 {'純引導器基準' if blue == 'guide' else '新模型'}", flush=True)
                    with (folder / (name + ".log")).open("w", encoding="utf-8") as log:
                        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                        try:
                            code = child.wait(timeout=max(1, deadline - time.monotonic()))
                        except subprocess.TimeoutExpired:
                            child.terminate(); child.wait()
                            report["status"] = "time_limit"
                            raise TimeoutError("單場評估逾時；未完成場次不列入成績")
                    child = None
                    if code != 0:
                        raise RuntimeError(f"評估失敗：{name}，請查看 log")
                    data = json.loads((output / "report.json").read_text(encoding="utf-8"))
                    episode = data["episodes"][0]
                    if not episode["full_round_completed"]:
                        raise RuntimeError("短程驗證資料不能當完整評估")
                    report["cases"].append({"p2": p2, "blue": blue, **episode})
                    write_json(folder / "report.json", report)
        report["status"] = "completed"
    except KeyboardInterrupt:
        report["status"] = "interrupted"
        if child is not None:
            child.terminate(); child.wait()
    except Exception as error:
        if report["status"] != "time_limit":
            report["status"] = "failed"
        report["error"] = repr(error)
    finally:
        for p2 in ["rule", "rl"]:
            for blue in ["guide", "rl"]:
                cases = [c for c in report["cases"] if c["p2"] == p2 and c["blue"] == blue]
                if cases:
                    report["groups"].append({"p2": p2, "blue": blue, "episodes": len(cases),
                                             "kills": sum(c["final"]["is_kill"] for c in cases),
                                             "survivals": sum(c["final"]["survived"] for c in cases),
                                             "mean_attack_seconds": sum(c["final"]["attack_seconds"] for c in cases) / len(cases)})
        write_json(folder / "report.json", report)
        lines = ["# 新對手開發評估", "", f"狀態：{report['status']}。這是本地開發評估，不是官方驗證或獨立保留測試。", "",
                 f"完整場次：{len(report['cases'])}/{report['expected_cases']}。", "",
                 "| P2 | 藍方 | 場數 | 擊落 | 存活 | 平均攻擊秒數 |", "| --- | --- | --- | --- | --- | --- |"]
        if verification_only:
            lines.insert(2, "僅驗證流程：使用短程測試模型，不能用這份結果判斷正式訓練成效。")
        for group in report["groups"]:
            lines.append(f"| {group['p2']} | {group['blue']} | {group['episodes']} | {group['kills']} | {group['survivals']} | {group['mean_attack_seconds']:.3f} |")
        if report.get("error"):
            lines.extend(["", "未完成原因：" + report["error"]])
        lines.extend(["", "少量場次只用來篩選；需更多新種子測試才能決定是否替換部署版本。"])
        for case in report["cases"]:
            path = Path(case["acmi"]).as_posix()
            lines.extend(["", f"- [{case['p2']} / {case['blue']} / {case['seed']} 回放](<{path}>)"])
        (folder / "結果.md").write_text("\n".join(lines), encoding="utf-8")
        if not args.no_publish:
            write_json(ROOT / "latest_evaluation.json", {"status": report["status"], "report": str(folder / "report.json"), "markdown": str(folder / "結果.md")})
        print("評估結果：" + str(folder / "結果.md"), flush=True)
    if report["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
