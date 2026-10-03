"""Two-call authenticated Pump pool snapshot. No trades, no paid APIs."""
import hashlib,json,time
from pathlib import Path
from protocol_screening import pool_state,token_controls,liquidity_observation
from wallet_intelligence import Store,Client,render
from free_risk_evidence import valid

def collect(result,root):
    pair=result.get("pair");mint=result["mint"]
    out={"status":"UNKNOWN","pair":pair,"reason":"missing_pinned_pair"}
    store=Store(Path(root)/"wallets.sqlite");client=Client(store,2)
    try:
        if not valid(pair):return result
        pool_response=client.rpc("getAccountInfo",[pair,{"encoding":"base64","commitment":"finalized"}])
        state=pool_state(pool_response.get("value"))
        if state["base_mint"]!=mint:raise ValueError("pool_mint_mismatch")
        response=client.rpc("getMultipleAccounts",[[mint,state["quote_mint"],state["lp_mint"],state["base_vault"],state["quote_vault"]],
                           {"encoding":"jsonParsed","commitment":"finalized","minContextSlot":pool_response["context"]["slot"]}])
        values=response.get("value")
        if not isinstance(values,list) or len(values)!=5:raise ValueError("missing_accounts")
        observation=int(time.time())
        raw={"pool":pool_response,"accounts":response}
        key=store.evidence("authenticated-pump-pool:"+pair,raw)
        out={"status":"OBSERVED","pair":pair,"mint":mint,"observed_at":observation,
             "evidence_ref":key,"slot":response["context"]["slot"],"pool_state":state,
             "base_token_controls":token_controls(values[0]),
             "quote_token_controls":token_controls(values[1]),
             "liquidity_observation":liquidity_observation(pair,state,values[2:]),
             "complete_screening":False}
    except Exception as exc:
        out={"status":"UNKNOWN","pair":pair,"reason":type(exc).__name__+":"+str(exc)[:100]}
    finally:
        client.session.close();store.db.close()
        result["onchain_pool_screening"]=out
        p=Path(root)/(mint+".json");tmp=p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(result,indent=2));tmp.replace(p)
        render(result,Path(root)/(mint+".html"))
    return result
