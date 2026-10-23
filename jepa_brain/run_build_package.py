"""Worker-friendly wrapper (the job worker only runs scripts in this folder): runs portable/build_package.py."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parent / 'portable' / 'build_package.py'), run_name='__main__')
