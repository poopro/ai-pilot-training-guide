"""rollout_bfm eval with the pool3 opponent kinds (adv:<name>, sacx:<path>) available in every worker.

  python eval_pool3.py eval --arms base_t3 --opponents adv:f1_00,adv:f1_01 --n 24 --seed0 6000000 --workers 2 --out runs/val_adv
Arms are rollout_bfm arms; for tuned2 use --arms tuned2 (added here: ParamPilot + runs/tune02/best.json + shield v3).
"""
import json
import pool3  # noqa: F401  (patch must be active in spawned workers, which re-import this main module)
import rollout_bfm
from common import HERE

_make = rollout_bfm.make_arm


def make_arm(name):
    if name == 'tuned2':
        p = json.loads((HERE / 'runs' / 'tune02' / 'best.json').read_text(encoding='utf-8'))['params']
        return _make({'params': p})
    if isinstance(name, str) and name.startswith('tuned2w:'):
        import wide_pilot
        return wide_pilot.make_wide(float(name.split(':')[1]))
    return _make(name)


rollout_bfm.make_arm = make_arm

if __name__ == '__main__':
    import os
    if os.name == 'nt':   # ask Windows not to sleep while this evaluation runs (no setting is changed)
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
        except Exception:
            pass
    rollout_bfm.main()
