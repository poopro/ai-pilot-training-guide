from pathlib import Path
import ast,datetime,json,sys
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/far_speed_v1';NEW=ROOT/'experiments/opponent_pool/rule_family_v1'
sys.path.insert(0,str(SOURCE));import battle as b
prior=ROOT/'diagnostics/rule_family_precheck_v1_20261018_092908_52c797'
v=b.read(prior/'VERIFICATION.json');e=b.read(prior/'WORKER_EXIT.json');assert v['verified_rule_family_saved_packet_wiring'] and e['actual_worker_exit']==0 and e['absent']
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
b.write(prior/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=0,session_id=75606,chunk_id='fd510d',observed_utc=now,actual_wall_seconds=14.547,observation_source='unified exec process wait'))
lp=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=b.read(lp)
for item in ledger['items']:
    if item['id']==prior.name:item.update(status='verified_saved_packet_wiring_no_initial_command_effect',actual_parent_exit=0,actual_worker_exit=0,actual_wall_seconds=14.547)
b.write(lp,ledger)
prep=b.read(NEW/'PREPARATION.json');prep.update(status='real_saved_packet_wiring_verified_but_no_prefix_command_difference',precheck_run=str(prior),verification=str(prior/'VERIFICATION.json'),actual_parent_exit=0,actual_worker_exit=0,FDM_launch_allowed=False,
    reason='Pureguide and station command outputs match both first300-packet prefixes. First bound a longer activation check; do not launch four potentially identical games.',full_comparison_runner_implemented=False)
b.write(NEW/'PREPARATION.json',prep)
old=(ROOT/'diagnostics/rule_family_precheck_guardian_v1.py').read_text(encoding='utf8')
new=old.replace('rule_family_precheck','rule_family_activation')
needle="        write(out/'CONTRACT.json',spec)";assert needle in new
new=new.replace(needle,"        spec.update(prior_precheck=str(ROOT/'diagnostics/rule_family_precheck_v1_20261018_092908_52c797'),prior_precheck_verification_sha256=sha(ROOT/'diagnostics/rule_family_precheck_v1_20261018_092908_52c797/VERIFICATION.json'),max_prefix_ticks=3600,hypothesis='Determine first changed actual controller output, if any, before spending four new FDM games',window_definitions='Stateful first300 history rebuild, then new suffix through3600 or first output difference')\n"+needle)
path=ROOT/'diagnostics/rule_family_activation_guardian_v1.py';assert not path.exists();ast.parse(new);path.write_text(new,encoding='utf8')
path.with_suffix('.usage.json').write_text((ROOT/'diagnostics/rule_family_precheck_guardian_v1.usage.json').read_text(encoding='utf8'),encoding='utf8')
ast.parse((ROOT/'diagnostics/rule_family_activation_worker_v1.py').read_text(encoding='utf8'))
print(json.dumps(dict(parent_precheck_actual_exit=0,precheck_check_groups=v['check_groups'],initial_command_differences=[x['changed_actual_commands'] for x in v['results']],activation_guardian=str(path),FDM_launch_allowed=False)))
