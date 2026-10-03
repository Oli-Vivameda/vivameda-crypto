"""Pump AMM evidence decoding, pinned to official IDL inspected 2026-10-03.
Unknown layouts/programs remain unsupported. No transaction construction.
"""
import base64,struct
PUMP="pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
SPL="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN22="TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ALPHABET="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
POOL=bytes([241,154,109,4,17,177,109,188])
OPS={bytes([51,230,133,164,1,127,131,173]):("sell",1),
     bytes([183,18,70,156,148,109,161,34]):("withdraw",2),
     bytes([102,6,61,18,1,218,235,234]):("buy",1)}
def b58encode(raw):
    zero=len(raw)-len(raw.lstrip(b"\0"));n=int.from_bytes(raw,"big");s=""
    while n:n,r=divmod(n,58);s=ALPHABET[r]+s
    return "1"*zero+s
def b58decode(value):
    if not isinstance(value,str) or len(value)>4096: raise ValueError("invalid base58")
    n=0
    for c in value:n=n*58+ALPHABET.index(c)
    zero=len(value)-len(value.lstrip("1"))
    return b"\0"*zero+(n.to_bytes((n.bit_length()+7)//8,"big") if n else b"")
def pool_state(account):
    if not isinstance(account,dict) or account.get("owner")!=PUMP or account.get("executable"):
        raise ValueError("unsupported pool owner")
    data=account.get("data")
    if not isinstance(data,list) or len(data)<2 or data[1]!="base64": raise ValueError("encoding")
    raw=base64.b64decode(data[0],validate=True)
    if len(raw)<243 or raw[:8]!=POOL: raise ValueError("unknown pool layout")
    names=("creator","base_mint","quote_mint","lp_mint","base_vault","quote_vault")
    out={name:b58encode(raw[11+32*i:43+32*i]) for i,name in enumerate(names)}
    out["recorded_lp_supply"]=struct.unpack_from("<Q",raw,203)[0]
    out["coin_creator"]=b58encode(raw[211:243])
    out["layout_bytes"]=len(raw)
    out["advanced_controls_verified"]=False
    # Optional newer fields are recorded, not assumed absent in older layouts.
    if len(raw)>=271 and all(raw[i] in (0,1) for i in (243,244,269,270)):
        out.update(is_mayhem_mode=bool(raw[243]),is_cashback_coin=bool(raw[244]),
            virtual_quote_reserves=int.from_bytes(raw[245:261],"little",signed=True),
            creator_fee_bps=struct.unpack_from("<Q",raw,261)[0],
            can_edit_creator_fee=bool(raw[269]),is_holder_reward=bool(raw[270]),
            advanced_controls_verified=True)
    return out
def token_controls(account):
    result={"status":"UNKNOWN","reason":"unverified_token_account"}
    if not isinstance(account,dict) or account.get("owner") not in (SPL,TOKEN22) or account.get("executable"):
        return result
    parsed=account.get("data",{}).get("parsed",{}) if isinstance(account.get("data"),dict) else {}
    if not isinstance(parsed,dict): return result
    info=parsed.get("info",{})
    if not isinstance(info,dict): return result
    if account.get("owner")==TOKEN22 and "extensions" not in info: return result
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

PUMP_LAUNCH_PROGRAM="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
def launch_v2_instruction(ins):
    """Two observed layouts reviewed against pump-public-docs IDL ffe966c42f1a."""
    if ins.get("programId")!=PUMP_LAUNCH_PROGRAM:return None
    accounts=ins.get("accounts")
    if not isinstance(accounts,list) or len(accounts)<27:return None
    try:
        if any(len(b58decode(a))!=32 for a in accounts):return None
        raw=b58decode(ins.get("data"))
    except (ValueError,TypeError):return None
    system="11111111111111111111111111111111"
    associated="ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
    if raw[:8]==bytes([184,23,238,97,103,197,211,61]) and len(raw)==24:
        if (accounts[3] not in (SPL,TOKEN22) or accounts[4] not in (SPL,TOKEN22)
            or accounts[5]!=associated or accounts[24]!=system or accounts[26]!=PUMP_LAUNCH_PROGRAM):return None
        amount=int.from_bytes(raw[8:16],"little")
        if amount<=0:return None
        return {"relation":"pump_launch_buy_v2","source":accounts[13],"target":accounts[1],"raw_instruction_amount":str(amount)}
    if raw[:8]==bytes([187,203,18,31,206,237,254,41]) and len(raw)==8:
        if (accounts[8]!=system or accounts[9]!=PUMP or accounts[19] not in (SPL,TOKEN22)
            or accounts[20] not in (SPL,TOKEN22) or accounts[21]!=TOKEN22
            or accounts[22]!=associated or accounts[26]!=PUMP_LAUNCH_PROGRAM):return None
        return {"relation":"pump_launch_migrate_v2","source":accounts[7],"target":accounts[2],"pool":accounts[10]}
    return None

def protocol_events(tx,signature):
    if not isinstance(tx,dict) or not isinstance(tx.get("meta"),dict) or tx["meta"].get("err") is not None:return []
    msg=tx.get("transaction",{}).get("message",{})
    instructions=[(str(i),v) for i,v in enumerate(msg.get("instructions",[]))]
    for group in tx["meta"].get("innerInstructions") or []:
        instructions += [(str(group["index"])+"."+str(i),v) for i,v in enumerate(group.get("instructions",[]))]
    events=[]
    for index,ins in instructions:
        launch=launch_v2_instruction(ins)
        if launch:
            events.append(dict(launch,signature=signature,instruction=index,slot=tx.get("slot"),
                block_time=tx.get("blockTime"),scope="successful reviewed Pump launch instruction; not reputation clearance"))
            continue
        if ins.get("programId")!=PUMP or not isinstance(ins.get("accounts"),list):continue
        try:raw=b58decode(ins.get("data"))
        except (ValueError,TypeError):continue
        op=OPS.get(raw[:8])
        if op is None or len(raw)<16:continue
        kind,user_index=op;accounts=ins["accounts"]
        if len(accounts)<=user_index or not all(isinstance(a,str) for a in accounts):continue
        amount=struct.unpack_from("<Q",raw,8)[0]
        if amount<=0:continue
        events.append({"signature":signature,"instruction":index,"slot":tx.get("slot"),
            "block_time":tx.get("blockTime"),"relation":"pump_amm_"+kind,
            "source":accounts[user_index],"target":accounts[0],"raw_instruction_amount":str(amount),
            "scope":"successful protocol instruction, not profit/rug attribution"})
    return events
def liquidity_observation(pool_address,state,accounts):
    """Authenticate vault relationships and record LP redeemability; no lock guesses."""
    lp,base,quote=accounts
    def info(a,kind):
        if not isinstance(a,dict) or a.get("owner") not in (SPL,TOKEN22):return None
        d=a.get("data",{});p=d.get("parsed",{}) if isinstance(d,dict) else {}
        return p.get("info") if p.get("type")==kind else None
    li=info(lp,"mint");bi=info(base,"account");qi=info(quote,"account")
    if not all(isinstance(i,dict) for i in (li,bi,qi)):
        return {"status":"UNKNOWN","reason":"missing_lp_or_vault_accounts"}
    for i,m in ((bi,state["base_mint"]),(qi,state["quote_mint"])):
        if i.get("owner")!=pool_address or i.get("mint")!=m or i.get("state")!="initialized":
            return {"status":"UNKNOWN","reason":"vault_relationship_or_state_mismatch"}
        if i.get("delegate") or i.get("closeAuthority"):
            return {"status":"UNKNOWN","reason":"vault_delegate_or_close_authority"}
        if int(i.get("tokenAmount",{}).get("amount",0))<=0:
            return {"status":"REJECT","reason":"empty_pool_reserve"}
    supply=int(li.get("supply",-1))
    if li.get("mintAuthority")!=pool_address or li.get("freezeAuthority") is not None:
        return {"status":"UNKNOWN","reason":"unexpected_lp_authorities"}
    return {"status":"OBSERVED","outstanding_lp_supply":supply,
        "zero_outstanding_lp":supply==0,"reason":"authenticated_pool_vault_and_lp_snapshot",
        "scope":"not complete withdrawal-control or historical liquidity-removal clearance"}
