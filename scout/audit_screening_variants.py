#!/usr/bin/env python3
"""Read-only screening counterfactual audit. Never sends alerts or changes policy.
Replays each latest saved packet at its original decision time; not a backtest.
"""
import argparse,collections,hashlib,json
from pathlib import Path
from screening_policy import CHECKS,screen_packet

VARIANTS={
 "current":set(),
 "age_warning":{"wallet_age"},
 "age_and_concentration_warning":{"wallet_age","top_holder_ownership"},
}
SOFT_REASONS={"wallet_age":"young_wallet_exposure",
              "top_holder_ownership":"concentration_policy_exceeded"}

def comparison(checks,soft):
    unknown=[];reject=[];warnings=[]
    for name in CHECKS:
        c=checks.get(name,{})
        status=c.get("status","UNKNOWN")
        if status=="REJECT" and name in soft and c.get("reason")==SOFT_REASONS[name]:
            warnings.append(name)
        elif status=="REJECT":reject.append(name)
        elif status!="PASS":unknown.append(name)
    verdict="REJECT" if reject else ("HOLD" if unknown else "SHADOW_ELIGIBLE")
    return {"verdict":verdict,"remaining_rejections":reject,
            "unknown_checks":unknown,"warnings":warnings}

def audit(root):
    counts={k:collections.Counter() for k in VARIANTS}
    reasons=collections.Counter();records=[];skipped=collections.Counter()
    files=sorted(root.iterdir())
    for path in files:
        if path.suffix!=".json" or path.name in ("worker_status.json","index.json"):continue
        if path.is_symlink():skipped["symlink"]+=1;continue
        if path.stat().st_size>16*1024*1024:skipped["oversized"]+=1;continue
        try:
            raw=path.read_bytes();r=json.loads(raw)
            if r.get("schema")!="wallet-intelligence-v3":
                skipped["other_schema"]+=1;continue
            p=r["screening_packet"];at=r["generated_at"]
            if type(at) is not int:raise ValueError("invalid_time")
            checks=screen_packet(p,r["mint"],p["pair"],p["creator"],at)
            variants={name:comparison(checks,soft) for name,soft in VARIANTS.items()}
            for name,v in variants.items():counts[name][v["verdict"]]+=1
            for name,c in checks.items():
                reasons[(name,c["status"],c["reason"])]+=1
            records.append({"mint":r["mint"],"decision_time":at,
                "report_sha256":hashlib.sha256(raw).hexdigest(),
                "checks":{k:{"status":v["status"],"reason":v["reason"],
                   "details":v.get("details",{})} for k,v in checks.items()},
                "variants":variants})
        except (ValueError,KeyError,TypeError):
            skipped["invalid_report"]+=1
    return {"read_only":True,"telegram_changes":False,
      "scope":"Latest saved report per mint, replayed at saved decision time. No outcome or profitability comparison.",
      "policy_sha256":hashlib.sha256(Path(__file__).with_name("screening_policy.py").read_bytes()).hexdigest(),
      "reports":len(records),"skipped":dict(skipped),
      "variant_counts":{k:dict(v) for k,v in counts.items()},
      "reason_counts":[{"check":k[0],"status":k[1],"reason":k[2],"count":v}
         for k,v in sorted(reasons.items())],
      "records":records,
      "limitations":["Shadow eligibility never authorizes Telegram or trading.",
        "Short observed activity is not proof of wallet youth.",
        "Concentration warning variant measures sensitivity only; no new safe threshold is inferred.",
        "UNKNOWN remains unresolved in every variant.",
        "Latest reports are not a historical sequence or a forward performance evaluation."]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data",type=Path,default=Path("/var/lib/vivameda-wallet-intelligence/data"))
    a=p.parse_args()
    print(json.dumps(audit(a.data),indent=2))
if __name__=="__main__":main()
