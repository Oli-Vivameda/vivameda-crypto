"""Vivameda wallet intelligence v1: resumable, evidence-backed shadow graph.
No keys, paid providers, alerts, trades, or production DB writes.
"""
import argparse, base64, hashlib, html, json, math, sqlite3, time, zlib
from pathlib import Path
import requests
from free_risk_evidence import valid, holder_summary
from protocol_screening import protocol_events

RPC = "https://api.mainnet-beta.solana.com"
HISTORY_RPC = "https://solana-rpc.publicnode.com"
MAINNET_GENESIS = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d"
SYSTEM = "11111111111111111111111111111111"
TOKENS = {"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
          "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"}
def decode(tx, signature):
    """Only successful parsed instructions; preserve account/owner distinction."""
    if not isinstance(tx, dict) or not isinstance(tx.get("meta"),dict) or tx["meta"].get("err") is not None:
        return []
    meta=tx["meta"]; msg=tx.get("transaction",{}).get("message",{})
    keys=msg.get("accountKeys",[])
    addresses=[k.get("pubkey") if isinstance(k,dict) else k for k in keys]
    signers=[k["pubkey"] for k in keys if isinstance(k,dict) and k.get("signer")]
    owners={}
    for row in (meta.get("preTokenBalances") or [])+(meta.get("postTokenBalances") or []):
        idx=row.get("accountIndex")
        if isinstance(idx,int) and 0<=idx<len(addresses) and row.get("owner"):
            owners[addresses[idx]]=(row["owner"],row.get("mint"))
    instructions=list(enumerate(msg.get("instructions",[])))
    for group in meta.get("innerInstructions") or []:
        instructions += [(str(group["index"])+"."+str(i),v) for i,v in enumerate(group.get("instructions",[]))]
    events=protocol_events(tx, signature)
    for idx,ins in instructions:
        parsed=ins.get("parsed")
        if not isinstance(parsed,dict): continue
        info=parsed.get("info",{}); kind=parsed.get("type"); program=ins.get("programId")
        event={"signature":signature,"instruction":str(idx),"slot":tx.get("slot"),
               "block_time":tx.get("blockTime"),"kind":kind}
        if program==SYSTEM and kind in ("transfer","transferWithSeed"):
            event.update(source=info.get("source"),target=info.get("destination"),
                         asset="SOL",raw_amount=str(info.get("lamports")),relation="native_transfer")
        elif program in TOKENS and kind in ("transfer","transferChecked"):
            source,target=info.get("source"),info.get("destination")
            so,sm=owners.get(source,(None,None)); to,tm=owners.get(target,(None,None))
            event.update(source=so or source,target=to or target,
                source_account=source,target_account=target,owner_resolution=bool(so and to),
                asset=info.get("mint") or sm or tm,
                raw_amount=str(info.get("amount",info.get("tokenAmount",{}).get("amount"))),
                relation="token_transfer")
        elif program in TOKENS and kind in ("initializeMint","initializeMint2"):
            event.update(source=info.get("mintAuthority"),target=info.get("mint"),
                         relation="mint_authority_at_initialization",transaction_signers=signers)
        else: continue
        if valid(event.get("source")) and valid(event.get("target")): events.append(event)
    return events

class Store:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,source TEXT,observed INTEGER,body TEXT);
        CREATE TABLE IF NOT EXISTS signatures(wallet TEXT,sig TEXT,ts INTEGER,failed INTEGER,PRIMARY KEY(wallet,sig));
        CREATE TABLE IF NOT EXISTS cursors(wallet TEXT PRIMARY KEY,before_sig TEXT,exhausted INTEGER);
        CREATE TABLE IF NOT EXISTS tx(sig TEXT PRIMARY KEY,body TEXT);
        CREATE TABLE IF NOT EXISTS events(sig TEXT,idx TEXT,body TEXT,PRIMARY KEY(sig,idx));
        """)
    def evidence(self,source,data):
        body=json.dumps(data,sort_keys=True); key=hashlib.sha256((source+body).encode()).hexdigest()
        self.db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?,?,?)",(key,source,int(time.time()),body))
        self.db.commit(); return key

class Client:
    def __init__(self,store,budget):
        self.store=store; self.left=budget; self.session=requests.Session()
        self.session.headers["User-Agent"]="Vivameda-Wallet-Intelligence/1.0"
    def rpc(self,method,params):
        # This public endpoint was live-verified for history; indexed holder calls stay on RPC.
        endpoint=HISTORY_RPC if method in ("getTransaction","getSignaturesForAddress") else RPC
        if endpoint==HISTORY_RPC and not getattr(self,"history_chain_verified",False):
            if self._rpc_at("getGenesisHash",[],endpoint)!=MAINNET_GENESIS:
                raise RuntimeError("history_rpc_wrong_chain")
            self.history_chain_verified=True
        return self._rpc_at(method,params,endpoint)
    def _rpc_at(self,method,params,endpoint):
        if time.monotonic()>getattr(self,"deadline",float("inf"))-17:raise RuntimeError("research_time_budget")
        db=self.store.db
        db.execute("CREATE TABLE IF NOT EXISTS rpc_method_backoff(method TEXT PRIMARY KEY,until_ts REAL)")
        db.execute("UPDATE rpc_method_backoff SET method=?||method WHERE instr(method,'|')=0",(RPC+"|",));db.commit()
        key=endpoint+"|"+method
        cooldown=db.execute("SELECT until_ts FROM rpc_method_backoff WHERE method=?",(key,)).fetchone()
        if cooldown and cooldown[0]>time.time():raise RuntimeError("rpc_method_cooldown_"+method)
        if self.left<=0:raise RuntimeError("request_budget_exhausted")
        self.left-=1
        time.sleep(1.1)
        large=method=="getProgramAccounts"
        r=self.session.post(endpoint,json={"jsonrpc":"2.0","id":1,"method":method,"params":params},timeout=15,stream=large)
        try:
            if r.status_code==429:
                try:delay=max(120,float(r.headers.get("Retry-After",120)))
                except (TypeError,ValueError):delay=120
                if not math.isfinite(delay):delay=120
                db.execute("INSERT OR REPLACE INTO rpc_method_backoff VALUES(?,?)",(key,time.time()+delay));db.commit()
            r.raise_for_status()
            if large:
                chunks=[];size=0
                for chunk in r.iter_content(65536):
                    size+=len(chunk)
                    if size>8*1024*1024:raise RuntimeError("rpc_response_size_limit")
                    if time.monotonic()>getattr(self,"deadline",float("inf"))-5:raise RuntimeError("research_time_budget")
                    chunks.append(chunk)
                d=json.loads(b"".join(chunks))
            else:d=r.json()
        finally:r.close()
        if d.get("error"):
            code=d["error"].get("code") if isinstance(d["error"],dict) else None
            raise RuntimeError("rpc_error_code_" + str(code) + "_method_" + method)
        if "result" not in d:raise RuntimeError("rpc_missing_result")
        evidence=d
        if large:
            raw=json.dumps(d,sort_keys=True,separators=(",",":")).encode()
            evidence={"encoding":"zlib+base64","sha256":hashlib.sha256(raw).hexdigest(),
                      "data":base64.b64encode(zlib.compress(raw)).decode()}
        self.last_evidence_ref=self.store.evidence(endpoint+"|"+method+json.dumps(params),evidence)
        return d["result"]

def scan(mint,root,budget=12,wallet_limit=4):
    if not valid(mint): raise ValueError("invalid mint")
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    store=Store(root/"wallets.sqlite"); client=Client(store,budget)
    issues=[]; report={}; wallets=[]; holders=[]
    try:
        r=client.session.get("https://api.rugcheck.xyz/v1/tokens/"+mint+"/report",timeout=15)
        r.raise_for_status(); report=r.json()
        if report.get("mint")!=mint: raise ValueError("wrong mint")
        store.evidence("rugcheck:"+mint,report)
        holders=holder_summary(report)["owners"]
        creator=report.get("creator")
        if valid(creator): wallets.append(creator)
        for h in holders:
            label=h.get("provider_label")
            if isinstance(label,dict) and str(label.get("type","")).upper() in {"AMM","DEX","CEX","EXCHANGE","LOCKER","BURN"}:
                continue
            if h["owner"] not in wallets: wallets.append(h["owner"])
        wallets=wallets[:wallet_limit]
        # One backward page per wallet per run; durable cursor enables later continuation.
        for wallet in wallets:
            cursor=store.db.execute("SELECT before_sig,exhausted FROM cursors WHERE wallet=?",(wallet,)).fetchone()
            # Always refresh the head; separately continue the historical cursor.
            if cursor:
                head=client.rpc("getSignaturesForAddress",[wallet,{"limit":1000,"commitment":"finalized"}])
                if not isinstance(head,list): raise ValueError("invalid head")
                for row in head:
                    store.db.execute("INSERT OR IGNORE INTO signatures VALUES(?,?,?,?)",
                        (wallet,row["signature"],row.get("blockTime"),int(row.get("err") is not None)))
                store.db.commit()
                if cursor[1]: continue
            opts={"limit":1000,"commitment":"finalized"}
            if cursor and cursor[0]: opts["before"]=cursor[0]
            rows=client.rpc("getSignaturesForAddress",[wallet,opts])
            if not isinstance(rows,list): raise ValueError("invalid signatures")
            for row in rows:
                store.db.execute("INSERT OR IGNORE INTO signatures VALUES(?,?,?,?)",
                    (wallet,row["signature"],row.get("blockTime"),int(row.get("err") is not None)))
            before=rows[-1]["signature"] if rows else (cursor[0] if cursor else None)
            store.db.execute("INSERT OR REPLACE INTO cursors VALUES(?,?,?)",(wallet,before,int(len(rows)<1000)))
            store.db.commit()
        # Round-robin oldest observed and recent transactions, creator first.
        pending={}
        for wallet in wallets:
            rows=store.db.execute("SELECT sig FROM signatures WHERE wallet=? AND failed=0 AND sig NOT IN (SELECT sig FROM tx) ORDER BY ts",(wallet,)).fetchall()
            order=[]
            while rows:
                order.append(rows.pop(0)[0])
                if rows: order.append(rows.pop()[0])
            pending[wallet]=order
        while client.left and any(pending.values()):
            for wallet in wallets:
                if not client.left or not pending[wallet]: continue
                sig=pending[wallet].pop(0)
                tx=client.rpc("getTransaction",[sig,{"encoding":"jsonParsed","commitment":"finalized","maxSupportedTransactionVersion":0}])
                if tx is None:
                    issues.append("transaction_unavailable:"+sig); continue
                store.db.execute("INSERT OR REPLACE INTO tx VALUES(?,?)",(sig,json.dumps(tx)))
                for e in decode(tx,sig):
                    store.db.execute("INSERT OR REPLACE INTO events VALUES(?,?,?)",(sig,e["instruction"],json.dumps(e)))
                store.db.commit()
    except (requests.RequestException,ValueError,RuntimeError,KeyError,TypeError) as exc:
        issues.append(type(exc).__name__+":"+("rate_or_provider_error" if isinstance(exc,requests.RequestException) else str(exc)[:80]))
    finally: client.session.close()
    events=[json.loads(r[0]) for r in store.db.execute("SELECT DISTINCT e.body FROM events e JOIN signatures s ON s.sig=e.sig WHERE s.wallet IN ("+",".join("?"*len(wallets))+")",wallets)] if wallets else []
    histories=[]
    for wallet in wallets:
        n,old,new=store.db.execute("SELECT count(*),min(ts),max(ts) FROM signatures WHERE wallet=? AND failed=0",(wallet,)).fetchone()
        cur=store.db.execute("SELECT exhausted FROM cursors WHERE wallet=?",(wallet,)).fetchone()
        histories.append({"wallet":wallet,"successful_signatures_indexed":n,"earliest_observed":old,
            "latest_observed":new,"provider_page_end_reached":bool(cur and cur[0]),
            "full_history_verified":False,"wallet_creation_time":None})
    # Shared senders are evidence of transfers, never automatic common ownership.
    funding={}
    for e in events:
        if e["relation"]=="native_transfer" and e["target"] in wallets:
            funding.setdefault(e["source"],set()).add(e["target"])
    shared=[{"sender":k,"recipients":sorted(v),"interpretation":"shared_sender_not_proof_of_common_control"}
            for k,v in funding.items() if len(v)>1]
    result={"schema":"wallet-intelligence-v1","mint":mint,"mode":"SHADOW","verdict":"HOLD",
        "generated_at":int(time.time()),"rpc_requests_used":budget-client.left,
        "holders":holders,"wallet_histories":histories,"events":events,"shared_senders":shared,
        "developer":report.get("creator"),"provider_risks":report.get("risks"),"issues":issues,
        "coverage":"BOUNDED_PARTIAL","limitations":["Not BubbleMaps","No verified full lifetime history",
        "Transfers do not prove ownership or intent","Pools/exchanges not excluded from concentration",
        "Mint authority is not conclusive developer identity","No liquidity-removal or rug outcome classifier"]}
    dest=root/(mint+".json"); dest.write_text(json.dumps(result,indent=2))
    render(result,root/(mint+".html"))
    store.db.close()
    return result

def render(result,path):
    nodes=sorted({e[k] for e in result["events"] for k in ("source","target")}|{w["wallet"] for w in result["wallet_histories"]}|{h["owner"] for h in result.get("holders",[])})
    holdings={h["owner"]:h["reported_pct"] for h in result.get("holders",[])}
    roles={h["owner"]:h.get("provider_label") for h in result.get("holders",[])}
    positions={n:(450+340*math.cos(i*2*math.pi/max(1,len(nodes))),380+290*math.sin(i*2*math.pi/max(1,len(nodes)))) for i,n in enumerate(nodes)}
    svg=[]
    for e in result["events"]:
        x,y=positions[e["source"]]; a,b=positions[e["target"]]
        svg.append(f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#64748b"><title>{html.escape(e["relation"]+" | "+e["signature"])}</title></line>')
    for n,(x,y) in positions.items():
        label=roles.get(n); infra=isinstance(label,dict) and str(label.get("type","")).upper() in {"AMM","DEX","CEX","EXCHANGE","LOCKER","BURN"}
        color="#fb923c" if n==result["developer"] else ("#a78bfa" if infra else "#38bdf8")
        radius=8+2*math.sqrt(max(0,holdings.get(n,0)))
        svg.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{color}"><title>{html.escape(n)}</title></circle><text x="{x+12}" y="{y}" fill="white" font-size="10">{n[:6]}…</text>')
    details=html.escape(json.dumps(result,indent=2))
    screening=result.get("screening",{})
    verdict=html.escape(screening.get("verdict","HOLD"))
    status_rows="".join("<tr><td>"+html.escape(name)+"</td><td>"+html.escape(item.get("status","UNKNOWN"))+"</td><td>"+html.escape(item.get("reason",""))+"</td></tr>" for name,item in screening.get("checks",{}).items())
    status_panel="<h2>Screening: "+verdict+"</h2><table><tr><th>Check</th><th>Status</th><th>Reason</th></tr>"+status_rows+"</table><p>Coverage is bounded by the recorded policy. PASS is eligibility, not a guarantee of safety.</p>"

    path.write_text('<!doctype html><meta charset="utf-8"><title>Vivameda Wallet Intelligence</title><style>body{background:#0f172a;color:#e2e8f0;font:16px system-ui;margin:32px}pre{white-space:pre-wrap}svg{max-width:100%}</style><h1>Vivameda · Wallet Intelligence</h1>'+status_panel+'<p>Orange: reported developer. Purple: provider-labelled infrastructure. Blue: other wallets/accounts. Bubble size reflects reported holding share where available. Lines: observed relationships; hover for evidence. No common-control conclusion.</p><svg viewBox="0 0 900 760">'+''.join(svg)+'</svg><details><summary>Histories, findings and transaction evidence</summary><pre>'+details+'</pre></details>',encoding="utf-8")

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--mint",required=True); p.add_argument("--output",required=True)
    p.add_argument("--budget",type=int,default=12); p.add_argument("--wallets",type=int,default=4)
    a=p.parse_args()
    if not 1<=a.budget<=100 or not 1<=a.wallets<=21: p.error("budget 1..100; wallets 1..21")
    r=scan(a.mint,a.output,a.budget,a.wallets)
    print(json.dumps({k:r[k] for k in ("mode","coverage","rpc_requests_used","issues")}|{"events":len(r["events"]),"wallets":len(r["wallet_histories"])}))
