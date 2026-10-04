#!/usr/bin/env python3
"""One-time owner-run installer for fixed wallet connector operations."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile,time
from pathlib import Path
EXPECTED="1f212c7a2fc489ff1fdf30e46619038f89d942d9bd442b6d90a0d027180b8c37"
TOOLS='''
@mcp.tool(annotations={'readOnlyHint':True,'openWorldHint':False})
async def wallet_status()->dict:
    """Read wallet worker status and bounded screening reasons; no credentials or writes."""
    require_owner();return await asyncio.to_thread(helper,{'op':'wallet_status'})

@mcp.tool(annotations={'readOnlyHint':True,'openWorldHint':False})
async def wallet_release()->dict:
    """Hash existing wallet collector source for owner-reviewed deployment."""
    require_owner();return await asyncio.to_thread(helper,{'op':'wallet_release'})

@mcp.tool(annotations={'destructiveHint':True,'openWorldHint':False})
async def deploy_wallet(expected_sha256:str)->dict:
    """Deploy reviewed wallet source only, with tests, backup and worker health check. No unit or permission changes."""
    require_owner()
    result=await asyncio.to_thread(helper,{'op':'deploy_wallet','expected_sha256':expected_sha256})
    audit('deploy_wallet',expected_sha256)
    return result

'''
def patch(helper,server):
    if "import wallet_ops" not in helper:
        anchor="class Handler(socketserver.StreamRequestHandler):"
        if helper.count(anchor)!=1:raise ValueError("Helper anchor changed")
        helper=helper.replace(anchor,"import wallet_ops\n\n"+anchor)
        anchor="elif op=='crypto_status':result=crypto_status()"
        if helper.count(anchor)!=1:raise ValueError("Crypto status anchor changed")
        helper=helper.replace(anchor,anchor+";result['wallet']=wallet_ops.status()")
        anchor="elif op=='crypto_cases':"
        if helper.count(anchor)!=1:raise ValueError("Dispatch anchor changed")
        helper=helper.replace(anchor,
          "elif op=='wallet_status':result=wallet_ops.status()\n"
          "            elif op=='wallet_release':result=wallet_ops.release(child_call)\n"
          "            elif op=='deploy_wallet':result=wallet_ops.deploy(child_call,data.get('expected_sha256'))\n"
          "            "+anchor)
    if "async def wallet_status(" not in server:
        if server.count("def worker():")!=1:raise ValueError("Server anchor changed")
        server=server.replace("def worker():",TOOLS+"\ndef worker():")
    compile(helper,"helper.py","exec");compile(server,"server.py","exec")
    return helper,server
def write(p,raw):
    fd,name=tempfile.mkstemp(prefix=".connector-wallet-",dir=p.parent)
    try:
        with os.fdopen(fd,"wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.chown(name,0,0);os.chmod(name,0o644);os.replace(name,p)
    finally:
        if os.path.exists(name):os.unlink(name)
def restart():
    for unit in ("vivameda-engineering-helper.service","vivameda-connect.service"):
        subprocess.run(["/usr/bin/systemctl","restart",unit],check=True,timeout=30)
    time.sleep(2)
    for unit in ("vivameda-engineering-helper.service","vivameda-connect.service"):
        subprocess.run(["/usr/bin/systemctl","is-active","--quiet",unit],check=True,timeout=10)
def main():
    p=argparse.ArgumentParser();p.add_argument("--install",action="store_true");a=p.parse_args()
    base=Path(__file__).resolve().parent;source=base/"wallet_ops.py"
    if source.is_symlink():raise SystemExit("Source symlink refused")
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise SystemExit("Extension hash mismatch")
    if not a.install:
        patch((base/"helper.py").read_text(),(base/"server.py").read_text())
        print(json.dumps({"validated":True,"extension_sha256":EXPECTED,"installed":False}));return
    if os.geteuid()!=0:raise SystemExit("Run in the existing Hetzner root terminal")
    root=Path("/opt/vivameda-connect")
    if root.is_symlink() or root.stat().st_uid!=0 or root.stat().st_mode&0o022:raise SystemExit("Unsafe connector directory")
    for name in ("helper.py","server.py","wallet_ops.py"):
        q=root/name
        if q.is_symlink() or (q.exists() and (q.stat().st_uid!=0 or q.stat().st_mode&0o022)):raise SystemExit("Unsafe connector file")
    h,s=patch((root/"helper.py").read_text(),(root/"server.py").read_text())
    # Preserve current live files, including changes from other work.
    backup=Path(tempfile.mkdtemp(prefix="vivameda-connect-wallet-backup-",dir="/opt/vivameda-operations"))
    names=("helper.py","server.py","wallet_ops.py");previous={}
    for name in names:
        q=root/name;previous[name]=q.exists()
        if q.exists():shutil.copy2(q,backup/name)
    try:
        write(root/"wallet_ops.py",raw);write(root/"helper.py",h.encode());write(root/"server.py",s.encode())
        restart()
    except Exception:
        for name in names:
            if previous[name]:write(root/name,(backup/name).read_bytes())
            else:(root/name).unlink(missing_ok=True)
        restart();raise
    print(json.dumps({"installed":True,"backup":str(backup),"extension_sha256":EXPECTED,
        "tools":["wallet_status","wallet_release","deploy_wallet"],
        "existing_crypto_status_includes_wallet":True,"scanner_rules_changed":False}))
if __name__=="__main__":main()
