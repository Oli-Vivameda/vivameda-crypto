#!/usr/bin/env python3
import hashlib, json, logging, math, re, sqlite3, time
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
                fc_observe_pairs(d, int(time.time()))
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

def alert(con, row, pair, score, m, level, ledger_rows=None, ledger_captured_ns=None, fc_cycle_id=None):
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
        fc_emit_screening(mint, fc_cycle_id, verdict, False)
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
    ledger_seq = None
    try:
        ledger_match(con)
        ledger_seq = ledger_record(con, mint, ledger_rows, ledger_captured_ns, score, level, pair.get("pairAddress"))
    except Exception:
        logging.exception("LEDGER_RECORD_FAILED")
        ledger_fail(con, "record_failed")
    try:
        telegram(msg)
    except Exception:
        fc_emit_screening(mint, fc_cycle_id, "PASS", False)
        try: ledger_delivery(con, ledger_seq, False)
        except Exception: ledger_fail(con, "delivery_record_failed")
        raise
    fc_emit_screening(mint, fc_cycle_id, "PASS", True)
    try: ledger_delivery(con, ledger_seq, True)
    except Exception: ledger_fail(con, "delivery_record_failed")
    con.execute("UPDATE launches SET alert_level=?,last_alert_ts=? WHERE mint=?",
                (level, int(time.time()), mint))
    con.commit()
    logging.info("ALERT %s level=%s score=%s", mint, level, score)

def enrich_and_score(con):
    cand = candidates(con)
    if not cand:
        fc_emit_cycle([], [], 0, str(time.time_ns()), int(time.time()))
        return
    by_mint = {}
    for p in dex_pairs([r[0] for r in cand]):
        by_mint.setdefault(p.get("baseToken",{}).get("address"), []).append(p)
    batch, failures = [], []
    for row in cand:
        mint, _, _, _, _, pinned = row
        pair = choose_pair(mint, by_mint.get(mint, []), pinned)
        if not pair:
            failures.append("pair_unavailable")
            continue
        record_pair(con, mint, pair)
        decision_rows = history(con, mint)
        captured_ns = time.time_ns()
        score, metrics, failed = score_candidate(decision_rows)
        prev = con.execute("SELECT alert_level FROM launches WHERE mint=?",(mint,)).fetchone()[0]
        if not metrics:
            failures.extend(failed if len(failed)==1 else ["invalid_score_inputs"])
            continue
        batch.append((row, pair, score, metrics, failed, prev, decision_rows, captured_ns))
    cycle_id, cycle_ts = str(time.time_ns()), int(time.time())
    cohort_ids = fc_emit_cycle(batch, failures, len(cand), cycle_id, cycle_ts)
    for row, pair, score, metrics, failed, prev, decision_rows, captured_ns in batch:
        mint = row[0]
        level = 2 if score >= 10 else (1 if score >= 8 else 0)
        if level > prev:
            try:
                alert(con, row, pair, score, metrics, level, decision_rows, captured_ns,
                      fc_cycle_id=cohort_ids.get(mint))
            except Exception as e:
                logging.exception("alert failed %s: %s", mint, e)

# Prospective ledger runtime v1. Lives in this source so the reviewed two-file
# crypto deployment includes the whole runtime. No extra service or paid calls.
LEDGER_VERSION = 'crypto_forward_v2_20261004_runtime1'
LEDGER_PLAN_SHA256 = '5e28cba35985815722e2fa253b651075982532bab1dea1bd4e39142c86dfb490'
LEDGER_FEATURES = ('band','pc5','pc1','buy_ratio','vol_mc','liq_change','vol_accel')
LEDGER_MODEL = {'type': 'L2 logistic regression', 'features': ['band', 'pc5', 'pc1', 'buy_ratio', 'vol_mc', 'liq_change', 'vol_accel'], 'mean': [0.5714515528356651, 1.4973809523809527, 283.97166666666664, 0.6768091230195044, 2.070681823692103, 0.10699170745855573, 1.0019364948704794], 'scale': [0.754161433235202, 13.38687809182378, 270.37848794321695, 0.12554634956569816, 1.3350089760204908, 0.2187470825003618, 1.297246962409168], 'coefficients': [-2.880440878205335, 0.22001863007987396, -0.21765489196635218, 0.592822938529118, 0.26169061959322854, -0.31379048968321765, -0.1442328037383409, 0.2574084979753935], 'source_sha256': '3e2af3efebd6e50127ff545e2a7eaaea38745fd10ba184b0d66901c26a2bb39c', 'production': False}

def ledger_json(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)

def ledger_hash(x):
    return hashlib.sha256(ledger_json(x).encode()).hexdigest()

def ledger_preprocess(rows):
    # Same seven numerical inputs as V2 features + scanner metrics. Raw rows
    # are copied before security review and persisted, not reconstructed later.
    if not rows:return {}
    cur=rows[-1];ps=[r[1] for r in rows if r[1]>0];ls=[r[3] for r in rows if r[3]>0]
    if not ps:return {}
    return {'band':(max(ps)-min(ps))/min(ps),'pc5':cur[10],'pc1':cur[11],
        'buy_ratio':cur[8]/max(1,cur[8]+cur[9]),'vol_mc':cur[5]/max(1,cur[2]),
        'liq_change':ls[-1]/ls[0]-1 if len(ls)>1 else 0,
        'vol_accel':cur[4]/max(1,cur[5]/12)}

def ledger_preprocessor_hash():
    import inspect
    return hashlib.sha256(inspect.getsource(ledger_preprocess).encode()).hexdigest()

def ledger_event(c,kind,key,payload,now):
    last=c.execute('SELECT seq,hash FROM pl_events ORDER BY seq DESC LIMIT 1').fetchone()
    seq=last[0]+1 if last else 1;prev=last[1] if last else '0'*64
    body=ledger_json(payload);h=ledger_hash([seq,kind,key,now,body,prev])
    c.execute('INSERT INTO pl_events VALUES(?,?,?,?,?,?,?)',(seq,kind,key,now,body,prev,h))
    return h

def ledger_initialize(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS pl_activation(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS pl_excluded(mint TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS pl_predictions(seq INTEGER PRIMARY KEY,mint TEXT UNIQUE NOT NULL,
      case_id TEXT UNIQUE NOT NULL,decision_ts INTEGER NOT NULL,body TEXT NOT NULL,valid INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS pl_results(seq INTEGER PRIMARY KEY,body TEXT NOT NULL,eligible INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS pl_events(seq INTEGER PRIMARY KEY,kind TEXT,key TEXT,ts INTEGER,
      body TEXT,previous_hash TEXT,hash TEXT,UNIQUE(kind,key));
    ''')
    for table in ('pl_activation','pl_excluded','pl_predictions','pl_results','pl_events'):
        for op in ('UPDATE','DELETE'):
            c.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'ledger append only'); END")
    c.execute("CREATE TRIGGER IF NOT EXISTS pl_exclusions_frozen BEFORE INSERT ON pl_excluded WHEN EXISTS(SELECT 1 FROM pl_activation) BEGIN SELECT RAISE(ABORT,'exclusions frozen'); END")
    c.commit();c.execute('PRAGMA synchronous=FULL')
    c.execute('BEGIN IMMEDIATE')
    try:
        row=c.execute('SELECT body FROM pl_activation').fetchone()
        if row:
            a=json.loads(row[0])
            if a['model_sha256']!=ledger_hash(LEDGER_MODEL) or a['preprocessor_sha256']!=ledger_preprocessor_hash():
                raise ValueError('frozen ledger model/preprocessor changed')
        else:
            # One transaction excludes ALL known mints before the activation time.
            c.execute('''INSERT INTO pl_excluded SELECT mint FROM launches UNION
                SELECT mint FROM snapshots UNION SELECT mint FROM v2_cases''')
            exclusions=[r[0] for r in c.execute('SELECT mint FROM pl_excluded ORDER BY mint')]
            now=int(time.time());a={'version':LEDGER_VERSION,'activated_at':now,
                'deadline':now+30*86400,'target_eligible':200,'horizon_seconds':3600,
                'max_lateness':180,'max_gap':180,'baseline_probability':3/42,
                'model_sha256':ledger_hash(LEDGER_MODEL),'model':LEDGER_MODEL,
                'preprocessor_sha256':ledger_preprocessor_hash(),'plan_sha256':LEDGER_PLAN_SHA256,
                'excluded_count':len(exclusions),'excluded_sha256':ledger_hash(exclusions),
                'time_semantics':'local input capture and decision UTC; provider observation time not asserted',
                'source':'ALERT decisions passing existing gates, before Telegram delivery'}
            c.execute('INSERT INTO pl_activation VALUES(1,?)',(ledger_json(a),))
            ledger_event(c,'activation','1',a,now)
        c.commit()
    except BaseException:c.rollback();raise
    logging.info('LEDGER_ACTIVATION %s',ledger_json({k:v for k,v in a.items() if k!='model'}))
    return a

def ledger_stop(c,reason,now,cutoff_seq=None):
    if not c.execute("SELECT 1 FROM pl_events WHERE kind='stop'").fetchone():
        ledger_event(c,'stop','1',{'reason':reason,'cutoff_seq':cutoff_seq},now)

def ledger_record(c,mint,rows,captured_ns,score,level,pair):
    c.commit();c.execute('BEGIN IMMEDIATE')
    try:
        a=json.loads(c.execute('SELECT body FROM pl_activation').fetchone()[0]);now=int(time.time())
        if now>=a['deadline']:
            ledger_stop(c,'time_limit',now);c.commit();return None
        if c.execute("SELECT 1 FROM pl_events WHERE kind='stop'").fetchone():c.commit();return None
        if c.execute('SELECT 1 FROM pl_excluded WHERE mint=?',(mint,)).fetchone() or c.execute('SELECT 1 FROM pl_predictions WHERE mint=?',(mint,)).fetchone():
            c.commit();return None
        if a['preprocessor_sha256']!=ledger_preprocessor_hash() or a['model_sha256']!=ledger_hash(LEDGER_MODEL):
            raise ValueError('frozen runtime changed')
        reason=None;x={};p=None
        if type(captured_ns) is not int or not a['activated_at']*10**9<=captured_ns<=time.time_ns():reason='capture_time'
        elif not rows or any(r[0]>captured_ns/10**9 for r in rows):reason='future_or_missing_input'
        else:
            try:
                x=ledger_preprocess(rows)
                if not all(type(x.get(k)) in (int,float) and math.isfinite(x[k]) for k in LEDGER_FEATURES):raise ValueError('features')
                if not all(type(v) in (int,float) and math.isfinite(v) for r in rows for v in r):raise ValueError('snapshot')
                if rows[-1][2]<=0:raise ValueError('entry market cap')
                m=a['model'];z=m['coefficients'][0]+sum(w*(x[k]-mu)/sd for k,w,mu,sd in zip(LEDGER_FEATURES,m['coefficients'][1:],m['mean'],m['scale']))
                p=1/(1+math.exp(-max(-40,min(40,z))))
            except (ValueError,TypeError,IndexError,ZeroDivisionError):reason='invalid_features_or_entry'
        # Store invalid attempts too, preventing a later replacement for the mint.
        clean=lambda v: v if type(v) in (int,float) and math.isfinite(v) else None
        raw=[[clean(v) for v in r] for r in (rows or [])]
        seq=c.execute('SELECT COALESCE(max(seq),0)+1 FROM pl_predictions').fetchone()[0]
        cid=f'{mint}:ledger:{now}'
        body={'decision_ts':now,'recorded_ns':time.time_ns(),'feature_capture_ns':captured_ns,
            'source_snapshot':raw,'source_snapshot_sha256':ledger_hash(raw),
            'features':{k:clean(v) for k,v in x.items()},'model_sha256':a['model_sha256'],
            'preprocessor_sha256':a['preprocessor_sha256'],'model_probability':p,
            'baseline_probability':3/42,'exclusion_reason':reason,'pair':pair,
            'entry_mc':rows[-1][2] if not reason else None,'source':'ALERT'}
        c.execute('INSERT INTO pl_predictions VALUES(?,?,?,?,?,?)',(seq,mint,cid,now,ledger_json(body),int(reason is None)))
        ledger_event(c,'prediction',str(seq),{'seq':seq,'mint':mint,'case_id':cid,**body},now)
        if reason is None:
            # Dedicated source keeps existing ALERT/SHADOW statistics separate.
            cur=rows[-1]
            c.execute('''INSERT INTO v2_cases(id,mint,decision_ts,source,score,level,regime,features,entry_price,entry_mc,entry_liq)
              VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(cid,mint,now,'LEDGER_ALERT',score,level,'FROZEN',ledger_json(x),cur[1],cur[2],cur[3]))
        else:
            result={'reason':reason,'eligible':False}
            c.execute('INSERT INTO pl_results VALUES(?,?,0)',(seq,ledger_json(result)))
            ledger_event(c,'result',str(seq),result,now)
        c.commit()
        head=c.execute('SELECT hash FROM pl_events ORDER BY seq DESC LIMIT 1').fetchone()[0]
        logging.info('LEDGER_RECORD seq=%s valid=%s head=%s',seq,reason is None,head)
        return seq
    except BaseException:c.rollback();raise

def ledger_fail(c,reason):
    # Ledger failures stop evaluation, not the existing alert service.
    c.rollback()
    try:
        c.execute('BEGIN IMMEDIATE');ledger_stop(c,'integrity_error:'+reason,int(time.time()));c.commit()
    except Exception:c.rollback();logging.exception('LEDGER_STOP_WRITE_FAILED')
    logging.error('LEDGER_EVALUATION_STOPPED %s',reason)

def ledger_delivery(c,seq,delivered):
    if seq is None:return
    c.execute('BEGIN IMMEDIATE')
    try:
        ledger_event(c,'delivery',str(seq),{'delivered':bool(delivered)},int(time.time()));c.commit()
    except BaseException:c.rollback();raise

def ledger_match(c):
    # No label summaries or comparative scores are logged before the fixed stop.
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='pl_activation'").fetchone():return
    arow=c.execute('SELECT body FROM pl_activation').fetchone()
    if not arow:return
    c.commit();c.execute('BEGIN IMMEDIATE')
    try:
        a=json.loads(arow[0]);now=int(time.time())
        pending=c.execute('''SELECT p.seq,p.case_id,p.decision_ts,p.body FROM pl_predictions p
          LEFT JOIN pl_results r ON r.seq=p.seq WHERE r.seq IS NULL ORDER BY p.seq''').fetchall()
        for seq,cid,dts,pbody in pending:
            if now<dts+3600:continue
            row=c.execute('''SELECT o.observed_ts,o.lateness,o.mc,m.coverage_ok,m.max_gap
              FROM v2_outcomes o LEFT JOIN v2_horizon_metrics m ON m.id=o.id AND m.horizon=o.horizon
              WHERE o.id=? AND o.horizon=60''',(cid,)).fetchone()
            if row is None and now<=dts+3780:continue
            reason='missing_endpoint';mult=None;ok=False
            if row:
                ots,late,mc,coverage,gap=row;entry=json.loads(pbody)['entry_mc']
                if type(late) not in (int,float) or not 0<=late<=180 or ots!=dts+3600+late:reason='invalid_timing'
                elif coverage!=1 or gap is None or gap>180:reason='incomplete_coverage'
                elif type(mc) not in (int,float) or not math.isfinite(mc) or mc<=0 or entry<=0:reason='invalid_endpoint'
                else:ok=True;reason=None;mult=mc/entry
            result={'eligible':ok,'reason':reason,'multiple':mult,'outcome':int(mult>=2) if ok else None,
                'matched_at':now,'endpoint_evidence':list(row) if row else None}
            c.execute('INSERT INTO pl_results VALUES(?,?,?)',(seq,ledger_json(result),int(ok)))
            ledger_event(c,'result',str(seq),result,now)
        # Resolve in decision order: later outcomes cannot select the cohort
        # ahead of an earlier case still waiting for its allowed endpoint.
        n=0;cutoff=None
        for seq,eligible in c.execute('SELECT p.seq,r.eligible FROM pl_predictions p LEFT JOIN pl_results r ON r.seq=p.seq ORDER BY p.seq'):
            if eligible is None:break
            n+=eligible
            if n==a['target_eligible']:cutoff=seq;break
        if cutoff is not None:ledger_stop(c,'sample_limit',now,cutoff)
        elif now>=a['deadline']:ledger_stop(c,'time_limit',now)
        c.commit()
    except BaseException:c.rollback();raise

def ledger_health(c):
    arow=c.execute('SELECT body FROM pl_activation').fetchone()
    if not arow:return {'status':'not_activated'}
    a=json.loads(arow[0]);stop=c.execute("SELECT body FROM pl_events WHERE kind='stop'").fetchone()
    pred=c.execute('SELECT count(*) FROM pl_predictions').fetchone()[0]
    matched=c.execute('SELECT count(*),COALESCE(sum(eligible),0) FROM pl_results').fetchone()
    head=c.execute('SELECT seq,hash FROM pl_events ORDER BY seq DESC LIMIT 1').fetchone()
    return {'status':'enrollment_stopped' if stop else 'active','activated_at':a['activated_at'],
        'deadline':a['deadline'],'predictions_or_exclusions':pred,'matched':matched[0],
        'eligible':matched[1],'stop':json.loads(stop[0]) if stop else None,
        'head_seq':head[0],'head_sha256':head[1],'excluded_mints':a['excluded_count']}


def main():
    con = db()
    try: ledger_initialize(con)
    except Exception:
        logging.exception("LEDGER_INITIALIZATION_FAILED")
        ledger_fail(con, "initialization_failed")
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

# Passive forward capture: reviewed embedded core + adapter.
"""Private, passive candidate capture. No network, production imports or trading.

Caller supplies exact scanner inputs and provider-response receipt times.
This module is an engineering candidate; no runtime integration is activated.
"""
import hashlib
import json
import math
import sqlite3
FC_CORE_SIGNALS = ('liq25k', 'vol_mc25', 'buy52', 'h1_not_extended', 'm5_not_extended', 'band_compact', 'net_constructive', 'higher_low', 'liq_stable', 'volume_accel', 'txns100')
FC_CORE_FIELDS = {'mint', 'pair', 'created_ts', 'captured_ts', 'snapshot_ts', 'points', 'history_seconds', 'mc', 'liq', 'vol1', 'score', 'signals', 'prior_alert_level', 'input_sha256'}

def fc_core_canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def fc_core_digest(value):
    return hashlib.sha256(fc_core_canonical(value).encode()).hexdigest()

def fc_core_number(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and (value >= minimum)

def fc_core_integer(value, minimum=0):
    return type(value) is int and value >= minimum

def fc_core_validate(row, cycle_ts):
    if set(row) != FC_CORE_FIELDS:
        raise ValueError('unexpected or missing decision fields')
    for key in ('mint', 'pair'):
        if not isinstance(row[key], str) or not 1 <= len(row[key]) <= 100:
            raise ValueError(key)
    for key in ('created_ts', 'captured_ts', 'snapshot_ts', 'points', 'history_seconds', 'score', 'prior_alert_level'):
        if not fc_core_integer(row[key]):
            raise ValueError(key)
    if not row['created_ts'] <= row['captured_ts'] <= cycle_ts:
        raise ValueError('future decision or creation')
    if not 1800 <= row['captured_ts'] - row['created_ts'] <= 21600:
        raise ValueError('outside current scanner age universe')
    if not 0 <= row['captured_ts'] - row['snapshot_ts'] <= 120:
        raise ValueError('stale or future snapshot')
    if cycle_ts - row['captured_ts'] > 120:
        raise ValueError('cycle inputs not contemporaneous')
    for key in ('mc', 'liq', 'vol1'):
        if not fc_core_number(row[key]):
            raise ValueError(key)
    s = row['signals']
    if not isinstance(s, dict) or set(s) != set(FC_CORE_SIGNALS) or any((type(v) is not bool for v in s.values())) or (row['score'] != sum(s.values())):
        raise ValueError('exact emitted signal vector required')
    h = row['input_sha256']
    if not isinstance(h, str) or len(h) != 64 or any((c not in '0123456789abcdef' for c in h)):
        raise ValueError('input hash')
    return row

def fc_core_eligible(row):
    return row['points'] >= 4 and row['history_seconds'] >= 600 and (30000 <= row['mc'] <= 750000) and (row['liq'] >= 25000) and (row['vol1'] >= 20000)

def fc_core_matched_controls(alert, rows):
    """Same-cycle, outcome-blind controls; do not match score components."""
    age = alert['captured_ts'] - alert['created_ts']
    possible = []
    for row in rows:
        if row['mint'] == alert['mint'] or not fc_core_eligible(row) or row['score'] >= 8 or (row['prior_alert_level'] != 0):
            continue
        control_age = row['captured_ts'] - row['created_ts']
        if abs(control_age - age) > 900:
            continue
        if not (0.5 <= row['mc'] / alert['mc'] <= 2 and 0.5 <= row['liq'] / alert['liq'] <= 2):
            continue
        distance = abs(control_age - age) / 900 + abs(math.log(row['mc'] / alert['mc'])) + abs(math.log(row['liq'] / alert['liq']))
        possible.append((distance, row['mint'], row))
    return [r for _, _, r in sorted(possible)[:3]]

def fc_core_initialize(con, activation_ts, excluded_mints, protocol_sha256, runtime_binding=None):
    """Explicit initialization only. Runtime lives outside the git checkout."""
    if not fc_core_integer(activation_ts) or not isinstance(protocol_sha256, str) or len(protocol_sha256) != 64 or any((c not in '0123456789abcdef' for c in protocol_sha256)):
        raise ValueError('activation')
    con.executescript('\n    CREATE TABLE IF NOT EXISTS fc_activation(id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);\n    CREATE TABLE IF NOT EXISTS fc_excluded(mint TEXT PRIMARY KEY);\n    CREATE TABLE IF NOT EXISTS fc_events(seq INTEGER PRIMARY KEY, kind TEXT NOT NULL,\n      event_key TEXT NOT NULL, body TEXT NOT NULL, previous_hash TEXT NOT NULL,\n      hash TEXT NOT NULL, UNIQUE(kind,event_key));\n    ')
    for table in ('fc_activation', 'fc_events', 'fc_excluded'):
        for op in ('UPDATE', 'DELETE'):
            con.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'capture append only'); END")
    exclusions = sorted(set(excluded_mints))
    if any((not isinstance(m, str) or not m for m in exclusions)):
        raise ValueError('exclusions')
    con.execute("CREATE TRIGGER IF NOT EXISTS fc_excluded_frozen BEFORE INSERT ON fc_excluded WHEN EXISTS(SELECT 1 FROM fc_activation) BEGIN SELECT RAISE(ABORT,'exclusions frozen'); END")
    body_value = {'activation_ts': activation_ts, 'deadline': activation_ts + 14 * 86400, 'excluded_count': len(exclusions), 'excluded_sha256': fc_core_digest(exclusions), 'protocol_sha256': protocol_sha256, 'schema': 1}
    if runtime_binding is not None:
        if set(runtime_binding) != {'scanner_sha256', 'tracker_sha256'}:
            raise ValueError('runtime binding fields')
        if any((not isinstance(v, str) or len(v) != 64 or any((ch not in '0123456789abcdef' for ch in v)) for v in runtime_binding.values())):
            raise ValueError('runtime binding hashes')
        body_value.update(runtime_binding)
    body = fc_core_canonical(body_value)
    existing = con.execute('SELECT body FROM fc_activation').fetchone()
    if existing and existing[0] != body:
        raise ValueError('activation cannot change')
    if not existing:
        con.executemany('INSERT INTO fc_excluded VALUES(?)', [(m,) for m in exclusions])
        con.execute('INSERT INTO fc_activation VALUES(1,?)', (body,))
    con.commit()

def fc_core_activation(con):
    row = con.execute('SELECT body FROM fc_activation').fetchone()
    if not row:
        raise ValueError('not activated')
    return json.loads(row[0])

def fc_core_append(con, kind, key, payload):
    body = fc_core_canonical(payload)
    existing = con.execute('SELECT body,hash FROM fc_events WHERE kind=? AND event_key=?', (kind, key)).fetchone()
    if existing:
        if existing[0] != body:
            raise ValueError('conflicting replay')
        return existing[1]
    last = con.execute('SELECT seq,hash FROM fc_events ORDER BY seq DESC LIMIT 1').fetchone()
    seq, previous = (last[0] + 1, last[1]) if last else (1, '0' * 64)
    h = fc_core_digest([seq, kind, key, body, previous])
    con.execute('INSERT INTO fc_events VALUES(?,?,?,?,?,?)', (seq, kind, key, body, previous, h))
    return h

def fc_core_verify(con):
    previous = '0' * 64
    for expected, (seq, kind, key, body, prev, h) in enumerate(con.execute('SELECT * FROM fc_events ORDER BY seq'), 1):
        if seq != expected or prev != previous or h != fc_core_digest([seq, kind, key, body, prev]):
            raise ValueError('capture integrity failed')
        previous = h
    return previous

def fc_core_record_cycle(con, cycle_id, cycle_ts, rows, scanner_sha256, verifier=fc_core_verify):
    """Atomic complete evaluated cycle; capture before screening/delivery.

    Input errors reject the whole cycle. Outcome fields are not accepted.
    The adapter must pass EVERY successfully scored input, not a score subset.
    """
    if not fc_core_integer(cycle_ts) or not isinstance(cycle_id, str) or (not cycle_id):
        raise ValueError('cycle')
    if not isinstance(scanner_sha256, str) or len(scanner_sha256) != 64 or any((c not in '0123456789abcdef' for c in scanner_sha256)):
        raise ValueError('scanner hash')
    a = fc_core_activation(con)
    if cycle_ts < a['activation_ts']:
        raise ValueError('preactivation cycle')
    if cycle_ts >= a['deadline']:
        raise ValueError('pilot enrollment stopped')
    checked = sorted([fc_core_validate(dict(r), cycle_ts) for r in rows], key=lambda r: r['mint'])
    if len({r['mint'] for r in checked}) != len(checked):
        raise ValueError('duplicate mint in cycle')
    if any((r['captured_ts'] < a['activation_ts'] for r in checked)):
        raise ValueError('preactivation input')
    if len(checked) > 60:
        raise ValueError('cycle exceeds current scanner cap')
    if any((fc_core_eligible(r) and (not r['signals']['liq25k']) for r in checked)):
        raise ValueError('eligible row contradicts liquidity signal')
    excluded = {r['mint'] for r in checked if con.execute('SELECT 1 FROM fc_excluded WHERE mint=?', (r['mint'],)).fetchone()}
    with con:
        verifier(con)
        key = str(cycle_id)
        payload = {'cycle_ts': cycle_ts, 'scanner_sha256': scanner_sha256, 'rows': checked}
        existing = con.execute("SELECT body FROM fc_events WHERE kind='cycle' AND event_key=?", (key,)).fetchone()
        if existing:
            fc_core_append(con, 'cycle', key, payload)
            return []
        fc_core_append(con, 'cycle', key, payload)
        enrolled = {json.loads(r[0])['mint'] for r in con.execute("SELECT body FROM fc_events WHERE kind='cohort'")}
        added = []
        for row in checked:
            if row['mint'] in excluded or row['mint'] in enrolled or (not fc_core_eligible(row)) or (row['score'] < 8) or (row['prior_alert_level'] != 0):
                continue
            controls = fc_core_matched_controls(row, [r for r in checked if r['mint'] not in excluded and r['mint'] not in enrolled])
            cohort = {'mint': row['mint'], 'cycle_id': key, 'index_ts': cycle_ts, 'alert_input': row, 'controls': controls, 'screening': 'not_yet_observed'}
            fc_core_append(con, 'cohort', row['mint'], cohort)
            added.append(cohort)
        return added

def fc_core_record_screening(con, mint, cycle_id, observed_ts, verdict, delivered, verifier=fc_core_verify):
    if verdict not in ('PASS', 'HOLD', 'REJECT', 'ERROR') or type(delivered) is not bool:
        raise ValueError('screening')
    if delivered and verdict != 'PASS':
        raise ValueError('delivery without pass')
    row = con.execute("SELECT body FROM fc_events WHERE kind='cohort' AND event_key=?", (mint,)).fetchone()
    if not row:
        raise ValueError('cohort missing')
    cohort = json.loads(row[0])
    if cycle_id != cohort['cycle_id'] or not fc_core_integer(observed_ts) or observed_ts < cohort['index_ts']:
        raise ValueError('screening timing')
    with con:
        verifier(con)
        return fc_core_append(con, 'screening', mint, {'observed_ts': observed_ts, 'verdict': verdict, 'delivered': delivered})

def fc_core_record_observation(con, mint, pair, received_ts, mc, verifier=fc_core_verify):
    if any((not isinstance(s, str) or not 1 <= len(s) <= 100 for s in (mint, pair))):
        raise ValueError('observation identity')
    if not fc_core_integer(received_ts) or not fc_core_number(mc, 1e-06):
        raise ValueError('observation')
    a = fc_core_activation(con)
    if received_ts < a['activation_ts']:
        raise ValueError('preactivation observation')
    if received_ts > a['deadline'] + 3780:
        raise ValueError('pilot follow-up stopped')
    with con:
        verifier(con)
        return fc_core_append(con, 'observation', fc_core_canonical([mint, pair, received_ts]), {'mint': mint, 'pair': pair, 'received_ts': received_ts, 'mc': mc})

def fc_core_endpoint(con, entry, index_ts, now):
    """Pure read after window closes. Earliest valid same-pair local receipt."""
    if not fc_core_integer(now) or now <= index_ts + 3780:
        raise ValueError('endpoint window still open')
    fc_core_verify(con)
    observations = [json.loads(r[0]) for r in con.execute("SELECT body FROM fc_events WHERE kind='observation'")]
    rows = sorted((r for r in observations if r['mint'] == entry['mint'] and r['pair'] == entry['pair'] and (index_ts + 3600 <= r['received_ts'] <= index_ts + 3780)), key=lambda r: r['received_ts'])
    if not rows:
        return {'eligible': False, 'reason': 'missing_timed_same_pair_endpoint', 'multiple': None}
    r = rows[0]
    return {'eligible': True, 'received_ts': r['received_ts'], 'lateness': r['received_ts'] - index_ts - 3600, 'multiple': r['mc'] / entry['mc']}

"""Embedded into early_scout.py by build_integration.py; no extra imports/files.

Core functions have fc_core_ names. Integration remains dormant unless a
separately reviewed activation creates the private database and binding.
"""
FC_DIRECTORY = BASE / 'data' / 'forward_capture'
FC_PROTOCOL_SHA256 = '3baef84dc6f3dfddff9ea38c1139c4979b86af0d4dbb66e641ea00b44b7359ad'
FC_SCORER_SHA256 = '4f5c0fd4c978b45b51368e2f364db83f50f557ca0788edc977947c93f3b90b78'
FC_AMENDMENT_SHA256 = '20ceb6f4d9c9a2024ffb802f9c8642b5e7509af263245b3b6fea498383878fdd'
FC_ORIGINAL_SCANNER_SHA256 = '3e73978a41e2e21e090a7eea92bbdc1a52dc190ce229ac262a3c6a2b0af6a043'
FC_MAX_BYTES = 512 * 1024 * 1024
FC_MIN_DISK_BYTES = 2 * 1024 * 1024 * 1024
_fc_connection = None
_fc_verified = (0, '0' * 64)
_fc_paused = False


def fc_guard(con):
    """Full verification on process open; then anchored append verification.

    Old rows are protected by immutable triggers. Privileged rewrite of an
    old prefix is detected at restart/full audit, not guaranteed each append.
    """
    global _fc_verified
    seq, previous = _fc_verified
    if seq:
        anchor = con.execute('SELECT seq,kind,event_key,body,previous_hash,hash FROM fc_events WHERE seq=?', (seq,)).fetchone()
        if not anchor or anchor[-1] != previous or anchor[-1] != fc_core_digest(list(anchor[:-1])):
            raise ValueError('capture anchor changed')
    for row in con.execute('SELECT * FROM fc_events WHERE seq>? ORDER BY seq', (seq,)):
        n, kind, key, body, prev, h = row
        if n != seq + 1 or prev != previous or h != fc_core_digest([n, kind, key, body, prev]):
            raise ValueError('capture append chain changed')
        seq, previous = n, h
    _fc_verified = (seq, previous)
    return previous


def fc_safe_reason(error):
    # Static allowlist only: exception text may contain identities or paths.
    allowed = {'incomplete candidate accounting', 'provider or capture failure invalidates cycle',
               'capture runtime binding', 'capture tracker binding', 'capture repair binding',
               'capture immutability triggers missing', 'capture exclusion binding',
               'capture integrity failed', 'capture anchor changed', 'capture append chain changed',
               'capture storage cap', 'capture minimum free disk', 'exact score replay mismatch',
               'future decision or creation', 'outside current scanner age universe',
               'stale or future snapshot', 'cycle inputs not contemporaneous',
               'exact emitted signal vector required'}
    return str(error) if type(error) is ValueError and str(error) in allowed else 'other_capture_error'


def fc_pause(error):
    global _fc_paused
    _fc_paused = True
    logging.error('FORWARD_CAPTURE_PAUSED reason=%s', type(error).__name__)
    try:
        # Count-only health artifact. No identities, endpoints or exception text.
        if FC_DIRECTORY.is_dir():
            p = FC_DIRECTORY / 'PAUSED.json'
            import os
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as out:
                out.write(json.dumps({'paused': True, 'reason': type(error).__name__,
                                      'observed_ts': int(time.time()),
                                      'code': fc_safe_reason(error)}))
    except OSError:
        logging.error('FORWARD_CAPTURE_PAUSE_MARKER_FAILED')


def fc_connection():
    global _fc_connection, _fc_verified
    if _fc_paused or (FC_DIRECTORY / 'PAUSED.json').exists():
        return None
    database = FC_DIRECTORY / 'capture.sqlite'
    if not database.exists():
        return None  # No autoactivation, schema creation or private-file writes.
    import shutil
    if sum(p.stat().st_size for p in FC_DIRECTORY.glob('capture.sqlite*')) >= FC_MAX_BYTES:
        raise ValueError('capture storage cap')
    if shutil.disk_usage(FC_DIRECTORY).free < FC_MIN_DISK_BYTES:
        raise ValueError('capture minimum free disk')
    if _fc_connection is None:
        con = sqlite3.connect('file:' + str(database) + '?mode=rw', uri=True, timeout=0.1)
        try:
            con.execute('PRAGMA busy_timeout=100')
            con.execute('PRAGMA synchronous=FULL')
            a = fc_core_activation(con)
            # Verify before trusting a hash-bound recovery event.
            fc_core_verify(con)
            repair = con.execute("SELECT body FROM fc_events WHERE kind='runtime_repair' ORDER BY seq DESC LIMIT 1").fetchone()
            binding = a['scanner_sha256']
            if repair:
                r = json.loads(repair[0])
                if (r.get('original_scanner_sha256') != FC_ORIGINAL_SCANNER_SHA256 or
                    r.get('amendment_sha256') != FC_AMENDMENT_SHA256 or
                    r.get('tracker_sha256') != a['tracker_sha256'] or
                    r.get('activation_ts') != a['activation_ts'] or r.get('deadline') != a['deadline']):
                    raise ValueError('capture repair binding')
                binding = r['scanner_sha256']
            if a['protocol_sha256'] != FC_PROTOCOL_SHA256 or binding != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
                raise ValueError('capture runtime binding')
            if a['tracker_sha256'] != hashlib.sha256(Path(__file__).with_name('scout_learning_v2.py').read_bytes()).hexdigest():
                raise ValueError('capture tracker binding')
            # No runtime trigger installation: reviewed activation owns schema.
            names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
            if not {'fc_activation_no_UPDATE', 'fc_activation_no_DELETE',
                    'fc_events_no_UPDATE', 'fc_events_no_DELETE',
                    'fc_excluded_no_UPDATE', 'fc_excluded_no_DELETE', 'fc_excluded_frozen'} <= names:
                raise ValueError('capture immutability triggers missing')
            exclusions = [r[0] for r in con.execute('SELECT mint FROM fc_excluded ORDER BY mint')]
            if len(exclusions) != a['excluded_count'] or fc_core_digest(exclusions) != a['excluded_sha256']:
                raise ValueError('capture exclusion binding')
            fc_core_verify(con)
            head = con.execute('SELECT seq,hash FROM fc_events ORDER BY seq DESC LIMIT 1').fetchone()
            _fc_verified = tuple(head) if head else (0, '0'*64)
            _fc_connection = con
        except BaseException:
            con.close()
            raise
    return _fc_connection


def fc_emit_cycle(batch, failures, selected_count, cycle_id, cycle_ts):
    """Persist raw exact rows and the admitted common cycle atomically."""
    try:
        con = fc_connection()
        if con is None:
            return {}
        a = fc_core_activation(con)
        if cycle_ts >= a['deadline']:
            return {}
        if selected_count > 60 or len(batch) + len(failures) != selected_count:
            raise ValueError('incomplete candidate accounting')
        if any(reason not in ('history', 'base_gate', 'price_history', 'pair_unavailable') for reason in failures):
            raise ValueError('provider or capture failure invalidates cycle')
        if 'pair_unavailable' in failures:
            # Reject the WHOLE cycle, with no input/cohort/endpoint substitution.
            con.execute('BEGIN IMMEDIATE')
            try:
                fc_guard(con)
                fc_core_append(con, 'rejected_cycle', cycle_id,
                               {'cycle_ts': cycle_ts, 'selected': selected_count,
                                'pair_unavailable': failures.count('pair_unavailable'),
                                'scored_discarded': len(batch),
                                'amendment_sha256': FC_AMENDMENT_SHA256})
                con.commit()
            except BaseException:
                con.rollback()
                raise
            return {}
        rows = []
        for item in batch:
            row, pair, score, metrics, failed, prev, history_rows, captured_ns = item
            mint, created_ms, _, _, _, _ = row
            captured_ts = captured_ns // 1000000000
            if not metrics:
                continue
            exact = [list(r) for r in history_rows]
            signals = {k: k not in failed for k in FC_CORE_SIGNALS}
            record = {'mint': mint, 'pair': pair['pairAddress'], 'created_ts': int(created_ms // 1000),
                      'captured_ts': captured_ts, 'snapshot_ts': int(history_rows[-1][0]),
                      'points': len(history_rows), 'history_seconds': int(history_rows[-1][0]-history_rows[0][0]),
                      'mc': metrics['mc'], 'liq': metrics['liq'], 'vol1': metrics['vol1'],
                      'score': score, 'signals': signals, 'prior_alert_level': prev,
                      'input_sha256': fc_core_digest(exact)}
            fc_core_validate(record, cycle_ts)
            # Validate exact vector against unchanged production scorer.
            actual_score, actual_metrics, actual_failed = score_candidate(exact)
            if actual_score != score or actual_metrics != metrics or actual_failed != failed:
                raise ValueError('exact score replay mismatch')
            rows.append((record, exact))
        con.execute('BEGIN IMMEDIATE')
        try:
            fc_guard(con)
            fc_core_append(con, 'cycle_health', cycle_id, {'cycle_ts': cycle_ts,
                           'selected': selected_count, 'scored': len(rows),
                           'admission_failures': sorted(failures)})
            # Keep immutable raw input evidence private, once per content hash.
            for record, exact in rows:
                fc_core_append(con, 'inputs', record['input_sha256'], exact)
            cohorts = fc_core_record_cycle(con, cycle_id, cycle_ts, [r for r, _ in rows],
                                         hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), verifier=fc_guard)
            return {r['mint']: cycle_id for r in cohorts}
        except BaseException:
            con.rollback()
            raise
    except Exception as error:
        fc_pause(error)
        return {}


def fc_emit_screening(mint, cycle_id, verdict, delivered):
    if cycle_id is None:
        return
    try:
        con = fc_connection()
        if con is None:
            return
        con.execute('BEGIN IMMEDIATE')
        fc_core_record_screening(con, mint, cycle_id, int(time.time()), verdict, delivered, verifier=fc_guard)
    except Exception as error:
        if _fc_connection is not None:
            _fc_connection.rollback()
        fc_pause(error)


def fc_count_status():
    """Operational counts only; never probabilities, multiples or identities."""
    try:
        con = fc_connection()
        if con is None:
            return {'status': 'paused' if _fc_paused or (FC_DIRECTORY/'PAUSED.json').exists() else 'not_activated'}
        a = fc_core_activation(con)
        cohorts = [json.loads(r[0]) for r in con.execute("SELECT body FROM fc_events WHERE kind='cohort'")]
        return {'status': 'enrollment_stopped' if int(time.time()) >= a['deadline'] else 'collecting',
                'activation_ts': a['activation_ts'], 'deadline': a['deadline'],
                'cycles': con.execute("SELECT count(*) FROM fc_events WHERE kind='cycle'").fetchone()[0],
                'qualified_events': len(cohorts),
                'matched_events': sum(bool(r['controls']) for r in cohorts),
                'control_entries': sum(len(r['controls']) for r in cohorts),
                'screening_events': con.execute("SELECT count(*) FROM fc_events WHERE kind='screening'").fetchone()[0],
                'timed_observation_rows': con.execute("SELECT count(*) FROM fc_events WHERE kind='observation'").fetchone()[0]}
    except Exception as error:
        fc_pause(error)
        return {'status':'paused'}


def fc_observe_pairs(pairs, received_ts):
    """Accept only already fetched pairs; no new request or polling selection."""
    try:
        con = fc_connection()
        if con is None:
            return
        a = fc_core_activation(con)
        if received_ts > a['deadline'] + 3780:
            return
        # Only store endpoint-window observations relevant to frozen cohorts.
        wanted = set()
        for (body,) in con.execute("SELECT body FROM fc_events WHERE kind='cohort'"):
            cohort = json.loads(body)
            if cohort['index_ts'] + 3600 <= received_ts <= cohort['index_ts'] + 3780:
                for entry in [cohort['alert_input']] + cohort['controls']:
                    wanted.add((entry['mint'], entry['pair']))
        if not wanted:
            return
        con.execute('BEGIN IMMEDIATE')
        try:
            fc_guard(con)
            for pair in pairs:
                mint = (pair.get('baseToken') or {}).get('address')
                identity = (mint, pair.get('pairAddress'))
                mc = pair.get('marketCap')
                # Invalid/unavailable evidence remains missing, never zero.
                if identity not in wanted or not fc_core_number(mc, 0.000001):
                    continue
                fc_core_append(con, 'observation', fc_core_canonical([*identity, received_ts]),
                               {'mint': mint, 'pair': identity[1], 'received_ts': received_ts, 'mc': mc})
            con.commit()
        except BaseException:
            con.rollback()
            raise
    except Exception as error:
        fc_pause(error)


if __name__ == "__main__":
    main()
