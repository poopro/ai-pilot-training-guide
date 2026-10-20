"""Short real games (JSBSim) for every pool-v2 opponent kind, blue = base_t3. Run through the job queue."""
import sys, time, json
import rollout
import rollout_bfm
import pool2

kinds = list(pool2.POOL_V2) + list(pool2.CTL) + ['saccf']
n_ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 2400
ok = True
for kind in kinds:
    t0 = time.time()
    try:
        cfg = dict(rollout.game_config(1, 950000, kind, n_ticks), host_fidelity=True)
        r = rollout_bfm.play_game(cfg, 'base_t3')
        print('%-16s %-10s atk %3d/%-3d margin %8.1f minAGL %6.0f shield %3d wall %5.1fs' % (
            kind, r['event'], r['atk_b'], r['atk_r'], r['margin'], r['min_agl_m'], r['shield_ticks'], time.time() - t0), flush=True)
    except Exception as e:
        ok = False
        import traceback
        print('%-16s ERROR %s' % (kind, traceback.format_exc()[-600:]), flush=True)
print('SMOKE_POOL2 ' + ('OK' if ok else 'FAILED'))
