#!/usr/bin/env python3
"""Offline source integrity and complete isolated test-suite release gate."""
import hashlib,json,pathlib,re,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
def included(p):
    parts=p.relative_to(ROOT).parts
    return not any(x in {'.git','.venv','__pycache__','data','logs','numerical_training_v1'} for x in parts) and p.suffix!='.pyc' and p.name!='MANIFEST.json'
def main():
    data=json.loads((ROOT/'MANIFEST.json').read_text())
    actual={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and included(p)}
    if actual!=data['sha256']:
        changed=sorted(k for k in actual.keys()|data['sha256'].keys() if actual.get(k)!=data['sha256'].get(k))
        raise SystemExit('Manifest mismatch: '+', '.join(changed))
    started=time.monotonic(); results=[]
    directories=sorted({p.parent for p in ROOT.rglob('test_*.py') if included(p)})
    for directory in directories:
        # Separate processes prevent identically named historical modules sharing imports.
        label=str(directory.relative_to(ROOT))
        run=subprocess.run([sys.executable,'-m','unittest','discover','-s',label,'-p','test_*.py'],cwd=ROOT,capture_output=True,text=True,timeout=300)
        output=run.stdout+run.stderr
        count=re.search(r'Ran (\d+) tests?',output)
        results.append({'directory':label,'tests':int(count.group(1)) if count else 0,'passed':run.returncode==0 and count is not None})
        if not results[-1]['passed']:
            print(output,file=sys.stderr)
            raise SystemExit('Release blocked: test suite failed in '+label)
    if not directories:raise SystemExit('Release blocked: no test suites found')
    print(json.dumps({'verified_files':len(actual),'complete_live_setup':data['complete_live_setup'],'test_suites':results,'tests_total':sum(r['tests'] for r in results),'full_suite_passed':True,'elapsed_seconds':round(time.monotonic()-started,3)}))
if __name__=='__main__':main()
