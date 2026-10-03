#!/usr/bin/env python3
"""Owner-run, read-only crypto audit. No network, sends, service changes or credential files."""
import ast,datetime,hashlib,json,math,re,sqlite3,subprocess
from pathlib import Path
DENY=re.compile(r"secret|password|credential|private|seed|mnemonic|bot.?token|chat.?id|api.?key|authorization",re.I)
ALLOWED={"name","symbol","chain","chainid","mint","contract","address","pool","pair","pairaddress","quote",
         "enabled","threshold","threshold_pct","alert_pct","change_pct","interval","interval_seconds",
         "poll_seconds","cooldown_seconds","tokens","coins","watchlist","pools","markets"}
def public(value,key="",depth=0):
    if depth>6 or DENY.search(key):return None
    if isinstance(value,dict):
        out={}
        for k,v in value.items():
            if str(k).lower() in ALLOWED:
                clean=public(v,str(k),depth+1)
                if clean is not None:out[k]=clean
        return out or None
    if isinstance(value,list):
        out=[public(v,key,depth+1) for v in value[:100]]
        return [v for v in out if v is not None]
    if isinstance(value,bool):return value
    if type(value) in (int,float):
        return value if math.isfinite(value) and abs(value)<1e12 else None
    if isinstance(value,str):
        if re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}|0x[0-9a-fA-F]{40,64}",value):return value
        if key.lower() in {"name","symbol","chain","chainid","quote"} and re.fullmatch(r"[A-Za-z0-9 ._+%-]{1,30}",value):return value
    return None
def source_audit(path):
    out={"path":str(path)}
    try:
        raw=path.read_bytes();tree=ast.parse(raw);out["sha256"]=hashlib.sha256(raw).hexdigest()
        out["functions"]=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
        out["seven_check_reference"]=any(isinstance(n,ast.Name) and n.id in {"screen_packet","evaluate_prealert_review","collect_prealert_review"} for n in ast.walk(tree))
        out["telegram_api_reference"]=any(isinstance(n,ast.Constant) and isinstance(n.value,str) and "api.telegram.org" in n.value for n in ast.walk(tree))
        settings={}
        for n in tree.body:
            if not isinstance(n,ast.Assign):continue
            for target in n.targets:
                if not isinstance(target,ast.Name) or DENY.search(target.id):continue
                name=target.id.lower()
                if not (name in ALLOWED or any(x in name for x in ("threshold","interval","cooldown","poll","watchlist","pools"))):continue
                try:val=ast.literal_eval(n.value)
                except (ValueError,TypeError):continue
                clean=public(val,name)
                if clean is not None:settings[target.id]=clean
        out["public_settings"]=settings
        configs={}
        for name in ("config.json","watchlist.json","pools.json"):
            p=path.parent/name
            if p.is_file() and not p.is_symlink() and p.stat().st_size<=1024*1024:
                try:configs[name]=public(json.loads(p.read_text())) or {}
                except (OSError,ValueError):configs[name]={"readable":False}
        out["public_config_fields"]=configs
    except (OSError,SyntaxError):out["status"]="UNREADABLE"
    return out
def unit_audit(name):
    fields="Id,ActiveState,SubState,Result,ExecMainStatus,NRestarts,ExecMainStartTimestamp,ExecMainExitTimestamp"
    r=subprocess.run(["systemctl","show",name,"--property="+fields],capture_output=True,text=True,timeout=15)
    return dict(l.split("=",1) for l in r.stdout.splitlines() if "=" in l)
def journal_summary(unit):
    r=subprocess.run(["journalctl","-u",unit,"--since","2 hours ago","-n","300","-o","json","--no-pager"],capture_output=True,text=True,timeout=15)
    counts={k:0 for k in ("http_429","http_401","http_403","timeout","traceback","error_or_failed")}
    read=0;last=None
    for line in r.stdout.splitlines():
        try:row=json.loads(line)
        except ValueError:continue
        read+=1;msg=row.get("MESSAGE","").lower();last=row.get("__REALTIME_TIMESTAMP")
        for key,pattern in {"http_429":r"\b429\b","http_401":r"\b401\b","http_403":r"\b403\b","timeout":r"timeout|timed out","traceback":r"traceback","error_or_failed":r"\berror\b|\bfailed\b"}.items():
            counts[key]+=bool(re.search(pattern,msg))
    return {"records_examined":read,"last_record_unix_microseconds":last,"error_mentions":counts,"journal_exit":r.returncode}
def screening_audit():
    root=Path("/var/lib/vivameda-wallet-intelligence/data");out={}
    try:
        status=json.loads((root/"worker_status.json").read_text())
        out["worker"]={k:status[k] for k in ("status","until","checked_at","verdict","checks","error_type") if k in status}
        files=sorted((p for p in root.glob("*.json") if re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}",p.stem)),key=lambda p:p.stat().st_mtime,reverse=True)[:5]
        reports=[]
        for p in files:
            if p.is_symlink() or p.stat().st_size>8*1024*1024:continue
            v=json.loads(p.read_text());s=v.get("screening",{})
            reports.append({"mint":v.get("mint"),"generated_at":v.get("generated_at"),"schema":v.get("schema"),"verdict":s.get("verdict"),
                "checks":{k:{"status":x.get("status"),"reason":x.get("reason")} for k,x in s.get("checks",{}).items()}})
        out["recent_reports"]=reports
    except (OSError,ValueError):out["status"]="UNREADABLE"
    try:
        c=sqlite3.connect("file:/opt/vivameda-crypto-early-scout/data/early_scout.sqlite?mode=ro",uri=True)
        out["recent_gate_counts"]=dict(c.execute("SELECT verdict,count(*) FROM prealert_reviews WHERE checked_at>=strftime('%s','now')-7200 GROUP BY verdict"))
        c.close()
    except sqlite3.Error:out["gate_counts"]="UNAVAILABLE"
    return out
def main():
    units=["vivameda-telegram-pool-monitor.service","vivameda-watchlist.service","vivameda-watchlist.timer","vivameda-wallet-intelligence.service","vivameda-wallet-intelligence.timer"]
    result={"checked_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"read_only":True,
        "sources":[source_audit(Path(p)) for p in ("/opt/vivameda-crypto-pool-monitor/monitor.py","/opt/vivameda-crypto-watchlist/watch.py")],
        "units":[unit_audit(u) for u in units],"recent_journals":{u:journal_summary(u) for u in units if u.endswith(".service")},
        "screening":screening_audit()}
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
