#!/usr/bin/env python3
"""Install dedicated bounded screening collector services. Owner runs as root.
No scanner edits, permissions broadening, paid services or Telegram.
"""
import argparse, ast, grp, hashlib, json, os, pwd, shutil, subprocess, sys
from pathlib import Path
EXPECTED = {'free_risk_evidence.py': '49408c03b8814fa969c2427d8f8170a1b653d8682a5b6a9c6d7048d66846bc6a', 'wallet_intelligence.py': 'daaf6452ab817c95ab8dff1ac86cdf880d3b1ab94746c855b0ac6942be2b838f', 'wallet_analysis.py': '88696a881e71db5956de02a7783bcd220abcee5de84a99ed10cfaa64f6f36f90', 'wallet_candidates.py': '8b925165a887f32a45a3b5574b2682e67d51f628b39391ebca405f3286a2074c', 'wallet_worker.py': 'baaa4e66065625abab3233eb160a6b6ba3c92e901d3ed4c1a1701f3edd269ef7', 'vivameda-wallet-candidates.service': '26a8f81225d0c8fd15a733df8fd9e555474b698d86928ca187ec52533e20ac5a', 'vivameda-wallet-candidates.timer': '1df6353a7f6122459158ee128ab3c69af26b67085606cf12f92650dec64a34a0', 'vivameda-wallet-intelligence.service': '766541710a156071adb23665932e1a2c5d8945cf2de48d795f7295f4d143decc', 'vivameda-wallet-intelligence.timer': '8d4d24c579693cca5e0384ae1b65f3aea11d7d0144bb3cdd8027c17555211ef0', 'protocol_screening.py': 'ca049acdde2198e70d83a82d95552b4bd193116de0b4d28f64c34cd699827636', 'pool_screening.py': 'e5822988b2b0592e8eaf293b9748779acbaeabbca64c4c21825dd9cb57e2172f', 'full_screening.py': 'a10816f174a2afd7ba8aff923cff31914e3dda43acfd89843adf21266de6a2ad', 'screening_policy.py': 'd07690e75a3b64d4466f1334c5a1222f80dbde87b5c394db99a455d4b24d5ccd'}
BASE=Path(__file__).resolve().parent
APP=Path("/opt/vivameda-wallet-intelligence")
STATE=Path("/var/lib/vivameda-wallet-intelligence")
def command(*args):
    subprocess.run(args,check=True,timeout=240)
def validate():
    payload={}
    for name,digest in EXPECTED.items():
        p=BASE/name
        if p.is_symlink(): raise SystemExit("Refusing symlink: "+name)
        data=p.read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest: raise SystemExit("Source changed: "+name)
        if name.endswith(".py"): ast.parse(data.decode())
        payload[name]=data
    return payload
def directory(path,uid,gid,mode):
    if path.is_symlink(): raise SystemExit("Refusing symlink directory: "+str(path))
    path.mkdir(parents=True,exist_ok=True)
    os.chown(path,uid,gid);path.chmod(mode)
def write(path,data,mode=0o644):
    if path.is_symlink(): raise SystemExit("Refusing symlink: "+str(path))
    temp=path.with_name(path.name+".install-tmp")
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
    with os.fdopen(fd,"wb") as f: f.write(data)
    os.chown(temp,0,0);os.chmod(temp,mode);os.replace(temp,path)
def main():
    p=argparse.ArgumentParser();p.add_argument("--install",action="store_true");a=p.parse_args()
    payload=validate()
    if not a.install:
        print(json.dumps({"status":"validated","files":EXPECTED}));return
    if os.geteuid()!=0: raise SystemExit("Run --install in the Hetzner root terminal")
    pwd.getpwnam("vivameda-scout")
    command("/usr/bin/python3","-I","-c","import requests,sqlite3")
    try: wallet=pwd.getpwnam("vivameda-wallet")
    except KeyError:
        command("/usr/sbin/useradd","--system","--user-group","--home-dir",str(STATE),
                "--no-create-home","--shell","/usr/sbin/nologin","vivameda-wallet")
        wallet=pwd.getpwnam("vivameda-wallet")
    scout=pwd.getpwnam("vivameda-scout")
    # Existing dedicated account must not be privileged.
    if wallet.pw_uid==0 or wallet.pw_gid==0: raise SystemExit("Invalid dedicated account")
    directory(APP,0,0,0o755)
    directory(STATE,0,wallet.pw_gid,0o750)
    directory(STATE/"inbox",scout.pw_uid,wallet.pw_gid,0o750)
    directory(STATE/"data",wallet.pw_uid,wallet.pw_gid,0o750)
    # Stop only these new services/timers before replacing their source.
    for unit in ("vivameda-wallet-intelligence.timer","vivameda-wallet-candidates.timer",
                 "vivameda-wallet-intelligence.service","vivameda-wallet-candidates.service"):
        subprocess.run(["/usr/bin/systemctl","stop",unit],check=False,timeout=30,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for name,data in payload.items():
        if name.endswith(".py"): write(APP/name,data)
        else: write(Path("/etc/systemd/system")/name,data)
    write(APP/"release.json",json.dumps(EXPECTED,indent=2).encode())
    command("/usr/bin/systemd-analyze","verify",
        "/etc/systemd/system/vivameda-wallet-candidates.service",
        "/etc/systemd/system/vivameda-wallet-intelligence.service",
        "/etc/systemd/system/vivameda-wallet-candidates.timer",
        "/etc/systemd/system/vivameda-wallet-intelligence.timer")
    # Grant only the scanner service read access to the dedicated wallet group.
    dropin=Path("/etc/systemd/system/vivameda-early-scout.service.d")
    directory(dropin,0,0,0o755)
    write(dropin/"wallet-evidence.conf", ("[Service]" + chr(10) + "SupplementaryGroups=vivameda-wallet" + chr(10)).encode())
    command("/usr/bin/systemctl","daemon-reload")
    command("/usr/bin/systemctl","start","vivameda-wallet-candidates.service")
    command("/usr/bin/systemctl","start","vivameda-wallet-intelligence.service")
    status_path=STATE/"data"/"worker_status.json"
    status=json.loads(status_path.read_text())
    if status.get("status") not in {"idle","PARTIAL_RESEARCH","PARTIAL_PROVIDER_ERROR","provider_cooldown","SCREENED_PASS","SCREENED_HOLD","SCREENED_REJECT"}:
        raise SystemExit("Smoke test did not pass; timers not enabled: "+json.dumps(status))
    command("/usr/bin/systemctl","enable","--now","vivameda-wallet-candidates.timer","vivameda-wallet-intelligence.timer")
    command("/usr/bin/systemctl","restart","vivameda-early-scout.service")
    command("/usr/bin/systemctl","is-active","--quiet","vivameda-early-scout.service")
    print(json.dumps({"installed":True,"mode":"BOUNDED_SCREENING_V2","worker":status,
                     "maps":str(STATE/"data"/"index.html"),"telegram_gate":"collector installed; scanner independently enforces three mandatory PASS checks and blocks any explicit REJECT"},indent=2))
if __name__=="__main__":main()

