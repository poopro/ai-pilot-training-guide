from pathlib import Path
import json
import subprocess
import sys
import uuid
from artifacts import ROOT,read_manifest

if __name__=='__main__':
    latest=json.loads((ROOT/'latest_train.json').read_text(encoding='utf-8'))
    read_manifest(Path(latest['bundle']),verify_replay=True)
    out=ROOT/'evaluations'/('model_'+uuid.uuid4().hex[:8])
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/'compare.py'),'--baseline','repair_guide',
        '--candidate',latest['bundle'],'--out',str(out)],check=True)
    print('完整比較：'+str(out/'report.json'))
