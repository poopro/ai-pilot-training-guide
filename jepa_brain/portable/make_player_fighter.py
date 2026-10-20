"""Derive tools/player_fighter.py from the OFFICIAL portable package's tools/player.py (read from the zip; nothing official is modified).
Only three things change: it imports fighter.build, takes --profile (default: network.json 'profile', else 'base_t3'), and builds that pilot
instead of RepairController.  Everything else (UDP loop, state machine, 60 Hz cap, duplicate handling) is the official code, byte for byte."""
import zipfile, difflib
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
z = zipfile.ZipFile(ROOT / 'ai-pilot-cpu-player-win64-20261016.zip')
base = 'ASUS_檢查工具/repair_guide_portable_20261012/'
src = z.read(base + 'tools/player.py').decode('utf-8')
new = src
def sub(old, rep):
    global new
    assert new.count(old) == 1, old
    new = new.replace(old, rep)
sub("from controller import RepairController", "from controller import RepairController;from fighter import build as build_pilot")
sub("ap.add_argument('--guide',action='store_true')", "ap.add_argument('--guide',action='store_true');ap.add_argument('--profile',default=None);ap.add_argument('--resume',action='store_true')")
sub("controller=RepairController(config);", "profile=a.profile or net.get('profile') or 'base_t3';controller=build_pilot(profile);")
sub("round_state=RoundState()", "round_state=RoundState();round_state.count=61 if a.resume else 0")
sub("print('原修正版引導器；無SAC。每回合前重啟Player。',flush=True)", "print('Profile:',profile,'(fighter.py；無SAC)。每回合前重啟Player。',flush=True)")
(HERE / 'player_fighter.py').write_text(new, encoding='utf-8')
compile(new, 'player_fighter.py', 'exec')
print(''.join(difflib.unified_diff(src.splitlines(True), new.splitlines(True), 'player.py', 'player_fighter.py', n=0)))
