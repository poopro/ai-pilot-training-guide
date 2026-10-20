"""Record frozen references without changing historical experiments."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent
ORIGINAL = Path('E:/ai_pilot/autopilot/combat_fix')
INITIAL_BUNDLE = ORIGINAL / 'training/run_20261006_192453_c95b/final_0000024000'

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(2**20), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    names = ('controller.py', 'env.py', 'train.py', 'artifacts.py', 'evaluate.py',
             'verify_saved.py', 'player.py', 'verify_udp.py', 'udp_config.json')
    sources = {}
    for name in names:
        original = sha(ORIGINAL / name)
        copied = sha(ROOT / 'repair_v1' / name)
        if original != copied:
            raise RuntimeError('Frozen copy mismatch: ' + name)
        sources[name] = copied
    manifest = json.loads((INITIAL_BUNDLE / 'manifest.json').read_text(encoding='utf-8'))
    hashes = {name: sha(INITIAL_BUNDLE / name) for name in ('model.zip', 'replay.pkl', 'manifest.json')}
    if hashes['model.zip'] != manifest['model_sha256'] or hashes['replay.pkl'] != manifest['replay_sha256']:
        raise RuntimeError('Initial bundle checksum mismatch')
    evidence = ORIGINAL / 'official_validation/host_20261006_204436_608d'
    value = {'captured_utc': datetime.now(timezone.utc).isoformat(),
             'baseline': 'frozen repair guide; not a measured tournament win rate',
             'frozen_repair_root': str(ROOT / 'repair_v1'), 'source_sha256': sources,
             'initial_training_bundle': str(INITIAL_BUNDLE), 'initial_bundle_sha256': hashes,
             'initial_decisions': manifest['decision_steps'],
             'registration': {'completed': False, 'solo_approved_by_organizer': True,
                              'evidence': 'User corrected on 2026-10-12: not registered; solo eligibility confirmed'},
             'host_evidence_dir': str(evidence),
             'host_evidence': 'one unchanged local published Host round; internal PID opponent',
             'competition_date_taipei': '2026-11-07',
             'research_freeze_taipei': '2026-11-03T23:59:00+08:00',
             'automation_ids': {'monitor': 'ai', 'daily_review': 'ai-2'}}
    target = ROOT / 'BASELINE.json'
    if target.exists():
        raise RuntimeError('Baseline already captured; preserve existing record')
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'baseline_captured': True, 'copied_sources': len(sources),
                      'bundle_decisions': manifest['decision_steps'], 'path': str(target)}))

if __name__ == '__main__':
    main()
