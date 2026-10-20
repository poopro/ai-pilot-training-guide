from pathlib import Path
import argparse,csv,hashlib,json,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def analyze(path):
    path=Path(path);r=json.loads(path.read_text(encoding='utf-8'))
    assert r['complete'] and r['initials_identical'] and r['warmup_boundaries_identical']
    results=[];curves=[]
    for case in r['cases']:
        assert case['valid_calibration'] and case['worker_exit_code']==0
        src=Path(case['folder'])/(case['case']['case_id']+'.csv')
        with src.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
        assert len(rows)==2100
        test=[x for x in rows if x['phase']=='test'];steady=[x for x in test if float(x['sim_time_s'])>30]
        vals=lambda k:np.array([float(x[k]) for x in steady])
        errors=[]
        for x in rows:
            phi,theta=np.radians([float(x['post_phi_deg']),float(x['post_theta_deg'])])
            q,br=float(x['post_q_rad_s']),float(x['post_r_rad_s'])
            post=math.degrees((q*math.sin(phi)+br*math.cos(phi))/math.cos(theta))
            errors.append(abs(float(x['fd_yaw_rate_deg_s'])-.5*(float(x['euler_yaw_rate_deg_s'])+post)))
        d={'case_id':case['case']['case_id'],'csv_sha256':sha(src),'steady_samples':len(steady),
            'median':{k:float(np.median(vals(k))) for k in ['pre_phi_deg','pre_theta_deg','pilot_load_signed',
                'pilot_load_abs','euler_yaw_rate_deg_s','cas_kts','tas_kts','alpha_deg','beta_deg','cmd_elevator']},
            'max_abs_load':max(abs(float(x['pilot_load_signed'])) for x in rows),
            'min_altitude_msl_m':min(float(x['alt_msl_m']) for x in rows),
            'guard_ticks':case['result']['tick_counts']['guard'],'warmup_flags':case['result']['warmup_stability_flags'],
            'yaw_fd_vs_midpoint_euler_abs_error_p50_p95_deg_s':np.percentile(errors,[50,95]).tolist()}
        results.append(d);curves.append((case['case']['case_id'],test))
    fig,axes=plt.subplots(3,1,figsize=(10,8),sharex=True,layout='constrained')
    for name,rows in curves:
        if '70' not in name and '80' not in name:continue
        t=[float(x['sim_time_s'])-15 for x in rows]
        for ax,key in zip(axes,['pre_phi_deg','pilot_load_abs','euler_yaw_rate_deg_s']):
            ax.plot(t,[float(x[key]) for x in rows],label=name,lw=1.3)
    for ax,label in zip(axes,['Bank (deg)','Abs pilot load','Heading rate (deg/s)']):
        ax.set_ylabel(label);ax.grid(alpha=.25);ax.legend(fontsize=8)
    axes[-1].set_xlabel('Seconds after bank step')
    fig.suptitle('Original FDM/controller command-channel calibration; not combat scoring')
    fig.savefig(path.parent/'calibration_plot.png',dpi=150);plt.close(fig)
    out={'report':str(path),'report_sha256':sha(path),'cases':results,'official_validation':False,
        'combat_score_eligible':False,'window':'last 5 of 20 test simulation seconds',
        'limits':'Fixed initialization, one speed/altitude and positive bank steps only. No aiming, negative-bank/rudder-sign test or competition win probability.'}
    (path.parent/'ANALYSIS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('report');a=p.parse_args();analyze(a.report)
