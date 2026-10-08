#!/usr/bin/env python3
"""Separate spot movement monitor. No scanner DB, trading or paid API calls."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

BASE = Path('/opt/vivameda-market-moves')
STATE = Path('/var/lib/vivameda-market-moves')
CREDS = Path('/opt/vivameda-crypto-watchlist/credentials.json')

def atomic(path, value, mode=0o600):
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, sort_keys=True, allow_nan=False)
            out.flush(); os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def validate(config):
    if config.get('window_seconds') != 900 or config.get('cooldown_seconds') != 1800:
        raise ValueError('unsupported timing')
    products = config.get('products')
    if not isinstance(products, list) or not 1 <= len(products) <= 10:
        raise ValueError('watchlist size')
    seen = set()
    for item in products:
        p = item.get('product')
        if not isinstance(p, str) or not re.fullmatch(r'[A-Z0-9]{2,12}-USD', p) or p in seen:
            raise ValueError('product identity')
        threshold = item.get('threshold_pct')
        if isinstance(threshold, bool) or not isinstance(threshold, (int,float)) or not math.isfinite(threshold) or not .1 <= threshold <= 50:
            raise ValueError('threshold')
        seen.add(p)
    return config

def parse_tick(payload, received):
    price = float(payload['price'])
    if not math.isfinite(price) or price <= 0: raise ValueError('price')
    stamp = datetime.fromisoformat(payload['time'].replace('Z', '+00:00'))
    if stamp.tzinfo is None: raise ValueError('source timestamp timezone')
    source_ts = stamp.timestamp()
    if not -5 <= received-source_ts <= 120: raise ValueError('stale or future tick')
    return {'ts': received, 'source_ts': source_ts, 'price': price}

def fetch(product):
    # Fixed public provider and validated product; no arbitrary outbound URL.
    request = urllib.request.Request('https://api.exchange.coinbase.com/products/'+product+'/ticker',
                                     headers={'User-Agent':'Vivameda-Market-Moves/1.0'})
    with urllib.request.urlopen(request, timeout=8) as response:
        data = response.read(65537)
    if len(data)>65536: raise ValueError('response bound')
    return parse_tick(json.loads(data), int(time.time()))

def movement(samples, now, window=900):
    rows = sorted(samples, key=lambda r:r['ts'])
    if not rows or rows[-1]['ts'] != now: return None
    candidates = [r for r in rows if now-window-90 <= r['ts'] <= now-window]
    if not candidates: return None
    baseline = candidates[-1]
    segment = [r for r in rows if r['ts'] >= baseline['ts']]
    if any(b['ts']-a['ts']>120 for a,b in zip(segment,segment[1:])): return None
    return {'pct':100*(rows[-1]['price']/baseline['price']-1),
            'baseline_ts':baseline['ts'], 'baseline_price':baseline['price'],
            'price':rows[-1]['price'], 'elapsed_seconds':now-baseline['ts']}

def evaluate(item, tick, spec, config):
    now = tick['ts']
    rows = item.setdefault('samples', [])
    # Clock reversal/duplicate sample cannot replace existing historical evidence.
    if rows and now <= rows[-1]['ts']: return None, 'clock_or_duplicate'
    if rows and tick['source_ts'] < rows[-1]['source_ts']: return None, 'source_time_reversed'
    rows.append(tick)
    item['samples'] = [r for r in rows if r['ts'] >= now-2100]
    result = movement(item['samples'], now, config['window_seconds'])
    if result is None: return None, 'warming_or_gap'
    if abs(result['pct'])+1e-9 < spec['threshold_pct']: return None, 'below_threshold'
    if now-item.get('last_sent_ts',0) < config['cooldown_seconds']: return None, 'cooldown'
    if now-item.get('last_attempt_ts',0) < 60: return None, 'retry_wait'
    return dict(result, product=spec['product'], observed_ts=now), 'triggered'

def format_message(event):
    ticker = event['product'].replace('-','')
    direction = 'UP' if event['pct']>=0 else 'DOWN'
    utc = datetime.fromtimestamp(event['observed_ts'], timezone.utc).isoformat()
    return (f"🚨 VIVAMEDA MARKET MOVE — {event['product']} {direction}\n"
            f"Move: {event['pct']:+.2f}% over {event['elapsed_seconds']/60:.1f} minutes\n"
            f"Price: USD {event['price']:.8g}\nReference: USD {event['baseline_price']:.8g}\n"
            f"Observed: {utc}\nSource: Coinbase spot; sampled once per minute\n"
            f"https://www.tradingview.com/chart/?symbol=COINBASE%3A{ticker}\n"
            "Movement notification; no order executed.")

def send(message):
    # Reuse existing bot/destination. Secret values never appear in logs/status.
    c = json.loads(CREDS.read_text())
    body = urllib.parse.urlencode({'chat_id':str(c['chat_id']), 'text':message,
                                  'disable_web_page_preview':'true'}).encode()
    request = urllib.request.Request('https://api.telegram.org/bot'+c['bot_token']+'/sendMessage', data=body, method='POST')
    with urllib.request.urlopen(request, timeout=8) as response: result=json.load(response)
    if result.get('ok') is not True: raise ValueError('delivery failed')
    return time.time()

def alarm_log(path, attempt, observed, result, acknowledged=None):
    # No instrument, prices, bot/chat IDs, payload or exception text retained.
    if result not in ('pending','sent','failed'):raise ValueError('alarm result')
    if not isinstance(attempt,str) or not re.fullmatch('[a-f0-9]{32}',attempt):raise ValueError('attempt')
    if type(observed) not in (int,float) or not math.isfinite(observed):raise ValueError('observation time')
    if acknowledged is not None and (type(acknowledged) not in (int,float) or not math.isfinite(acknowledged) or acknowledged<observed):acknowledged=None
    row={'attempt':attempt,'observation_time':observed,'send_result':result,
         'telegram_api_acknowledgement_time':acknowledged,
         'delay_seconds':round(acknowledged-observed,3) if acknowledged is not None else None}
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
        try:os.write(fd,(json.dumps(row,sort_keys=True,allow_nan=False)+'\n').encode());os.fsync(fd)
        finally:os.close(fd)
        return True
    except OSError:return False


def run(state_dir=STATE, config_path=BASE/'config.json', sender=send, fetcher=fetch):
    config = validate(json.loads(config_path.read_text()))
    state_dir.mkdir(exist_ok=True)
    with (state_dir/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        path=state_dir/'state.json'
        state=json.loads(path.read_text()) if path.exists() else {'products':{}}
        digest=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
        report={'checked_at':int(time.time()),'live_execution':False,'provider':'coinbase_spot',
                'tradingview_data_connection':False,'products':{},'setup_notification':'already_sent'}
        if state.get('setup_digest') != digest:
            try:
                sender('Vivameda BTC/SOL movement monitor configured.\n'+
                       '\n'.join(f"{p['product']}: ±{p['threshold_pct']}% over 15 minutes" for p in config['products'])+
                       '\nChecked once per minute; 30-minute cooldown per coin. First comparison needs 15 minutes of fresh samples.\nNo trading enabled.')
                state['setup_digest']=digest; report['setup_notification']='sent'
            except Exception: report['setup_notification']='delivery_failed'
        atomic(path,state)
        for spec in config['products']:
            product=spec['product']; item=state['products'].setdefault(product,{})
            now=int(time.time())
            if now < item.get('provider_retry_at',0):
                report['products'][product]={'status':'provider_cooldown'};continue
            try:
                tick=fetcher(product)
                event,reason=evaluate(item,tick,spec,config)
                report['products'][product]={'status':reason,'samples':len(item.get('samples',[])),
                                             'last_observed_ts':tick['ts']}
                if event:
                    # Persist attempt before transmission. A crash after successful delivery may
                    # duplicate after retry; not an exactly-once guarantee.
                    item['last_attempt_ts']=tick['ts'];atomic(path,state)
                    attempt=uuid.uuid4().hex
                    logged=alarm_log(state_dir/'alarm_delivery.jsonl',attempt,event['observed_ts'],'pending')
                    report['products'][product]['audit_log']='available' if logged else 'unavailable'
                    try:
                        ack=sender(format_message(event))
                        logged=alarm_log(state_dir/'alarm_delivery.jsonl',attempt,event['observed_ts'],'sent',ack)
                        report['products'][product]['audit_log']='available' if logged else 'unavailable'
                        item['last_sent_ts']=tick['ts'];report['products'][product]['notification']='sent'
                    except Exception:
                        alarm_log(state_dir/'alarm_delivery.jsonl',attempt,event['observed_ts'],'failed')
                        report['products'][product]['notification']='delivery_failed'
                item.pop('provider_retry_at',None)
            except urllib.error.HTTPError as error:
                item['provider_retry_at']=now+(300 if error.code==429 else 60)
                report['products'][product]={'status':'provider_rate_limited' if error.code==429 else 'provider_unavailable'}
            except Exception:
                report['products'][product]={'status':'unavailable'}
            atomic(path,state)
        atomic(state_dir/'status.json',report,0o644)
        return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--probe',action='store_true');args=parser.parse_args()
    if args.probe:
        result={}
        for product in ('BTC-USD','SOL-USD'):
            try:
                tick=fetch(product);result[product]={'fresh':True,'source_age_seconds':round(tick['ts']-tick['source_ts'],3)}
            except Exception:result[product]={'fresh':False}
        print(json.dumps({'public_provider_probe':result,'telegram_sent':False,'live_execution':False}))
    else:
        try: print(json.dumps(run(),sort_keys=True))
        except Exception: raise SystemExit('Monitor unavailable; no private exception details emitted')
