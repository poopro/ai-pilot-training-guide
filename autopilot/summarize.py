"""Read-only artifact checks plus concise, evidence-linked final report."""
import argparse,csv,math,collections,shutil
from common import *

def interval(k,n):
    if not n:return '無樣本'
    z=1.96;p=k/n;den=1+z*z/n
    c=(p+z*z/(2*n))/den;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return f'{max(0,c-h):.0%}–{min(1,c+h):.0%}'

def audit_acmi(path):
    ids=set();count=0;previous=-1.;both=0
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('#'):
            t=float(line[1:]);assert t>=previous;previous=t;count+=1
        elif ',T=' in line:
            ident=line.split(',',1)[0];ids.add(ident)
            assert all(math.isfinite(float(v)) for v in line.split('T=',1)[1].split(',',1)[0].split('|'))
            both+=1
    assert len(ids)==2 and count>1 and both>=count
    return {'path':str(path),'two_aircraft':True,'monotonic_time':True,'frames':count,'last_seconds':previous,
            'sha256':digest(path)}

def build(job,require_finished=False):
    folder=experiment_dir(job)
    if require_finished and (alive(job.get('supervisor')) or alive(job.get('process'))):raise RuntimeError('仍運行，不能覆寫最終報告')
    reports={}
    for d in ('baseline_guide','guide_revision1','guide_preflight','dev_20000','dev_50000','dev_100000','dev_199000','holdout'):
        r=read(folder/d/'report.json')
        if r:reports[d]=r
    audits=[]
    for name,r in reports.items():
        for ep in r['episodes']:audits.append(audit_acmi(ep['acmi']))
    atomic(folder/'acmi_format_audit.json',audits)
    frozen=read(folder/'frozen_source/hashes.json',{})
    source_match=all(digest(BASE/'combat_v3'/n)==v for n,v in frozen.items())
    atomic(folder/'source_current_audit.json',{'matches_frozen_training':source_match,'sha256':frozen,'utc':stamp()})
    shutil.copy2(ROOT/'規則對照.md',folder/'規則對照.md')
    configuration={k:job[k] for k in ('job_id','first_started_epoch','deadline_epoch','deadline_taipei','step_budget','config')}
    atomic(folder/'job_configuration.json',configuration)
    chart=None
    if reports:
        import matplotlib;matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        names=[n for n in ('dev_20000','dev_50000','dev_100000','dev_199000') if n in reports]
        fig,axes=plt.subplots(1,2,figsize=(12,4.5));x=list(range(len(names)))
        for opponent in ('easy','maneuver','duel'):
            for policy,style in (('guide','--'),('policy','-')):
                kills=[]
                for name in names:
                    g=next(g for g in reports[name]['groups'] if g['opponent']==opponent and g['policy']==policy)
                    kills.append(g['kills']/g['episodes'])
                axes[0].plot(x,kills,style,marker='o',label=opponent+' / '+policy)
        labels=[]
        for name in names:
            bundle=reports[name].get('bundle')
            labels.append(str(read(Path(bundle)/'manifest.json',{}).get('timesteps',name.replace('dev_',''))) if bundle else name.replace('dev_',''))
        axes[0].set_xticks(x);axes[0].set_xticklabels(labels,rotation=25)
        axes[0].set_title('Development kills: fixed 5 seeds per opponent')
        axes[0].set_xlabel('Actual candidate training steps')
        h=reports.get('holdout')
        if h:
            for policy,offset in (('guide',-.18),('policy',.18)):
                values=[next(g for g in h['groups'] if g['policy']==policy and g['opponent']==o) for o in ('easy','maneuver','duel')]
                bars=axes[1].bar([i+offset for i in range(3)],[g['kills']/g['episodes'] for g in values],width=.36,label=policy)
                for bar,g in zip(bars,values):axes[1].text(bar.get_x()+bar.get_width()/2,bar.get_height()+.02,f"{g['kills']}/{g['episodes']}",ha='center',fontsize=9)
            axes[1].set_xticks(range(3));axes[1].set_xticklabels(('easy','maneuver','duel'))
        axes[1].set_title('Holdout kills: 20 unseen seeds per opponent')
        for ax in axes:
            ax.set_ylim(-.04,1.12);ax.set_ylabel('Local kill rate');ax.grid(axis='y',alpha=.2);ax.legend(fontsize=8)
        fig.tight_layout();chart=folder/'evaluation_summary.png';fig.savefig(chart,dpi=160);plt.close(fig)
    decision=read(folder/'deployment_selection.json') or read(folder/'selection.json',{})
    selected=decision.get('decision','尚未選定')
    chosen={'policy_candidate':'SAC＋引導器候選','retain_guide':'修正後純引導器（SAC residual 為零）'}.get(selected,'尚未選出；請勿當作可用部署版本')
    elapsed=(job.get('pipeline_completed_epoch',time.time())-job['first_started_epoch'])/60
    lines=['# AI 空戰無人值守結果','',f"**{job['status']}**；核心管線約 {elapsed:.0f} 分鐘，新增訓練 **{job['new_steps']:,}/{job['step_budget']:,} 步**。訓練與監督程序已結束，未再啟動訓練。",
           f'目前本地部署選擇：**{chosen}**。學習成效：{job.get("learning","尚未評估")}。','',
           '程式驗證：'+job.get('verification','尚未完成')+'。',
           '官方驗證：'+job.get('official_host','pending_manual')+'。本地擊殺與位置優勢估計不能當作正式比賽成果。','']
    if job.get('error'):lines+=['停止／限制原因：'+job['error'],'']
    if job.get('retired_candidates'):
        lines+=['第一候選因實際初始空速與設定不符而退役，舊 50,000 步模型與 replay 仍保留。第二候選修正為實際初始 CAS 340 knots 後重跑，沒有混用舊 replay；下表只列修正後初始化的測試，兩種物理條件不混算。',
                '步數帳本：第一候選與驗證 50,658 步＋第二候選驗證 658 步＋第二候選主訓練 148,682 步＝199,998 步。最後資料夾名稱含 199000 是原檢查點標籤；模型實際步數以 manifest 的 148,682 為準。','']
    holdout=reports.get('holdout')
    if holdout:
        lines+=['版本選定後才執行一次保留測試；每類 20 個新種子，不能拿這批結果調參後仍稱為獨立測試。','',
          '| 版本／對手 | 場數 | 本地勝率 | 擊殺率 | 存活率 | 平均攻擊秒數 | 平均回合獎勵 |',
          '| --- | --- | --- | --- | --- | --- | --- |']
        for g in holdout['groups']:
            n=g['episodes'];lines.append(f"| {g['policy']}/{g['opponent']} | {n} | {g['wins']}/{n} | {g['kills']}/{n} | {g['survivals']}/{n} | {g['attack_seconds']:.3f} | {g['mean_reward']:.2f} |")
        lines+=['','95% Wilson 擊殺率區間：'+ '；'.join(f"{g['policy']}/{g['opponent']} {interval(g['kills'],g['episodes'])}" for g in holdout['groups'])+'。即使 20/20 存活，區間下限約 84%，仍不足以保證真實存活率達 95%。',
                '終止原因：'+str(holdout['end_reasons'])+'；完整逐回合包含敵方攻擊、最低離地高度、過 G、安全介入與計算時間。','']
        lines+=['SAC 在最後開發測試對反擊對手由引導器 0/5 擊殺提高到 2/5，因此在保留測試之前凍結為測試候選。保留測試兩者卻同為 6/20 擊殺、19/20 本地估計勝利、20/20 存活；SAC 攻擊時間較少，沒有證明可靠改善。依任務要求，日常部署回退到純引導器；原 selection.json、模型與保留測試維持不變。這是發布判斷，不是重訓或重新調參。',
                '每個版本都完成 60 場：46 次擊殺、14 次滿時；無墜機或被擊落，滿時各有 1 場依本地位置優勢估計落敗。反擊對手仍有 14/20 無法擊殺；碰撞未模擬，近距離穿越不算已驗證安全。','']
        lines+=['第二版來源與完整 model／replay 校驗仍一致，沒有覆蓋。本輪沒有在這批新種子對第二版做同條件重評，因此不宣稱第三版已勝過第二版。','']
    else:lines+=['保留測試尚未完成；不能宣稱達到完整評估要求。','']
    before=reports.get('baseline_guide');after=reports.get('guide_revision1')
    if before and after:
        lines+=['相同 15 場開發情境：原引導器擊殺 '+str(sum(g['kills'] for g in before['groups']))+'/15 → 修正後 '+str(sum(g['kills'] for g in after['groups']))+'/15。這是引導器工程修正的改善，不是 SAC 學習的證據。','']
    lines+=['操作：','',
        '- 查看結果：[最新結果.md](<E:/ai_pilot/autopilot/最新結果.md>)。',
        '- 查看進度：[查看結果.cmd](<E:/ai_pilot/autopilot/查看結果.cmd>)；停止：[停止並保存.cmd](<E:/ai_pilot/autopilot/停止並保存.cmd>)。',
        '- 中斷後續跑：[接續未完成工作.cmd](<E:/ai_pilot/autopilot/接續未完成工作.cmd>)，沿用同一期限／預算；已完成不會重啟。',
        '- 回放：[查看回放.cmd](<E:/ai_pilot/autopilot/查看回放.cmd>)；本地 Player：[啟動最佳本地控制器.cmd](<E:/ai_pilot/autopilot/啟動最佳本地控制器.cmd>)；官方步驟：[官方Host人工驗證.md](<E:/ai_pilot/autopilot/官方Host人工驗證.md>)。',
        '- 本地藍色＝你，紅色＝對手。點下方 ACMI，在 Tacview 開啟；官方顏色仍需核對。','']
    for name,r in reports.items():lines.append(f'- [{name} 完整報告](<{(folder/name/"report.json").as_posix()}>)')
    if job.get('checkpoint'):lines.append(f'- [最後完整模型／replay](<{Path(job["checkpoint"]).as_posix()}>)')
    if (folder/'final_audit.json').exists():lines.append(f'- [完整存檔、預算、來源與測試稽核](<{(folder/"final_audit.json").as_posix()}>)')
    if holdout:
        for opponent in ('easy','maneuver','duel'):
            ep=next(r for r in holdout['episodes'] if r['opponent']==opponent)
            lines.append(f'- [{opponent} 兩機回放](<{Path(ep["acmi"]).as_posix()}>)')
    for label,name in (('最終 SAC UDP 與延遲','deployment_udp_final'),('預設引導器 UDP 與延遲','deployment_udp_guide')):
        r=read(folder/name/'report.json')
        if r:
            lines+=['',f"{label}：通過={r['passed']}，p50／p95／p99／最大={r['network_latency_p50_ms']:.2f}／{r['network_latency_p95_ms']:.2f}／{r['network_latency_p99_ms']:.2f}／{r['network_latency_max_ms']:.2f} ms。測試含真實 Player 與本機 UDP，未包含官方 Host；60 Hz 的單 tick 為約 16.7 ms。",f'- [封包測試報告](<{(folder/name/"report.json").as_posix()}>)']
    lines+=['',f'已檢查 {len(audits)} 份 ACMI 的兩機、數值與時間格式；Tacview 實際視覺確認狀態：'+job.get('tacview','pending_manual')+'。',
          '目前程式符合本輪凍結來源：'+str(source_match)+'。',
          '必要人工下一步：在可信的官方來源確認 Host 安全提示、完成 Host 初始化／START／完整回合並保存裁判結果。碰撞、平局重賽、位置計分歧義仍以 Host 為準。',
          'Host 留待人工的依據：[computer-use SKILL.md](<C:/Users/USER/.codex/plugins/cache/openai-bundled/computer-use/26.930.31730/skills/computer-use/SKILL.md>) 引用操作規範「Do not act on security or privacy permission requests.」。本輪未操作 SmartScreen，也未改 Windows 安全設定。',
          '', '[規則對照](<E:/ai_pilot/autopilot/規則對照.md>)；[操作說明](<E:/ai_pilot/autopilot/操作說明.md>)；[LLM 後續介面](<E:/ai_pilot/autopilot/LLM後續介面.md>)。']
    if chart:lines+=['',f'![固定評估比較](<{chart.as_posix()}>)']
    content='\n'.join(lines)+'\n';(folder/'結果.md').write_text(content,encoding='utf-8')
    temp=ROOT/'最新結果.tmp';temp.write_text(content,encoding='utf-8');os.replace(temp,ROOT/'最新結果.md')
    return {'reports':list(reports),'acmi_files':len(audits),'source_match':source_match}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--require-finished',action='store_true');a=p.parse_args()
    print(build(read(ROOT/'最新狀態.json'),a.require_finished))
