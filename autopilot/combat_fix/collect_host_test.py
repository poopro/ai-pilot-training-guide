"""Collect real published-Host logs; never substitute local score estimates."""
import csv
import json
import math
from pathlib import Path
import shutil
from artifacts import ROOT, atomic_json, file_hash


def collect():
    registry = ROOT / 'active_host_test.json'
    session = json.loads(registry.read_text(encoding='utf-8-sig'))
    folder = Path(session['folder'])
    candidates = []
    for directory in (Path(session['host_dir']), Path(session['runtime_dir'])):
        for path in directory.glob('*.csv'):
            stat = path.stat()
            previous = session['preexisting_csv'].get(str(path))
            if previous and previous['mtime_ns'] == stat.st_mtime_ns:
                continue
            if stat.st_mtime < session['start_clicked_epoch']:
                continue
            candidates.append(path)
    if len(candidates) != 1:
        raise RuntimeError(f'需要唯一的新回合 CSV，目前找到 {len(candidates)} 個')
    source = candidates[0]
    with source.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise RuntimeError('Host CSV 沒有資料列')
    times = [float(row['time']) for row in rows]
    finite = all(math.isfinite(float(value)) for row in rows for value in row.values())
    monotonic = all(b > a for a, b in zip(times, times[1:]))
    duration = times[-1]
    full_round = duration >= 299.9 and len(rows) >= 17900
    active = any(float(row['player1_state']) == 2 for row in rows)
    moved = any(abs(float(row['player1_lat_deg']) - float(rows[0]['player1_lat_deg'])) > 1e-7
                or abs(float(row['player1_lon_deg']) - float(rows[0]['player1_lon_deg'])) > 1e-7
                for row in rows)
    last = rows[-1]
    early_adjudication = (float(last['system_Final_whoiswinner']) != 0
                          and min(float(last['player1_Score_RemainingHP']),
                                  float(last['player2_Score_RemainingHP'])) <= 0)
    checks = dict(finite=finite, strictly_increasing_sim_time=monotonic,
                  full_round_or_host_early_adjudication=full_round or early_adjudication,
                  player1_state2=active, player1_moved=moved)
    players = {}
    for side in (1, 2):
        prefix = f'player{side}_'
        players[str(side)] = {
            'hp': float(last[prefix + 'Score_RemainingHP']),
            'score_kills': float(last[prefix + 'Score_Kills']),
            'advantage': float(last[prefix + 'Score_FinalAdvantage']),
            'attack_advantage': float(last[prefix + 'Score_AttackAdvantage']),
            'position_advantage': float(last[prefix + 'Score_PositionAdvantage']),
            'gforce_overload': float(last[prefix + 'Score_GForceOverload']),
            'min_altitude_m': min(float(r[prefix + 'alt_ft']) for r in rows) * .3048,
        }
    evidence = {'controller': session['controller'], 'model': session['model'],
                'source_csv': str(source), 'csv_sha256': file_hash(source),
                'rows': len(rows), 'sim_seconds': duration, 'checks': checks,
                'full_five_minute_round': full_round,
                'host_early_adjudication': early_adjudication,
                'players': players, 'host_winner_raw': last['system_Final_whoiswinner'],
                'host_timer_remaining_raw': last['system_time_remaining'],
                'published_host_round_completed': all(checks.values()),
                'competition_certification': False,
                'score_source': 'unchanged published Host CSV; no local estimate'}
    shutil.copy2(source, folder / source.name)
    acmis = []
    for path in (source.parent / 'output_acmi').glob('*'):
        if path.is_file() and path.stat().st_mtime >= session['start_clicked_epoch']:
            shutil.copy2(path, folder / path.name)
            acmis.append({'path': str(folder / path.name), 'sha256': file_hash(path)})
    evidence['acmi'] = acmis
    logs = Path(session['host_log_dir'])
    for name in ('host_stdout.log', 'host_stderr.log'):
        shutil.copy2(logs / name, folder / name)
    # The published Windows executable writes Traditional-Chinese CP950 bytes.
    host_text = (logs / 'host_stdout.log').read_bytes().decode('cp950', errors='replace')
    (folder / 'host_stdout_繁中.txt').write_text(host_text, encoding='utf-8')
    evidence['host_game_over_logged'] = '[GAME OVER]' in host_text
    atomic_json(folder / 'host_result.json', evidence)
    session['status'] = 'completed' if evidence['published_host_round_completed'] else 'incomplete'
    session['host_validation_completed'] = evidence['published_host_round_completed']
    session['result'] = str(folder / 'host_result.json')
    atomic_json(folder / 'session.json', session)
    atomic_json(registry, session)
    lines = ['# 官方公告版 Host 實測', '',
             '我方 Player1 使用 repair_guide 純引導器，沒有 RL。官方 Host、Setting.txt 與控制器均未修改。', '',
             f"CSV：{len(rows):,} 列；模擬時間 {duration:.3f} 秒。完整五分鐘：{full_round}；Host 提前裁決：{early_adjudication}。", '',
             '| Host 原始欄位 | 我方 Player1 | 內建 Player2 |',
             '| --- | ---: | ---: |']
    for key in ('hp', 'score_kills', 'advantage', 'attack_advantage',
                'position_advantage', 'gforce_overload', 'min_altitude_m'):
        lines.append(f"| {key} | {players['1'][key]:.6f} | {players['2'][key]:.6f} |")
    lines += ['', f"Host winner 原值：`{evidence['host_winner_raw']}`；保留原值，不擅自推定代碼。",
              '', '這是官方提供的本機公告版 Host 實測；不是正式賽事認證，也不是固定測試集勝率。',
              '', 'score_kills 保留 Host 原始欄位數字；不把分數 3 解讀為擊落三架飛機。',
              '', '核對項目：`' + json.dumps(checks, ensure_ascii=False) + '`。',
              '', '原始 CSV、ACMI、程式 SHA256、Player／Host log 與 session.json 均保存在同資料夾。']
    (folder / '官方Host結果.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return evidence


if __name__ == '__main__':
    collect()
