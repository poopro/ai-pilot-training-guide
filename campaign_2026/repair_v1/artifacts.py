"""Complete repair bundles, strict environment contracts, read-only old actors."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parent
LAB = Path('E:/ai_pilot/autopilot/opponent_lab')
BASE = Path(r'E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test')
FORMAT = 'combat_fix_sac_v1'
DECISION_REPEAT = 4
PHYSICS_HZ = 60
DECISION_HZ = PHYSICS_HZ / DECISION_REPEAT


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp_' + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)


def source_paths():
    paths = {f'repair/{name}': ROOT / name for name in ('controller.py', 'env.py')}
    paths['lab/duel_lab.py'] = LAB / 'duel_lab.py'
    paths.update({f'base/combat_v3/{name}': BASE / 'combat_v3' / name for name in
                  ('env.py', 'controller.py', 'interface.py', 'fdm.py', 'rules.py', 'config.json')})
    paths['base/envs/jsbsimEnv/jsbsimFdm.py'] = BASE / 'envs/jsbsimEnv/jsbsimFdm.py'
    return paths


def contract_sources():
    # Training/logging code is saved for audit, not locked for policy inference.
    return {name: file_hash(path) for name, path in source_paths().items()}


def contract_fingerprint(contract):
    return hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode('utf-8')).hexdigest()


def snapshot_sources(folder):
    folder = Path(folder)
    hashes = {}
    paths = source_paths()
    paths.update({f'repair/{name}': ROOT / name for name in ('train.py', 'artifacts.py', 'evaluate.py')})
    for name, source in paths.items():
        destination = folder / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        hashes[name] = file_hash(destination)
    return hashes


def read_manifest(bundle, *, verify_replay=False, verify_sources=True):
    bundle = Path(bundle)
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != FORMAT:
        raise ValueError('不是修復版 SAC 完整存檔')
    if manifest.get('complete') is not True:
        raise ValueError('存檔尚未完整完成')
    if contract_fingerprint(manifest['contract']) != manifest['environment_fingerprint']:
        raise ValueError('環境契約指紋不符')
    if manifest['source_sha256'] != manifest['contract']['source_sha256']:
        raise ValueError('環境來源 SHA 與契約不符')
    for key, expected in [('decision_repeat', DECISION_REPEAT), ('physics_hz', PHYSICS_HZ),
                          ('decision_hz', DECISION_HZ), ('observation_shape', [20]), ('action_shape', [4])]:
        if manifest.get(key) != expected:
            raise ValueError(f'修復版契約不相容：{key}')
    if file_hash(bundle / 'model.zip') != manifest['model_sha256']:
        raise ValueError('模型 SHA256 不符')
    if verify_replay and file_hash(bundle / 'replay.pkl') != manifest['replay_sha256']:
        raise ValueError('Replay SHA256 不符')
    if verify_sources:
        expected_sources = manifest['source_sha256']
        actual_sources = contract_sources()
        if set(expected_sources) != set(actual_sources):
            raise ValueError('環境來源契約缺漏')
        changed = [name for name in actual_sources if actual_sources[name] != expected_sources[name]]
        if changed:
            raise ValueError('環境與模型不相容：' + ', '.join(changed))
    return manifest


def load_policy(bundle, device='cpu'):
    """Load a strict new bundle, or an unchanged old bundle through its loader."""
    import torch
    torch.set_num_threads(1)
    bundle = Path(bundle)
    raw = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    if raw.get('format') == FORMAT:
        manifest = read_manifest(bundle)
        from stable_baselines3 import SAC
        model = SAC.load(str(bundle / 'model.zip'), device=device)
        if model.observation_space.shape != (20,) or model.action_space.shape != (4,):
            raise ValueError('模型本體的輸入／動作維度不符')
        model.combat_fix_manifest = manifest
        return model
    # The legacy loader checks frozen controller/interface/config and model SHA.
    # It never loads replay or changes the old bundle.
    sys.path.insert(0, str(LAB))
    from duel_lab import load_policy as load_legacy
    return load_legacy(bundle)


def save_bundle(model, folder, config, counters, label='checkpoint'):
    """Publish only after both files, source snapshots and manifest are saved."""
    folder = Path(folder)
    destination = folder / f'{label}_{model.num_timesteps:010d}'
    if destination.exists():
        raise ValueError(f'不覆蓋既有完整存檔：{destination}')
    if contract_sources() != config['contract']['source_sha256']:
        raise ValueError('訓練期間環境來源改變，拒絕發佈不一致存檔')
    staging = folder / ('.saving_' + uuid.uuid4().hex)
    staging.mkdir()
    model.save(str(staging / 'model.zip'))
    model.save_replay_buffer(str(staging / 'replay.pkl'))
    startup_snapshot = folder / 'source'
    if startup_snapshot.is_dir():
        shutil.copytree(startup_snapshot, staging / 'source')
        snapshot_hashes = {path.relative_to(staging / 'source').as_posix(): file_hash(path)
                           for path in (staging / 'source').rglob('*') if path.is_file()}
    else:
        snapshot_hashes = snapshot_sources(staging / 'source')
    if any(snapshot_hashes[name] != value for name, value in config['contract']['source_sha256'].items()):
        raise ValueError('來源快照與啟動時契約不符')
    manifest = {
        'format': FORMAT, 'complete': True, 'official_validation': False,
        'decision_repeat': DECISION_REPEAT, 'physics_hz': PHYSICS_HZ, 'decision_hz': DECISION_HZ,
        'observation_shape': list(model.observation_space.shape), 'action_shape': list(model.action_space.shape),
        'timesteps': int(model.num_timesteps), 'decision_steps': int(model.num_timesteps),
        'physics_ticks': int(counters['physics_ticks']), 'n_updates': int(model._n_updates),
        'actor_updates': max(0, int(model._n_updates) - int(model.critic_burnin_updates)),
        'critic_burnin_updates': int(model.critic_burnin_updates),
        'replay_size': int(model.replay_buffer.size()),
        'model_sha256': file_hash(staging / 'model.zip'), 'replay_sha256': file_hash(staging / 'replay.pkl'),
        'source_sha256': config['contract']['source_sha256'], 'snapshot_sha256': snapshot_hashes,
        'contract': config['contract'], 'environment_fingerprint': config['environment_fingerprint'],
        'config': json.loads(json.dumps(config)), 'counters': json.loads(json.dumps(counters)),
    }
    atomic_json(staging / 'manifest.json', manifest)
    staging.rename(destination)
    print('已完整儲存：' + str(destination), flush=True)
    return destination
