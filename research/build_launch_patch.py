"""Build a candidate only. Never edit the input or deployed scanner."""
import argparse, ast, hashlib, pathlib
from earlier_entry import SOURCE_SHA, require_python

HOOK='''    # Directive 3 passive launch path: post-stop reviewed owner install only.
    try:
        from launch_path import append_rows as _d3_append_rows
        _d3_append_rows(rows, now)
    except Exception:
        logging.error("LAUNCH_PATH_CAPTURE_FAILED")
'''
def build(source):
    if hashlib.sha256(source.encode()).hexdigest()!=SOURCE_SHA:raise ValueError('Reviewed base mismatch; rebase/review required')
    tree=ast.parse(source);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='upsert_pump')
    lines=source.splitlines(keepends=True);candidate=''.join(lines[:fn.end_lineno])+HOOK+''.join(lines[fn.end_lineno:])
    other=ast.parse(candidate)
    old={n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)}
    new={n.name:ast.dump(n,include_attributes=False) for n in other.body if isinstance(n,ast.FunctionDef)}
    if {k:v for k,v in old.items() if k!='upsert_pump'}!={k:v for k,v in new.items() if k!='upsert_pump'}:raise ValueError('Unrelated function changed')
    new_fn=next(n for n in other.body if isinstance(n,ast.FunctionDef) and n.name=='upsert_pump')
    if ast.dump(ast.Module(body=fn.body,type_ignores=[]),include_attributes=False)!=ast.dump(ast.Module(body=new_fn.body[:-1],type_ignores=[]),include_attributes=False):raise ValueError('Original upsert body changed')
    # AST is a same-interpreter comparison only; no scorer hash is regenerated.
    return candidate
def main():
    p=argparse.ArgumentParser();p.add_argument('base',type=pathlib.Path);p.add_argument('output',type=pathlib.Path);a=p.parse_args();require_python()
    if a.base.resolve()==a.output.resolve() or a.output.exists():raise SystemExit('New candidate output path required')
    a.output.write_text(build(a.base.read_text()));print(hashlib.sha256(a.output.read_bytes()).hexdigest())
if __name__=='__main__':main()

