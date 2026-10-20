"""Observe one exact live watchdog exit; do not infer an exit from a receipt."""
import argparse
import json
from pathlib import Path
import time
import psutil

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', required=True)
    args = parser.parse_args()
    record = json.loads((ROOT / 'active_host_watchdog.json').read_text(encoding='utf-8'))
    if record['token'] != args.token or record['status'] != 'armed':
        raise RuntimeError('Expected the requested armed watchdog')
    process = psutil.Process(record['pid'])
    if abs(process.create_time() - record['create_time']) >= .01 or process.cmdline() != record['command']:
        raise RuntimeError('Watchdog identity differs')
    print('observing exact watchdog', process.pid, flush=True)
    try:
        code = process.wait(timeout=max(1., record['deadline_epoch'] - time.time() + 30))
    except psutil.TimeoutExpired:
        print('Observation timed out; exit code remains unknown', flush=True)
        return 1
    output = ROOT / ('watchdog_exit_' + args.token + '.json')
    output.write_text(json.dumps({'identity': record, 'actual_watchdog_exit_code': code,
                                 'observed_epoch': time.time()}, indent=2), encoding='utf-8')
    print('actual watchdog exit', code, str(output), flush=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
