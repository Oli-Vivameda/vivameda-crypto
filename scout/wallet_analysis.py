"""Evidence-derived interpretations; no trading decisions."""
import json, time
from pathlib import Path
import requests
from wallet_intelligence import Store, render
from free_risk_evidence import valid

INFRA={"AMM","DEX","CEX","EXCHANGE","LOCKER","BURN"}
def analyse(result, db):
    labels={h["owner"]:h.get("provider_label") for h in result["holders"]}
    def role(address):
        if address==result.get("developer"): return "REPORTED_CREATOR"
        label=labels.get(address)
        return label.get("type","UNCLASSIFIED").upper() if isinstance(label,dict) else "UNCLASSIFIED"
    infra={a for a in labels if role(a) in INFRA}
    positions=[]
    for h in result["holders"]:
        positions.append(dict(h,role=role(h["owner"]),excluded_from_unclassified_concentration=h["owner"] in infra))
    eligible=[h for h in positions if not h["excluded_from_unclassified_concentration"]]
    creator=result.get("developer")
    # Include previously indexed creator events even when current holder set changes.
    historical=db.execute("SELECT DISTINCT e.body FROM events e JOIN signatures s ON s.sig=e.sig WHERE s.wallet=?",(creator,)).fetchall()
    creator_events=[json.loads(row[0]) for row in historical]
    withdrawals=[e for e in creator_events if e["relation"]=="pump_amm_withdraw" and e["source"]==creator]
    mints={}
    for event in creator_events:
        if event["relation"]=="mint_authority_at_initialization":
            authority=event["source"]==creator
            signed=creator in event.get("transaction_signers",[])
            if authority or signed:
                mints.setdefault(event["target"],[]).append({"signature":event["signature"],
                    "block_time":event.get("block_time"),"authority_match":authority,"signed_transaction":signed})
    events=result["events"]
    direct=[e for e in events if e["source"]==creator and
        e["target"] in {h["owner"] for h in eligible} and
        (e["relation"]=="native_transfer" or (e["relation"]=="token_transfer" and e.get("owner_resolution")))]
    funders={}
    selected={h["owner"] for h in eligible}
    for e in events:
        if e["relation"]=="native_transfer" and e["source"] not in infra and e["target"] in selected:
            funders.setdefault(e["source"],set()).add(e["target"])
    shared=[{"sender":a,"recipients":sorted(v),"sender_role":role(a),
             "meaning":"observed transfers; shared control unproven"}
            for a,v in funders.items() if len(v)>1]
    coverage=[]
    for wallet in result["wallet_histories"]:
        address=wallet["wallet"]
        total=wallet["successful_signatures_indexed"]
        decoded=db.execute("SELECT count(*) FROM signatures s JOIN tx t ON t.sig=s.sig WHERE s.wallet=? AND s.failed=0",(address,)).fetchone()[0]
        coverage.append(dict(wallet,transactions_available=decoded,
            indexed_transactions_pending=max(0,total-decoded),role=role(address),
            observed_activity_age_lower_bound_seconds=max(0,result["generated_at"]-wallet["earliest_observed"]) if wallet["earliest_observed"] else None))
    result["holder_roles"]=positions
    result["concentration"]={"unclassified_top10_reported_pct":sum(h["reported_pct"] for h in eligible[:10]),
        "labelled_infrastructure_reported_pct":sum(h["reported_pct"] for h in positions if h["excluded_from_unclassified_concentration"]),
        "scope":"provider top-account sample; labels not independently verified; unclassified includes unknown programs"}
    result["wallet_histories"]=coverage
    result["developer_history"]={"reported_developer":creator,"associated_mint_initializations":[
        {"mint":m,"evidence":e} for m,e in mints.items()],
        "creator_to_holder_transfers":direct,"complete":False,
        "attribution":"authority/signature association, not verified identity",
        "liquidity_removal_history":{"coverage":"partial_supported_protocol_history",
            "observed_pump_amm_withdrawals":withdrawals,"interpretation":"withdrawal is not proof of rug or misconduct"},
        "observed_pump_amm_sales":[e for e in events if e["relation"]=="pump_amm_sell"]}
    result["shared_senders"]=shared
    result["admission"]={"status":"HOLD","reason":"partial history and unverified trading/liquidity controls",
                         "production_alerts_affected":False}
    return result

def enrich(result,root,max_prior=2):
    root=Path(root); store=Store(root/"wallets.sqlite")
    result=analyse(result,store.db)
    session=requests.Session();session.headers["User-Agent"]="Vivameda-Wallet-Intelligence/1.0"
    prior=[]
    try:
        for row in result["developer_history"]["associated_mint_initializations"]:
            mint=row["mint"]
            if mint==result["mint"] or not valid(mint): continue
            if len(prior)>=max_prior: break
            source="rugcheck:"+mint
            saved=store.db.execute("SELECT observed,body FROM evidence WHERE source=? ORDER BY observed DESC LIMIT 1",(source,)).fetchone()
            cached=bool(saved and time.time()-saved[0]<3600)
            if cached: report=json.loads(saved[1]); observed=saved[0]
            else:
                time.sleep(1.1)
                try:
                    r=session.get("https://api.rugcheck.xyz/v1/tokens/"+mint+"/report",timeout=15)
                    r.raise_for_status();report=r.json()
                    if report.get("mint")!=mint: raise ValueError("wrong mint")
                    store.evidence(source,report);observed=int(time.time())
                except (requests.RequestException,ValueError):
                    prior.append({"mint":mint,"status":"UNAVAILABLE"});break
            prior.append({"mint":mint,"provider_rugged_flag":report.get("rugged"),
                "provider_risks":report.get("risks"),"observed_at":observed,
                "provider_detected_at":report.get("detectedAt"),
                "interpretation":"provider report, not independently verified rug attribution"})
    finally:
        session.close();store.db.close()
    result["developer_history"]["associated_token_reports"]=prior
    result["schema"]="wallet-intelligence-v2"
    path=root/(result["mint"]+".json")
    tmp=path.with_suffix(".json.tmp");tmp.write_text(json.dumps(result,indent=2));tmp.replace(path)
    render(result,root/(result["mint"]+".html"))
    return result
