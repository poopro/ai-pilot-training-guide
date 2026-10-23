"""Check the new competition package (2026-10-23): extract it to a fresh folder, run its own self-check with the
package's embedded Python (exactly what each 啟動_*.cmd does first), then the fake-Host UDP loopback for tuned2w:80 and tuned2."""
import subprocess, sys, zipfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
ZIP = HERE.parent / 'ai-pilot-fighter-player-win64-20261023.zip'
DST = HERE.parent / '_claude_stage' / 'pkg_20261023'
if not DST.exists():
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(DST)
PKG = DST / 'ASUS_檢查工具' / 'repair_guide_portable_20261012'
print('package dir', PKG, 'exists', PKG.exists(), flush=True)
r = subprocess.run([str(PKG / 'runtime' / 'python.exe'), '-I', '-S', '-B', '-X', 'utf8', str(PKG / 'tools' / 'self_check_fighter.py')],
                   cwd=str(PKG), capture_output=True, text=True, encoding='utf-8', errors='replace')
print('SELF_CHECK exit', r.returncode, flush=True)
print(r.stdout[-1500:], r.stderr[-1500:], flush=True)
r = subprocess.run([sys.executable, '-B', str(HERE / 'portable' / 'loopback_test.py'), str(PKG), 'tuned2w:80', 'tuned2'],
                   cwd=str(HERE), capture_output=True, text=True, encoding='utf-8', errors='replace')
print('LOOPBACK exit', r.returncode, flush=True)
print(r.stdout[-3000:], r.stderr[-1500:], flush=True)
