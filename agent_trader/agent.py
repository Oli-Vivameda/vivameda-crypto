"""Paper-only cross-market trading agent layer.

The agent drafts proposals from supplied evidence. It cannot approve, execute,
choose a verifier, or call a broker. Feedback is stored as versioned playbook
entries for supervised improvement.
"""
import argparse, hashlib, json, sqlite3, uuid
from datetime import datetime, timezone
from decimal import Decimal

DOMAINS = {"equity", "crypto_major", "solana_meme", "prediction_market"}

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()

def now(): return datetime.now(timezone.utc).isoformat()

def init(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS proposals(
          id TEXT PRIMARY KEY, created_at TEXT NOT NULL, domain TEXT NOT NULL,
          asset_id TEXT NOT NULL, payload TEXT NOT NULL, evidence_hash TEXT NOT NULL,
          state TEXT NOT NULL CHECK(state IN ('DRAFT','APPROVED','REJECTED','EXPIRED')),
          feedback_id TEXT);
        CREATE TABLE IF NOT EXISTS feedback(
          id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL, created_at TEXT NOT NULL,
          owner_label TEXT NOT NULL CHECK(owner_label IN ('ACCEPT','REJECT','EDIT')),
          note TEXT NOT NULL, corrected_payload TEXT, playbook_version INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS playbook(
          version INTEGER PRIMARY KEY, created_at TEXT NOT NULL, source_feedback TEXT NOT NULL,
          rule TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_events(
          seq INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
          kind TEXT NOT NULL, body TEXT NOT NULL, body_sha256 TEXT NOT NULL)
        """)

def event(db, kind, body):
    raw=canonical(body); db.execute("INSERT INTO agent_events(created_at,kind,body,body_sha256) VALUES(?,?,?,?)",(now(),kind,raw,digest(body)))

def validate_evidence(evidence):
    if not isinstance(evidence, dict) or not evidence.get("evidence_id"):
        raise ValueError("Evidence must have a stable evidence_id")
    if evidence.get("status") == "UNKNOWN" or evidence.get("verified") is not True:
        raise ValueError("Unverified or UNKNOWN evidence cannot produce a trade proposal")
    return evidence

def draft(path, domain, asset_id, side, quantity, limit_usd, evidence, thesis, exit_plan):
    if domain not in DOMAINS: raise ValueError("Unsupported market domain")
    if not asset_id or side not in ("BUY", "SELL"): raise ValueError("Invalid asset or side")
    q=Decimal(str(quantity)); limit=Decimal(str(limit_usd))
    if q <= 0 or limit <= 0: raise ValueError("Quantity and limit must be positive")
    if not thesis or not exit_plan: raise ValueError("Thesis and exit plan are required")
    ev=validate_evidence(evidence)
    payload={"domain":domain,"asset_id":asset_id,"side":side,"quantity":str(q),"limit_usd":str(limit),"evidence_id":ev["evidence_id"],"thesis":thesis,"exit_plan":exit_plan,"mode":"PAPER_ONLY"}
    pid=uuid.uuid4().hex; eh=digest(ev)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?)",(pid,now(),domain,asset_id,canonical(payload),eh,"DRAFT",None)); event(db,"proposal_drafted",{"id":pid,"payload":payload,"evidence_hash":eh})
    return {"proposal_id":pid,"state":"DRAFT","payload":payload,"evidence_hash":eh,"live_execution":False}

def feedback(path, proposal_id, label, note, corrected_payload=None):
    if label not in ("ACCEPT","REJECT","EDIT") or not note: raise ValueError("Feedback label and note required")
    with sqlite3.connect(path) as db:
        row=db.execute("SELECT state FROM proposals WHERE id=?",(proposal_id,)).fetchone()
        if not row: raise ValueError("Unknown proposal")
        v=(db.execute("SELECT COALESCE(MAX(version),0) FROM playbook").fetchone()[0])+1
        fid=uuid.uuid4().hex; rule=json.dumps({"label":label,"note":note,"correction":corrected_payload},sort_keys=True)
        db.execute("INSERT INTO feedback VALUES(?,?,?,?,?,?,?)",(fid,proposal_id,now(),label,note,canonical(corrected_payload) if corrected_payload else None,v))
        db.execute("INSERT INTO playbook VALUES(?,?,?,?)",(v,now(),fid,rule))
        state="APPROVED" if label=="ACCEPT" else "REJECTED" if label=="REJECT" else "DRAFT"
        db.execute("UPDATE proposals SET state=?,feedback_id=? WHERE id=?",(state,fid,proposal_id)); event(db,"owner_feedback",{"feedback_id":fid,"proposal_id":proposal_id,"label":label,"playbook_version":v})
    return {"feedback_id":fid,"proposal_id":proposal_id,"state":state,"playbook_version":v,"live_execution":False}

def list_open(path):
    with sqlite3.connect(path) as db:
        return [{"proposal_id":r[0],"created_at":r[1],"domain":r[2],"asset_id":r[3],"payload":json.loads(r[4]),"state":r[5]} for r in db.execute("SELECT id,created_at,domain,asset_id,payload,state FROM proposals WHERE state='DRAFT' ORDER BY created_at")]

def main():
    p=argparse.ArgumentParser();p.add_argument("db");s=p.add_subparsers(dest="cmd",required=True);s.add_parser("init");s.add_parser("open")
    a=s.add_parser("feedback");a.add_argument("proposal");a.add_argument("label",choices=["ACCEPT","REJECT","EDIT"]);a.add_argument("note")
    x=p.parse_args();init(x.db)
    if x.cmd=="open": print(json.dumps(list_open(x.db),indent=2))
    elif x.cmd=="feedback": print(json.dumps(feedback(x.db,x.proposal,x.label,x.note),indent=2))
    else: print(json.dumps({"state":"INITIALIZED","live_execution":False}))
if __name__=='__main__': main()
