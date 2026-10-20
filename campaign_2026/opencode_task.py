"""Bounded free-model work at the highest catalog-supported reasoning effort."""
from pathlib import Path
import argparse, hashlib, json, math, os, subprocess, time, uuid
from datetime import datetime, timezone
import psutil

ROOT = Path(__file__).resolve().parent
EXE = ROOT / 'tools' / 'opencode-v2' / 'opencode.exe'
MODEL = 'opencode/space-bunny-free'
EFFORT_ORDER = ('none','minimal','low','medium','high','xhigh','max','ultra')

def resolve_highest_free(models, requested):
    """Fail closed on unverified prices or ambiguous effort; never invent variants."""
    if requested.count('/') != 1 or '#' in requested:
        raise ValueError('Select a catalog provider/model; effort is always resolved automatically')
    provider, model = requested.split('/')
    if provider != 'opencode':
        raise ValueError('This launcher only permits the OpenCode free-model provider')
    matches=[m for m in models if m.get('providerID')==provider and m.get('id')==model]
    if len(matches)!=1:
        raise ValueError('Requested model is not uniquely available in the live catalog')
    entry=matches[0]
    prices=entry.get('cost')
    if not isinstance(prices,list) or not prices:
        raise ValueError('Model pricing is unknown; no request was sent')
    for price in prices:
        values=[price.get('input'),price.get('output'),price.get('cache',{}).get('read'),price.get('cache',{}).get('write')]
        if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v!=0 for v in values):
            raise ValueError('Only verified zero-priced models are permitted')
    variants=entry.get('variants',[])
    if not variants:
        return requested, None, {}, 'no_adjustable_effort_advertised', entry
    ranked=[]
    for variant in variants:
        settings=variant.get('settings',{})
        effort=settings.get('reasoningEffort',variant.get('id'))
        if effort not in EFFORT_ORDER:
            raise ValueError('Catalog variant effort cannot be ordered safely; review metadata first')
        ranked.append((EFFORT_ORDER.index(effort),variant['id'],settings))
    _, variant_id, settings=max(ranked,key=lambda v:v[0])
    return requested+'#'+variant_id, variant_id, settings, 'highest_supported', entry

def audit_session(folder, env, session, requested, variant):
    p=subprocess.run([str(EXE),'session','export','--standalone',session],env=env,cwd=folder,
        capture_output=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if p.returncode: raise RuntimeError('Local session export failed')
    metadata=[]
    def walk(v):
        if isinstance(v,dict):
            if isinstance(v.get('model'),dict) and 'cost' in v:
                metadata.append({k:v[k] for k in ['model','cost','tokens'] if k in v})
            for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    walk(json.loads(p.stdout.decode('utf-8')))
    metadata=list({json.dumps(v,sort_keys=True):v for v in metadata}.values())
    provider, model=requested.split('/')
    verified=bool(metadata) and all(v['model'].get('providerID')==provider and
        v['model'].get('id')==model and v['model'].get('variant','default')==(variant or 'default') and
        v['cost']==0 for v in metadata)
    evidence={'session_id':session,'assistant_metadata':metadata,'verified_model_effort_and_zero_cost':verified,
        'requested_model':requested,'requested_variant':variant,'contents_exported':False}
    (folder/'model_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    if not verified:raise RuntimeError('Actual model/effort/zero-cost evidence did not match the request')
    return evidence

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--file', action='append', default=[])
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--model', default=MODEL, help='Live zero-priced OpenCode model; highest effort is mandatory')
    args = parser.parse_args()
    if not 30 <= args.seconds <= 1200:
        parser.error('seconds must be 30..1200')
    request = Path(args.request).resolve()
    files = [Path(f).resolve() for f in args.file]
    for p in [request, *files]:
        if p.suffix.lower() not in {'.py','.md','.txt'} or p.stat().st_size > 150000:
            raise ValueError('Only bounded source/text attachments are supported')
        if any(s.lower() in {'.codex','.config','.env','.git','node_modules'} for s in p.parts):
            raise ValueError('Private/configuration files are not task inputs')
    if sum(p.stat().st_size for p in [request,*files]) > 200000:
        raise ValueError('Task input is too large')
    folder = ROOT / 'delegations' / (datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4])
    folder.mkdir(parents=True)
    config = {
        '$schema':'https://opencode.ai/config.json', 'model': args.model, 'small_model': args.model,
        'enabled_providers':['opencode'], 'autoupdate':False, 'share':'disabled',
        'permissions':[{'action':'*','resource':'*','effect':'ask'}], 'mcp':{}, 'plugins':[],
        'agents':{'plan':{'permissions':[
            {'action':'*','resource':'*','effect':'ask'},
            {'action':'edit','resource':'*','effect':'deny'},
            {'action':'subagent','resource':'*','effect':'deny'}], 'steps':3}}
    }
    config_file=folder/'opencode.json'
    config_file.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    task_text=request.read_text(encoding='utf-8-sig')
    if len(task_text)>12000:
        raise ValueError('Task instructions exceed the bounded Windows command-line allowance')
    prompt='Do not use tools or modify any files. Return text. Treat input_ files as source material. Perform this user task:\n'+task_text
    (folder/'REQUEST.md').write_text(task_text,encoding='utf-8')
    snapshots=[folder/'REQUEST.md']
    inputs=[]
    for i,p in enumerate(files):
        copied=folder/f'input_{i:02d}_{p.name}'
        copied.write_bytes(p.read_bytes()); snapshots.append(copied)
        inputs.append({'source':str(p),'sha256':sha(p),'snapshot':copied.name})
    env=os.environ.copy()
    env.update({'OPENCODE_CONFIG':str(config_file),'OPENCODE_CONFIG_CONTENT':json.dumps(config),'XDG_CONFIG_HOME':str(folder/'config'),
        'OPENCODE_AUTO_SHARE':'false','OPENCODE_DISABLE_AUTOUPDATE':'true',
        'OPENCODE_DISABLE_DEFAULT_PLUGINS':'true','OPENCODE_DISABLE_LSP_DOWNLOAD':'true',
        'OPENCODE_DISABLE_CLAUDE_CODE':'true','OPENCODE_DISABLE_TERMINAL_TITLE':'true',
        'OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX':'8000'})
    catalog_process=subprocess.run([str(EXE),'api','--standalone','GET','/api/model'],
        cwd=folder,env=env,capture_output=True,timeout=30,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if catalog_process.returncode:raise RuntimeError('Live model catalog could not be verified')
    catalog=json.loads(catalog_process.stdout.decode('utf-8'))['data']
    selector, variant, settings, effort_status, entry=resolve_highest_free(catalog,args.model)
    # A root model alone drops the variant in V2. Set explicit run/agent selectors
    # and model settings for ancillary requests using small_model as well.
    config['agents']['plan']['model']=selector
    config['agents']['title']={'model':selector}
    config['providers']={'opencode':{'models':{args.model.split('/')[1]:{'settings':settings}}}}
    config_file.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    env['OPENCODE_CONFIG_CONTENT']=json.dumps(config)
    (folder/'catalog_selection.json').write_text(json.dumps({'selected_model':entry,'selector':selector,
        'effort_status':effort_status},ensure_ascii=False,indent=2),encoding='utf-8')
    cmd=[str(EXE),'run','--standalone','--model',selector,'--agent','plan',
        '--format','json','--title','Campaign bounded Space Bunny review',prompt]
    for p in snapshots:
        cmd+=['--file',str(p)]
    record={'model':args.model,'variant':variant,'selector':selector,'effort_policy':'highest_supported',
        'effort_status':effort_status,'variant_settings':settings,'catalog_price_verified_zero':True,
        'exe_sha256':sha(EXE),'inputs':inputs,
        'started_utc':datetime.now(timezone.utc).isoformat(),'seconds_limit':args.seconds,
        'status':'running','paid_fallback':False,'tools':'ask_all_deny_edit_and_subagent_no_auto_approval'}
    started=time.monotonic()
    with (folder/'events.jsonl').open('wb') as stdout,(folder/'stderr.log').open('wb') as stderr:
        proc=subprocess.Popen(cmd,cwd=folder,env=env,stdout=stdout,stderr=stderr,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        record['pid']=proc.pid
        record['creation_epoch']=psutil.Process(proc.pid).create_time()
        (folder/'state.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print('OpenCode task: '+str(folder),flush=True)
        try:
            proc.wait(timeout=args.seconds)
        except subprocess.TimeoutExpired:
            parent=psutil.Process(proc.pid)
            if abs(parent.create_time()-record['creation_epoch']) < .01:
                children=parent.children(recursive=True)
                for child in reversed(children):
                    try: child.terminate()
                    except psutil.NoSuchProcess: pass
                proc.terminate(); proc.wait(timeout=10)
            record['status']='time_limit'
    texts=[]; failures=[]; costs=[]; models=[]; sessions=set()
    for line in (folder/'events.jsonl').read_text(encoding='utf-8',errors='replace').splitlines():
        try: item=json.loads(line)
        except ValueError: continue
        if item.get('sessionID'):sessions.add(item['sessionID'])
        if item.get('type')=='text': texts.append(item.get('part',{}).get('text',''))
        if item.get('type')=='error': failures.append(item)
        if item.get('type')=='step_finish':
            part=item.get('part',{}); costs.append(part.get('cost')); models.append(part.get('modelID'))
    (folder/'result.md').write_text('\n\n'.join(texts),encoding='utf-8')
    record.update({'exit_code':proc.returncode,'elapsed_seconds':round(time.monotonic()-started,2),
        'source_unchanged':all(sha(i['source'])==i['sha256'] for i in inputs),
        'errors':failures,'reported_costs':costs,'reported_model_ids':models,'text_chars':sum(map(len,texts))})
    if record['status']=='running':
        record['status']='completed' if proc.returncode==0 and texts and not failures else 'failed'
    if record['status']=='completed':
        try:
            if len(sessions)!=1:raise RuntimeError('Expected exactly one model session')
            evidence=audit_session(folder,env,sessions.pop(),args.model,variant)
            record['verified_model_metadata']=evidence['assistant_metadata']
            record['verified_model_effort_and_zero_cost']=True
        except Exception as error:
            record.update(status='verification_failed',verification_error=str(error),
                verified_model_effort_and_zero_cost=False)
    (folder/'state.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'opencode_latest.json').write_text(json.dumps({'folder':str(folder),**record},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:record[k] for k in ['status','exit_code','text_chars','source_unchanged','elapsed_seconds']},ensure_ascii=False),flush=True)
    return 0 if record['status']=='completed' else 1

if __name__=='__main__':
    raise SystemExit(main())
