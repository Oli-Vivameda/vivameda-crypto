"""Free-RPC bounded screener. Durable history progress; no keys or transactions."""
import base64,hashlib,json,time,zlib
from pathlib import Path
import requests
from wallet_intelligence import Store,Client,decode,render
from protocol_screening import PUMP,SPL,TOKEN22,pool_state,token_controls,liquidity_observation,b58decode,launch_v2_instruction
from screening_policy import POLICY,LIMITS,screen_packet,screen_creator_link
from free_risk_evidence import valid,evidence_error
SYSTEM="11111111111111111111111111111111"
WSOL="So11111111111111111111111111111111111111112"
# Unknown top-level programs are a coverage HOLD for history review.
SUPPORTED={SYSTEM,SPL,TOKEN22,PUMP,"ComputeBudget111111111111111111111111111111",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"}
class ScreenClient(Client):
    def __init__(self,store,budget):
        super().__init__(store,budget);self.deadline=time.monotonic()+140
    def rpc(self,method,params):
        if time.monotonic()>self.deadline-17:raise RuntimeError("research_time_budget")
        return super().rpc(method,params)

PUMP_LAUNCH="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_LAUNCH_OPS={bytes(x) for x in (
    [102,6,61,18,1,218,235,234],[56,252,116,8,158,223,205,95],
    [24,30,200,40,5,28,7,119],[214,144,76,236,95,139,49,180],
    [155,234,231,146,236,158,162,30],[51,230,133,164,1,127,131,173])}
def supported_instruction(ins):
    if ins.get("programId") in SUPPORTED:return True
    if ins.get("programId")==PUMP_LAUNCH:
        if launch_v2_instruction(ins):return True
        try:return b58decode(ins.get("data"))[:8] in PUMP_LAUNCH_OPS
        except (ValueError,TypeError):return False
    return False

def account_info(account,kind):
    if not isinstance(account,dict) or account.get("owner") not in (SPL,TOKEN22) or account.get("executable"):raise ValueError("unsupported_token_account")
    p=account.get("data",{}).get("parsed",{})
    if not isinstance(p,dict) or p.get("type")!=kind or not isinstance(p.get("info"),dict):raise ValueError("unparsed_token_account")
    return p["info"]
def save_tx(store,sig,tx):
    if not isinstance(tx,dict) or not isinstance(tx.get("meta"),dict):raise ValueError("malformed_transaction")
    version=tx.get("version","legacy")
    if version!="legacy" and (type(version) is not int or version not in (0,1)):raise ValueError("unsupported_transaction_version")
    message=tx.get("transaction",{}).get("message")
    if not isinstance(message,dict) or not isinstance(message.get("instructions"),list):raise ValueError("unparsed_transaction_message")
    store.db.execute("INSERT OR REPLACE INTO tx VALUES(?,?)",(sig,json.dumps(tx)))
    for e in decode(tx,sig):
        store.db.execute("INSERT OR REPLACE INTO events VALUES(?,?,?)",(sig,e["instruction"],json.dumps(e)))
    store.db.commit()
def get_tx(client,sig):
    row=client.store.db.execute("SELECT body FROM tx WHERE sig=?",(sig,)).fetchone()
    if row:return json.loads(row[0])
    tx=client.rpc("getTransaction",[sig,{"encoding":"jsonParsed","commitment":"finalized","maxSupportedTransactionVersion":1}])
    if tx is not None:save_tx(client.store,sig,tx)
    return tx
def sale_receipts(tx,sig,pair,mint):
    if not isinstance(tx,dict) or not isinstance(tx.get("meta"),dict) or tx["meta"].get("err") is not None:return []
    msg=tx.get("transaction",{}).get("message",{});out=[]
    groups={g["index"]:g.get("instructions",[]) for g in tx["meta"].get("innerInstructions") or []}
    # Pair each pool invocation with only its descendants. Never mix sibling swaps.
    invocations=[]
    for index,ins in enumerate(msg.get("instructions",[])):
        children=groups.get(index,[])
        invocations.append((ins,children))
        for pos,child in enumerate(children):
            if child.get("programId")!=PUMP:continue
            depth=child.get("stackHeight")
            if type(depth) is not int or depth<2:continue
            descendants=[]
            for following in children[pos+1:]:
                level=following.get("stackHeight")
                if type(level) is not int:
                    descendants=[];break
                if level<=depth:break
                descendants.append(following)
            invocations.append((child,descendants))
    for ins,children in invocations:
        if ins.get("programId")!=PUMP:continue
        try:raw=b58decode(ins.get("data"))
        except (ValueError,TypeError):continue
        a=ins.get("accounts",[])
        if raw[:8]!=bytes([51,230,133,164,1,127,131,173]) or len(a)<13 or a[0]!=pair or a[3]!=mint or a[4]!=WSOL:continue
        sent=received=0
        for child in children:
            if child.get("programId") not in (SPL,TOKEN22):continue
            p=child.get("parsed",{})
            if not isinstance(p,dict) or p.get("type") not in ("transfer","transferChecked"):continue
            v=p.get("info",{})
            try:amount=int(v.get("amount",v.get("tokenAmount",{}).get("amount",0)))
            except (ValueError,TypeError):continue
            if v.get("source")==a[5] and v.get("destination")==a[7]:sent+=amount
            if v.get("source")==a[8] and v.get("destination")==a[6]:received+=amount
        if sent>0 and received>0:
            out.append({"pool":pair,"mint":mint,"seller":a[1],"global_config":a[2],
                        "base_sent":sent,"quote_received":received,"signature":sig,"time":tx.get("blockTime")})
    return out
def index_window(client,wallet,seconds,now):
    db=client.store.db;cutoff=now-seconds
    db.execute("""CREATE TABLE IF NOT EXISTS screen_ranges(
      wallet TEXT PRIMARY KEY,head TEXT,before_sig TEXT,lower_ts INTEGER,ended INTEGER,
      head_at INTEGER,null_times INTEGER)""")
    previous=db.execute("SELECT head,before_sig,lower_ts,ended,head_at,null_times FROM screen_ranges WHERE wallet=?",(wallet,)).fetchone()
    rows=client.rpc("getSignaturesForAddress",[wallet,{"limit":1000,"commitment":"finalized"}])
    if not isinstance(rows,list):raise ValueError("invalid_signatures")
    def ingest(items):
        for row in items:
            if not isinstance(row.get("signature"),str):raise ValueError("invalid_signature")
            db.execute("""INSERT INTO signatures VALUES(?,?,?,?) ON CONFLICT(wallet,sig)
                DO UPDATE SET ts=COALESCE(excluded.ts,signatures.ts),failed=excluded.failed""",
                (wallet,row["signature"],row.get("blockTime"),int(row.get("err") is not None)))
        db.commit()
    ingest(rows)
    head=rows[0]["signature"] if rows else None
    contiguous=bool(previous and previous[0] and any(r["signature"]==previous[0] for r in rows))
    timestamps=[r["blockTime"] for r in rows if type(r.get("blockTime")) is int]
    lower=min(timestamps) if timestamps else None
    nulls=sum(type(r.get("blockTime")) is not int for r in rows)
    before=rows[-1]["signature"] if rows else None;ended=len(rows)<1000
    if contiguous:
        before=previous[1]
        lower=min([t for t in (lower,previous[2]) if t is not None],default=None)
        ended=bool(previous[3]);nulls+=previous[5]
    # At most one backward page per wallet per pass; leave budget for other wallets.
    if not ended and (lower is None or lower>cutoff) and client.left>1:
        older=client.rpc("getSignaturesForAddress",[wallet,{"limit":1000,"commitment":"finalized","before":before}])
        if not isinstance(older,list):raise ValueError("invalid_history_page")
        ingest(older)
        times=[r["blockTime"] for r in older if type(r.get("blockTime")) is int]
        lower=min([t for t in [lower]+times if t is not None],default=None)
        nulls+=sum(type(r.get("blockTime")) is not int for r in older)
        before=older[-1]["signature"] if older else before;ended=len(older)<1000
    nulls=db.execute("SELECT count(*) FROM signatures WHERE wallet=? AND ts IS NULL",(wallet,)).fetchone()[0]
    db.execute("INSERT OR REPLACE INTO screen_ranges VALUES(?,?,?,?,?,?,?)",(wallet,head,before,lower,int(ended),now,nulls));db.commit()
    return {"wallet":wallet,"window_start":cutoff,"head_at":now,"pagination_complete":bool(ended or (lower is not None and lower<=cutoff)),
            "null_timestamps":nulls,"provider_scope":"contiguous provider-returned address history; not guaranteed lifetime"}
def history_packet(client,selection,now,priority_owner=None,scope_key=None):
    db=client.store.db;windows=[];issues=[]
    # Shared address/signature cache survives token changes; indexed bodies are immutable.
    db.execute("CREATE INDEX IF NOT EXISTS screen_signatures_window ON signatures(wallet,failed,ts)")
    db.execute("CREATE TABLE IF NOT EXISTS screen_tx_cursor(scope TEXT PRIMARY KEY,last_address TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS screen_windows(address TEXT PRIMARY KEY,body TEXT)")
    # Persist round-robin position so a bounded pass cannot starve tail addresses.
    db.execute("CREATE TABLE IF NOT EXISTS screen_schedule(key TEXT PRIMARY KEY,offset INTEGER)")
    schedule_key=scope_key or hashlib.sha256(json.dumps(sorted(selection),sort_keys=True).encode()).hexdigest()
    db.execute("CREATE TABLE IF NOT EXISTS screen_address_cursor(scope TEXT PRIMARY KEY,last_address TEXT)")
    # Developer primary and token-account histories precede holder rotation.
    priorities=sorted((row for row in selection if row[2]==priority_owner),key=lambda row:(row[0]!=priority_owner,row[0]))[:4]
    regular=sorted(row for row in selection if row not in priorities)
    prior=db.execute("SELECT offset FROM screen_schedule WHERE key=?",(schedule_key,)).fetchone()
    offset=(prior[0] if prior else 0)%max(1,len(regular))
    if scope_key:
        cursor=db.execute("SELECT last_address FROM screen_address_cursor WHERE scope=?",(scope_key,)).fetchone()
        if cursor:offset=next((i for i,row in enumerate(regular) if row[0]>cursor[0]),0)
    ordered=priorities+regular[offset:]+regular[:offset]
    reserve=max(1,client.left//3)
    for wallet,seconds,owner in ordered:
        if client.left<reserve+2 or time.monotonic()>client.deadline-34:break
        try:
            saved=db.execute("SELECT body FROM screen_windows WHERE address=?",(wallet,)).fetchone()
            cached=json.loads(saved[0]) if saved else None
            if not (cached and 0<=now-cached["head_at"]<=120 and cached["window_start"]<=now-seconds and cached["pagination_complete"]):
                item=index_window(client,wallet,seconds,now)
                db.execute("INSERT OR REPLACE INTO screen_windows VALUES(?,?)",(wallet,json.dumps(item)));db.commit()
        except (requests.RequestException,RuntimeError,ValueError) as exc:
            issues.extend(["history_address_incomplete:"+wallet,evidence_error(exc)])
            if "rpc_method_cooldown_" in str(exc):break
        if (wallet,seconds,owner) not in priorities:
            offset=(offset+1)%max(1,len(regular))
            if scope_key:db.execute("INSERT OR REPLACE INTO screen_address_cursor VALUES(?,?)",(scope_key,wallet))
        db.execute("INSERT OR REPLACE INTO screen_schedule VALUES(?,?)",(schedule_key,offset));db.commit()
    # Reuse durable progress without laundering its head timestamp or completeness.
    for wallet,seconds,owner in selection:
        saved=db.execute("SELECT body FROM screen_windows WHERE address=?",(wallet,)).fetchone()
        if not saved:continue
        item=json.loads(saved[0])
        # A shorter cached window cannot satisfy a newly requested longer window.
        if item["window_start"]>now-seconds:item["pagination_complete"]=False
        item["window_start"]=now-seconds
        item["review_owner"]=owner;windows.append(item)
    db.execute("CREATE TABLE IF NOT EXISTS screen_tx_retry(sig TEXT PRIMARY KEY,next_due INTEGER,attempts INTEGER)")
    pending={}
    windows.sort(key=lambda w:(w["review_owner"]!=priority_owner,w["wallet"]!=priority_owner))
    for w in windows:
        pending[w["wallet"]]=[r[0] for r in db.execute("SELECT sig FROM signatures WHERE wallet=? AND failed=0 AND (ts>=? OR ts IS NULL) AND sig NOT IN (SELECT sig FROM tx) AND sig NOT IN (SELECT sig FROM screen_tx_retry WHERE next_due>?) ORDER BY ts DESC LIMIT ?",(w["wallet"],w["window_start"],now,max(1,client.left)))]
    developer_addresses=[w["wallet"] for w in windows if w["review_owner"]==priority_owner]
    regular_tx=sorted(wallet for wallet in pending if wallet not in developer_addresses)
    tx_scope=scope_key or schedule_key
    last_tx=db.execute("SELECT last_address FROM screen_tx_cursor WHERE scope=?",(tx_scope,)).fetchone()
    if last_tx:
        split=next((i for i,a in enumerate(regular_tx) if a>last_tx[0]),0)
        regular_tx=regular_tx[split:]+regular_tx[:split]
    fetch_order=developer_addresses*4+regular_tx
    attempted=set();failures=0
    while client.left and failures<3 and any(pending.values()) and time.monotonic()<client.deadline-17:
        for wallet in fetch_order:
            if not client.left or not pending[wallet] or time.monotonic()>client.deadline-17:continue
            if failures>=3:break
            sig=pending[wallet].pop(0)
            if sig in attempted:continue
            attempted.add(sig)
            if wallet not in developer_addresses:
                db.execute("INSERT OR REPLACE INTO screen_tx_cursor VALUES(?,?)",(tx_scope,wallet));db.commit()
            def defer():
                old=db.execute("SELECT attempts FROM screen_tx_retry WHERE sig=?",(sig,)).fetchone()
                attempts=(old[0] if old else 0)+1
                db.execute("INSERT OR REPLACE INTO screen_tx_retry VALUES(?,?,?)",(sig,now+min(3600,120*2**min(attempts-1,5)),attempts));db.commit()
            try:
                if get_tx(client,sig) is None:
                    issues.append("transaction_unavailable");defer()
                else:
                    db.execute("DELETE FROM screen_tx_retry WHERE sig=?",(sig,));db.commit()
            except (requests.RequestException,RuntimeError,ValueError) as exc:
                defer();failures+=1
                issues.extend(["history_transaction_incomplete:"+type(exc).__name__,evidence_error(exc)])
                # Keep successful address evidence; leave every missing tx pending.
                pending[wallet]=[]
    all_events={};refs=[]
    for w in windows:
        rows=db.execute("SELECT s.sig,s.ts,t.body FROM signatures s LEFT JOIN tx t ON t.sig=s.sig WHERE s.wallet=? AND s.failed=0 AND (s.ts>=? OR s.ts IS NULL)",(w["wallet"],w["window_start"])).fetchall()
        w["indexed_transactions"]=len(rows);w["pending_transactions"]=sum(not r[2] for r in rows)
        oldest=db.execute("SELECT min(ts) FROM signatures WHERE wallet=? AND failed=0",(w["wallet"],)).fetchone()[0]
        w["activity_age_lower_bound"]=max(0,now-oldest) if oldest is not None else None
        unknown=set()
        for sig,ts,body in rows:
            if not body:continue
            tx=json.loads(body)
            for ins in tx.get("transaction",{}).get("message",{}).get("instructions",[]):
                program=ins.get("programId")
                if not supported_instruction(ins):unknown.add(program or "unresolved_program")
            for e in decode(tx,sig):all_events[(sig,e["instruction"])]=e
        w["unknown_programs"]=sorted(unknown)
    merged=[]
    required={}
    for address,seconds,owner in selection:required.setdefault(owner,set()).add(address)
    for owner,addresses in required.items():
        parts=[w for w in windows if w["review_owner"]==owner]
        if not parts:continue
        primary=next((w for w in parts if w["wallet"]==owner),{})
        merged.append({"wallet":owner,"window_start":max(w["window_start"] for w in parts),
            "head_at":min(w["head_at"] for w in parts),
            "pagination_complete":{w["wallet"] for w in parts}==addresses and all(w["pagination_complete"] for w in parts),
            "null_timestamps":sum(w["null_timestamps"] for w in parts),
            "pending_transactions":sum(w["pending_transactions"] for w in parts),
            "indexed_transactions":sum(w["indexed_transactions"] for w in parts),
            "activity_age_lower_bound":primary.get("activity_age_lower_bound"),
            "unknown_programs":sorted({p for w in parts for p in w["unknown_programs"]}),
            "addresses_required":len(addresses),"addresses_reviewed":len(parts)})
    body={"wallets":merged,"events":list(all_events.values()),"observed_at":int(time.time()),
        "index_metrics":{"transaction_attempts":len(attempted),"shared_transaction_bodies":db.execute("SELECT count(*) FROM tx").fetchone()[0],
                         "indexed_addresses":db.execute("SELECT count(*) FROM screen_windows").fetchone()[0],
                         "scope":tx_scope},
        "coverage_summary":{"owners_required":len(required),"owners_observed":len(merged),
            "owners_missing":len(required)-len(merged),"addresses_required":len({a for a,s,o in selection}),
            "addresses_observed":len(windows),"owners_complete_fresh":sum(
                w["pagination_complete"] and w["pending_transactions"]==0 and w["null_timestamps"]==0
                and not w["unknown_programs"] and 0<=now-w["head_at"]<=LIMITS["max_age"] for w in merged),
            "owners_with_activity_age":sum(w["activity_age_lower_bound"] is not None for w in merged)}}
    ref=client.store.evidence("screen-history:"+json.dumps(selection),body)
    body["evidence_refs"]=[ref]
    return body,issues
def holder_addresses(top,base_vault):
    """Include the authenticated pool vault even when discovery omits it."""
    if not isinstance(top,list) or not 1<=len(top)<=20:raise ValueError("invalid_largest_accounts")
    addresses=[r["address"] for r in top]
    if len(set(addresses))!=len(addresses):raise ValueError("duplicate_largest_account")
    if not valid(base_vault) or not all(valid(a) for a in addresses):raise ValueError("invalid_holder_address")
    if base_vault not in addresses:addresses.append(base_vault)
    return addresses

def census_ownership(client,mint,creator,pair,state,program,supply,min_slot,now):
    """Verified mint-filtered census; require exact supply reconciliation."""
    db=client.store.db
    db.execute("CREATE TABLE IF NOT EXISTS holder_census(mint TEXT PRIMARY KEY,observed INTEGER,body BLOB)")
    cached=db.execute("SELECT observed,body FROM holder_census WHERE mint=?",(mint,)).fetchone()
    snapshot=None
    if cached and 0<=now-cached[0]<=240:
        candidate=json.loads(zlib.decompress(cached[1]))
        if (candidate["pair"],candidate["vault"],candidate["program"],candidate["supply"])==(pair,state["base_vault"],program,supply):
            snapshot=candidate
    if snapshot is None:
        filters=[{"memcmp":{"offset":0,"bytes":mint}}]
        if program==SPL:filters.append({"dataSize":165})
        if program not in (SPL,TOKEN22):raise ValueError("census_unsupported_program")
        response=client.rpc("getProgramAccounts",[program,{"encoding":"jsonParsed","commitment":"finalized",
            "withContext":True,"minContextSlot":min_slot,"filters":filters}])
        rows=response.get("value");slot=response.get("context",{}).get("slot")
        if type(slot) is not int or slot<min_slot:raise ValueError("census_context_slot")
        if not isinstance(rows,list) or not 1<=len(rows)<=20000:raise ValueError("census_account_limit")
        accounts=[];seen=set();total=0
        for row in rows:
            address=row["pubkey"];account=row["account"];info=account_info(account,"account")
            amount=int(info["tokenAmount"]["amount"]);owner=info.get("owner")
            if (not valid(address) or address in seen or account["owner"]!=program or
                info.get("mint")!=mint or info.get("state")!="initialized" or not valid(owner) or amount<0):
                raise ValueError("census_account_mismatch")
            if owner==pair and address!=state["base_vault"]:raise ValueError("unverified_pool_owned_account")
            if address==state["base_vault"] and owner!=pair:raise ValueError("pool_vault_owner_mismatch")
            seen.add(address);total+=amount;accounts.append([address,owner,amount])
        if state["base_vault"] not in seen or total!=supply:raise ValueError("census_supply_not_reconciled")
        snapshot={"pair":pair,"vault":state["base_vault"],"program":program,"supply":supply,
                  "observed_at":int(time.time()),"slot":slot,"accounts":accounts,"rpc_ref":client.last_evidence_ref}
        db.execute("INSERT OR REPLACE INTO holder_census VALUES(?,?,?)",
            (mint,snapshot["observed_at"],zlib.compress(json.dumps(snapshot).encode())));db.commit()
    owners={};owner_accounts={};vault_amount=0
    for address,owner,amount in snapshot["accounts"]:
        if amount>0:owners[owner]=owners.get(owner,0)+amount
        if amount>0 or owner==creator:owner_accounts.setdefault(owner,set()).add(address)
        if address==state["base_vault"]:vault_amount=amount
    ownership={"authenticated":True,"discovery_source":"mint-filtered on-chain account census","mint":mint,
        "owners":[{"owner":owner,"pct":amount/supply*100} for owner,amount in sorted(owners.items(),key=lambda x:-x[1])],
        "unseen_pct":0.0,"creator_total_pct":owners.get(creator,0)/supply*100,"supply_raw":str(supply),
        "verified_total_raw":str(supply),"authenticated_pool_vault":state["base_vault"],
        "pool_vault_raw":str(vault_amount),"pool_vault_pct":vault_amount/supply*100,
        "verified_account_count":len(snapshot["accounts"]),"census_supply_reconciled":True,
        "context_slot":snapshot["slot"],"observed_at":snapshot["observed_at"],"evidence_refs":[snapshot["rpc_ref"]]}
    return ownership,owners,owner_accounts

def developer_associations(events,creator,pair,pool):
    associated=set();infrastructure=[]
    for e in events:
        if e.get("relation")!="mint_authority_at_initialization" or not (
            e.get("source")==creator or creator in e.get("transaction_signers",[])):continue
        # A pool's own authenticated LP mint is not a separate developer-launched coin.
        if (pool.get("authenticated") is True and pool.get("liquidity",{}).get("status")=="OBSERVED"
            and e.get("target")==pool.get("state",{}).get("lp_mint") and e.get("source")==pair):
            infrastructure.append({"mint":e["target"],"role":"authenticated_current_pool_lp",
                "pool":pair,"signature":e["signature"],"pool_evidence_refs":pool.get("evidence_refs",[])})
        else:associated.add(e["target"])
    return associated,infrastructure

def collect(mint,creator,pair,root,budget=40,research=True,time_budget=140):
    if not valid(mint):raise ValueError("invalid_mint")
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    store=Store(root/"wallets.sqlite");client=ScreenClient(store,budget)
    client.deadline=time.monotonic()+min(140,max(20,time_budget))
    now=int(time.time());issues=[]
    previous={}
    try:
        saved=root/(mint+".json")
        if saved.stat().st_size<=8*1024*1024:
            previous=json.loads(saved.read_text())
    except (OSError,ValueError):pass
    old_packet=previous.get("screening_packet",{})
    same_identity=(previous.get("schema")=="wallet-intelligence-v3" and old_packet.get("mint")==mint
        and old_packet.get("pair")==pair and old_packet.get("creator")==creator)
    # A fast pass cannot erase a previously observed background rejection.
    background=("wallet_clusters","developer_history","top_holder_ownership","wallet_age")
    if not research and same_identity and any(
        previous.get("screening",{}).get("checks",{}).get(k,{}).get("status")=="REJECT" for k in background):
        client.session.close();store.db.close()
        previous["fast_refresh_deferred"]="background_rejection_requires_research"
        return previous
    packet={"policy":POLICY,"mint":mint,"pair":pair,"creator":creator}
    result={"schema":"wallet-intelligence-v3","mint":mint,"pair":pair,"developer":creator,
            "generated_at":now,"holders":[],"wallet_histories":[],"events":[],"issues":issues,
            "mode":"SCREENING","coverage":"BOUNDED_POLICY","limitations":[
            "Supply-reconciled on-chain census when available, otherwise verified account sample; at most 10% unobserved supply for eligibility",
            "24-hour holder links and 30-day supported developer history, not lifetime history",
            "Activity age is a lower bound, not creation time",
            "Transfers and shared funding do not prove common ownership",
            "Observed sells do not guarantee future execution; protocol admin and upgrade risk remains"]}
    result["collection_lane"]="research" if research else "fast"
    if not research and same_identity:
        # Reuse evidence only with its original timestamps; never redate history.
        for key in ("history","developer"):
            if key in old_packet:packet[key]=old_packet[key]
        result["wallet_histories"]=packet.get("history",{}).get("wallets",[])
        result["events"]=packet.get("history",{}).get("events",[])
    try:
        if not valid(pair) or not valid(creator):raise ValueError("missing_pair_or_creator")
        pr=client.rpc("getAccountInfo",[pair,{"encoding":"base64","commitment":"finalized"}])
        state=pool_state(pr.get("value"))
        if state["base_mint"]!=mint or state["quote_mint"]!=WSOL:raise ValueError("unsupported_pool_mints")
        ar=client.rpc("getMultipleAccounts",[[mint,state["lp_mint"],state["base_vault"],state["quote_vault"]],
                      {"encoding":"jsonParsed","commitment":"finalized","minContextSlot":pr["context"]["slot"]}])
        av=ar.get("value")
        if not isinstance(av,list) or len(av)!=4:raise ValueError("missing_pool_accounts")
        supply=int(account_info(av[0],"mint")["supply"])
        if supply<=0:raise ValueError("invalid_supply")
        pool={"authenticated":True,"state":state,"observed_at":int(time.time()),
              "context_slot":ar["context"]["slot"],"mint_account":av[0],"token_controls":token_controls(av[0]),"liquidity":liquidity_observation(pair,state,av[1:]),
              "evidence_refs":[store.evidence("screen-pool:"+pair,{"pool":pr,"accounts":ar})]}
        packet["pool"]=pool
        packet["creator_provenance"]={"scanner_creator":creator,
            "scanner_source":"Pump discovery creator stored at first insertion",
            "pool_coin_creator":state["coin_creator"],"provider_creator":None,
            "identity_changed":False,"status":"MATCH" if creator==state["coin_creator"] else "CONFLICT",
            "observed_at":pool["observed_at"],"pool_evidence_refs":pool["evidence_refs"][:]}
        if creator!=state["coin_creator"]:
            try:
                sharing=client.rpc("getAccountInfo",[state["coin_creator"],{"encoding":"base64","commitment":"finalized","minContextSlot":ar["context"]["slot"]}])
                pool["creator_sharing"]={"address":state["coin_creator"],"account":sharing.get("value") or {},
                    "context_slot":sharing.get("context",{}).get("slot"),"observed_at":int(time.time()),
                    "evidence_refs":[store.evidence("screen-creator-sharing:"+mint,sharing)]}
            except (requests.RequestException,RuntimeError,ValueError) as exc:
                issues.append(evidence_error(exc))
            if screen_creator_link(pool,mint,creator,int(time.time())):
                packet["creator_provenance"]["status"]="AUTHENTICATED_FEE_SHARING"
                packet["creator_provenance"]["pool_coin_creator_role"]="Pump Fees sharing configuration PDA"
                packet["creator_provenance"]["identity_changed"]=False
            else:issues.append("creator_identity_conflict")
        largest={};top=[];native=[]
        try:
            discovery=client.session.get("https://api.rugcheck.xyz/v1/tokens/"+mint+"/report",timeout=10)
            discovery.raise_for_status();largest=discovery.json()
            if largest.get("mint")!=mint:raise ValueError("holder_discovery_mint_mismatch")
            top=largest.get("topHolders")
            holder_addresses(top,state["base_vault"])
        except (requests.RequestException,ValueError,KeyError,TypeError):
            issues.append("provider_holder_discovery_unavailable");largest={};top=[]
        packet["creator_provenance"]["provider_creator"]=largest.get("creator")
        packet["creator_provenance"]["provider_agrees_with_pool"]=largest.get("creator")==state["coin_creator"]
        packet["creator_provenance"]["provider_evidence_ref"]=store.evidence("screen-discovery:"+mint,largest)
        try:
            ownership,owners,owner_accounts=census_ownership(client,mint,creator,pair,state,av[0]["owner"],supply,ar["context"]["slot"],now)
        except (requests.RequestException,RuntimeError,ValueError,KeyError,TypeError) as exc:
            issues.extend(["holder_census_unavailable",evidence_error(exc)])
            try:
                native=client.rpc("getTokenLargestAccounts",[mint,{"commitment":"finalized"}]).get("value",[])
                holder_addresses(native,state["base_vault"])
            except (requests.RequestException,RuntimeError,ValueError,KeyError,TypeError) as exc:
                issues.append("rpc_holder_discovery_unavailable:"+str(exc)[:100]);native=[]
            addresses=list(dict.fromkeys([state["base_vault"]]+[r["address"] for r in native+top]))
            hr=client.rpc("getMultipleAccounts",[addresses,{"encoding":"jsonParsed","commitment":"finalized","minContextSlot":ar["context"]["slot"]}])
            if len(hr.get("value",[]))!=len(addresses):raise ValueError("missing_holder_accounts")
            owners={};owner_accounts={};total=0;vault_amount=0;verified=set()
            for address,a in zip(addresses,hr["value"]):
                if a is None and address!=state["base_vault"]:
                    issues.append("discovered_holder_account_closed");continue
                info=account_info(a,"account")
                if info.get("mint")!=mint or info.get("state")!="initialized":raise ValueError("holder_account_mismatch")
                owner=info.get("owner")
                if not valid(owner):raise ValueError("invalid_holder_owner")
                if owner==pair and address!=state["base_vault"]:raise ValueError("unverified_pool_owned_account")
                amount=int(info["tokenAmount"]["amount"])
                if amount<0:raise ValueError("negative_balance")
                if address==state["base_vault"]:
                    if owner!=pair:raise ValueError("pool_vault_owner_mismatch")
                    vault_amount=amount
                verified.add(address)
                total+=amount;owners[owner]=owners.get(owner,0)+amount
                owner_accounts.setdefault(owner,set()).add(address)
            if total>supply:raise ValueError("inconsistent_supply_snapshot")
            cr=client.rpc("getTokenAccountsByOwner",[creator,{"mint":mint},{"encoding":"jsonParsed","commitment":"finalized","minContextSlot":hr["context"]["slot"]}])
            if not isinstance(cr.get("value"),list):raise ValueError("missing_creator_accounts")
            creator_amount=0;creator_seen=set()
            for a in cr["value"]:
                i=account_info(a["account"],"account")
                if i.get("mint")!=mint or i.get("owner")!=creator:raise ValueError("creator_account_mismatch")
                address=a["pubkey"];amount=int(i["tokenAmount"]["amount"])
                if not valid(address) or address in creator_seen or amount<0 or i.get("state")!="initialized":
                    raise ValueError("invalid_creator_account")
                creator_seen.add(address);creator_amount+=amount
                if address not in verified:
                    verified.add(address);total+=amount;owners[creator]=owners.get(creator,0)+amount
                owner_accounts.setdefault(creator,set()).add(address)
            if total>supply or creator_amount>supply:raise ValueError("inconsistent_supply_snapshot")
            ownership={"authenticated":True,"discovery_source":"native RPC and free provider account lists; balances verified on-chain","mint":mint,"owners":[{"owner":a,"pct":v/supply*100} for a,v in owners.items()],
                       "unseen_pct":max(0,(supply-total)/supply*100),"creator_total_pct":creator_amount/supply*100,
                       "supply_raw":str(supply),"verified_total_raw":str(total),
                       "authenticated_pool_vault":state["base_vault"],"pool_vault_raw":str(vault_amount),
                       "pool_vault_pct":vault_amount/supply*100,"verified_account_count":len(verified),
                       "pool_vault_in_discovery":state["base_vault"] in [r["address"] for r in top],
                       "observed_at":int(time.time()),"evidence_refs":[store.evidence("screen-ownership:"+mint,{"largest":largest,"native_largest":native,"addresses":addresses,"holders":hr,"creator":cr})]}
        packet["ownership"]=ownership
        result["holders"]=[{"owner":a,"reported_pct":v/supply*100,"provider_label":{"type":"AMM"} if a==pair else None} for a,v in owners.items()]
        # Read recent pool executions before spending remaining budget on historical research.
        try:
            signatures=client.rpc("getSignaturesForAddress",[pair,{"limit":20,"commitment":"finalized"}])
            sales=[]
            for row in signatures:
                if client.left<=(25 if research else 2) or len({e["seller"] for e in sales})>=3:break
                if row.get("err") is not None or type(row.get("blockTime")) is not int or now-row["blockTime"]>300:continue
                try:tx=get_tx(client,row["signature"])
                except RuntimeError as exc:
                    if str(exc)=="rpc_error_code_-32015_method_getTransaction":
                        issues.append("unsupported_pool_transaction_version");continue
                    raise
                sales.extend(sale_receipts(tx,row["signature"],pair,mint))
            trades={"sales":sales,"observed_at":int(time.time()),"evidence_refs":[store.evidence("screen-sales:"+pair,sales)]}
            packet["trades"]=trades
            globals_={e["global_config"] for e in sales}
            if len(globals_)==1:
                global_address=next(iter(globals_))
                gr=client.rpc("getAccountInfo",[global_address,{"encoding":"base64","commitment":"finalized"}])
                ga=gr.get("value") or {}
                data=ga.get("data",[])
                raw=base64.b64decode(data[0],validate=True) if len(data)==2 and data[1]=="base64" else b""
                if ga.get("owner")==PUMP and not ga.get("executable") and len(raw)>=57 and raw[:8]==bytes([149,8,156,202,160,252,176,217]):
                    pool["sell_enabled"]=not bool(raw[56]&16)
                    pool["evidence_refs"].append(store.evidence("screen-global:"+global_address,gr))
        except (requests.RequestException,RuntimeError,ValueError) as exc:
            issues.extend(["sale_probe_incomplete:"+type(exc).__name__,evidence_error(exc)])
        if not research:return result
        selection=[]
        for owner in [creator]+[a for a in owners if a not in (creator,pair)]:
            seconds=LIMITS["developer_window"] if owner==creator else LIMITS["holder_window"]
            selection.append((owner,seconds,owner))
        for owner in [creator]+[a for a in owners if a not in (creator,pair)]:
            seconds=LIMITS["developer_window"] if owner==creator else LIMITS["holder_window"]
            selection.extend((address,seconds,owner) for address in sorted(owner_accounts.get(owner,set())) if address!=owner)
        hist,hissues=history_packet(client,selection,now,priority_owner=creator,scope_key="mint:"+mint);issues.extend(hissues)
        packet["history"]=hist;result["wallet_histories"]=hist["wallets"];result["events"]=hist["events"]
        associated,infrastructure=developer_associations(hist["events"],creator,pair,pool)
        reports=[]
        # All associated mints must be covered before PASS; two refreshes per cycle.
        refreshed=0
        def prior_age(prior):
            row=store.db.execute("SELECT max(observed) FROM evidence WHERE source=?",("screen-prior:"+prior,)).fetchone()
            return (row[0] or 0,prior)
        for prior in sorted(associated-{mint},key=prior_age):
            saved=store.db.execute("SELECT observed,body FROM evidence WHERE source=? ORDER BY observed DESC LIMIT 1",("screen-prior:"+prior,)).fetchone()
            if saved and now-saved[0]<=240:body=json.loads(saved[1]);observed=saved[0]
            elif refreshed<2 and time.monotonic()<client.deadline-12:
                refreshed+=1
                try:
                    r=client.session.get("https://api.rugcheck.xyz/v1/tokens/"+prior+"/report",timeout=10);r.raise_for_status();body=r.json()
                    if body.get("mint")!=prior:raise ValueError("prior_mint_mismatch")
                    store.evidence("screen-prior:"+prior,body);observed=int(time.time())
                except (requests.RequestException,ValueError):
                    issues.append("prior_report_unavailable:"+prior);continue
            else:continue
            reports.append({"mint":prior,"retrieved":type(body.get("rugged")) is bool and isinstance(body.get("risks"),list),"observed_at":observed,"rugged":body.get("rugged"),
                            "danger":any(str(r.get("level","")).lower()=="danger" for r in body.get("risks",[]))})
        packet["developer"]={"attribution_verified":screen_creator_link(pool,mint,creator,int(time.time())),
                             "associated_mints":sorted(associated),"infrastructure_mints":infrastructure,"prior_reports":reports,
                             "current_provider_flag": (largest["rugged"] or any(str(r.get("level","")).lower()=="danger" for r in largest["risks"]))
                                if type(largest.get("rugged")) is bool and isinstance(largest.get("risks"),list) else None}
    except requests.RequestException as exc:
        code=getattr(getattr(exc,"response",None),"status_code",None)
        issues.append("provider_http_"+str(code) if code else "provider_network_error")
    except (ValueError,RuntimeError,KeyError,TypeError,IndexError) as exc:
        issues.append(type(exc).__name__+":"+str(exc)[:100])
    finally:
        client.session.close()
        result["screening_packet"]=packet
        checks=screen_packet(packet,mint,pair,creator,int(time.time()))
        statuses=[x["status"] for x in checks.values()]
        verdict="REJECT" if "REJECT" in statuses else ("PASS" if all(x=="PASS" for x in statuses) else "HOLD")
        result["screening"]={"policy":POLICY,"verdict":verdict,"checks":checks,"limits":LIMITS}
        result["generated_at"]=int(time.time());result["rpc_requests_used"]=budget-client.left
        raw=json.dumps(result,indent=2);tmp=root/(mint+".json.tmp");tmp.write_text(raw);tmp.replace(root/(mint+".json"))
        render(result,root/(mint+".html"));store.db.close()
    return result
