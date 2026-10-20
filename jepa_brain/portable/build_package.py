"""Build the 'fighter' overlay (and a full zip) on top of the OFFICIAL portable package. Nothing official is modified.
  python portable/build_package.py        (run python gen_portable.py and portable/make_player_fighter.py first)
Outputs:  portable/overlay/...   (copy its contents into the extracted repair_guide_portable_20261012 folder)
          ../ai-pilot-fighter-player-win64-20261018.zip   (= official zip + overlay, ready to extract and run)"""
import hashlib, json, zipfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = 'ASUS_檢查工具/repair_guide_portable_20261012/'
OFFICIAL = ROOT / 'ai-pilot-cpu-player-win64-20261016.zip'
OUT_ZIP = ROOT / 'ai-pilot-fighter-player-win64-20261018.zip'

SELF_CHECK = r'''"""Overlay self-check: (1) the official integrity/independence check, (2) overlay SHA256, (3) every profile builds and
produces finite, in-range commands on synthetic observations (including a head-on case that triggers the collision shield)."""
import sys, json, hashlib, runpy, math
from pathlib import Path
from bootstrap import ROOT, DLL_HANDLES
import numpy as np
runpy.run_path(str(ROOT / 'tools' / 'self_check.py'), run_name='__main__')      # raises AssertionError if the official bundle is damaged
man = json.loads((ROOT / 'fighter_manifest.json').read_text(encoding='utf-8'))
for rel, h in man['files_sha256'].items():
    assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == h, 'SHA mismatch: ' + rel
import fighter
LAT0, LON0, R_E, FT = 23.060552, 121.948555, 6378137.0, .3048
def ll(x, y): return LAT0 + math.degrees(x / R_E), LON0 + math.degrees(y / (R_E * math.cos(math.radians(LAT0))))
def obs(own, en):
    o = np.zeros(26)
    def vel(S): return np.array([S[3] * math.cos(S[4]), S[3] * math.sin(S[4]), 0.]) / FT
    o[0], o[1] = ll(own[0], own[1]); o[2] = own[2] / FT; o[4] = 3.; o[5] = math.degrees(own[4]) % 360
    o[6:9] = vel(own); o[12] = own[3] * .79 / FT; o[13] = o[15] = own[3] / FT; o[14] = 1.; o[18] = 3.
    o[20], o[21] = ll(en[0], en[1]); o[22] = en[2] / FT; o[23:26] = vel(en)
    return o
def stream(kind):
    own = [0., 0., 4500., 175., 0.]; en = {'abeam': [0., 1829., 4500., 175., math.pi], 'headon': [2200., 20., 4500., 175., math.pi]}[kind]
    for k in range(240):
        yield obs(own, en)
        for S in (own, en):
            S[0] += S[3] * math.cos(S[4]) / 60.; S[1] += S[3] * math.sin(S[4]) / 60.
profiles = ('base', 'base_t3', 'tuned', 'tuned2', 'tuned_open:9')
for prof in profiles:
    for kind in ('abeam', 'headon'):
        p = fighter.build(prof)
        for o in stream(kind):
            a, _ = p.act(o)
            assert np.isfinite(a).all() and a.shape == (4,) and (a >= np.array([-1., -1., -1., 0.]) - 1e-9).all() and (a <= 1 + 1e-9).all(), (prof, kind, a)
print('Fighter overlay self-check OK (official check + SHA + %d profiles).' % len(profiles))
'''

def launcher(profile, title, extra=''):
    return ('@echo off\r\nchcp 65001 >nul\r\ntitle %s\r\n'
            '"%%~dp0runtime\\python.exe" -I -S -B -X utf8 "%%~dp0tools\\self_check_fighter.py" --quiet\r\n'
            'if errorlevel 1 goto failed\r\n'
            '"%%~dp0runtime\\python.exe" -I -S -B -X utf8 "%%~dp0tools\\player_fighter.py" --network "%%~dp0network.json" --profile %s%s\r\n'
            ':failed\r\npause\r\n') % (title, profile, extra)

README = '''# Fighter 套件(官方可攜 Player + fighter.py)

以官方 repair_guide 可攜套件為底,新增啟動檔,**每一局開始前雙擊其中一個**(Player 每回合重新啟動,跟官方一樣):

| 啟動檔 | 設定 | 用途 |
|---|---|---|
| `啟動_tuned2.cmd` | 第二輪調參追擊 + 碰撞盾 v3 | **預設上場版本** |
| `啟動_tuned.cmd` | 第一輪調參追擊 + 碰撞盾 v3 | 次選(tuned2 出問題時) |
| `啟動_base_t3.cmd` | 原版 repair_guide 追擊 + 碰撞盾 v3 | 備用(對 lag 型對手 tuned2 / tuned 較弱時) |
| `啟動_tuned_open9.cmd` | tuned + 敵機在左側時開局先轉離 9 秒 | 僅在被 SAC 型尾追者壓制時的第二套設定 |
| `重連_tuned2_僅限回合進行中.cmd` / `重連_tuned_…` / `重連_base_t3_…` | 同上,但一啟動就送 state = 2 | **只有**回合進行中程式當掉、要重連時用;回合開始前不要用 |
| `啟動Player.cmd`(官方原檔) | 原版 repair_guide,無盾 | 最後保底 |

- 網路設定仍然是 `network.json`(官方原檔,未改動)。
- 每個啟動檔先跑 `tools/self_check_fighter.py`:官方完整性檢查 + 新增檔案 SHA256 + 所有設定的合成觀測冒煙測試;失敗就不會啟動 Player。
- 新增檔案只有:`policy/fighter.py`、`tools/player_fighter.py`、`tools/self_check_fighter.py`、`fighter_manifest.json`、各 .cmd、本說明。官方檔案一個位元都沒改。
- `player_fighter.py` 與官方 `player.py` 只差 6 處(匯入 fighter、新增 `--profile` 與 `--resume`、建立控制器、`--resume` 時直接送 state = 2、啟動訊息)。
- 本地研究結果(非 Host 認證,種子 1300000):對官方範例鏡像 tuned2 48-0、tuned 33-15、base_t3 20-28;對 lag 型 base_t3 44-4 最好、tuned2 39-9、tuned 38-10。上場前務必在官方 Host 實測至少一輪。
'''

def main():
    ov = HERE / 'overlay'
    files = {
        'policy/fighter.py': (HERE / 'fighter.py').read_bytes(),
        'tools/player_fighter.py': (HERE / 'player_fighter.py').read_bytes(),
        'tools/self_check_fighter.py': SELF_CHECK.encode('utf-8'),
        '啟動_tuned2.cmd': launcher('tuned2', 'Fighter - tuned2').encode('utf-8'),
        '啟動_tuned.cmd': launcher('tuned', 'Fighter - tuned').encode('utf-8'),
        '啟動_base_t3.cmd': launcher('base_t3', 'Fighter - base_t3').encode('utf-8'),
        '啟動_tuned_open9.cmd': launcher('tuned_open:9', 'Fighter - tuned_open9').encode('utf-8'),
        '重連_tuned2_僅限回合進行中.cmd': launcher('tuned2', 'Fighter - tuned2 RESUME (mid-round only)', ' --resume').encode('utf-8'),
        '重連_tuned_僅限回合進行中.cmd': launcher('tuned', 'Fighter - tuned RESUME (mid-round only)', ' --resume').encode('utf-8'),
        '重連_base_t3_僅限回合進行中.cmd': launcher('base_t3', 'Fighter - base_t3 RESUME (mid-round only)', ' --resume').encode('utf-8'),
        '先讀我_fighter.md': README.encode('utf-8'),
    }
    manifest = {'format': 'fighter_overlay_v1', 'base_package': OFFICIAL.name,
                'files_sha256': {k: hashlib.sha256(v).hexdigest() for k, v in files.items() if k.endswith('.py')}}
    files['fighter_manifest.json'] = json.dumps(manifest, indent=1, ensure_ascii=False).encode('utf-8')
    for rel, data in files.items():
        p = ov / BASE / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    print('overlay written:', len(files), 'files')
    with zipfile.ZipFile(OFFICIAL) as zin, zipfile.ZipFile(OUT_ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
        names = set()
        for info in zin.infolist():
            zout.writestr(info, zin.read(info.filename)); names.add(info.filename)
        for rel, data in files.items():
            assert BASE + rel not in names, rel
            zout.writestr(BASE + rel, data)
    print('zip written:', OUT_ZIP.name, OUT_ZIP.stat().st_size // 1024, 'KiB')

if __name__ == '__main__':
    main()
