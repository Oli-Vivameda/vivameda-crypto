"""Narrow read-only candidate export; run as existing scout user."""
import argparse, json, sqlite3, time
from pathlib import Path
from free_risk_evidence import valid
def export(db_path,destination,now=None):
    now=int(time.time()) if now is None else now
    con=sqlite3.connect("file:"+str(Path(db_path).resolve())+"?mode=ro",uri=True,timeout=5)
    try:
        rows=con.execute("""SELECT mint,creator,pinned_pair,alert_level,last_alert_ts
          FROM launches WHERE created_ts BETWEEN ? AND ?
          AND last_trade_ts>=? AND current_mc BETWEEN 30000 AND 750000
          ORDER BY alert_level DESC,last_trade_ts DESC LIMIT 200""",
          ((now-21600)*1000,(now-1800)*1000,(now-720)*1000)).fetchall()
        has_reviews=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='prealert_reviews'").fetchone()
        urgent={}
        if has_reviews:
            urgent={m:level for m,level in con.execute("SELECT mint,max(level) FROM prealert_reviews WHERE checked_at>=? GROUP BY mint",(now-900,))}
    finally: con.close()
    discovered=[dict(mint=m,creator=c,pair=p,alert_level=l,last_alert_ts=t) for m,c,p,l,t in rows if valid(m)]
    deferred=[dict(mint=i["mint"],reason="missing_pair_or_creator",
                   missing=[k for k in ("pair","creator") if not valid(i.get(k))]) for i in discovered if not all(valid(i.get(k)) for k in ("pair","creator"))]
    items=[i for i in discovered if all(valid(i.get(k)) for k in ("pair","creator"))]
    # Addresses are discovery hints; collect_full authenticates the pool on-chain.
    for item in items:item["identity_source"]="scanner_discovery_pending_onchain_authentication"
    for item in items:item["screening_priority"]=urgent.get(item["mint"],0)
    items.sort(key=lambda item:item["screening_priority"],reverse=True)
    items=items[:40]
    path=Path(destination);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".tmp");temp.write_text(json.dumps({"schema":1,"exported_at":now,"candidates":items,"deferred_identities":deferred,"identity_retry":"reconsidered on each scanner export"}))
    temp.chmod(0o640);temp.replace(path)
    print(json.dumps({"exported":len(items),"at":now}))
    return items
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--db",required=True);p.add_argument("--output",required=True);a=p.parse_args();export(a.db,a.output)
