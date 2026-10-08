"""Owner-only sanitized custody/postflight metadata. Never opens an archive DB."""
import json,pathlib,sys
ROOT=pathlib.Path('/var/lib/vivameda-snapshot-archive')
def receipt(root=ROOT):
    out={}
    for name in ('activation','first_copy_receipt','postflight','two_hour_postflight','timer_disabled','STOP'):
        p=root/(name+'.json')
        if p.exists():out[name]=json.loads(p.read_text())
    p=root/'runs.jsonl'
    if p.exists():
        with p.open('rb') as f:
            f.seek(0,2);f.seek(max(0,f.tell()-65536));lines=f.readlines()
        if lines:out['latest_run']=json.loads(lines[-1])
    return out
if __name__=='__main__':
    if sys.version_info[:2]!=(3,12):raise SystemExit('Python 3.12 required')
    print(json.dumps(receipt(),sort_keys=True))
