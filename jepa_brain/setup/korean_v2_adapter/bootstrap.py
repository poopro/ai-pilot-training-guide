import os
import sys
from pathlib import Path

# Set before importing NumPy; a single low-priority process shares the PC.
for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[name] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REFERENCE = HERE / 'reference/jepa_brain'
sys.path.insert(0, str(REFERENCE))
sys.path.insert(0, str(HERE / 'reference/simulator'))
if os.name == 'nt':
    import ctypes
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    ctypes.windll.kernel32.SetPriorityClass(ctypes.c_void_p(ctypes.windll.kernel32.GetCurrentProcess()), 0x40)

# Lock this package to the snapshot before the historical repair controller
# inserts its original E: path into sys.path. Its source is otherwise unchanged.
import importlib
importlib.import_module('combat_v3.interface')
