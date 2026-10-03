"""Telegram wallet evidence formatting; no sending and no safety approval."""
import math

def wallet_text(report,mint,now):
    missing="Wallet review: INCOMPLETE — no current matching report. Not safety-cleared."
    if not isinstance(report,dict) or report.get("mint")!=mint:
        return missing
    ts=report.get("generated_at")
    if type(ts) not in (int,float) or not math.isfinite(ts) or not 0<=now-ts<=300:
        return "Wallet review: STALE / INCOMPLETE. Not safety-cleared."
    histories=report.get("wallet_histories") or []
    if not isinstance(histories,list): return missing
    rows=[r for r in histories if isinstance(r,dict)]
    def count(value):
        return value if type(value) is int and value>=0 else 0
    indexed=sum(count(r.get("successful_signatures_indexed")) for r in rows)
    decoded=sum(count(r.get("transactions_available")) for r in rows)
    text=["Wallet review: PARTIAL — not safety-cleared.",
          f"Wallets inspected: {len(rows)} | transactions retrieved: {decoded}/{indexed} indexed"]
    concentration=report.get("concentration") or {}
    value=concentration.get("unclassified_top10_reported_pct") if isinstance(concentration,dict) else None
    if type(value) in (int,float) and math.isfinite(value) and 0<=value<=100:
        text.append(f"Top 10 unclassified holders: {value:.1f}% of supply in provider sample; labelled infrastructure excluded.")
    dev=report.get("developer_history") or {}
    mints=dev.get("associated_mint_initializations") if isinstance(dev,dict) else None
    if isinstance(mints,list):
        text.append(f"Associated mint initializations observed: {len(mints)}. Developer history incomplete.")
    else: text.append("Developer history: incomplete.")
    text.append("Wallet links do not prove common control. Liquidity-removal history unverified.")
    if report.get("issues"): text.append("Provider errors reduced coverage.")
    return "\n".join(text)

def strict_eligible(report):
    # Current research schema has no reviewed certification path.
    # A provider report or arbitrary admission='PASS' cannot authorize release.
    return False
