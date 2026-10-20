"""Shared paths and frozen-module loaders for the jepa_brain package.

Works on Windows (E:\\ai_pilot) and on any mount of the same tree.
Nothing under campaign_2026 or the official folder is modified.
"""
import sys, json, importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_matches = sorted(ROOT.glob('2026 AI 飛行員*/*/*/AirCombat_Train_Test'))
if not _matches:
    raise RuntimeError('AirCombat_Train_Test folder not found under ' + str(ROOT))
BASE = _matches[0]
for _p in (str(BASE), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


repair = load_module('frozen_repair_controller', ROOT / 'campaign_2026' / 'repair_v1' / 'controller.py')
judge_mod = load_module('frozen_rules_judge', ROOT / 'campaign_2026' / 'experiments' / 'rules_v20261014' / 'judge.py')
SETTINGS = json.loads((BASE / 'combat_v3' / 'config.json').read_text(encoding='utf-8'))
# Research profile: 10/14 admin answers (1 deg cone, AGL 50 m, inclusive edges). Not Host-certified.
PROFILE = judge_mod.RuleProfile('line_20261014_1deg', 'AGL', 'right_bin')
