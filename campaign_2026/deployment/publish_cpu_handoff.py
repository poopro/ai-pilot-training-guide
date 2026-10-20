from pathlib import Path
import shutil, json, hashlib, zipfile, datetime, subprocess

root = Path(r'E:\ai_pilot\campaign_2026')
out = root/'deployment/github_cpu_release_20261016'
out.mkdir(exist_ok=True)
src = root/'deployment/ASUS_檢查工具'
stage = out/'ASUS_檢查工具'
stage.mkdir(exist_ok=True)
if not (stage/'repair_guide_portable_20261012/manifest.json').exists():
    shutil.copytree(src/'repair_guide_portable_20261012', stage/'repair_guide_portable_20261012')
for name in ('ASUS_先檢查.cmd', 'check_vivobook.py'):
    shutil.copy2(src/name, stage/name)
readme = '''# ASUS Vivobook：CPU Player 檢查包

適用 Windows 64 位元；不需要獨立顯示卡，也不用安裝 Python 或 Git。

## 在 ASUS 上做這五步

1. 登入你自己的 GitHub 帳號，打開本專案的 Releases 頁面。
2. 在 Assets 下載 `ai-pilot-cpu-player-win64-20261016.zip`。不要下載 Source code。
3. 對 ZIP 按右鍵 →「解壓縮全部」。請先解壓，不要在 ZIP 裡直接執行。
4. 開啟 `ASUS_檢查工具`，雙擊 `ASUS_先檢查.cmd`，等畫面顯示完成。
5. 把同資料夾新產生的 `vivobook_readiness.json` 上傳回原本的 Codex 聊天；失敗則傳 `vivobook_readiness_error.txt` 或畫面截圖。

若看到 GitHub 404，先確認已登入擁有此私人專案的帳號。
若 Windows 防護或防毒阻擋，先傳畫面，不需要關閉防毒。

## 這包包含什麼

包含目前保留的 repair_guide CPU Player、Python、NumPy、原套件自檢及 CPU 計時工具，授權檔案隨附。
先檢查只在本機運作，不啟動網路、比賽或訓練。CPU 合成計時通過仍不等於實際 60Hz 網路測試通過。
原套件內 README 為凍結時的歷史說明；之後已在主電腦完成六次可攜 Host 回合，但 ASUS 和跨電腦 LAN 仍待驗證。

## 接下來

取得 ASUS 報告後，再依兩台電腦的實際區域網路位址準備 LAN 設定。現在不必修改 network.json 或雙擊啟動 Player。
這份套件供第二台電腦執行 Player；官方 Host 留在主電腦。這不是完整訓練環境，也沒有新版候選 SAC 模型。
'''
(stage/'先讀我.md').write_text(readme, encoding='utf8')
pkg = stage/'repair_guide_portable_20261012'
manifest = json.loads((pkg/'manifest.json').read_text(encoding='utf8'))
for rel, sha in manifest['files_sha256'].items():
    assert hashlib.sha256((pkg/rel).read_bytes()).hexdigest() == sha, rel
assert len(manifest['files_sha256']) == 2115
for p in stage.rglob('*'):
    if p.is_file():
        assert p.name not in ('MAIN_PC_REFERENCE.json','vivobook_readiness.json','vivobook_readiness_error.txt')
        if p.suffix.lower() in ('.pkl','.acmi','.csv','.env','.log'):
            rel=p.relative_to(pkg).as_posix()
            assert rel.startswith('runtime/Lib/site-packages/numpy/') and '/tests/data/' in rel and rel in manifest['files_sha256'],rel
        if p.suffix.lower() in ('.py','.json','.cmd','.md') and p.stat().st_size < 1000000:
            txt=p.read_text(encoding='utf8',errors='replace')
            assert not any(x in txt for x in ('ghp_', 'github_pat_', '-----BEGIN PRIVATE KEY-----')), p
(stage/'HANDOFF_MANIFEST.json').write_text(json.dumps({'release':'20261016','checked_manifest_files':2115,'baseline_manifest_sha256':hashlib.sha256((pkg/'manifest.json').read_bytes()).hexdigest(),'ASUS_execution_verified':False,'LAN_verified':False,'main_PC_portable_Host_completed':6,'helper_sha256':{n:hashlib.sha256((stage/n).read_bytes()).hexdigest() for n in ('ASUS_先檢查.cmd','check_vivobook.py','先讀我.md')}},indent=2,ensure_ascii=False),encoding='utf8')
archive=out/'ai-pilot-cpu-player-win64-20261016.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in stage.rglob('*'):
        if p.is_file(): z.write(p,p.relative_to(out))
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
(out/'SHA256SUMS.txt').write_text(sha+'  '+archive.name+'\n',encoding='ascii')
repo=out/'repository'; repo.mkdir()
(repo/'README.md').write_text(readme,encoding='utf8')
(repo/'.gitignore').write_text('*.zip\nvivobook_readiness*\n',encoding='utf8')
test=out/'fresh_extraction'
with zipfile.ZipFile(archive) as z: z.extractall(test)
tool=test/'ASUS_檢查工具'
runtime=tool/'repair_guide_portable_20261012/runtime/python.exe'
r=subprocess.run([str(runtime),'-I','-S','-B','-X','utf8',str(tool/'check_vivobook.py')],capture_output=True,text=True,encoding='utf8',timeout=60)
result={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'archive':str(archive),'sha256':sha,'size':archive.stat().st_size,'checked_manifest_files':2115,'fresh_extract_probe_actual_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'ASUS_execution_verified':False,'LAN_verified':False,'repo':'poopro/ai-pilot-cpu-player','visibility':'private','usage_observation':{'primary_remaining_percent':92,'weekly_remaining_percent':56}}
(out/'LOCAL_RELEASE_VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
assert r.returncode==0,result
print(json.dumps(result,ensure_ascii=False))
