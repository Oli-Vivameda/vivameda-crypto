#!/usr/bin/env python3
"""Owner-run, read-only export of crypto source for private publication review.
No credentials/config/data reads, network, service changes or execution of source.
"""
import ast, hashlib, json, os, pathlib, pwd, re, stat, tempfile

ROOTS=(pathlib.Path('/opt/vivameda-crypto-watchlist'),pathlib.Path('/opt/vivameda-crypto-pool-monitor'))
LEGACY=pathlib.Path('/opt/vivameda-crypto-early-scout/scout_learning.py')
UNITS=('vivameda-watchlist.service','vivameda-watchlist.timer','vivameda-telegram-pool-monitor.service','vivameda-scout-learning.service')
SECRET_NAME=re.compile(r'password|secret|bot.?token|chat.?id|api.?key|private.?key|mnemonic|seed.?phrase',re.I)
SECRET_VALUE=re.compile(r'\b\d{7,12}:[A-Za-z0-9_-]{30,}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}')

def read_source(path):
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Symlink refused: '+str(path))
    st=path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size>2*1024*1024:
        raise ValueError('Not bounded regular source: '+str(path))
    text=path.read_text()
    if SECRET_VALUE.search(text):
        raise ValueError('Possible embedded secret; owner redaction required: '+path.name)
    if path.suffix=='.py':
        tree=ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node,(ast.Assign,ast.AnnAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                value=node.value
                if isinstance(value,ast.Constant) and value.value:
                    if any(isinstance(t,ast.Name) and SECRET_NAME.search(t.id) for t in targets):
                        raise ValueError('Sensitive literal needs owner review: '+path.name)
            if isinstance(node,ast.Dict):
                for key,value in zip(node.keys,node.values):
                    if isinstance(key,ast.Constant) and isinstance(key.value,str) and SECRET_NAME.search(key.value) and isinstance(value,ast.Constant) and value.value:
                        raise ValueError('Sensitive dictionary literal needs owner review: '+path.name)
    elif any(SECRET_NAME.search(line) for line in text.splitlines() if line.startswith('Environment=')):
        raise ValueError('Sensitive unit environment needs owner review: '+path.name)
    return text

def main():
    if os.geteuid()!=0: raise SystemExit('Run from the owner maintenance terminal as root.')
    owner=pwd.getpwnam('vivameda-engineer')
    if owner.pw_uid==0: raise SystemExit('Invalid engineering account')
    payload={}; missing=[]
    for root in ROOTS:
        if any(p.is_symlink() for p in (root,*root.parents)):raise ValueError('Symlink root refused')
        if not root.is_dir(): missing.append(str(root));continue
        for path in sorted(root.glob('*.py')):
            if SECRET_NAME.search(path.name) or 'credential' in path.name.lower():continue
            payload[root.name+'/'+path.name]=read_source(path)
    if LEGACY.exists():payload['legacy/scout_learning.py']=read_source(LEGACY)
    else:missing.append(str(LEGACY))
    for unit in UNITS:
        path=pathlib.Path('/etc/systemd/system')/unit
        if path.exists():payload['units/'+unit]=read_source(path)
        else:missing.append(str(path))
    if not payload:raise SystemExit('No source files found')
    dest=pathlib.Path(tempfile.mkdtemp(prefix='vivameda-crypto-source-review-',dir='/var/tmp'))
    manifest={}
    for name,text in payload.items():
        p=dest/name;p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        p.write_text(text);p.chmod(0o600)
        manifest[name]=hashlib.sha256(text.encode()).hexdigest()
    (dest/'MANIFEST.json').write_text(json.dumps({'private_review_only':True,'files':manifest,'missing':missing},indent=2))
    for p in sorted(dest.rglob('*'),reverse=True):
        os.chown(p,owner.pw_uid,owner.pw_gid);p.chmod(0o700 if p.is_dir() else 0o600)
    os.chown(dest,owner.pw_uid,owner.pw_gid);dest.chmod(0o700)
    print(json.dumps({'exported':len(payload),'directory':str(dest),'production_changed':False,'public_upload_performed':False,'missing':missing}))

if __name__=='__main__':main()
