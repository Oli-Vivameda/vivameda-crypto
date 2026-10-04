"""Fixed-path wallet operations for the owner-authenticated connector.
Never executes engineering code as root. Source deploy runs only as wallet service.
"""
import base64,fcntl,hashlib,json,os,re,shutil,stat,subprocess,tempfile,time
from pathlib import Path
ROOT=Path("/opt/vivameda-wallet-intelligence")
DATA=Path("/var/lib/vivameda-wallet-intelligence/data")
BACKUPS=Path("/opt/vivameda-operations/wallet-source-backups")
REPO="server_source/vivameda-crypto-early-scout"
FILES=("free_risk_evidence.py","wallet_intelligence.py","wallet_analysis.py",
 "wallet_candidates.py","wallet_worker.py","protocol_screening.py","pool_screening.py",
 "full_screening.py","screening_policy.py")
UNITS=("vivameda-wallet-intelligence.timer","vivameda-wallet-intelligence.service",
 "vivameda-wallet-candidates.timer","vivameda-wallet-candidates.service")
CHECKS=("wallet_clusters","developer_history","top_holder_ownership","wallet_age",
 "token_controls","liquidity_control","trading_mechanics")
def read_json(p):
    # Fixed roots; no caller-controlled path. Refuse symlinks at every component.
    for part in (p,*p.parents):
        if part.is_symlink():raise ValueError("Symlink refused")
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,"rb") as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size>8*1024*1024:raise ValueError("Invalid report size/type")
        return json.load(f)
def status():
    out={"read_only":True,"checked_at":int(time.time()),"services":{},"reports":[]}
    for unit in UNITS:
        r=subprocess.run(["/usr/bin/systemctl","show",unit,"--property=ActiveState,SubState,Result,ExecMainStatus"],capture_output=True,text=True,timeout=10)
        out["services"][unit]=dict(line.split("=",1) for line in r.stdout.splitlines() if "=" in line)
    try:
        raw=read_json(DATA/"worker_status.json")
        out["worker"]={k:raw.get(k) for k in ("status","mint","events","wallets","issues","verdict","checks","checked_at","until")}
    except (OSError,ValueError):out["worker"]={"status":"unavailable"}
    try:
        paths=[p for p in DATA.iterdir() if re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}\.json",p.name) and not p.is_symlink()]
        for p in sorted(paths,key=lambda p:p.stat().st_mtime,reverse=True)[:20]:
            try:
                r=read_json(p);packet=r.get("screening_packet",{})
                checks=r.get("screening",{}).get("checks",{})
                out["reports"].append({"mint":r.get("mint"),"generated_at":r.get("generated_at"),
                  "schema":r.get("schema"),"issues":r.get("issues",[]),
                  "screening":{n:{k:checks.get(n,{}).get(k) for k in ("status","reason","details")} for n in CHECKS},
                  "coverage":{"wallets":len(packet.get("history",{}).get("wallets",[])),
                     "pool_authenticated":packet.get("pool",{}).get("authenticated"),
                     "creator_matches_pool":packet.get("pool",{}).get("state",{}).get("coin_creator")==packet.get("creator"),
                     "unseen_pct":packet.get("ownership",{}).get("unseen_pct"),
                     "sell_receipts":len(packet.get("trades",{}).get("sales",[]))}})
            except (OSError,ValueError,TypeError):out["reports"].append({"status":"unreadable_report"})
    except OSError:out["report_access"]="unavailable"
    out["diagnostics"]=diagnostics()
    return out
def bundle(child):
    script="import base64,json,pathlib;names="+repr(FILES)+";print(json.dumps({n:base64.b64encode(pathlib.Path(n).read_bytes()).decode() for n in names}))"
    r=child({"op":"command","argv":["python3","-c",script],"cwd":REPO})
    if r.get("state")!="succeeded":raise ValueError("Cannot read wallet source bundle")
    files=json.loads(r["output"])
    if set(files)!=set(FILES):raise ValueError("Invalid bundle files")
    raw={n:base64.b64decode(files[n],validate=True) for n in FILES}
    if sum(map(len,raw.values()))>512*1024:raise ValueError("Source bundle too large")
    digest=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return digest,raw
def release(child):
    digest,raw=bundle(child)
    return {"sha256":digest,"files":{n:hashlib.sha256(v).hexdigest() for n,v in raw.items()},
       "target":"Existing wallet collector Python source only; no units, permissions, credentials or scanner"}
def atomic(p,raw):
    if p.is_symlink() or p.parent.is_symlink():raise ValueError("Symlink target refused")
    fd,name=tempfile.mkstemp(prefix=".wallet-",dir=p.parent)
    try:
        with os.fdopen(fd,"wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.chown(name,0,0);os.chmod(name,0o644);os.replace(name,p)
    finally:
        if os.path.exists(name):os.unlink(name)
def ctl(action,unit):
    subprocess.run(["/usr/bin/systemctl",action,unit],check=True,capture_output=True,timeout=210)
def deploy(child,expected):
    if not isinstance(expected,str) or not re.fullmatch("[0-9a-f]{64}",expected):raise ValueError("Invalid reviewed hash")
    with open("/run/vivameda-engineering/wallet-deploy.lock","a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        digest,raw=bundle(child)
        if digest!=expected:raise ValueError("Reviewed hash mismatch")
        for n,v in raw.items():compile(v,n,"exec")
        tests=child({"op":"command","argv":["python3","-m","unittest",
          "test_wallet_intelligence","test_wallet_pipeline","test_full_screening",
          "test_prealert_risk","test_protocol_screening","test_wallet_telegram"],"cwd":REPO})
        if tests.get("state")!="succeeded":raise ValueError("Wallet tests failed")
        if bundle(child)[0]!=expected:raise ValueError("Source changed during tests")
        for p in (ROOT,BACKUPS.parent):
            if p.is_symlink() or p.stat().st_uid!=0 or p.stat().st_mode&0o022:raise ValueError("Unsafe deployment directory")
        for n in FILES:
            p=ROOT/n
            if p.is_symlink() or not p.is_file() or p.stat().st_uid!=0:raise ValueError("Expected root-owned installed file missing")
        BACKUPS.mkdir(mode=0o700,exist_ok=True)
        if BACKUPS.is_symlink() or BACKUPS.stat().st_uid!=0 or BACKUPS.stat().st_mode&0o022:raise ValueError("Unsafe backup directory")
        backup=Path(tempfile.mkdtemp(prefix=time.strftime("%Y%m%dT%H%M%SZ-"),dir=BACKUPS))
        for n in FILES:shutil.copy2(ROOT/n,backup/n)
        timers={u:subprocess.run(["/usr/bin/systemctl","is-active","--quiet",u]).returncode==0 for u in UNITS if u.endswith(".timer")}
        started=int(time.time());changed=False
        try:
            for u in timers:ctl("stop",u)
            ctl("stop","vivameda-wallet-intelligence.service")
            ctl("stop","vivameda-wallet-candidates.service")
            changed=True
            for n,v in raw.items():atomic(ROOT/n,v)
            ctl("start","vivameda-wallet-candidates.service")
            ctl("start","vivameda-wallet-intelligence.service")
            worker=read_json(DATA/"worker_status.json")
            if type(worker.get("checked_at")) is not int or worker["checked_at"]<started or worker.get("status") not in {
                "idle","provider_cooldown","PARTIAL_PROVIDER_ERROR","SCREENED_PASS","SCREENED_HOLD","SCREENED_REJECT"}:
                raise ValueError("Worker did not produce a fresh valid status")
        except Exception:
            if changed:
                ctl("stop","vivameda-wallet-intelligence.service")
                for n in FILES:atomic(ROOT/n,(backup/n).read_bytes())
            raise ValueError("Wallet deployment failed; prior source restored where changed")
        finally:
            for u,was_active in timers.items():
                if was_active:ctl("start",u)
        return {"deployed_sha256":expected,"backup_id":backup.name,"worker":worker,
                "screening_pass_verified":worker.get("status")=="SCREENED_PASS",
                "tests":tests["output"],"scanner_changed":False}

# Bounded numeric diagnostics only; no database access, transactions or credentials.
COVERAGE_KEYS=("owners_required","owners_observed","owners_missing","addresses_required",
 "addresses_observed","owners_complete_fresh","owners_with_activity_age")
INDEX_KEYS=("transaction_attempts","shared_transaction_bodies","indexed_addresses")
def numbers(value,keys):
    if not isinstance(value,dict):return {}
    return {k:value[k] for k in keys if type(value.get(k)) in (int,float) and 0<=value[k]<1e15}
def diagnostics():
    out={"read_only":True,"capacity_observations":[]}
    try:
        raw=read_json(DATA/"capacity_observations.json")
        if not isinstance(raw,list):raise ValueError("Invalid capacity observations")
        for entry in raw[-20:]:
            if not isinstance(entry,dict):continue
            item=numbers(entry,("observed_at","elapsed_seconds"));item["runs"]=[]
            runs=entry.get("runs",[])
            for run in (runs[:2] if isinstance(runs,list) else []):
                if not isinstance(run,dict):continue
                row=numbers(run,("rpc_requests_used",))
                row["status"]=run.get("status") if run.get("status") in {
                    "idle","ERROR","PARTIAL_PROVIDER_ERROR","SCREENED_PASS",
                    "SCREENED_HOLD","SCREENED_REJECT","capacity_hold","evidence_quota_hold",
                    "stale_candidate_feed","already_running"} else "unknown"
                row["history_coverage"]=numbers(run.get("history_coverage"),COVERAGE_KEYS)
                row["index_metrics"]=numbers(run.get("index_metrics"),INDEX_KEYS)
                item["runs"].append(row)
            out["capacity_observations"].append(item)
    except (OSError,ValueError,TypeError):out["capacity_access"]="unavailable"
    try:
        out["identity_pending"]=numbers(read_json(DATA/"identity_pending.json"),("checked_at","count"))
    except (OSError,ValueError,TypeError):out["identity_pending"]={"status":"unavailable"}
    return out
