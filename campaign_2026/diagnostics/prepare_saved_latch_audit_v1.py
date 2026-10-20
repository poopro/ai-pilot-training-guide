from pathlib import Path
import json
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/rear_latch60_v2';RUN=SOURCE/'run_20261017_203915_d840e7'
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
write(RUN/'VERIFIER_WRAPPER_EXIT_OBSERVED.json',dict(actual_exit=1,tool_session=10728,tool_chunk='68522e',child_verifier_actual_exit=2,reason='ACMI checker incorrectly assumed geodetic pose latitude equals geocentric OWN packet latitude; original failure preserved'))
s=(SOURCE/'verify.py').read_text(encoding='utf8');s=s[:s.index('def guarded(')]
s=s.replace('def verify(out,parent_exit):','def verify(out,parent_exit,audit):')
a="""                expected=[p[1],p[0],p[2]*.3048,p[3],p[4],p[5]]
                check(len(poses[tick].get(k,[]))==6 and all(abs(a-b)<1e-5 for a,b in zip(poses[tick].get(k,[]),expected)),tag+' ACMI legal pose '+str(tick))"""
b="""                actual=poses[tick].get(k,[])
                if len(actual)!=6:check(False,tag+' ACMI pose length');continue
                # Original wrapper uses pose[7]=lat-geod-deg; OWN uses lat-gc-deg.
                # WGS84 axes in JSBSim FGInertial.cpp (feet, converted to metres).
                aa=20925646.32546*.3048;bb=20855486.5951*.3048;ecc=1-(bb/aa)**2
                gd=math.radians(actual[1]);rn=aa/math.sqrt(1-ecc*math.sin(gd)**2);h=actual[2]
                gc=math.degrees(math.atan2((rn*(1-ecc)+h)*math.sin(gd),(rn+h)*math.cos(gd)))
                check(abs(gc-p[0])<1e-8,tag+' ACMI WGS84 geodetic/geocentric latitude '+str(tick))
                expected=[p[1],p[2]*.3048,p[3],p[4],p[5]]
                check(all(abs(a-b)<1e-5 for a,b in zip([actual[0],*actual[2:]],expected)),tag+' ACMI legal other pose fields '+str(tick))"""
assert a in s;s=s.replace(a,b)
s=s.replace("write(out/'COMPARISON.json',verification)","verification['audit_only_coordinate_mapping_correction']=True;verification['original_failed_comparison_preserved']=True;write(audit/'COMPARISON.json',verification)")
(ROOT/'diagnostics/saved_latch_audit_v1.py').write_text(s,encoding='utf8')
original=(ROOT/'diagnostics/rear_latch_review_guardian.py').read_text(encoding='utf8')
head=original[:original.index('def worker(out):')].replace('LIMIT=120','LIMIT=180')
worker='''def worker(out):
    spec=read(out/'CONTRACT.json')
    if sha(Path(__file__))!=spec['diagnostic_source_sha256']:raise RuntimeError('Guardian source changed')
    if sha(ROOT/'diagnostics/saved_latch_audit_v1.py')!=spec['audit_source_sha256']:raise RuntimeError('Audit source changed')
    import importlib.util
    exact=importlib.util.spec_from_file_location('saved_latch_audit_exact_v1',ROOT/'diagnostics/saved_latch_audit_v1.py');v=importlib.util.module_from_spec(exact);exact.loader.exec_module(v)
    code=v.verify(RUN,0,out)
    if code!=0:return code
    write(RUN/'SAVED_DATA_AUDIT_LINK.json',dict(comparison=str(out/'COMPARISON.json'),comparison_sha256=sha(out/'COMPARISON.json'),original_failed_comparison=str(RUN/'COMPARISON.json'),original_failed_comparison_sha256=sha(RUN/'COMPARISON.json'),audit_source_sha256=spec['audit_source_sha256'],no_new_FDM=True))
    import rear_latch_review_worker
    return rear_latch_review_worker.worker(out)

'''
launch=original[original.index('def launch():'):].replace('rear_latch_review_v1_','saved_latch_audit_v1_')
launch=launch.replace("spec['comparison_sha256']=sha(RUN/'COMPARISON.json')","spec['failed_comparison_sha256']=sha(RUN/'COMPARISON.json')\n        spec['audit_source_sha256']=sha(ROOT/'diagnostics/saved_latch_audit_v1.py')\n        spec['correction']='Wrong latitude coordinate equality corrected with WGS84 transform; all strict numeric/event/source/policy/initial/CSV/ACMI checks retained. No new FDM, no original deadline extension.'\n        spec['primary_sources']=['https://raw.githubusercontent.com/JSBSim-Team/jsbsim/master/src/math/FGLocation.cpp','https://raw.githubusercontent.com/JSBSim-Team/jsbsim/master/src/models/FGInertial.cpp']")
(ROOT/'diagnostics/saved_latch_audit_guardian_v1.py').write_text(head+worker+launch,encoding='utf8')
print('Prepared independent 180s saved-data audit/review; original simulation and failed verifier unchanged')
