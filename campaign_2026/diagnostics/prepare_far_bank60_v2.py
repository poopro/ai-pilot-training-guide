"""Isolate the diagnosed import-order fix; original failed branch is frozen."""
from pathlib import Path
import json
ROOT=Path(r'E:\ai_pilot\campaign_2026')
OLD=ROOT/'experiments/opponent_pool/far_bank60_v1';NEW=OLD.with_name('far_bank60_v2')
NEW.mkdir(exist_ok=False)
for name in ('battle.py','verify.py','test_static.py','candidate.py','USAGE_OBSERVATION.json'):
    s=(OLD/name).read_text(encoding='utf8')
    if name=='battle.py':
        assert s.count("from candidate import project_goal")==1
        s=s.replace("        from candidate import project_goal\n",'')
        marker="TRIAL='far_bank60_v1_2026310300_two_openings_two_doctrines'"
        assert s.count(marker)==1
        s=s.replace(marker,"""TRIAL='far_bank60_v2_2026310400_two_openings_two_doctrines'
# Bind the precise file before framework imports can change sys.path or cache
# another experiment's generic candidate module.
_goal_spec=importlib.util.spec_from_file_location('far_bank60_v2_goal_projection',HERE/'candidate.py')
_goal_module=importlib.util.module_from_spec(_goal_spec);_goal_spec.loader.exec_module(_goal_module)
project_goal=_goal_module.project_goal
if Path(project_goal.__code__.co_filename).resolve()!=HERE/'candidate.py':raise RuntimeError('Wrong exact projection source')""")
        s=s.replace('SEEDS=(2026310300,2026310301)','SEEDS=(2026310400,2026310401)')
        s=s.replace("experiment='far_bank60_v1'","experiment='far_bank60_v2'")
    elif name=='test_static.py':
        s=s.replace('battle.SEEDS==(2026310300,2026310301)','battle.SEEDS==(2026310400,2026310401)')
        s += '''\n# Reproduce framework sys.path changes without constructing FDM/environment.
import sys,types
saved_candidate=sys.modules.get('candidate')
poison=types.ModuleType('candidate');poison.project_goal=lambda *a,**k: (_ for _ in ()).throw(AssertionError('wrong candidate'))
sys.modules['candidate']=poison
sys.path.insert(0,str(HERE.parents[2]/'experiments/m4_tactical_v4'))
import m4_tactical_rl
assert Path(battle.project_goal.__code__.co_filename).resolve()==HERE/'candidate.py'
assert battle.project_goal(1200,[72,2,300,0],enabled=True)==[60,2,300,0]
assert sys.modules['candidate'] is poison
if saved_candidate is None:del sys.modules['candidate']
else:sys.modules['candidate']=saved_candidate
print({'cold_framework_import_collision_test':'passed','new_FDM_ticks':0,'environment_constructed':False})
'''
    (NEW/name).write_text(s,encoding='utf8')
(NEW/'PREPARATION.json').write_text(json.dumps(dict(status='prepared_not_launched',failed_source_branch=str(OLD),root_cause='m4_tactical_rl mutates import order; generic candidate import resolved near_bank80/candidate.py after reset',unique_fix='Resolve and bind candidate.py by absolute path before framework imports; no changes to physical/control/candidate arithmetic',prior_failure_preserved=True,failed_seeds_not_reused=[2026310300,2026310301],new_seed_plan=[2026310400,2026310401],original_worker_seconds=90,original_whole_seconds=600,verifier_seconds=120,training_started=False),ensure_ascii=False,indent=2),encoding='utf8')
print(str(NEW))
