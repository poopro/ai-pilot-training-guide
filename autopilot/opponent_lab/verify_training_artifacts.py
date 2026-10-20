"""Read-only evidence audit for transfer/resume/archive changes."""
import hashlib
import json
from pathlib import Path
import py_compile
import re

import numpy as np
from stable_baselines3 import SAC
from duel_lab import BASE, DEFAULT_BUNDLE, file_hash, load_policy

ROOT = Path(__file__).resolve().parent
ARCHIVE = Path('E:/ai_pilot/_archive/cleanup_20261006')


def audit():
    archive = json.loads((ARCHIVE / 'manifest.json').read_text(encoding='utf-8-sig'))
    assert len(archive['items']) == 20
    for item in archive['items']:
        assert Path(item['destination']).exists(), item['destination']
        assert not Path(item['source']).exists(), item['source']
    for name in ['duel_lab.py', 'train_opponents.py', 'training_control.py', 'test_opponents.py']:
        py_compile.compile(str(ROOT / name), doraise=True)
    old = json.loads((DEFAULT_BUNDLE / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in old['config']['source_sha256'].items():
        assert file_hash(BASE / 'combat_v3' / name) == expected, name
    for name, expected in old['config']['dependency_sha256'].items():
        assert file_hash(BASE / name) == expected, name
    bundles = [DEFAULT_BUNDLE,
               ROOT / 'verification_training/actor_transfer_current/final_0000000256',
               ROOT / 'verification_training/resume_current/final_0000000384',
               ROOT / 'verification_training/save_stop/final_0000000001']
    checked = []
    for bundle in bundles:
        manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
        for label, extension in [('model', 'zip'), ('replay', 'pkl')]:
            assert file_hash(bundle / (label + '.' + extension)) == manifest[label + '_sha256']
        model = SAC.load(str(bundle / 'model.zip'), device='cpu')
        model.load_replay_buffer(str(bundle / 'replay.pkl'))
        assert model.num_timesteps == manifest['timesteps']
        assert model._n_updates == manifest['n_updates']
        assert model.replay_buffer.size() == manifest['replay_size']
        checked.append({'bundle': str(bundle), 'timesteps': model.num_timesteps,
                        'updates': model._n_updates, 'replay_size': model.replay_buffer.size(),
                        'actor_optimizer_states': len(model.actor.optimizer.state),
                        'critic_optimizer_states': len(model.critic.optimizer.state),
                        'model_hash_ok': True, 'replay_hash_ok': True, 'reload_ok': True})
        if bundle != DEFAULT_BUNDLE:
            cfg = manifest['config']
            assert cfg['environment']['sources']['trainer'] == file_hash(ROOT / 'train_opponents.py')
            assert cfg['environment']['sources']['lab'] == file_hash(ROOT / 'duel_lab.py')
            checks = cfg.get('transfer_checks')
            if checks:
                assert all(checks[name] for name in ['actor_weights_exactly_copied', 'new_replay_empty',
                           'new_actor_optimizer_empty', 'new_critic_optimizer_empty', 'new_update_count_zero'])
        del model
    assert checked[1]['timesteps'] == 256 and checked[2]['timesteps'] == 384
    assert checked[1]['updates'] == 27 and checked[2]['updates'] == 42
    assert checked[2]['actor_optimizer_states'] > 0 and checked[2]['critic_optimizer_states'] > 0
    stop = json.loads((ROOT / 'verification_training/save_stop/result.json').read_text(encoding='utf-8'))
    assert stop['status'] == 'stopped_by_user'
    assert not (ROOT / 'verification_training/should_not_exist').exists()
    separation = json.loads((ROOT / 'verification_training/separate_blue_red/report.json').read_text(encoding='utf-8'))
    assert not separation['episodes'][0]['full_round_completed']
    evaluation = ROOT / 'evaluations/eval_20261006_003722_fee5/report.json'
    development = json.loads(evaluation.read_text(encoding='utf-8'))
    assert development['status'] == 'completed' and len(development['cases']) == 4
    assert development['verification_only'] and not development['official_validation']
    for case in development['cases']:
        assert case['full_round_completed'] and Path(case['acmi']).exists()
    assert not (ROOT / 'latest_training.json').exists()
    assert not (ROOT / 'latest_evaluation.json').exists()
    ap = ROOT.parent
    for name in ['沿用舊策略_訓練新對手.cmd', '接續新對手訓練.cmd', '停止新對手訓練並保存.cmd',
                 '評估新對手模型.cmd', '查看目前訓練進度.cmd', '查看新對手評估結果.cmd']:
        launcher = (ap / name).read_text(encoding='utf-8')
        assert launcher.startswith('@echo off')
        assert 'C:\\Users\\USER\\anaconda3\\envs\\F16_ai\\python.exe' in launcher
        target = 'train_opponents.py' if name in ['沿用舊策略_訓練新對手.cmd', '接續新對手訓練.cmd'] else 'training_control.py'
        assert target in launcher and (ROOT / target).exists()
    for name in ['啟動入口.md', '現在要做什麼.md', '操作說明.md']:
        document = (ap / name).read_text(encoding='utf-8')
        for link in re.findall(r'\]\(<([A-Za-z]:/[^>]+)>\)', document):
            assert Path(link).exists(), link
    output = {'verification_only': True, 'main_training_started': False, 'official_validation': False,
              'archive_items': 20, 'v3_and_original_dependencies_unchanged': True, 'bundles': checked,
              'transfer_cuda_steps': 256, 'resume_cuda_steps': 384,
              'stop_save_passed': True, 'incompatible_resume_rejected_before_output': True,
              'full_evaluation_flow_cases': 4, 'full_evaluation_flow_report': str(evaluation),
              'published_user_training_or_evaluation_pointer': False,
              'onedrive_entry_updated': False,
              'onedrive_limitation': 'Existing file denied write; original content remains. Use E:/ai_pilot/autopilot/啟動入口.md'}
    (ROOT / 'verification_training/驗證結果.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    audit()
