from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[1]
DLL_HANDLES=[os.add_dll_directory(str(ROOT/'runtime/Library/bin'))] if os.name=='nt' else []
