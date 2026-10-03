#!/usr/bin/env python3
"""Offline public-source integrity check."""
import hashlib,json,pathlib
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
    print(json.dumps({'verified_files':len(actual),'complete_live_setup':data['complete_live_setup']}))
if __name__=='__main__':main()
