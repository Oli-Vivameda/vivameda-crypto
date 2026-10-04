#!/usr/bin/env python3
import json, subprocess, time, urllib.parse, urllib.request
from pathlib import Path

BASE = Path("/opt/vivameda-crypto-watchlist")
STATE = BASE / "state.json"
LOG = BASE / "watch.log"
TELEGRAM_CREDS = Path("/opt/vivameda-crypto-watchlist/credentials.json")

PAIRS = {
    "JEANPHIL": "4R8CiMnJWDNoes3fQi1ccPFJygPXazaHaWpHrN3rZeNj",
    "20xx": "GvdfErkq5mvvphEriajrjArakyqqUXXiyBWdzMoxS3Tk",
    "CHIIKAWA": "EY75tsmUY7GnB3noq7pdcjg8GxCzTHou6h6XjwcCFVh3",
}

BASE.mkdir(parents=True, exist_ok=True)

def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg + "\n")

def fetch(pair):
    url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair}"
    p = subprocess.run(
        ["/usr/bin/curl","-sS","-A","Mozilla/5.0",url],
        capture_output=True, text=True, timeout=20
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or f"curl exit {p.returncode}")
    data = json.loads(p.stdout)
    rows = data.get("pairs") or []
    if not rows:
        raise RuntimeError("no pair data")
    row = rows[0]
    if row.get("pairAddress") != pair:
        raise RuntimeError("pair mismatch")
    return float(row["priceUsd"]), row

def telegram_send(message):
    creds = json.loads(TELEGRAM_CREDS.read_text())
    token = creds["bot_token"]
    chat_id = str(creds["chat_id"])
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("ok"):
        raise RuntimeError("Telegram send failed")
def notify(name, price, ref, pair):
    pct = (price / ref - 1.0) * 100
    title = f"🚨 {name} +10% move"
    body = (
        f"{name} is USD " + format(price, ".10g") +
        f" — +{pct:.1f}% from armed reference USD " + format(ref, ".10g")
    )
    telegram_send(
        "🚨💎 MEME MOVE ALERT — SOLANA\n\n"
        f"{name} has moved +{pct:.1f}% from its armed reference.\n"
        f"Current: USD {price:.10g}\n"
        f"Reference: USD {ref:.10g}\n"
        f"Pool: https://dexscreener.com/solana/{pair}"
    )

try:
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
except Exception:
    state = {}

changed = False
for name, pair in PAIRS.items():
    try:
        price, row = fetch(pair)
        item = state.get(name) or {}
        ref = float(item.get("reference_price") or price)

        if name not in state:
            state[name] = {
                "pair": pair,
                "reference_price": price,
                "last_price": price,
                "armed_at": int(time.time())
            }
            changed = True
            log(f"ARMED {name} pair={pair} ref={price}")
            continue

        if price >= ref * 1.10:
            notify(name, price, ref, pair)
            log(
                f"TRIGGER {name} price={price} ref={ref} " +
                f"move={(price/ref-1)*100:.2f}%"
            )
            item["reference_price"] = price
            item["armed_at"] = int(time.time())
            changed = True

        item["last_price"] = price
        item["last_checked"] = int(time.time())
        state[name] = item
        changed = True
    except Exception as e:
        log(f"ERROR {name} {e}")

if changed:
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True))
