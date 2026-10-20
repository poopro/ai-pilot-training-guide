"""Load the unchanged official FDM wrapper without its training-only package initializer."""
import importlib.util
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[1]/'envs/jsbsimEnv/jsbsimFdm.py'
_spec=importlib.util.spec_from_file_location('_official_fdm_v3',SOURCE)
_module=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
JsbsimFdm=_module.JsbsimFdm
