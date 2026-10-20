"""Local CPU-only readiness probe. No sockets, FDM, GPU or training."""
from pathlib import Path
import json, platform, struct, subprocess, sys, time, statistics, traceback

HERE = Path(__file__).resolve().parent
PACKAGE = HERE / 'repair_guide_portable_20261012'

def main():
    package = PACKAGE if PACKAGE.exists() else HERE.parent / 'repair_guide_portable_20261012'
    report = {'scope': 'local self-check and synthetic CPU timing only; not LAN or combat validation',
              'tested_computer': platform.node(), 'processor': platform.processor(),
              'windows': platform.platform(), 'machine': platform.machine(),
              'python_bits': struct.calcsize('P') * 8, 'gpu_required': False,
              'new_FDM_ticks': 0, 'network_started': False}
    if sys.platform != 'win32' or report['python_bits'] != 64:
        raise RuntimeError('需要64位元Windows套件執行環境')
    command = [str(package / 'runtime/python.exe'), '-I', '-S', '-B', '-X', 'utf8', str(package / 'tools/self_check.py')]
    check = subprocess.run(command, capture_output=True, text=True, encoding='utf8', timeout=45)
    report['self_check_actual_exit'] = check.returncode
    if check.returncode != 0:
        report['self_check_error'] = check.stderr[-4000:]
        raise RuntimeError('套件自我檢查未通過，請保留報告，不繼續連線')
    report['self_check'] = json.loads(check.stdout)
    from bootstrap import ROOT
    if ROOT.resolve() != package.resolve():
        raise RuntimeError('載入的套件路徑不同')
    import numpy as np
    from controller import RepairController
    from combat_v3.interface import decode_packet, encode_command
    config = json.loads((ROOT / 'policy/combat_v3/config.json').read_text(encoding='utf8'))
    controller = RepairController(config)
    residual = np.zeros(4, dtype=np.float32)
    timings = []
    for i in range(2100):
        # Deliberately synthetic OWN20+ENEMY6 packets, not saved flight data.
        o = [23.0, 121.0, 10000.0, (i % 151) - 75.0, (i % 31) - 15.0,
             float(i % 360), 700.0, 100.0, 0.0, 0.0, 0.0, 0.0,
             650.0, 710.0, 1.0 + (i % 70) / 10.0, 700.0, 0.0, 0.0, 3.0, 0.0,
             23.0 + .001 + (i % 60) / 1000.0, 121.0 + (i % 41 - 20) / 1000.0,
             10000.0 + (i % 51 - 25) * 50.0, 600.0, 0.0, 0.0]
        packet = struct.pack('<26d', *o)
        began = time.perf_counter()
        command, _ = controller.act(decode_packet(packet), residual, True)
        encoded = encode_command(command, 2)
        elapsed = (time.perf_counter() - began) * 1000
        if len(encoded) != 30:
            raise RuntimeError('不正確的命令封包長度')
        if i >= 100:
            timings.append(elapsed)
    timings.sort()
    report.update(synthetic_samples=len(timings), mean_ms=statistics.mean(timings),
                  p99_ms=timings[int(len(timings) * .99) - 1], max_ms=max(timings),
                  synthetic_CPU_margin_pass=timings[int(len(timings) * .99) - 1] <= 8.0,
                  real_60Hz_network_verified=False)
    (HERE / 'vivobook_readiness.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print('套件完整性通過。CPU合成測試 p99：%.3f ms；這不是實際連線或戰力驗證。' % report['p99_ms'])
    print('請將 vivobook_readiness.json 帶回這個聊天。')
    return 0 if report['synthetic_CPU_margin_pass'] else 2

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        (HERE / 'vivobook_readiness_error.txt').write_text(traceback.format_exc(), encoding='utf8')
        print('檢查未完成：' + str(error))
        raise SystemExit(1)
