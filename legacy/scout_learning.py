#!/usr/bin/env python3
import json, logging, sqlite3, time
from pathlib import Path
import requests
import early_scout as production_scout

BASE = Path("/opt/vivameda-crypto-early-scout")
DB_PATH = BASE / "data" / "early_scout.sqlite"
LOG_PATH = BASE / "logs" / "learning_tracker.log"
DEX_BATCH = "https://api.dexscreener.com/tokens/v1/solana/"
HORIZONS = (5, 15, 30, 60, 180, 360, 720, 1440)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Vivameda-Scout-Learning/1.0"})
logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s")

def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS learning_cases(
      mint TEXT, alert_ts INTEGER, symbol TEXT, level INTEGER,
      alert_price REAL, alert_mc REAL, alert_liq REAL,
      peak_price REAL, peak_mc REAL, trough_price REAL,
      last_price REAL, last_mc REAL, last_liq REAL, last_seen INTEGER,
      label TEXT, PRIMARY KEY(mint, alert_ts))""")
    con.execute("""CREATE TABLE IF NOT EXISTS outcome_snapshots(
      mint TEXT, alert_ts INTEGER, horizon_min INTEGER, observed_ts INTEGER,
      price REAL, mc REAL, liq REAL, multiple REAL, drawdown REAL,
      PRIMARY KEY(mint, alert_ts, horizon_min))""")
    con.execute("""CREATE TABLE IF NOT EXISTS alert_features(
      mint TEXT, alert_ts INTEGER, feature_json TEXT,
      PRIMARY KEY(mint, alert_ts))""")
    con.execute("""CREATE TABLE IF NOT EXISTS candidate_evaluations(
      mint TEXT, decision_ts INTEGER, score INTEGER, metrics_json TEXT,
      failed_json TEXT, alert_level INTEGER,
      PRIMARY KEY(mint, decision_ts))""")
    con.execute("DELETE FROM outcome_snapshots WHERE observed_ts-alert_ts > horizon_min*60+180")
    con.execute("""UPDATE learning_cases SET peak_mc=MAX(peak_mc,
      COALESCE((SELECT ath_mc FROM launches WHERE launches.mint=learning_cases.mint),0))""")
    con.commit()
    return con
def f(v):
    try:
        return float(v)
    except Exception:
        return 0.0

def seed_cases(con):
    rows = con.execute("SELECT mint,symbol,alert_level,last_alert_ts FROM launches WHERE alert_level>0 AND last_alert_ts>0").fetchall()
    for mint, symbol, level, alert_ts in rows:
        snap = con.execute("""SELECT price,mc,liq FROM snapshots
          WHERE mint=? AND ts<=? ORDER BY ts DESC LIMIT 1""",(mint,alert_ts)).fetchone()
        if not snap or not snap[0] or not snap[1]:
            continue
        price,mc,liq = map(f,snap)
        ath = con.execute("SELECT ath_mc FROM launches WHERE mint=?",(mint,)).fetchone()
        known_peak_mc = max(mc, f(ath[0]) if ath else 0)
        con.execute("""INSERT OR IGNORE INTO learning_cases
          (mint,alert_ts,symbol,level,alert_price,alert_mc,alert_liq,
           peak_price,peak_mc,trough_price,last_price,last_mc,last_liq,last_seen,label)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (mint,alert_ts,symbol,level,price,mc,liq,price,known_peak_mc,price,
           price,mc,liq,alert_ts,"OPEN"))
        con.execute("""UPDATE learning_cases SET alert_price=?,alert_mc=?,alert_liq=?,
          peak_mc=MAX(peak_mc,?) WHERE mint=? AND alert_ts=?""",
          (price,mc,liq,known_peak_mc,mint,alert_ts))
    con.commit()

def freeze_features(con):
    cases=con.execute("""SELECT mint,alert_ts FROM learning_cases
      WHERE NOT EXISTS (SELECT 1 FROM alert_features f
      WHERE f.mint=learning_cases.mint AND f.alert_ts=learning_cases.alert_ts)""").fetchall()
    for mint,alert_ts in cases:
        rows=con.execute("""SELECT ts,price,mc,liq,vol_m5,vol_h1,
          buys_m5,sells_m5,buys_h1,sells_h1,pc_m5,pc_h1
          FROM snapshots WHERE mint=? AND ts<=? AND ts>=? ORDER BY ts""",
          (mint,alert_ts,alert_ts-35*60)).fetchall()
        if len(rows)<2:
            continue
        cur=rows[-1]
        prices=[f(r[1]) for r in rows if f(r[1])>0]
        liqs=[f(r[3]) for r in rows if f(r[3])>0]
        if not prices:
            continue
        b1,s1=int(cur[8] or 0),int(cur[9] or 0)
        vol1,vol5=f(cur[5]),f(cur[4])
        mc=f(cur[2])
        feature={"history_minutes":round((rows[-1][0]-rows[0][0])/60,1),
          "points":len(rows),"price":f(cur[1]),"mc":mc,"liq":f(cur[3]),
          "vol_m5":vol5,"vol_h1":vol1,"buys_h1":b1,"sells_h1":s1,
          "buy_ratio":b1/max(1,b1+s1),"vol_mc_ratio":vol1/max(1,mc),
          "pc_m5":f(cur[10]),"pc_h1":f(cur[11]),
          "band":(max(prices)-min(prices))/min(prices),
          "net":prices[-1]/prices[0]-1,
          "liq_change":(liqs[-1]/liqs[0]-1) if len(liqs)>1 else 0,
          "volume_accel_ratio":vol5/max(1,vol1/12)}
        con.execute("INSERT OR IGNORE INTO alert_features VALUES(?,?,?)",
          (mint,alert_ts,json.dumps(feature,sort_keys=True)))
    con.commit()

def fetch_pair(mint, pair_addr):
    r = SESSION.get(DEX_BATCH + mint, timeout=12)
    r.raise_for_status()
    data = r.json()
    rows = data if isinstance(data,list) else []
    exact = [p for p in rows if p.get("pairAddress") == pair_addr]
    if exact:
        return exact[0]
    rows = [p for p in rows if (p.get("liquidity") or {}).get("usd") is not None]
    rows.sort(key=lambda p:f((p.get("liquidity") or {}).get("usd")), reverse=True)
    return rows[0] if rows else None

def classify(peak_multiple,last_multiple,liq):
    if peak_multiple >= 10: return "10X_PLUS"
    if peak_multiple >= 5: return "5X"
    if peak_multiple >= 3: return "3X"
    if peak_multiple >= 2: return "2X"
    if peak_multiple >= 1.35: return "WEAK"
    if last_multiple <= 0.55 or liq <= 5000: return "FAILED"
    return "FLAT"

def capture_candidates(con):
    now=int(time.time())
    bucket=now//300*300
    mints=con.execute("""SELECT DISTINCT s.mint FROM snapshots s JOIN launches l ON l.mint=s.mint
      WHERE s.ts>=? AND l.created_ts BETWEEN ? AND ?""",
      (now-120,(now-6*3600)*1000,(now-30*60)*1000)).fetchall()
    for (mint,) in mints:
        if con.execute("SELECT 1 FROM candidate_evaluations WHERE mint=? AND decision_ts=?",(mint,bucket)).fetchone():
            continue
        rows=con.execute("""SELECT ts,price,mc,liq,vol_m5,vol_h1,buys_m5,sells_m5,
          buys_h1,sells_h1,pc_m5,pc_h1 FROM snapshots
          WHERE mint=? AND ts>=? ORDER BY ts""",(mint,now-35*60)).fetchall()
        score,metrics,failed=production_scout.score_candidate(rows)
        if rows:
            cur=rows[-1]
            raw={"price":f(cur[1]),"mc":f(cur[2]),"liq":f(cur[3]),
                 "vol_m5":f(cur[4]),"vol_h1":f(cur[5]),
                 "buys_h1":int(cur[8] or 0),"sells_h1":int(cur[9] or 0),
                 "pc_m5":f(cur[10]),"pc_h1":f(cur[11]),"points":len(rows)}
            raw.update(metrics)
        else:
            raw={}
        alert=con.execute("SELECT alert_level FROM launches WHERE mint=?",(mint,)).fetchone()
        con.execute("INSERT OR IGNORE INTO candidate_evaluations VALUES(?,?,?,?,?,?)",
          (mint,bucket,int(score),json.dumps(raw,sort_keys=True),
           json.dumps(failed),int(alert[0] if alert else 0)))
    con.commit()

def update_case(con,case):
    mint,alert_ts,alert_price,alert_mc,peak_price,peak_mc,trough_price=case
    launch=con.execute("SELECT pinned_pair FROM launches WHERE mint=?",(mint,)).fetchone()
    pair=fetch_pair(mint,launch[0] if launch else None)
    if not pair:
        return
    now=int(time.time())
    price=f(pair.get("priceUsd"))
    mc=f(pair.get("marketCap"))
    liq=f((pair.get("liquidity") or {}).get("usd"))
    if not price or not mc:
        return
    peak_price=max(f(peak_price),price)
    peak_mc=max(f(peak_mc),mc)
    trough_price=min(f(trough_price) or price,price)
    peak_multiple=max(peak_price/f(alert_price), peak_mc/f(alert_mc))
    last_multiple=price/f(alert_price)
    label=classify(peak_multiple,last_multiple,liq)
    con.execute("""UPDATE learning_cases SET peak_price=?,peak_mc=?,trough_price=?,
      last_price=?,last_mc=?,last_liq=?,last_seen=?,label=?
      WHERE mint=? AND alert_ts=?""",
      (peak_price,peak_mc,trough_price,price,mc,liq,now,label,mint,alert_ts))
    age_min=(now-alert_ts)/60
    for h in HORIZONS:
        if age_min < h or age_min > h + 3:
            continue
        if con.execute("SELECT 1 FROM outcome_snapshots WHERE mint=? AND alert_ts=? AND horizon_min=?",(mint,alert_ts,h)).fetchone():
            continue
        multiple=price/f(alert_price)
        drawdown=price/peak_price-1 if peak_price else 0
        con.execute("""INSERT INTO outcome_snapshots
          (mint,alert_ts,horizon_min,observed_ts,price,mc,liq,multiple,drawdown)
          VALUES(?,?,?,?,?,?,?,?,?)""",
          (mint,alert_ts,h,now,price,mc,liq,multiple,drawdown))
    con.commit()

def main():
    con=db()
    logging.info("learning tracker started")
    while True:
        try:
            seed_cases(con)
            freeze_features(con)
            capture_candidates(con)
            cases=con.execute("""SELECT mint,alert_ts,alert_price,alert_mc,
              peak_price,peak_mc,trough_price FROM learning_cases
              WHERE alert_ts>=?""",(int(time.time())-7*86400,)).fetchall()
            for case in cases:
                try:
                    update_case(con,case)
                except Exception as e:
                    logging.warning("case %s failed: %s",case[0],e)
                time.sleep(0.2)
        except Exception as e:
            logging.exception("tracker loop failed: %s",e)
        time.sleep(60)

if __name__ == "__main__":
    main()
