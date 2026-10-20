"""Check reviewed math against existing local observation encoder; no flights."""
from pathlib import Path
import json, sys
BASE=Path(r'E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test')
sys.path.insert(0,str(BASE))
from combat_v3.interface import geometry_from_observation
from observation_diagnostics import analyze_observation

def check(folder):
    rows=[]
    for file in sorted(Path(folder).glob('cases/*/result.json')):
        r=json.loads(file.read_text(encoding='utf-8'))
        initial=r.get('initial',{})
        if 'blue_own20_audit_only' not in initial:
            continue
        blue,red=initial['blue_own20_audit_only'],initial['red_own20_audit_only']
        obs=blue+[red[i] for i in [0,1,2,6,7,8]]
        got=analyze_observation(obs); ref=geometry_from_observation(obs)
        differences={k:abs(got[k]-ref[v]) for k,v in {
            'range_m':'distance_m','nose_error_deg':'blue_angle_deg',
            'body_azimuth_deg':'blue_az_deg','body_elevation_deg':'blue_el_deg',
            'closing_mps':'closing_mps'}.items()}
        if any(v>1e-6 for v in differences.values()):
            raise ValueError('Geometry mismatch: '+str(differences))
        rows.append({'case':r['case_id'],'differences':differences})
    if not rows: raise ValueError('No saved initial observations')
    print(json.dumps({'passed':True,'checked_initials':len(rows),
        'max_absolute_error':max(v for r in rows for v in r['differences'].values()),
        'official_validation':False,'flight_performance_verified':False},ensure_ascii=False))

if __name__=='__main__': check(sys.argv[1])
