"""One bounded queued research pass; driven by systemd timer, no Telegram."""
import argparse, fcntl, html, json, shutil, sqlite3, time
from pathlib import Path
from full_screening import collect as collect_full
from free_risk_evidence import valid, candidate_retry_delay, transient_issue
def focus_research(db,eligible,current,now):
    """One stable 15-minute focus; every fourth eligible pass explores the queue."""
    db.execute("CREATE TABLE IF NOT EXISTS research_focus(id INTEGER PRIMARY KEY CHECK(id=1),mint TEXT,identity TEXT,until_ts INTEGER,passes INTEGER)")
    rows={r[0]:r for r in eligible if r[0] in current}
    if not rows:return None
    focus=db.execute("SELECT mint,identity,until_ts,passes FROM research_focus WHERE id=1").fetchone()
    def identity(mint):return json.dumps([current[mint].get("pair"),current[mint].get("creator")])
    def viable(mint):
        status=db.execute("SELECT last_status FROM queue WHERE mint=?",(mint,)).fetchone()
        return mint in current and not (status and status[0]=="SCREENED_REJECT")
    valid_focus=bool(focus and focus[0] in current and identity(focus[0])==focus[1] and now<focus[2] and viable(focus[0]))
    if not valid_focus:
        candidates=[r for r in eligible if r[0] in current and viable(r[0])]
        # Rotate after a lease, even if the old token still has highest priority.
        alternatives=[r for r in candidates if not focus or r[0]!=focus[0]]
        if alternatives:candidates=alternatives
        if not candidates:
            db.execute("DELETE FROM research_focus");db.commit()
            return next(iter(rows.values()))
        chosen=max(candidates,key=lambda r:int(current[r[0]].get("screening_priority",0)))
        focus=(chosen[0],identity(chosen[0]),now+900,0)
    passes=focus[3]+1
    db.execute("INSERT OR REPLACE INTO research_focus VALUES(1,?,?,?,?)",(focus[0],focus[1],focus[2],passes));db.commit()
    if passes%4==0:
        other=next((r for r in eligible if r[0] in current and r[0]!=focus[0]),None)
        if other:return other
    # Respect the existing candidate backoff; never force a not-due focus.
    return rows.get(focus[0],next(iter(rows.values())))

def cycle(inbox,root,now=None,research=True,rpc_budget=None):
    now=int(time.time()) if now is None else now
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    lock=(root/"worker.lock").open("w")
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: lock.close();return {"status":"already_running"}
    db=None
    try:
        if shutil.disk_usage(root).free < 3*1024**3: return {"status":"capacity_hold"}
        if sum(p.stat().st_size for p in root.glob("*") if p.is_file()) > 2*1024**3: return {"status":"evidence_quota_hold"}
        payload=json.loads(Path(inbox).read_text())
        ts=payload.get("exported_at")
        if type(ts) is not int or not 0<=now-ts<=300: return {"status":"stale_candidate_feed"}
        db=sqlite3.connect(root/"queue.sqlite")
        db.executescript("""CREATE TABLE IF NOT EXISTS queue(mint TEXT PRIMARY KEY,seen INTEGER,next_due INTEGER DEFAULT 0,attempts INTEGER DEFAULT 0,last_status TEXT);
        CREATE TABLE IF NOT EXISTS control(key TEXT PRIMARY KEY,value INTEGER);""")
        if "priority" not in {r[1] for r in db.execute("PRAGMA table_info(queue)")}:
            db.execute("ALTER TABLE queue ADD COLUMN priority INTEGER DEFAULT 0")
        columns={r[1] for r in db.execute("PRAGMA table_info(queue)")}
        if "research_due" not in columns:db.execute("ALTER TABLE queue ADD COLUMN research_due INTEGER DEFAULT 0")
        if "identity" not in columns:db.execute("ALTER TABLE queue ADD COLUMN identity TEXT")
        candidates=payload.get("candidates",[])[:40]
        current={item.get("mint"):item for item in candidates
                 if all(valid(item.get(k)) for k in ("mint","pair","creator"))}
        deferred=list(payload.get("deferred_identities",[]))
        deferred.extend({"mint":i.get("mint"),"reason":"missing_pair_or_creator"} for i in candidates
                        if valid(i.get("mint")) and i.get("mint") not in current)
        deferred_path=root/"identity_pending.json"
        tmp=deferred_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"checked_at":now,"count":len(deferred),"candidates":deferred}))
        tmp.replace(deferred_path)
        for item in current.values():
            mint=item.get("mint")
            if valid(mint):
                identity=json.dumps([item.get("pair"),item.get("creator")])
                db.execute("""INSERT INTO queue(mint,seen,priority,identity) VALUES(?,?,?,?)
                    ON CONFLICT(mint) DO UPDATE SET seen=excluded.seen,priority=excluded.priority,
                    next_due=CASE WHEN queue.identity IS NOT NULL AND queue.identity!=excluded.identity THEN 0 ELSE queue.next_due END,
                    research_due=CASE WHEN queue.identity IS NOT NULL AND queue.identity!=excluded.identity THEN 0 ELSE queue.research_due END,
                    attempts=CASE WHEN queue.identity IS NOT NULL AND queue.identity!=excluded.identity THEN 0 ELSE queue.attempts END,
                    identity=excluded.identity""",(mint,now,int(item.get("screening_priority",0)),identity))
        # Retire legacy global freezes once, preserving bounded candidate backoff.
        if not db.execute("SELECT 1 FROM control WHERE key='candidate_backoff_v2'").fetchone():
            db.execute("UPDATE queue SET next_due=? WHERE next_due>?",(now+120,now+600))
            db.execute("INSERT OR REPLACE INTO control VALUES('candidate_backoff_v2',?)",(now,))
        db.execute("DELETE FROM control WHERE key='cooldown'")
        db.commit()
        ordering="research_due,next_due,priority DESC,seen DESC" if research else "priority DESC,next_due,seen DESC"
        eligible=db.execute("SELECT mint,attempts FROM queue WHERE next_due<=? ORDER BY "+ordering,(now,)).fetchall()
        selected=focus_research(db,eligible,current,now) if research else next((row for row in eligible if row[0] in current),None)
        if not research:
            # Fast refresh of another token must not postpone the focused research.
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='research_focus'").fetchone()
            focus=db.execute("SELECT mint,until_ts FROM research_focus WHERE id=1").fetchone() if exists else None
            if focus and now<focus[1]:
                selected=next((row for row in eligible if row[0] in current and row[0]!=focus[0]),None)
        if not selected: return {"status":"idle","identity_pending":len(deferred)}
        mint,attempts=selected
        # Lease before network work prevents tight retry loops after a crash.
        db.execute("UPDATE queue SET next_due=?,last_status='RUNNING' WHERE mint=?",(now+600,mint));db.commit()
        try:
            candidate=current[mint]
            result=collect_full(mint,candidate.get("creator"),candidate.get("pair"),root,
                budget=(80 if research else 40) if rpc_budget is None else min(80,max(1,rpc_budget)),research=research,time_budget=(140 if research else 60) if rpc_budget is None else (90 if research else 45))
            failed=any(transient_issue(x) for x in result["issues"])
            status="PARTIAL_PROVIDER_ERROR" if failed else "SCREENED_"+result.get("screening",{}).get("verdict","HOLD")
            unsupported="ValueError:unsupported_pool_mints" in result["issues"]
            delay=1800 if unsupported else (candidate_retry_delay(attempts) if failed else 120)
            if result.get("fast_refresh_deferred"):delay=120
            db.execute("UPDATE queue SET next_due=?,attempts=?,last_status=? WHERE mint=?",
                (int(time.time())+delay,attempts+1 if failed else 0,status,mint))
            if research:db.execute("UPDATE queue SET research_due=? WHERE mint=?",(int(time.time())+600,mint))
            db.commit()
            links=[]
            for path in sorted(root.glob("*.html")):
                if valid(path.stem): links.append('<li><a href="'+path.name+'">'+path.stem+'</a></li>')
            (root/"index.html").write_text('<!doctype html><meta charset="utf-8"><title>Vivameda Wallet Intelligence</title><h1>Wallet Intelligence</h1><p>Bounded screening · PASS / HOLD / REJECT · scanner independently evaluates eligibility</p><ul>'+''.join(links)+'</ul>')
            return {"status":status,"mint":mint,"collection_lane":"research" if research else "fast","retry_scope":"candidate","retry_after_seconds":delay,"events":len(result["events"]),"wallets":len(result["wallet_histories"]),"issues":result["issues"],
                "rpc_requests_used":result.get("rpc_requests_used"),
                "history_coverage":result.get("screening_packet",{}).get("history",{}).get("coverage_summary",{}),
                "index_metrics":result.get("screening_packet",{}).get("history",{}).get("index_metrics",{}),
                "verdict":result.get("screening",{}).get("verdict","HOLD"),
                "checks":{k:v.get("status") for k,v in result.get("screening",{}).get("checks",{}).items()}}
        except Exception as exc:
            db.execute("UPDATE queue SET next_due=?,attempts=attempts+1,last_status='ERROR' WHERE mint=?",(int(time.time())+candidate_retry_delay(attempts),mint))
            db.commit()
            return {"status":"ERROR","mint":mint,"error_type":type(exc).__name__,
                    "retry_scope":"candidate","retry_after_seconds":candidate_retry_delay(attempts)}
    finally:
        if db: db.close()
        lock.close()

def run_batch(inbox,root):
    """Research then fast refresh every invocation; 60 research RPC plus 20 fast RPC, 80 total."""
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/"batch.lock").open("w") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {"status":"already_running"}
        started=time.monotonic();runs=[]
        # Research includes mandatory checks. Run it first so fast refresh cannot
        # consume the only due candidate and repeatedly postpone its history.
        for research in (True,False):
            result=cycle(inbox,root,research=research,rpc_budget=60 if research else 20);runs.append(result)
            if result["status"] in ("already_running","capacity_hold","evidence_quota_hold","stale_candidate_feed"):break
        out_result=next((r for r in reversed(runs) if r["status"]!="idle"),runs[-1])
        out=dict(out_result)
        out["batch"]=[{"mint":r.get("mint"),"status":r["status"],"collection_lane":r.get("collection_lane")} for r in runs]
        out["batch_elapsed_seconds"]=round(time.monotonic()-started,3)
        metrics=root/"capacity_observations.json"
        try:observations=json.loads(metrics.read_text())[-199:]
        except (OSError,ValueError,TypeError):observations=[]
        observations.append({"observed_at":int(time.time()),"elapsed_seconds":out["batch_elapsed_seconds"],
            "lane":"research_then_fast",
            "runs":[{k:r.get(k) for k in ("mint","status","rpc_requests_used","history_coverage","index_metrics")} for r in runs]})
        tmp=metrics.with_suffix(".tmp");tmp.write_text(json.dumps(observations));tmp.replace(metrics)
        return out

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--inbox",required=True);p.add_argument("--output",required=True);a=p.parse_args()
    result=run_batch(a.inbox,a.output)
    Path(a.output,"worker_status.json").write_text(json.dumps(dict(result,checked_at=int(time.time())),indent=2))
    print(json.dumps(result))
