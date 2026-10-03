"""Free read-only risk evidence; never certifies safety or sends alerts."""
import argparse, hashlib, json, math, re, time
from pathlib import Path
import requests

ADDRESS = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
RPC = "https://api.mainnet-beta.solana.com"

def valid(address):
    return isinstance(address, str) and ADDRESS.fullmatch(address) is not None


def candidate_retry_delay(attempts):
    """Bounded per-candidate backoff; never a daemon-wide sleep."""
    return min(600, 120 * 2 ** min(max(int(attempts), 0), 3))

def transient_issue(issue):
    return isinstance(issue, str) and issue.startswith((
        "provider_http_429", "provider_http_5", "provider_network_error", "RuntimeError:rpc_method_cooldown_",
        "RuntimeError:rpc_error_code_-32005_", "RuntimeError:rpc_error_code_-32011_",
        "RuntimeError:rpc_error_code_-32019_", "Timeout:", "ReadTimeout:", "ConnectTimeout:"))

def evidence_error(exc):
    """Return a bounded diagnostic without response bodies or URLs."""
    if isinstance(exc, requests.RequestException):
        code = getattr(getattr(exc, "response", None), "status_code", None)
        return "provider_http_" + str(code) if code else "provider_network_error"
    if isinstance(exc, RuntimeError) and re.fullmatch(r"(rpc_error_code_-?\d+_method_|rpc_method_cooldown_)[A-Za-z]+", str(exc)):
        return "RuntimeError:" + str(exc)
    return type(exc).__name__ + ":invalid_evidence"

def holder_summary(report):
    grouped = {}
    unknown = 0
    for row in report.get("topHolders") or []:
        owner, pct = row.get("owner"), row.get("pct")
        if not valid(owner) or type(pct) not in (float, int) or not math.isfinite(pct) or not 0 <= pct <= 100:
            unknown += 1
            continue
        grouped[owner] = grouped.get(owner, 0) + pct
    labels = report.get("knownAccounts") or {}
    if not isinstance(labels, dict):
        labels = {}
    return {"coverage": "reported_top_accounts_only", "unusable_rows": unknown,
            "pool_adjusted": False, "owners": [
                {"owner": owner, "reported_pct": pct, "provider_label": labels.get(owner)}
                for owner, pct in sorted(grouped.items(), key=lambda x: -x[1])]}

def activity_summary(rows, now):
    if not isinstance(rows, list):
        return {"status": "UNKNOWN", "reason": "invalid_rpc_result"}
    times = [r["blockTime"] for r in rows if isinstance(r, dict)
             and r.get("err") is None and type(r.get("blockTime")) is int
             and 0 < r["blockTime"] <= now]
    oldest = min(times) if times else None
    return {"status": "OBSERVED" if times else "UNKNOWN",
            "returned_signatures": len(rows), "page_limit_reached": len(rows) >= 1000,
            "earliest_returned_successful_activity": oldest,
            "observed_activity_age_lower_bound_seconds": now-oldest if oldest else None,
            "wallet_creation_time": None, "full_history_verified": False}

def collect(mint, outdir):
    if not valid(mint):
        raise ValueError("invalid mint")
    now = int(time.time())
    folder = Path(outdir) / (str(time.time_ns()) + "-" + mint)
    folder.mkdir(parents=True, exist_ok=False)
    result = {"schema": "free-risk-evidence-v1", "mint": mint, "collected_at": now,
              "mode": "SHADOW", "verdict": "HOLD", "bubblemap_review": "NOT_PERFORMED",
              "developer_history": "UNVERIFIED", "artifacts": [], "errors": []}
    session = requests.Session()
    session.headers["User-Agent"] = "Vivameda-Risk-Research/1.0"
    def save(name, data):
        path = folder / name
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        path.write_bytes(raw)
        result["artifacts"].append({"file": name, "sha256": hashlib.sha256(raw).hexdigest()})
    try:
        response = session.get("https://api.rugcheck.xyz/v1/tokens/" + mint + "/report", timeout=15)
        response.raise_for_status()
        report = response.json()
        if not isinstance(report, dict) or report.get("mint") != mint:
            raise ValueError("report identity mismatch")
        save("rugcheck.json", report)
        result["provider_detected_at"] = report.get("detectedAt")
        result["provider_snapshot_time_verified"] = False
        result["provider_risks"] = report.get("risks")
        result["provider_rugged_flag"] = report.get("rugged")
        result["holders"] = holder_summary(report)
        result["creator_tokens_reported"] = report.get("creatorTokens")
        result["insider_networks_reported"] = report.get("insiderNetworks")
        # Missing/empty provider fields are never evidence of a clean history.
        addresses = []
        creator = report.get("creator")
        if valid(creator):
            addresses.append(creator)
        for holder in result["holders"]["owners"]:
            if holder["owner"] not in addresses:
                addresses.append(holder["owner"])
            if len(addresses) >= 4:
                break
        result["wallet_activity"] = {}
        for index, address in enumerate(addresses):
            if index:
                time.sleep(1)
            try:
                response = session.post(RPC, json={"jsonrpc": "2.0", "id": 1,
                    "method": "getSignaturesForAddress",
                    "params": [address, {"limit": 1000, "commitment": "finalized"}]}, timeout=15)
                response.raise_for_status()
                payload = response.json()
                if payload.get("error"):
                    code = payload["error"].get("code") if isinstance(payload["error"], dict) else None
                    if type(code) is int:
                        raise RuntimeError("rpc_error_code_"+str(code)+"_method_getSignaturesForAddress")
                    raise ValueError("RPC invalid error")
                if not isinstance(payload.get("result"), list):
                    raise ValueError("RPC missing result")
                save("wallet-" + str(index) + ".json", payload)
                result["wallet_activity"][address] = activity_summary(payload["result"], int(time.time()))
            except (requests.RequestException, ValueError, TypeError, RuntimeError) as exc:
                issue = evidence_error(exc)
                result["errors"].append(issue)
                result["retry_scope"] = "candidate"
                result["retry_after_seconds"] = candidate_retry_delay(0)
                result["wallet_activity"][address] = {"status": "UNKNOWN", "reason": issue}
                for pending in addresses[index+1:]:
                    result["wallet_activity"][pending] = {"status": "UNKNOWN", "reason": "candidate_retry_pending"}
                # Do not hammer a public endpoint after a failed call.
                break
    except (requests.RequestException, ValueError, TypeError) as exc:
        result["errors"].append(evidence_error(exc))
        result["retry_scope"] = "candidate"
        result["retry_after_seconds"] = candidate_retry_delay(0)
    finally:
        session.close()
    result["finished_at"] = int(time.time())
    result["limitations"] = ["No BubbleMaps review", "No verified developer launch history",
        "Holder shares include unclassified pools and program accounts",
        "Wallet activity is a lower bound, not creation age",
        "Provider detection timestamp is not a verified snapshot timestamp"]
    (folder / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result, str(folder)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mint", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result, folder = collect(args.mint, args.output)
    print(json.dumps({"folder": folder, "mode": result["mode"], "verdict": result["verdict"],
                      "errors": result["errors"], "wallet_activity": result.get("wallet_activity"),
                      "provider_risks": result.get("provider_risks")}, indent=2))
