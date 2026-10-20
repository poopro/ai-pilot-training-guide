"""Read-only semantic delivery gate. Never imports or executes generated code."""
from pathlib import Path
import argparse,ast,hashlib,json,re

def inspect_delivery(text):
    blocks=re.findall(r'```(?:python|py)?[ \t]*\n(.*?)```',text,re.S)
    if len(blocks)!=1:
        return {'delivery_complete':False,'reason':'expected_exactly_one_python_code_block'},None
    code=blocks[0]
    try:tree=ast.parse(code)
    except SyntaxError as e:
        return {'delivery_complete':False,'reason':'python_syntax_error','line':e.lineno},None
    funcs={n.name:n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    if 'run_case' not in funcs:
        return {'delivery_complete':False,'reason':'missing_run_case_function'},code
    args=[a.arg for a in funcs['run_case'].args.args]
    expected=['adapter','controller','case_spec','output_dir','clock','should_stop']
    if args[:6]!=expected:
        return {'delivery_complete':False,'reason':'run_case_protocol_mismatch','arguments':args},code
    return {'delivery_complete':True,'reason':'code_and_interface_delivered_only',
        'runtime_verified':False,'safety_verified':False,'calibration_executed':False,
        'code_lines':len(code.splitlines()),'functions':list(funcs)},code

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);a=p.parse_args()
    state=json.loads((a.folder/'state.json').read_text(encoding='utf-8'))
    if state['status']!='completed':raise SystemExit('Model transport is not terminal success; inspect same handle')
    if not state.get('verified_model_effort_and_zero_cost'):raise SystemExit('Model effort/cost not verified')
    result_path=a.folder/'result.md';v,code=inspect_delivery(result_path.read_text(encoding='utf-8'))
    v.update(transport_status=state['status'],selector=state['selector'],
        result_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(),
        generated_code_trusted=False,official_validation=False)
    if code is not None:
        (a.folder/'worker_draft_unreviewed.py').write_text(code,encoding='utf-8')
    (a.folder/'DELIVERY.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(v,ensure_ascii=False))
    raise SystemExit(0 if v['delivery_complete'] else 2)
