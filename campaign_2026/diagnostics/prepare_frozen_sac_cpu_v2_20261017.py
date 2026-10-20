from pathlib import Path
import json,hashlib,datetime,ast
ROOT=Path(r'E:\ai_pilot\campaign_2026')
old=ROOT/'experiments/opponent_pool/frozen_sac_opponent_v1'
new=old.with_name('frozen_sac_opponent_v2')
new.mkdir(exist_ok=False)
for name in ('adapter.py','factory.py','packet_features.py','CONTRACT.json','README.md'):
    (new/name).write_bytes((old/name).read_bytes())
p=new/'factory.py';txt=p.read_text(encoding='utf8')
before='    from stable_baselines3 import SAC\n    python_state=random.getstate();numpy_state=np.random.get_state()'
after='    python_state=random.getstate();numpy_state=np.random.get_state()'
assert txt.count(before)==1
txt=txt.replace(before,after)
before='        with torch.random.fork_rng(devices=[]):\n            donor=SAC.load'
after='        with torch.random.fork_rng(devices=[]):\n            # Cold-import side effects belong inside the same RNG restore scope.\n            from stable_baselines3 import SAC\n            donor=SAC.load'
assert txt.count(before)==1
txt=txt.replace(before,after);ast.parse(txt);p.write_text(txt,encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
c=json.loads((new/'CONTRACT.json').read_text(encoding='utf8'))
c['executor_sha256']['factory.py']=sha(p)
c['revision']='v2: stable_baselines3 cold import moved inside Python/NumPy/Torch RNG restoration scope; no control math, model or packet changes'
c['parent_contract_sha256']=sha(old/'CONTRACT.json')
(new/'CONTRACT.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf8')
oldprobe=ROOT/'diagnostics/frozen_sac_cpu_probe_20261016.py'
newprobe=ROOT/'diagnostics/frozen_sac_cpu_probe_v2_20261017.py'
s=oldprobe.read_text(encoding='utf8').replace('frozen_sac_opponent_v1','frozen_sac_opponent_v2')
s=s.replace("    def rng():return hashlib.sha256(pickle.dumps((random.getstate(),np.random.get_state(),torch.random.get_rng_state().numpy()))).hexdigest()", "    def rng():\n        n=np.random.get_state()\n        return {'python':hashlib.sha256(repr(random.getstate()).encode()).hexdigest(),\n                'numpy':hashlib.sha256(n[0].encode()+n[1].tobytes()+repr(n[2:]).encode()).hexdigest(),\n                'torch_cpu':hashlib.sha256(torch.random.get_rng_state().numpy().tobytes()).hexdigest()}")
s=s.replace("        assert rng()==before,'RNG changed on factory construction'", "        after=rng();write(out/('RNG_'+model+'.json'),{'before':before,'after_construct':after,'equal_by_stream':{k:before[k]==after[k] for k in before}})\n        assert after==before,'RNG changed on factory construction'")
s=s.replace("'frozen_sac_cpu_probe_'+", "'frozen_sac_cpu_probe_v2_'+")
s=s.replace("ledgerpath=ROOT/'compute_budgets/2026-10-16.json';ledger=read(ledgerpath)", "budget_date=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()\n        ledgerpath=ROOT/('compute_budgets/'+budget_date+'.json')\n        ledger=read(ledgerpath) if ledgerpath.exists() else {'date_taipei':budget_date,'daily_limit_hours':6.0,'reserved_hours':0.0,'items':[]}")
s=s.replace("'five_hour_remaining':82,'weekly_remaining':55", "'five_hour_remaining':78,'weekly_remaining':54")
ast.parse(s);newprobe.write_text(s,encoding='utf8')
(new/'PREPARATION.json').write_text(json.dumps({'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'unique_change':c['revision'],'parent_sources_unchanged':True,'new_FDM_ticks':0,'actual_CPU_probe_pending':True,'probe':str(newprobe),'probe_sha256':sha(newprobe),'scope':'offline production factory/interface, not physical response or battle strength','first_probe_failure_preserved':'diagnostics/frozen_sac_cpu_probe_20261016_231331_e45d41/FAILURE_REVIEW.json'},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'branch':str(new),'probe':str(newprobe),'probe_sha256':sha(newprobe)},ensure_ascii=False))
