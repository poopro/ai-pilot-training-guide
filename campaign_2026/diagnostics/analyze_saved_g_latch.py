"""Saved CSV/result/source analysis only. No simulator, verifier or network imports."""
import ast
import csv
import difflib
import hashlib
import json
import math
from pathlib import Path

ROOT=Path('E:/ai_pilot/campaign_2026')
RUN=ROOT/'experiments/g_latch_development/run_20261014_150515_b846'
PAIR='r000_rule_3000_mirrored_2026101400'
RL='r000_rl_9000_mirrored_2026101412'
CONTROL=('aileron','elevator','rudder','throttle')
FIELDS=('controller_mode','guard_active','distance_m','blue_angle_deg_judge_only','bank_target','roll_deg','cas_kts','tas_mps',
        'speed_target','pitch_deg','pitch_target','alpha_deg','altitude_m','closing_mps','g_guard_latched')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def load(case):
    folder=RUN/'cases'/case
    with (folder/'telemetry_60hz.csv').open(encoding='utf-8-sig',newline='') as stream:
        rows=[{key:value if key=='controller_mode' else float(value) for key,value in row.items()} for row in csv.DictReader(stream)]
    return rows,read(folder/'result.json')
def brief(row):return {key:row[key] for key in ('tick','simulation_seconds',*CONTROL,*FIELDS)}
def intervals(rows,predicate):
    result=[];start=None
    for i,row in enumerate(rows):
        hit=predicate(row)
        if hit and start is None:start=i
        if start is not None and (not hit or i==len(rows)-1):
            end=i if hit else i-1
            result.append(dict(start_tick=int(rows[start]['tick']),end_tick=int(rows[end]['tick']),
                               start_s=rows[start]['simulation_seconds'],end_s=rows[end]['simulation_seconds'],
                               ticks=end-start+1,seconds=(end-start+1)/60))
            start=None
    return result
def main():
    guide,gr=load(PAIR+'_guide');candidate,cr=load(PAIR+'_candidate')
    assert gr['initial_sha256']==cr['initial_sha256'] and len(guide)==len(candidate)==18000
    assert not any(row['g_guard_latched'] for row in candidate)
    divergence=next(i for i,(g,c) in enumerate(zip(guide,candidate)) if any(abs(g[key]-c[key])>1e-12 for key in CONTROL))
    windows=[]
    for start,end in zip(range(0,300,30),range(30,301,30)):
        a=start*60;b=end*60
        item=dict(start_s=start,end_s=end)
        for name,rows in [('guide',guide),('candidate',candidate)]:
            block=rows[a:b];before=rows[a-1]['altitude_m'] if a else gr['initial']['blue_own20_audit_only'][2]*.3048
            item[name]=dict(altitude_start_m=before,altitude_end_m=block[-1]['altitude_m'],height_change_m=block[-1]['altitude_m']-before,
                min_altitude_m=min(r['altitude_m'] for r in block),min_altitude_s=min(block,key=lambda r:r['altitude_m'])['simulation_seconds'],
                min_cas_kts=min(r['cas_kts'] for r in block),max_cas_kts=max(r['cas_kts'] for r in block),
                min_pitch_deg=min(r['pitch_deg'] for r in block),max_pitch_deg=max(r['pitch_deg'] for r in block),
                min_pitch_target=min(r['pitch_target'] for r in block),max_pitch_target=max(r['pitch_target'] for r in block),
                roll_above75_seconds=sum(abs(r['roll_deg'])>75 for r in block)/60,
                bank_target_above75_seconds=sum(abs(r['bank_target'])>75 for r in block)/60,
                mode_ticks={mode:sum(r['controller_mode']==mode for r in block) for mode in sorted(set(r['controller_mode'] for r in block))},
                guard_ticks=sum(r['guard_active'] for r in block),
                first=brief(block[0]),last=brief(block[-1]))
        item['extra_candidate_height_change_m']=item['candidate']['height_change_m']-item['guide']['height_change_m']
        windows.append(item)
    minima={name:brief(min(rows,key=lambda r:r['altitude_m'])) for name,rows in [('guide',guide),('candidate',candidate)]}
    crossings={}
    for threshold in (1,10,50,100,250,300):
        i=next((i for i,(g,c) in enumerate(zip(guide,candidate)) if c['altitude_m']-g['altitude_m']<=-threshold),None)
        crossings[str(threshold)]=dict(guide=brief(guide[i]),candidate=brief(candidate[i])) if i is not None else None
    sources={
        'guide':Path('E:/ai_pilot/autopilot/combat_fix/controller.py'),
        'bank80':ROOT/'experiments/near_bank80/candidate.py',
        'latch':ROOT/'experiments/g_latch_development/safe_candidate.py',
        'judge':ROOT/'candidates/near_bank80_20261012/sources/base/combat_v3/rules.py',
        'lab':Path('E:/ai_pilot/autopilot/opponent_lab/duel_lab.py')}
    # Recorded source hashes connect analysis to the saved run without importing it.
    manifest=read(ROOT/'experiments/g_latch_development/MANIFEST.json')
    recorded=manifest['source_sha256']
    source_hashes={key:dict(path=str(path),sha256=sha(path)) for key,path in sources.items()}
    assert source_hashes['guide']['sha256']==recorded['repair/controller.py']
    assert source_hashes['bank80']['sha256']==recorded['candidate/near_bank80.py']
    assert source_hashes['latch']['sha256'] in recorded.values()
    assert source_hashes['judge']['sha256']==recorded['base/combat_v3/rules.py']
    assert source_hashes['lab']['sha256']==recorded['lab/duel_lab.py']
    def method(path,cls,name):
        tree=ast.parse(path.read_text(encoding='utf-8'))
        node=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name==cls)
        return next(node for node in node.body if isinstance(node,ast.FunctionDef) and node.name==name)
    guide_act=method(sources['guide'],'RepairController','act')
    bank_act=method(sources['bank80'],'Bank80Controller','act')
    guide_command=method(sources['guide'],'RepairController','command')
    latch_command=method(sources['latch'],'GGuardLatchBank80','command')
    act_diff=list(difflib.unified_diff(ast.unparse(guide_act).splitlines(),ast.unparse(bank_act).splitlines(),
                 fromfile='RepairController.act',tofile='Bank80Controller.act',lineterm=''))
    command_diff=list(difflib.unified_diff(ast.unparse(guide_command).splitlines(),ast.unparse(latch_command).splitlines(),
                 fromfile='RepairController.command',tofile='GGuardLatchBank80.command',lineterm=''))
    for index,node in enumerate(guide_command.body):
        if isinstance(node,ast.If) and ast.unparse(node.test)=='safety and abs(o[14]) > 8.5':
            guide_command.body[index:index+1]=ast.parse('''if safety:
    if abs(o[14]) > 8.5:
        self.g_guard_latched = True
    elif abs(o[14]) < 8.0:
        self.g_guard_latched = False
if safety and self.g_guard_latched:
    elevator = max(elevator, -0.08)
''').body
            break
    otherwise_same=ast.dump(guide_command,include_attributes=False)==ast.dump(latch_command,include_attributes=False)
    assert otherwise_same
    settings=read(ROOT/'candidates/near_bank80_20261012/sources/base/combat_v3/config.json')
    assert settings['hz']==60 and settings['attack_seconds']==3
    rl,rr=load(RL+'_candidate');rlguide,rgr=load(RL+'_guide')
    hits=intervals(rl,lambda r:152.4<=r['distance_m']<=914.4 and r['blue_angle_deg_judge_only']<=1.)
    hit_ticks=sum(x['ticks'] for x in hits)
    assert hit_ticks==round(rr['metrics']['attack_seconds']*60)==166
    with (RUN/'cases'/f'{RL}_candidate'/'telemetry.csv').open(encoding='utf-8-sig',newline='') as stream:
        counters=[{key:float(row[key]) for key in ('tick','simulation_seconds','attack_seconds')} for row in csv.DictReader(stream)]
    assert all(b['attack_seconds']>=a['attack_seconds'] for a,b in zip(counters,counters[1:]))
    rl_summary=[]
    for folder in sorted((RUN/'cases').glob('*rl*candidate')):
        r=read(folder/'result.json');rl_summary.append(dict(case_id=r['case_id'],attack_seconds=r['metrics']['attack_seconds'],kills=r['metrics']['kills']))
    output=dict(scope='Saved static telemetry/source analysis only; no new FDM, verifier, training, Host or external transfer',
        run=str(RUN),initial_sha256=gr['initial_sha256'],source_hashes=source_hashes,
        source_method_comparison=dict(act_diff=act_diff,command_diff=command_diff,
            command_identical_except_G_latch_AST=otherwise_same,
            trim_bank_cap_deg=75,bank80_near_limit_deg=80,guide_near_limit_deg=72,
            no_act_policy_or_geometry_change_except_near_bank_ceiling=True),
        worst_pair=dict(pair_key=PAIR,exposure_seconds=300,latch_active_ticks=0,
            first_bank_target_difference=dict(guide=brief(guide[0]),candidate=brief(candidate[0])),
            first_command_divergence=dict(tick=divergence+1,seconds=(divergence+1)/60,
                preceding=dict(guide=brief(guide[divergence-1]),candidate=brief(candidate[divergence-1])) if divergence else None,
                guide=brief(guide[divergence]),candidate=brief(candidate[divergence])),
            first_component_divergence={key:dict(tick=next(i+1 for i,(g,c) in enumerate(zip(guide,candidate)) if abs(g[key]-c[key])>1e-12))
                if any(abs(g[key]-c[key])>1e-12 for g,c in zip(guide,candidate)) else None for key in CONTROL},
            first_physical_state_divergence={key:dict(tick=next(i+1 for i,(g,c) in enumerate(zip(guide,candidate)) if abs(g[key]-c[key])>1e-10))
                if any(abs(g[key]-c[key])>1e-10 for g,c in zip(guide,candidate)) else None
                for key in ('roll_deg','pitch_deg','cas_kts','altitude_m','distance_m')},
            minima=minima,min_altitude_delta_m=minima['candidate']['altitude_m']-minima['guide']['altitude_m'],
            simultaneous_worst_delta=dict(guide=brief(guide[min(range(18000),key=lambda i:candidate[i]['altitude_m']-guide[i]['altitude_m'])]),
                candidate=brief(candidate[min(range(18000),key=lambda i:candidate[i]['altitude_m']-guide[i]['altitude_m'])])),
            first_loss_crossings=crossings,windows_30_seconds=windows,
            mode_intervals={name:{mode:intervals(rows,lambda row,mode=mode:row['controller_mode']==mode)
                for mode in sorted(set(row['controller_mode'] for row in rows))}
                for name,rows in [('guide',guide),('candidate',candidate)]},
            milestone_states=[dict(seconds=seconds,guide=brief(guide[round(seconds*60)-1]),candidate=brief(candidate[round(seconds*60)-1]))
                for seconds in (104.06666666666666,105.95,150,154.66666666666666,156,158.11666666666667,158.13333333333333,165,180,270,300)],
            detailed_paired_trends={f'{start}_{end}':dict(
                samples_every5s=[dict(seconds=seconds,guide=brief(guide[seconds*60-1]),candidate=brief(candidate[seconds*60-1]))
                                 for seconds in range(start,end+1,5)],
                candidate_binding_bank_above72_ticks=sum(abs(r['bank_target'])>72+1e-12 for r in candidate[start*60:end*60]),
                candidate_bank80_binding_intervals=intervals(candidate[start*60:end*60],lambda r:abs(r['bank_target'])>72+1e-12),
                note=('Bank80 actually binds only during154.666667–158.116667s; later intercept ceiling is72, trajectory/state divergence persists.'
                      if start==150 else 'Candidate is intercept for every tick here: ceiling72, no Bank80 binding; guide is track.'))
                for start,end in ((150,180),(270,300))},
            candidate_roll_above75_intervals=intervals(candidate,lambda r:abs(r['roll_deg'])>75),
            candidate_high_bank_target_intervals=intervals(candidate,lambda r:abs(r['bank_target'])>75)),
        rl_case=dict(case_id=RL+'_candidate',selection='Highest attack seconds among six RL candidate cases',
            guide_attack_seconds=rgr['metrics']['attack_seconds'],candidate_attack_seconds=rr['metrics']['attack_seconds'],
            all_rl_case_totals=rl_summary,per_case_total_not_cross_case_aggregation=True,
            exact_window_ticks=hit_ticks,kill_threshold_ticks=180,missing_ticks=180-hit_ticks,
            contiguous_attack_segments=hits,longest_contiguous_seconds=max(x['seconds'] for x in hits),
            attack_counter_decreases=sum(b['attack_seconds']<a['attack_seconds'] for a,b in zip(counters,counters[1:])),
            attack_counter_final=counters[-1],segments_do_not_reset_accumulated_time=True,
            judge_accumulation_source=dict(physics_hz=settings['hz'],attack_seconds_threshold=settings['attack_seconds'],
                attack_frames_threshold=settings['hz']*settings['attack_seconds'],
                initialized_once_per_new_judge=ast.unparse(method(sources['judge'],'LocalJudge','__init__')),
                exact_tick_update=ast.unparse(method(sources['lab'],'DiagnosticJudge','update')),
                window=ast.unparse(method(sources['lab'],'DiagnosticJudge','window')),
                kill_outcome=ast.unparse(method(sources['judge'],'LocalJudge','outcome')),
                conclusion='DiagnosticJudge uses += int(window) each tick, without clearing attack on window exit; LocalJudge kills at180 accumulated frames.'),
            segment_boundary_states=[dict(segment=x,entry=brief(rl[x['start_tick']-1]),exit=brief(rl[x['end_tick']-1]),
                next_nonattack=brief(rl[x['end_tick']]) if x['end_tick']<18000 else None) for x in hits]),
        input_sha256={str(path):sha(path) for path in [RUN/'SAFETY_REVIEW.json',RUN/'cases'/f'{PAIR}_guide'/'telemetry_60hz.csv',
            RUN/'cases'/f'{PAIR}_candidate'/'telemetry_60hz.csv',RUN/'cases'/f'{RL}_candidate'/'telemetry_60hz.csv']})
    output['interpretation']={
        'confirmed':['最差配對latch全程0tick；不能把高度退步歸因G latch啟動。',
            '起始觀測相同，第21tick先出現副翼差異；bank ceiling改變是此配對已辨識的控制差異。',
            '150秒candidate仍比guide高11.169642m；高度差主要在150–180秒與270–300秒擴大。',
            'candidate最後一次track於158.116667秒結束，後續到300秒全程intercept；guide最後30秒全程track。',
            'RL最高攻擊場累積166tick，非連續要求；四段計數沒有重置，距180tick尚差14tick。'],
        'causal_limits':['第一個舵面差異可連到bank ceiling，不能因此宣稱整段319.318m退步由單一瞬時bank造成。',
            '兩機後續位置、俯仰/速度目標、對手反應與mode切換已分歧；這是完整閉迴路轨跡結果。',
            'bank>75時trim計算仍固定75是可測機制，尚未證明它是高度差主因。',
            '記錄為HSL高度；原result最低高度使用AGL；本文件最低值採共同時間的HSL。',
            '不對signed_g正負作物理解讀；不改規則與攻擊門檻。'],
        'next_single_factor_hypothesis':{
            'change':'僅將candidate近距離bank ceiling從80改75；保留G latch、command/trim/gains、mode/距離/速度/俯仰邏輯。',
            'reason':'candidate在104–106與154–158秒實際roll達約82度，而command補償以75度為上限；縮小近距離bank只改一項可直接測的設定。',
            'test_plan':'未來先用最差rule3000 mirrored與最高攻擊RL9000mirrored，三方guide/current80/candidate75同initial完整300秒；如高度退步收斂且RL攻擊不退步，再回歸current80既有三個rule kill場（3000/6000/9000 normal）。已看過種子只稱開發回歸，禁止blind sweep。',
            'acceptance':'可反證：若最差高度差未改善，或RL9000mirrored累積attack低於166tick，便不支持此假設；要晉級須維持已得三個rule kill、零新增死亡/墜機/過9G，最差共同HSL最低高度不低於guide超過數值容差。不能只以平均高度差或peak G下降晉級，不改飛行安全閾值。',
            'status':'假設尚未改控制器、尚未實測；目前candidate仍不宜部署。'}}
    path=RUN/'ALTITUDE_TRADEOFF_ANALYSIS.json'
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    md=['# 高度退步與攻擊不足：已保存遙測分析','',
        '僅讀取既有CSV、result與來源；沒有新FDM、verifier、訓練、Host或外傳。此候選仍不宜部署。','',
        '最差為rule／3000ft／mirrored／seed 2026101400，兩側initial SHA完全相同，完整共同300秒。candidate的G latch全程0tick。','',
        '| 時點 | 精確觀察 |','|---|---|',
        '| 0.016667秒／tick1 | bank target：guide72°、candidate80°；舵面相同。 |',
        '| 0.350000秒／tick21 | 第一個副翼命令差異：guide0.9540773712、candidate1.0；elevator/rudder/throttle仍相同。tick20觀測與舵面相同。 |',
        '| 150秒 | guide高度2634.950429m、candidate2646.120072m；candidate仍高11.169642m。 |',
        '| 150–180秒 | guide下降138.250945m、candidate下降278.221311m；candidate多失139.970366m。 |',
        '| 154.666667秒 | candidate進track，d1091.902m、CAS462.493節、pitch target−13.665°；guide仍intercept，d1129.960m、target−0.834°。 |',
        '| 156秒 | candidate roll82.162°、guide75.319°，CAS442.820／440.714節；candidate目標bank80°但trim計算上限75°。 |',
        '| 158.133333秒起 | candidate離開track後直到300秒全程intercept；此刻d1106.476m、roll79.569°、CAS409.501節。 |',
        '| 180秒 | candidate d4982.669m、CAS300.014節、roll69.176°；guide d1755.941m、CAS402.354節、roll−36.269°。 |',
        '| 270–300秒 | guide全程track並上升26.512599m；candidate全程intercept並下降200.525603m，額外高度變化−227.038202m。 |',
        f"| 各自最低HSL高度 | guide{minima['guide']['altitude_m']:.6f}m＠{minima['guide']['simulation_seconds']:.6f}s；candidate{minima['candidate']['altitude_m']:.6f}m＠{minima['candidate']['simulation_seconds']:.6f}s；差{output['worst_pair']['min_altitude_delta_m']:.6f}m。 |",'',
        '150–180秒內，Bank80實際binding僅在154.666667–158.116667秒的208tick；此後為intercept，bank ceiling已回72°。270–300秒完全沒有Bank80 binding。晚期多失高度是在已分歧的追擊位置與mode下發生，不能說它仍持續命令80°轉彎。JSON提供兩段每5秒的双邊CAS／roll／pitch／bank target／distance／closing／altitude與mode。','',
        '這條因果鏈只確認第一個控制差異來自近距離bank ceiling。後續俯仰、速度、交戰位置、對手反應與mode切換已分歧，不能把整段高度差歸因於一次高bank，也不能歸因於未啟動的latch。','',
        '下一個可測單因素：近距離bank ceiling80→75，其他設定全部保留。先回歸最差3000 mirrored及最高攻擊RL9000 mirrored；若高度差未改善，或RL攻擊降到166tick以下，就不支持此假設。通過後仍须保留current80既有三個rule kill場結果（3000／6000／9000 normal），且零新增墜機／死亡／過9G。禁止blind sweep，不改飛行安全閾值。這是未驗證假設。','',
        'RL最高攻擊場為9000ft／mirrored／seed 2026101412。candidate累積166tick＝2.766667秒，四段如下：','',
        '| 命中時段 | tick數 | 秒數 |','|---|---:|---:|']
    for hit in hits:md.append(f"| {hit['start_s']:.6f}–{hit['end_s']:.6f}秒 | {hit['ticks']} | {hit['seconds']:.6f} |")
    md += ['',
        '每段退出後仍在合法距離（約692／686／669／653m），但機鼻角由≤1°跨到1.004092／1.009824／1.005694／1.000838°，所以暫停增加攻擊時間。已保存攻擊計數沒有下降或重置；累積還差14tick＝0.233333秒才滿180tick。六場總5.066667秒不能跨場拼成擊殺。','',
        '已核對凍結來源：DiagnosticJudge.update以`self.attack[0] += int(window)`逐tick累加；離開window沒有歸零，LocalJudge.outcome在TARGET_FRAMES＝3×60＝180判kill。跨段累積符合現有judge，並非假設需要連續3秒。JSON保留這些函式與SHA。','',
        'JSON保留30秒區間、精確狀態、mode連續區間、command/act來源差異、SHA與攻擊段邊界。遙測為step後狀態；本tick命令由前一個tick觀測計算，避免把同一列後狀態當作命令輸入。',
        '鏡像開局是本地測試設計，不等於官方P1/P2角色交換；所有成績為開發資料。','']
    (RUN/'ALTITUDE_TRADEOFF_ANALYSIS.md').write_text('\n'.join(md),encoding='utf-8')
    print(json.dumps(dict(first_divergence=output['worst_pair']['first_command_divergence'],minima=minima,
        windows=[{key:w[key] for key in ('start_s','end_s','extra_candidate_height_change_m')} for w in windows],
        rl=dict(attack_seconds=rr['metrics']['attack_seconds'],hit_ticks=hit_ticks,segments=hits)),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
