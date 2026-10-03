#!/usr/bin/env python3
import hashlib, json, logging, re, sqlite3, time
from pathlib import Path
import requests

BASE = Path("/opt/vivameda-crypto-early-scout")
DB_PATH = BASE / "data" / "early_scout.sqlite"
CREDS = BASE / "credentials.json"
LOG_PATH = BASE / "logs" / "early_scout.log"
PUMP_URL = "https://frontend-api-v3.pump.fun/coins"
DEX_BATCH = "https://api.dexscreener.com/tokens/v1/solana/"
RPC_URL = "https://api.mainnet-beta.solana.com"
SOL_QUOTES = {"SOL", "WSOL", "USDC"}
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Vivameda-Early-Scout/1.0"})

BASE.joinpath("data").mkdir(parents=True, exist_ok=True)
BASE.joinpath("logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s")

def get_json(url, params=None, timeout=10):
    r = SESSION.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def db():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS launches(
      mint TEXT PRIMARY KEY, created_ts INTEGER, creator TEXT, name TEXT, symbol TEXT,
      protocol TEXT, token_program TEXT, pump_pool TEXT, first_seen INTEGER,
      last_pump_seen INTEGER, last_trade_ts INTEGER, current_mc REAL, ath_mc REAL,
      complete INTEGER, pinned_pair TEXT, dex TEXT, quote TEXT,
      alert_level INTEGER DEFAULT 0, last_alert_ts INTEGER DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS snapshots(
      mint TEXT, ts INTEGER, pair TEXT, price REAL, mc REAL, liq REAL,
      vol_m5 REAL, vol_h1 REAL, buys_m5 INTEGER, sells_m5 INTEGER,
      buys_h1 INTEGER, sells_h1 INTEGER, pc_m5 REAL, pc_h1 REAL,
      PRIMARY KEY(mint, ts))""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_launch_age ON launches(created_ts)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_snap_mint_ts ON snapshots(mint, ts)")
    con.commit()
    return con

def pump_rows(sort):
    p = {"offset": 0, "limit": 100, "sort": sort,
         "order": "DESC", "includeNsfw": "false"}
    d = get_json(PUMP_URL, p)
    return d if isinstance(d, list) else []

def upsert_pump(con, rows):
    now = int(time.time() * 1000)
    for x in rows:
        mint = x.get("mint")
        created = int(x.get("created_timestamp") or 0)
        if not mint or not created:
            continue
        mc = x.get("market_cap_usd")
        ath = x.get("ath_market_cap")
        con.execute("""INSERT INTO launches
          (mint,created_ts,creator,name,symbol,protocol,token_program,pump_pool,
           first_seen,last_pump_seen,last_trade_ts,current_mc,ath_mc,complete)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(mint) DO UPDATE SET
           last_pump_seen=excluded.last_pump_seen,
           creator=COALESCE(NULLIF(launches.creator,''),excluded.creator),
           last_trade_ts=excluded.last_trade_ts,
           current_mc=COALESCE(excluded.current_mc,launches.current_mc),
           ath_mc=COALESCE(excluded.ath_mc,launches.ath_mc),
           complete=excluded.complete""",
          (mint, created, x.get("creator") if isinstance(x.get("creator"),str) and re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}",x["creator"]) else None, x.get("name"), x.get("symbol"),
           x.get("protocol"), x.get("token_program"), x.get("pool_address"),
           now, now, int(x.get("last_trade_timestamp") or 0),
           float(mc) if mc is not None else None,
           float(ath) if ath is not None else None, 1 if x.get("complete") else 0))
    con.commit()

def candidates(con):
    now = int(time.time() * 1000)
    lo, hi = now - 6*3600_000, now - 30*60_000
    recent = now - 12*60_000
    q = """SELECT mint,created_ts,creator,current_mc,ath_mc,pinned_pair
           FROM launches
           WHERE created_ts BETWEEN ? AND ?
             AND last_trade_ts >= ?
             AND current_mc BETWEEN 30000 AND 750000
             AND (ath_mc IS NULL OR ath_mc <= 0 OR current_mc >= ath_mc*0.35)
           ORDER BY last_trade_ts DESC LIMIT 60"""
    return con.execute(q, (lo, hi, recent)).fetchall()

def chunks(xs, n=30):
    for i in range(0, len(xs), n):
        yield xs[i:i+n]

def dex_pairs(mints):
    out = []
    for batch in chunks(mints):
        try:
            d = get_json(DEX_BATCH + ",".join(batch), timeout=12)
            if isinstance(d, list):
                out.extend(d)
        except Exception as e:
            logging.warning("dex batch failed: %s", e)
        time.sleep(0.25)
    return out

def choose_pair(mint, rows, pinned=None):
    rows = [p for p in rows if p.get("baseToken",{}).get("address") == mint]
    if pinned:
        hit = [p for p in rows if p.get("pairAddress") == pinned]
        return hit[0] if hit else None
    rows = [p for p in rows if p.get("quoteToken",{}).get("symbol") in SOL_QUOTES]
    rows = [p for p in rows if (p.get("liquidity") or {}).get("usd") is not None]
    if not rows:
        return None
    rows.sort(key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0), reverse=True)
    return rows[0]

def n(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def record_pair(con, mint, pair):
    ts = int(time.time() // 60 * 60)
    tx = pair.get("txns") or {}
    vol = pair.get("volume") or {}
    pc = pair.get("priceChange") or {}
    liq = pair.get("liquidity") or {}
    h5, h1 = tx.get("m5") or {}, tx.get("h1") or {}
    vals = (mint, ts, pair.get("pairAddress"), n(pair.get("priceUsd")),
            n(pair.get("marketCap")), n(liq.get("usd")), n(vol.get("m5")),
            n(vol.get("h1")), int(h5.get("buys") or 0), int(h5.get("sells") or 0),
            int(h1.get("buys") or 0), int(h1.get("sells") or 0),
            n(pc.get("m5")), n(pc.get("h1")))
    con.execute("""INSERT OR REPLACE INTO snapshots
       (mint,ts,pair,price,mc,liq,vol_m5,vol_h1,buys_m5,sells_m5,
        buys_h1,sells_h1,pc_m5,pc_h1) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", vals)
    con.execute("""UPDATE launches SET pinned_pair=COALESCE(pinned_pair,?),
       dex=COALESCE(dex,?),quote=COALESCE(quote,?) WHERE mint=?""",
       (pair.get("pairAddress"), pair.get("dexId"),
        pair.get("quoteToken",{}).get("symbol"), mint))
    con.commit()

def history(con, mint, minutes=35):
    cutoff = int(time.time()) - minutes*60
    return con.execute("""SELECT ts,price,mc,liq,vol_m5,vol_h1,buys_m5,sells_m5,
       buys_h1,sells_h1,pc_m5,pc_h1 FROM snapshots
       WHERE mint=? AND ts>=? ORDER BY ts""", (mint, cutoff)).fetchall()

def score_candidate(rows):
    if len(rows) < 4 or rows[-1][0] - rows[0][0] < 10*60:
        return 0, {}, ["history"]
    cur = rows[-1]
    price, mc, liq = cur[1], cur[2], cur[3]
    vol5, vol1 = cur[4], cur[5]
    b1, s1, pc5, pc1 = cur[8], cur[9], cur[10], cur[11]
    if not (30000 <= mc <= 750000 and liq >= 25000 and vol1 >= 20000):
        return 0, {}, ["base_gate"]
    prices = [r[1] for r in rows if r[1] > 0]
    liqs = [r[3] for r in rows if r[3] > 0]
    if len(prices) < 4:
        return 0, {}, ["price_history"]
    band = (max(prices)-min(prices))/min(prices)
    net = price/prices[0]-1
    third = max(1, len(prices)//3)
    higher_low = min(prices[-third:]) >= min(prices[:third])*0.97
    liq_stable = bool(liqs) and liq >= liqs[0]*0.90
    buy_ratio = b1/max(1, b1+s1)
    vratio = vol1/max(mc,1)
    vol_accel = vol5 >= (vol1/12.0)*1.20 if vol1 > 0 else False
    signals = {
      "liq25k": liq >= 25000, "vol_mc25": vratio >= 0.25,
      "buy52": buy_ratio >= 0.52, "h1_not_extended": -8 <= pc1 <= 22,
      "m5_not_extended": -5 <= pc5 <= 10, "band_compact": band <= 0.25,
      "net_constructive": -0.10 <= net <= 0.20, "higher_low": higher_low,
      "liq_stable": liq_stable, "volume_accel": vol_accel,
      "txns100": (b1+s1) >= 100
    }
    score = sum(bool(v) for v in signals.values())
    metrics = {"band":band,"net":net,"buy_ratio":buy_ratio,"vratio":vratio,
               "mc":mc,"liq":liq,"vol5":vol5,"vol1":vol1,"b1":b1,"s1":s1,
               "pc5":pc5,"pc1":pc1,"price":price}
    return score, metrics, [k for k,v in signals.items() if not v]

def rpc(method, params):
    try:
        r = SESSION.post(RPC_URL, json={"jsonrpc":"2.0","id":1,
                         "method":method,"params":params}, timeout=10)
        r.raise_for_status()
        return r.json().get("result")
    except Exception as e:
        logging.warning("rpc %s failed: %s", method, e)
        return None

def basic_security(mint, creator):
    """Use the dedicated collector snapshot; do not duplicate public RPC traffic."""
    out = {"mint_authority":"UNKNOWN","freeze_authority":"UNKNOWN",
           "creator_pct":"UNKNOWN","top10_raw_pct":"UNKNOWN"}
    if not isinstance(mint,str) or not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}",mint):return out
    try:
        path=Path("/var/lib/vivameda-wallet-intelligence/data")/(mint+".json")
        if path.stat().st_size>8*1024*1024:return out
        report=json.loads(path.read_bytes())
        packet=report.get("screening_packet",{})
        if report.get("schema")!="wallet-intelligence-v3" or packet.get("mint")!=mint or packet.get("creator")!=creator:return out
        pool=packet.get("pool",{});observed=pool.get("observed_at")
        if type(observed) not in (int,float) or not 0<=time.time()-observed<=300:return out
        account=pool.get("mint_account")
        if not isinstance(account,dict):return out
        x=account["data"]["parsed"]["info"]
        out["_mint_account"]=account;out["_observed_at"]=observed
        out["mint_authority"]=("REVOKED" if x["mintAuthority"] is None else "ACTIVE") if "mintAuthority" in x else "UNKNOWN"
        out["freeze_authority"]=("REVOKED" if x["freezeAuthority"] is None else "ACTIVE") if "freezeAuthority" in x else "UNKNOWN"
        ownership=packet.get("ownership",{})
        ots=ownership.get("observed_at")
        if type(ots) in (int,float) and 0<=time.time()-ots<=300:
            out["creator_pct"]=ownership.get("creator_total_pct","UNKNOWN")
            out["top10_raw_pct"]=round(sum(sorted((r["pct"] for r in ownership.get("owners",[])),reverse=True)[:10]),2)
    except (OSError,ValueError,TypeError,KeyError):pass
    return out

# Owner policy, 2026-10-03: suggestions require a fresh pre-alert risk review.
# Wallet evidence is read locally; incomplete evidence must HOLD, never PASS.
PREALERT_POLICY = "crypto-prealert-v1"
PREALERT_MAX_AGE_SECONDS = 300
PREALERT_REQUIRED = ("token_controls", "liquidity_control", "trading_mechanics")
PREALERT_ADMISSION_POLICY = "three-required-any-reject-v1"
PREALERT_CHECKS = ("wallet_clusters", "developer_history",
                   "top_holder_ownership", "wallet_age", "token_controls",
                   "liquidity_control", "trading_mechanics")

def screen_token_controls(account):
    result={"status":"UNKNOWN","reason":"unverified_token_account"}
    if not isinstance(account,dict) or account.get("owner") not in ("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA","TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb") or account.get("executable"):
        return result
    parsed=account.get("data",{}).get("parsed",{}) if isinstance(account.get("data"),dict) else {}
    if not isinstance(parsed,dict): return result
    info=parsed.get("info",{})
    if not isinstance(info,dict): return result
    if account.get("owner")=="TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb" and "extensions" not in info: return result
    if parsed.get("type")!="mint" or info.get("isInitialized") is not True:
        return result
    if not all(k in info for k in ("mintAuthority","freezeAuthority")): return result
    if info["mintAuthority"] is not None or info["freezeAuthority"] is not None:
        return {"status":"REJECT","reason":"active_mint_or_freeze_authority"}
    try:
        if int(info.get("supply","0"))<=0: return result
    except (ValueError,TypeError): return result
    extensions=info.get("extensions",[])
    if not isinstance(extensions,list):return result
    unsupported=[]
    for ext in extensions:
        if not isinstance(ext,dict) or ext.get("extension") not in ("metadataPointer","tokenMetadata"):
            unsupported.append(ext.get("extension","unknown") if isinstance(ext,dict) else "malformed")
    if unsupported:return {"status":"UNKNOWN","reason":"unsupported_token_extensions","extensions":unsupported}
    return {"status":"PASS","reason":"revoked_authorities_no_supported_transfer_restrictions",
            "scope":"current mint controls only; no sellability or liquidity conclusion"}

def screen_creator_link(pool,mint,creator,now):
    """Authenticate creator identity directly or through Pump's mint-specific fee-sharing PDA."""
    import base64,hashlib,math
    state=pool.get("state",{})
    if state.get("coin_creator")==creator:return True
    proof=pool.get("creator_sharing",{})
    observed=proof.get("observed_at");refs=proof.get("evidence_refs")
    if (type(observed) not in (int,float) or not math.isfinite(observed) or not 0<=now-observed<=300
        or not isinstance(refs,list) or not refs or not all(isinstance(r,str) and r for r in refs)):return False
    if type(proof.get("context_slot")) is not int or type(pool.get("context_slot")) is not int or proof["context_slot"]<pool["context_slot"]:return False
    account=proof.get("account",{});program="pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ"
    if account.get("owner")!=program or account.get("executable") is not False:return False
    def pubkey(value):
        alphabet="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        if not isinstance(value,str) or not 32<=len(value)<=44:raise ValueError("pubkey")
        n=0
        for c in value:n=n*58+alphabet.index(c)
        raw=bytes([0])*(len(value)-len(value.lstrip("1")))+(n.to_bytes((n.bit_length()+7)//8,"big") if n else b"")
        if len(raw)!=32:raise ValueError("pubkey")
        return raw
    try:
        data=account["data"]
        if len(data)!=2 or data[1]!="base64":return False
        raw=base64.b64decode(data[0],validate=True)
        if len(raw)!=1024 or raw[:8]!=bytes([216,74,9,0,56,140,93,75]):return False
        if raw[9]!=2 or raw[10]!=1 or raw[75] not in (0,1):return False
        if raw[11:43]!=pubkey(mint) or raw[43:75]!=pubkey(creator):return False
        derived=hashlib.sha256(b"sharing-config"+pubkey(mint)+raw[8:9]+pubkey(program)+b"ProgramDerivedAddress").digest()
        if derived!=pubkey(state["coin_creator"]) or proof.get("address")!=state["coin_creator"]:return False
        count=int.from_bytes(raw[76:80],"little")
        if not 1<=count<=10 or any(raw[80+34*count:]):return False
        shares=[(raw[80+34*i:112+34*i],int.from_bytes(raw[112+34*i:114+34*i],"little")) for i in range(count)]
        return len({a for a,v in shares})==count and all(a!=bytes(32) and v>0 for a,v in shares) and sum(v for a,v in shares)==10000
    except (ValueError,TypeError,KeyError,IndexError,OverflowError):return False

def screen_packet(packet,mint,pair,creator,now):
    import math
    POLICY="crypto-screen-v2"
    CHECKS=("wallet_clusters","developer_history","top_holder_ownership","wallet_age","token_controls","liquidity_control","trading_mechanics")
    LIMITS={"holder_window":86400,"developer_window":2592000,"max_age":300,
            "max_owner_pct":5.0,"max_top10_pct":30.0,"max_unseen_pct":10.0,
            "max_cluster_pct":10.0,"max_developer_pct":2.0,
            "min_holder_activity_age":86400,"min_developer_activity_age":604800,
            "max_young_share_pct":5.0,"min_distinct_sellers":3}
    checks={n:{"status":"UNKNOWN","reason":"missing_evidence","evidence_refs":[]} for n in CHECKS}
    def fresh(t): return type(t) in (int,float) and math.isfinite(t) and 0<=now-t<=LIMITS["max_age"]
    def put(name,status,reason,source,details=None):
        t=source.get("observed_at")
        refs=source.get("evidence_refs",[])
        if not fresh(t) or not isinstance(refs,list) or not refs or not all(isinstance(r,str) and r for r in refs):return
        checks[name]={"status":status,"reason":reason,"observed_at":t,"evidence_refs":refs,"details":details or {}}
    if not isinstance(packet,dict) or packet.get("policy")!=POLICY or packet.get("mint")!=mint or packet.get("pair")!=pair or packet.get("creator")!=creator:return checks
    pool=packet.get("pool",{});h=packet.get("ownership",{});history=packet.get("history",{})
    tc=pool.get("token_controls",{})
    if tc.get("status") in ("PASS","REJECT"):
        put("token_controls",tc["status"],tc.get("reason","mint_controls"),pool)
    state=pool.get("state",{});liq=pool.get("liquidity",{})
    identity_ok=screen_creator_link(pool,mint,creator,now)
    if pool.get("authenticated") is True and state.get("base_mint")==mint and identity_ok:
        if liq.get("status")=="REJECT":put("liquidity_control","REJECT",liq.get("reason","pool_risk"),pool)
        elif (liq.get("status")=="OBSERVED" and liq.get("outstanding_lp_supply")==0
              and state.get("advanced_controls_verified") is True
              and state.get("is_mayhem_mode") is False and state.get("can_edit_creator_fee") is False
              and state.get("creator_fee_bps")==0):
            put("liquidity_control","PASS","authenticated_vaults_zero_redeemable_lp",pool,
                {"scope":"current supported Pump AMM controls; protocol upgrade/admin risk remains"})
        else:put("liquidity_control","UNKNOWN","unresolved_lp_or_pool_controls",pool)
    if pool.get("authenticated") is True and state.get("base_mint")==mint and not identity_ok:
        put("liquidity_control","UNKNOWN","creator_identity_conflict",pool,
            {"scanner_creator":creator,"pool_coin_creator":state.get("coin_creator"),"identity_changed":False})
    owners=h.get("owners",[])
    ownership_ok=(h.get("authenticated") is True and h.get("mint")==mint and bool(owners))
    pct={}
    if ownership_ok:
        for row in owners:
            value=row.get("pct")
            if not isinstance(row.get("owner"),str) or type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=100:
                ownership_ok=False;break
            pct[row["owner"]]=pct.get(row["owner"],0)+value
    if ownership_ok:
        eligible={a:v for a,v in pct.items() if a!=pair}
        unseen=h.get("unseen_pct")
        if type(unseen) not in (int,float) or not math.isfinite(unseen) or not 0<=unseen<=100:ownership_ok=False
        else:
            details={"largest_pct":max(eligible.values(),default=0),"top10_pct":sum(sorted(eligible.values(),reverse=True)[:10]),
                     "unseen_pct":unseen,"creator_pct":h.get("creator_total_pct")}
            cp=details["creator_pct"]
            if type(cp) not in (int,float) or not math.isfinite(cp) or not 0<=cp<=100:
                put("top_holder_ownership","UNKNOWN","creator_balance_unverified",h,details)
            elif details["largest_pct"]>LIMITS["max_owner_pct"] or details["top10_pct"]>LIMITS["max_top10_pct"] or cp>LIMITS["max_developer_pct"]:
                put("top_holder_ownership","REJECT","concentration_policy_exceeded",h,details)
            elif unseen>LIMITS["max_unseen_pct"]:
                put("top_holder_ownership","UNKNOWN","top_account_sample_insufficient",h,details)
            else:put("top_holder_ownership","PASS","sample_concentration_with_bounded_unseen_supply",h,details)
    else:eligible={}
    wallets=history.get("wallets",[])
    by={w.get("wallet"):w for w in wallets if isinstance(w,dict)}
    def covered(address,seconds):
        w=by.get(address,{})
        start=w.get("window_start")
        return (fresh(w.get("head_at")) and type(start) is int and start<=now-seconds
                and w.get("pagination_complete") is True and w.get("pending_transactions")==0
                and w.get("null_timestamps")==0 and w.get("unknown_programs")==[]
                and type(w.get("indexed_transactions")) is int and w["indexed_transactions"]>=0)
    selected=set(eligible)|{creator}
    events=history.get("events",[])
    if ownership_ok and selected:
        young=[];unknown=[]
        for address in selected:
            age=by.get(address,{}).get("activity_age_lower_bound")
            required=LIMITS["min_developer_activity_age"] if address==creator else LIMITS["min_holder_activity_age"]
            if type(age) not in (int,float) or not math.isfinite(age) or age<0:unknown.append(address)
            elif age<required:
                # A short lower bound in an unfinished scan is not a young-wallet finding.
                if covered(address,required):young.append(address)
                else:unknown.append(address)
        if creator in young or sum(eligible.get(a,0) for a in young)>LIMITS["max_young_share_pct"]:
            put("wallet_age","REJECT","young_wallet_exposure",history,{"wallets":young})
        elif unknown:put("wallet_age","UNKNOWN","activity_age_unverified",history,
            {"owners_required":len(selected),"owners_observed":len(selected & set(by)),"owners_missing":len(selected-set(by)),"wallets":unknown})
        else:put("wallet_age","PASS","observed_activity_lower_bounds_within_policy",history,
                      {"young_wallets":young,"scope":"activity age, not wallet creation date"})
        # Observed links can prove rejection; PASS still requires every selected history.
        edges=[];funders={}
        for e in events:
            if type(e.get("block_time")) is not int or e["block_time"]<now-LIMITS["holder_window"]:continue
            a,b=e.get("source"),e.get("target")
            if e.get("relation")=="native_transfer" and b in selected and a!=pair:
                funders.setdefault(a,set()).add(b)
            if a in selected and b in selected and a!=b and (e.get("relation")=="native_transfer" or
                (e.get("relation")=="token_transfer" and e.get("asset")==mint and e.get("owner_resolution") is True)):
                edges.append((a,b))
        for sender,recipients in funders.items():
            if len(recipients)>1:
                rs=sorted(recipients);edges.extend((rs[0],v) for v in rs[1:])
        groups=[{a} for a in selected]
        for a,b in edges:
            touched=[g for g in groups if a in g or b in g]
            merged=set().union(*touched)
            groups=[g for g in groups if g not in touched]+[merged]
        linked=[{"wallets":sorted(g),"pct":sum(eligible.get(a,0) for a in g)} for g in groups if len(g)>1]
        bad=[g for g in linked if g["pct"]>LIMITS["max_cluster_pct"] or (creator in g["wallets"] and g["pct"]>LIMITS["max_developer_pct"])]
        details={"clusters":linked,"scope":"24h observed transfer links; common control unproven",
                 "owners_required":len(selected),"owners_observed":len(selected & set(by)),"owners_missing":len(selected-set(by))}
        if bad:put("wallet_clusters","REJECT","linked_exposure_exceeded",history,details)
        elif all(covered(a,LIMITS["holder_window"]) for a in selected):
            put("wallet_clusters","PASS","no_excess_linked_exposure_in_review_window",history,details)
        else:put("wallet_clusters","UNKNOWN","holder_history_incomplete_or_unsupported",history,details)
    dev=packet.get("developer",{})
    if covered(creator,LIMITS["developer_window"]) and dev.get("attribution_verified") is True:
        dev_events=[e for e in events if type(e.get("block_time")) is int and e["block_time"]>=now-LIMITS["developer_window"] and e.get("source")==creator]
        withdrawals=[e for e in dev_events if e.get("relation")=="pump_amm_withdraw"]
        reports=dev.get("prior_reports",[])
        expected=set(dev.get("associated_mints",[]))-{mint}
        actual={r.get("mint") for r in reports if r.get("retrieved") is True and fresh(r.get("observed_at"))}
        flagged=[r.get("mint") for r in reports if r.get("rugged") is True or r.get("danger") is True]
        if dev.get("current_provider_flag") is not False:put("developer_history","UNKNOWN","current_token_provider_risk_unresolved",history)
        elif any(e.get("relation")=="pump_amm_sell" and e.get("target")==pair for e in dev_events):put("developer_history","REJECT","developer_sold_current_pool_in_review_window",history)
        elif withdrawals:put("developer_history","REJECT","developer_withdrawal_requires_review",history,{"signatures":[e["signature"] for e in withdrawals]})
        elif flagged:put("developer_history","UNKNOWN","associated_token_provider_risk_requires_review",history,{"mints":flagged})
        elif expected!=actual:put("developer_history","UNKNOWN","associated_token_reports_incomplete",history)
        else:put("developer_history","PASS","no_trigger_in_supported_30day_developer_review",history,{"scope":"address association and supported protocols; not lifetime reputation"})
    else:put("developer_history","UNKNOWN","developer_history_or_attribution_incomplete",history)
    if (pool.get("authenticated") is True and state.get("base_mint")==mint
        and not identity_ok and checks["developer_history"]["status"]=="UNKNOWN"):
        put("developer_history","UNKNOWN","creator_identity_conflict",pool,
            {"scanner_creator":creator,"pool_coin_creator":state.get("coin_creator"),"identity_changed":False})
    trades=packet.get("trades",{})
    sells=[e for e in trades.get("sales",[]) if e.get("pool")==pair and e.get("mint")==mint
           and e.get("seller")!=creator and type(e.get("time")) is int and 0<=now-e["time"]<=300
           and e.get("quote_received",0)>0 and e.get("base_sent",0)>0 and e.get("signature")]
    sellers={e["seller"] for e in sells}
    if len(sellers)>=LIMITS["min_distinct_sellers"] and pool.get("sell_enabled") is True and checks["token_controls"]["status"]=="PASS":
        put("trading_mechanics","PASS","recent_successful_sales_with_received_quote",trades,
            {"distinct_sellers":len(sellers),"scope":"observed execution, no guarantee of future sellability or independence"})
    else:put("trading_mechanics","UNKNOWN","insufficient_recent_sell_receipts_or_controls",trades)
    return checks


def collect_prealert_review(mint, creator, pair, sec):
    """Read evidence, not a file-supplied PASS. Current research is not certification."""
    now = int(time.time())
    review = {
        "policy": PREALERT_POLICY, "mint": mint, "chain": "solana",
        "pair": pair.get("pairAddress"), "checked_at": now,
        "checks": {name: {"status": "UNKNOWN", "reason": "evidence_incomplete",
                          "evidence_refs": []} for name in PREALERT_CHECKS},
    }
    # Authorities alone do not establish transfer mechanics, extensions or liquidity.
    controls = review["checks"]["token_controls"]
    account = sec.get("_mint_account")
    if isinstance(account, dict):
        observed = sec.get("_observed_at")
        controls.update(screen_token_controls(account), observed_at=observed,
            evidence_refs=["solana-account-sha256:" + hashlib.sha256(json.dumps(account,sort_keys=True).encode()).hexdigest()])
        review["token_control_evidence"] = account
    if sec.get("mint_authority") == "ACTIVE" or sec.get("freeze_authority") == "ACTIVE":
        controls.update(status="REJECT", reason="active_token_authority",
                        observed_at=now, evidence_refs=["solana-rpc:getAccountInfo:" + mint])
    # Address validation prevents a mint from selecting an arbitrary local file.
    if not isinstance(mint, str) or not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", mint):
        return review
    path = Path("/var/lib/vivameda-wallet-intelligence/data") / (mint + ".json")
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("oversize")
        raw = path.read_bytes()
        report = json.loads(raw)
    except (OSError, ValueError):
        review["wallet_report_status"] = "unavailable_or_invalid"
        return review
    ts = report.get("generated_at")
    if (report.get("mint") != mint or report.get("schema") not in ("wallet-intelligence-v2","wallet-intelligence-v3")
        or type(ts) not in (int, float) or not 0 <= now-ts <= PREALERT_MAX_AGE_SECONDS):
        review["wallet_report_status"] = "identity_schema_or_freshness_failed"
        return review
    evidence_ref = "wallet-report-sha256:" + hashlib.sha256(raw).hexdigest()
    review["wallet_report_status"] = "partial_research_loaded"
    review["wallet_report_sha256"] = hashlib.sha256(raw).hexdigest()
    for name in ("wallet_clusters", "developer_history", "top_holder_ownership", "wallet_age"):
        review["checks"][name].update(observed_at=ts, evidence_refs=[evidence_ref],
            reason="partial_research_not_validated_screening")
    if report.get("schema") == "wallet-intelligence-v3":
        computed = screen_packet(report.get("screening_packet"),mint,pair.get("pairAddress"),creator,now)
        # Recompute policy from collector evidence; never accept report verdict.
        for name,item in computed.items():
            if name != "token_controls": review["checks"][name] = item
        review["wallet_report_status"] = "bounded_screening_evaluated"
        review["screening_policy"] = "crypto-screen-v2"
    # Never promote an arbitrary admission=PASS from research JSON.
    # A source-specific, validated screening adapter is required for each PASS.
    return review

def evaluate_prealert_review(review, mint, pair, sec, now):
    """Decide eligibility, not scam certainty. Only trusted collector output allowed."""
    if not isinstance(review, dict):
        return "HOLD", ["invalid_review"]
    if (review.get("policy") != PREALERT_POLICY or review.get("chain") != "solana"
        or review.get("mint") != mint or review.get("pair") != pair):
        return "HOLD", ["identity_or_policy_mismatch"]
    ts = review.get("checked_at")
    if type(ts) not in (int, float) or not 0 <= now - ts <= PREALERT_MAX_AGE_SECONDS:
        return "HOLD", ["stale_or_invalid_review"]
    if sec.get("mint_authority") == "ACTIVE" or sec.get("freeze_authority") == "ACTIVE":
        return "REJECT", ["active_token_authority"]
    reasons = []
    rejected = []
    if sec.get("mint_authority") != "REVOKED" or sec.get("freeze_authority") != "REVOKED":
        reasons.append("token_authority_unverified")
    checks = review.get("checks")
    if not isinstance(checks, dict):
        return "HOLD", ["missing_checks"]
    for name in PREALERT_CHECKS:
        item = checks.get(name)
        if isinstance(item, dict) and item.get("status") == "REJECT":
            rejected.append(name)
            continue
        if name not in PREALERT_REQUIRED:
            continue
        if not isinstance(item, dict):
            reasons.append(name + ":missing")
            continue
        refs = item.get("evidence_refs")
        observed = item.get("observed_at")
        valid_refs = (isinstance(refs, list) and bool(refs)
                      and all(isinstance(x, str) and x.strip() for x in refs))
        fresh = (type(observed) in (int, float)
                 and 0 <= now - observed <= PREALERT_MAX_AGE_SECONDS)
        if not valid_refs or not fresh:
            reasons.append(name + ":evidence_missing_or_stale")
        elif item.get("status") == "REJECT":
            rejected.append(name)
        elif item.get("status") != "PASS":
            reasons.append(name + ":unresolved")
    if rejected:
        return "REJECT", rejected + reasons
    return ("HOLD", reasons) if reasons else ("PASS", [])

def screening_summary(review, now):
    checks=review.get("checks",{})
    lines=["Required checks PASS: token controls, liquidity controls, verified sell receipts."]
    for name in PREALERT_CHECKS:
        if name in PREALERT_REQUIRED:continue
        item=checks.get(name,{})
        ts=item.get("observed_at")
        fresh=type(ts) in (int,float) and 0<=now-ts<=PREALERT_MAX_AGE_SECONDS
        refs=item.get("evidence_refs")
        verified=fresh and isinstance(refs,list) and bool(refs) and all(isinstance(r,str) and r.strip() for r in refs)
        status=item.get("status") if verified else "UNKNOWN"
        if status not in ("PASS","REJECT"):status="UNKNOWN"
        lines.append(name.replace("_"," ")+": "+status)
    lines.append("Background UNKNOWN checks are non-blocking. Not a safety guarantee.")
    return "\n".join(lines)+"\n"

def persist_prealert_review(con, mint, level, review, verdict, reasons, now):
    con.execute("""CREATE TABLE IF NOT EXISTS prealert_reviews(
        mint TEXT, level INTEGER, bucket INTEGER, checked_at INTEGER,
        policy TEXT, verdict TEXT, reasons TEXT, review TEXT,
        PRIMARY KEY(mint,level,bucket))""")
    con.execute("INSERT OR REPLACE INTO prealert_reviews VALUES(?,?,?,?,?,?,?,?)",
                (mint,level,now//300,now,PREALERT_POLICY,verdict,
                 json.dumps(reasons,sort_keys=True),json.dumps(review,sort_keys=True)))
    con.commit()


def telegram(text):
    c = json.loads(CREDS.read_text())
    r = SESSION.post("https://api.telegram.org/bot"+c["bot_token"]+"/sendMessage",
        data={"chat_id":str(c["chat_id"]),"text":text,
              "disable_web_page_preview":"true"}, timeout=12)
    r.raise_for_status()

def alert(con, row, pair, score, m, level):
    mint, created, creator, _, _, _ = row
    age = (int(time.time()*1000)-created)/3600000
    sec = basic_security(mint, creator)
    now = int(time.time())
    try:
        review = collect_prealert_review(mint, creator, pair, sec)
        verdict, reasons = evaluate_prealert_review(
            review, mint, pair.get("pairAddress"), sec, int(time.time()))
    except Exception:
        review = {"policy": PREALERT_POLICY, "mint": mint, "error": "review_failed"}
        verdict, reasons = "HOLD", ["review_failed"]
    review["admission_policy"] = PREALERT_ADMISSION_POLICY
    persist_prealert_review(con, mint, level, review, verdict, reasons, now)
    if verdict != "PASS":
        logging.info("PREALERT_%s %s reasons=%s", verdict, mint, reasons)
        return
    tag = "🟡 PRE-BREAKOUT" if level == 2 else "🟠 EARLY SCOUT"
    symbol = pair.get("baseToken",{}).get("symbol","?")
    qsym = pair.get("quoteToken",{}).get("symbol","?")
    msg = (
      "🚨💎 EARLY MEME SCOUT — SOLANA — " + tag + "\n\n"
      + f"{symbol} | age {age:.1f}h\n"
      + f"MC ${m['mc']:,.0f} | Liquidity ${m['liq']:,.0f}\n"
      + f"5m/1h: {m['pc5']:+.1f}% / {m['pc1']:+.1f}%\n"
      + f"Vol 5m ${m['vol5']:,.0f} | 1h ${m['vol1']:,.0f} ({m['vratio']:.0%} of MC)\n"
      + f"1h txns: {m['b1']} buys / {m['s1']} sells "
      + f"(buy-side {m['buy_ratio']:.0%}; NOT unique-wallet verified)\n"
      + f"30m band {m['band']:.0%} | net {m['net']:+.0%} | score {score}/11\n"
      + f"Mint/freeze: {sec['mint_authority']} / {sec['freeze_authority']}\n"
      + f"Creator holding: {sec['creator_pct']}% | top10 sampled owners: {sec['top10_raw_pct']}%\n"
      + screening_summary(review, int(time.time()))
      + f"Mint: {mint}\nPool: {pair.get('pairAddress')} ({pair.get('dexId')}/{qsym})\n"
      + f"https://dexscreener.com/solana/{pair.get('pairAddress')}"
    )
    telegram(msg)
    con.execute("UPDATE launches SET alert_level=?,last_alert_ts=? WHERE mint=?",
                (level, int(time.time()), mint))
    con.commit()
    logging.info("ALERT %s level=%s score=%s", mint, level, score)

def enrich_and_score(con):
    cand = candidates(con)
    if not cand:
        return
    by_mint = {}
    for p in dex_pairs([r[0] for r in cand]):
        by_mint.setdefault(p.get("baseToken",{}).get("address"), []).append(p)
    for row in cand:
        mint, _, _, _, _, pinned = row
        pair = choose_pair(mint, by_mint.get(mint, []), pinned)
        if not pair:
            continue
        record_pair(con, mint, pair)
        score, metrics, failed = score_candidate(history(con, mint))
        prev = con.execute("SELECT alert_level FROM launches WHERE mint=?",(mint,)).fetchone()[0]
        level = 2 if score >= 10 else (1 if score >= 8 else 0)
        if level > prev:
            try:
                alert(con, row, pair, score, metrics, level)
            except Exception as e:
                logging.exception("alert failed %s: %s", mint, e)

def main():
    con = db()
    last_score = 0
    logging.info("early scout started; strict pre-alert screening active; incomplete evidence HOLD")
    while True:
        try:
            rows = pump_rows("created_timestamp") + pump_rows("last_trade_timestamp")
            upsert_pump(con, rows)
            now = time.time()
            if now - last_score >= 60:
                enrich_and_score(con)
                last_score = now
            cutoff = int(time.time()) - 48*3600
            con.execute("DELETE FROM snapshots WHERE ts < ?", (cutoff,))
            con.commit()
        except Exception as e:
            logging.exception("loop error: %s", e)
        time.sleep(20)

if __name__ == "__main__":
    main()
