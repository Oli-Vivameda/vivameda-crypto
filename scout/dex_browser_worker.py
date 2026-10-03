#!/usr/bin/env python3
"""Dex browser evidence collector. No trading, Telegram, or automatic PASS.
Run in a dedicated unprivileged browser worker, never in the scanner loop.
"""
import argparse
import hashlib
import json
import re
import time
from pathlib import Path

ADDRESS = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
BLOCKS = ("verify you are human", "checking your browser", "access denied",
          "unusual traffic", "just a moment", "performing security verification")
REQUIRED = ("bubblemap_clusters", "developer_history", "top_holder_ownership",
            "wallet_age", "token_controls", "liquidity_control", "trading_mechanics")

def validate_address(value):
    if not isinstance(value, str) or not ADDRESS.fullmatch(value):
        raise ValueError("invalid Solana address")
    return value

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def collect(mint, pair, output):
    validate_address(mint)
    validate_address(pair)
    from playwright.sync_api import sync_playwright
    started = int(time.time())
    folder = Path(output) / (str(started) + "-" + pair)
    folder.mkdir(parents=True, exist_ok=False)
    result = {"schema": "dex-browser-evidence-v1", "mint": mint, "pair": pair,
              "chain": "solana", "started_at": started, "verdict": "HOLD",
              "reason": "review_not_completed", "artifacts": [], "checks": {
                  name: {"status": "UNKNOWN", "evidence_refs": []} for name in REQUIRED}}
    try:
        with sync_playwright() as p:
            # Use the browser sandbox; no stealth, credentials, or proxy rotation.
            browser = p.chromium.launch(
                executable_path="/opt/vivameda-browser/chrome-headless-shell-linux64/chrome-headless-shell",
                headless=True, chromium_sandbox=True)
            try:
                context = browser.new_context(viewport={"width": 1440, "height": 1000},
                                              accept_downloads=False)
                context.set_default_timeout(15000)
                page = context.new_page()
                response = page.goto("https://dexscreener.com/solana/" + pair,
                                     wait_until="domcontentloaded", timeout=30000)
                text = page.locator("body").inner_text(timeout=15000)
                body_path = folder / "page.txt"
                body_path.write_text(text, encoding="utf-8")
                screenshot = folder / "page.png"
                page.screenshot(path=str(screenshot), full_page=False)
                for artifact in (body_path, screenshot):
                    result["artifacts"].append({"file": artifact.name, "sha256": digest(artifact)})
                result["url"] = page.url
                result["http_status"] = response.status if response else None
                if any(x in text.lower() for x in BLOCKS):
                    result["reason"] = "site_verification_block"
                elif response and response.status >= 400:
                    result["reason"] = "http_error"
                else:
                    # Capture visible embedded content without requesting hidden APIs.
                    frames = []
                    for index, frame in enumerate(page.frames):
                        if frame == page.main_frame:
                            continue
                        try:
                            visible = frame.locator("body").inner_text(timeout=3000)
                        except Exception:
                            visible = ""
                        frames.append({"url": frame.url, "visible_text": visible})
                    frame_path = folder / "frames.json"
                    frame_path.write_text(json.dumps(frames, indent=2), encoding="utf-8")
                    result["artifacts"].append({"file": frame_path.name, "sha256": digest(frame_path)})
                    result["reason"] = "evidence_captured_requires_validated_reviewer"
                context.close()
            finally:
                browser.close()
    except Exception as exc:
        # Do not include arbitrary error messages, headers, cookies or credentials.
        result["reason"] = "browser_failure"
        result["error_type"] = type(exc).__name__
    result["finished_at"] = int(time.time())
    (folder / "manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mint", required=True)
    parser.add_argument("--pair", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = collect(args.mint, args.pair, args.output)
    print(json.dumps({"verdict": result["verdict"], "reason": result["reason"]}))
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
