"""Deterministic bounded screening policy. PASS means policy eligible, never scam-free."""
import hashlib,json,math
POLICY="crypto-screen-v2"
CHECKS=("wallet_clusters","developer_history","top_holder_ownership","wallet_age","token_controls","liquidity_control","trading_mechanics")
LIMITS={"holder_window":86400,"developer_window":2592000,"max_age":300,
        "max_owner_pct":5.0,"max_top10_pct":30.0,"max_unseen_pct":10.0,
        "max_cluster_pct":10.0,"max_developer_pct":2.0,
        "min_holder_activity_age":86400,"min_developer_activity_age":604800,
        "max_young_share_pct":5.0,"min_distinct_sellers":3}
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
