#!/usr/bin/env python3
"""Pool-pinned market observations, never automatic trades or entry recommendations."""
import argparse
import concurrent.futures
import datetime as dt
import email.utils
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
PREFIX = '🚨💎 MEME GEM ALERT — '

def utc(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec='seconds')

class FeedError(Exception):
    def __init__(self,message,retry_after=0):
        super().__init__(message)
        self.retry_after=retry_after

def request_json(url, payload=None, timeout=8):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={
        'User-Agent':'PoolWatch/1.0', 'Accept':'application/json',
        'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            headers = dict(response.headers.items())
            body = response.read(4_000_001)
            if len(body) > 4_000_000:
                raise FeedError('response too large')
            return json.loads(body), {k.lower():v for k,v in headers.items()}
    except urllib.error.HTTPError as error:
        # Never log the URL: Telegram URLs contain a bot credential.
        if error.code == 429:
            delay=60
            raw=error.headers.get('Retry-After','60')
            try:
                delay=float(raw)
            except ValueError:
                try: delay=email.utils.parsedate_to_datetime(raw).timestamp()-time.time()
                except (ValueError,TypeError): pass
            raise FeedError('HTTP 429; provider rate limit',max(60,delay)) from None
        raise FeedError('HTTP '+str(error.code)) from None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        raise FeedError('network or JSON failure') from None

def number(value, positive=False):
    if isinstance(value, bool):
        raise FeedError('invalid numeric value')
    try:
        n=float(value)
    except (TypeError,ValueError):
        raise FeedError('missing numeric value') from None
    if not math.isfinite(n) or n < 0 or (positive and n <= 0):
        raise FeedError('invalid numeric value')
    return n

def parse_pair(token, data, headers=None, now=None):
    now = time.time() if now is None else now
    headers = headers or {}
    if 'age' in headers and number(headers['age']) > 60:
        raise FeedError('cached response older than 60 seconds')
    if headers.get('date'):
        try:
            server_time=email.utils.parsedate_to_datetime(headers['date']).timestamp()
            if abs(now-server_time) > 120:
                raise FeedError('HTTP date stale or server clock incorrect')
        except (ValueError,TypeError,OverflowError):
            raise FeedError('invalid HTTP date') from None
    pairs=data.get('pairs') or []
    matches=[p for p in pairs if p.get('pairAddress') == token['pool']]
    if len(matches)!=1:
        raise FeedError('exact pool missing or ambiguous')
    p=matches[0]
    identity=(p.get('chainId'),p.get('dexId'),p.get('baseToken',{}).get('address'),
              p.get('quoteToken',{}).get('address'))
    if identity != (token['chain'],token['dex'],token['contract'],token['quote']):
        raise FeedError('pool identity mismatch; signals blocked')
    def optional(value):
        return None if value is None else number(value)
    return {'price':number(p.get('priceUsd'),True),
            'liquidity':optional((p.get('liquidity') or {}).get('usd')),
            'volume5m':optional((p.get('volume') or {}).get('m5')),
            'buys5m':optional((p.get('txns',{}).get('m5') or {}).get('buys')),
            'sells5m':optional((p.get('txns',{}).get('m5') or {}).get('sells')),
            'marketcap':optional(p.get('marketCap')),
            'fdv':optional(p.get('fdv')),
            'quote_time':None, 'received_at':now,
            'source':'https://dexscreener.com/'+token['chain']+'/'+token['pool']}

def fetch_pair(token):
    if token.get('provider') == 'geckoterminal':
        url='https://api.geckoterminal.com/api/v2/networks/'+token['chain']+'/pools/'+token['pool']
        data,headers=request_json(url)
        return parse_gecko(token,data,headers)
    url='https://api.dexscreener.com/latest/dex/pairs/'+token['chain']+'/'+token['pool']
    data,headers=request_json(url)
    return parse_pair(token,data,headers)

def parse_gecko(token,data,headers=None,now=None):
    pool=data.get('data') or {}
    a=pool.get('attributes') or {}
    relationships=pool.get('relationships') or {}
    def relation(name):
        return (relationships.get(name) or {}).get('data',{}).get('id')
    prefix=token['chain']+'_'
    if (pool.get('id')!=prefix+token['pool'] or pool.get('type')!='pool'
        or relation('base_token')!=prefix+token['contract']
        or relation('quote_token')!=prefix+token['quote']):
        raise FeedError('GeckoTerminal pool/token identity mismatch')
    pair={'pairAddress':a.get('address'),'chainId':token['chain'],
        'dexId':relation('dex'),'baseToken':{'address':token['contract']},
        'quoteToken':{'address':token['quote']},'priceUsd':a.get('base_token_price_usd'),
        'liquidity':{'usd':a.get('reserve_in_usd')},'volume':a.get('volume_usd') or {},
        'txns':a.get('transactions') or {},'marketCap':a.get('market_cap_usd'),
        'fdv':a.get('fdv_usd')}
    observation=parse_pair(token,{'pairs':[pair]},headers,now)
    observation['source']='https://www.geckoterminal.com/'+token['chain']+'/pools/'+token['pool']
    observation['provider']='geckoterminal'
    tx=(a.get('transactions') or {}).get('m5') or {}
    for name in ['buyers','sellers']:
        observation['unique_'+name+'5m']=None if tx.get(name) is None else number(tx[name])
    return observation

def parse_gecko_batch(tokens,data,headers=None,now=None):
    pools=data.get('data') or []
    if not isinstance(pools,list):
        raise FeedError('invalid pool batch schema')
    results=[]
    for t in tokens:
        matches=[p for p in pools if p.get('id')==t['chain']+'_'+t['pool']]
        try:
            if len(matches)!=1:
                raise FeedError('exact pool missing or ambiguous in batch')
            result=parse_gecko(t,{'data':matches[0]},headers,now)
        except (FeedError,KeyError,TypeError) as error:
            result=error if isinstance(error,FeedError) else FeedError('invalid pool batch schema')
        results.append((t,result))
    return results

def fetch_cycle(tokens,executor):
    if all(t.get('provider')=='geckoterminal' for t in tokens):
        url='https://api.geckoterminal.com/api/v2/networks/solana/pools/multi/'+','.join(t['pool'] for t in tokens)
        try:
            data,headers=request_json(url)
            return parse_gecko_batch(tokens,data,headers)
        except FeedError as error:
            return [(t,error) for t in tokens]
    futures={executor.submit(fetch_pair,t):t for t in tokens}
    results=[]
    for future in concurrent.futures.as_completed(futures):
        try: result=future.result()
        except (FeedError,KeyError,TypeError) as error: result=error
        results.append((futures[future],result))
    return results

class Store:
    def __init__(self,path):
        self.db=sqlite3.connect(path,timeout=10)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS observations(
            id INTEGER PRIMARY KEY, identity TEXT, ts REAL, data TEXT);
          CREATE INDEX IF NOT EXISTS observations_time ON observations(identity,ts);
          CREATE TABLE IF NOT EXISTS outbox(
            id TEXT PRIMARY KEY, ts REAL, expires REAL, message TEXT,
            status TEXT DEFAULT 'pending', message_id TEXT);
        ''')
    def get(self,k,default=None):
        row=self.db.execute('SELECT value FROM state WHERE k=?',(k,)).fetchone()
        return default if row is None else json.loads(row[0])
    def put(self,k,v):
        self.db.execute('INSERT OR REPLACE INTO state VALUES (?,?)',(k,json.dumps(v)))
    def enqueue(self,key,now,ttl,message):
        event=hashlib.sha256(key.encode()).hexdigest()[:16]
        self.db.execute('INSERT OR IGNORE INTO outbox(id,ts,expires,message) VALUES (?,?,?,?)',
                        (event,now,now+ttl,message+'\nEvent: '+event))
    def commit(self):
        self.db.commit()

def identity(token):
    return token.get('provider','dexscreener')+'|'+ '|'.join(token[x] for x in ['chain','pool','dex','contract','quote'])

class Engine:
    def __init__(self,store,config):
        self.s=store
        self.c=config
    def process(self,t,o,now):
        key=identity(t)
        old=self.s.get(key,{})
        gap=not old or now-old.get('ts',0)>self.c['max_gap_seconds']
        state=old.copy()
        if gap:
            state['levels']={}
            state['recent']=[]
        levels=state.setdefault('levels',{})
        price=o['price']
        def alert(kind,text,ttl=None):
            if t.get('notifications')=='marketcap_only' and not kind.startswith('mc-target-'):
                return
            self.s.enqueue(key+'|'+kind+'|'+str(now),now,
                self.c['alert_ttl_seconds'] if ttl is None else ttl,
                PREFIX+text+'\n'+t['name']+' | '+utc(now)+
                '\nPrice $'+format(price,'.8g')+
                '\nPool '+t['pool']+'\n'+o['source']+
                '\nProvider quote time unavailable. Observation only; no entry signal.')
        crossed=[]
        for level in t['levels']:
            name=str(level)
            entry=levels.get(name)
            if entry is None:
                entry={'armed':price < level,'last_alert':0}
                levels[name]=entry
            elif price <= level*(1-self.c['rearm_percent']/100):
                entry['armed']=True
            elif price >= level and entry['armed']:
                if now-entry['last_alert'] >= self.c['cooldown_seconds']:
                    crossed.append(level)
                    entry['last_alert']=now
                entry['armed']=False
        if crossed:
            alert('cross','PRICE TRIPWIRE — verification pending\nCrossed $'+
                  ', $'.join(format(x,'.8g') for x in crossed))
        # One-shot market-cap targets survive restarts and data gaps. FDV is
        # recorded separately and must never substitute for circulating MC.
        targets=state.setdefault('marketcap_targets',{})
        mc=o.get('marketcap')
        if t.get('marketcap_levels'):
            if mc is None:
                # Missing market cap is recorded silently. Never substitute FDV.
                state['marketcap_missing']=True
            else:
                if state.pop('marketcap_missing',False) and self.c.get('notify_recovery',True):
                    alert('mc-recovered','DATA HEALTH — market cap available again; target checks resumed.',ttl=600)
                for target in t['marketcap_levels']:
                    name=str(target)
                    strict=t.get('marketcap_strict_above',False)
                    reached=mc>target if strict else mc>=target
                    if reached and not targets.get(name):
                        alert('mc-target-'+name,'MARKET CAP TARGET — observed '+
                              ('above $' if strict else 'at or above $')+
                              format(target,',.0f')+'\nReported market cap $'+format(mc,',.2f')+
                              '\nFirst qualifying observation; exact crossing time unknown.')
                        targets[name]={'observed_at':now,'marketcap':mc}
        if gap and any(price>=x for x in t['levels']):
            # No false crossing from a process start, outage, or config change.
            last=state.get('above_notice',0)
            if now-last >= self.c['cooldown_seconds']:
                alert('baseline','BASELINE — already above a watch level; crossing time unknown')
                state['above_notice']=now
        recent=state.get('recent',[])
        # Consecutive observations, not overlapping rolling-volume differences.
        recent=[x for x in recent if now-x['ts'] <= 360]
        reference=next((x for x in reversed(recent) if now-x['ts']>=300),None)
        if reference and o['liquidity'] is not None and reference['liquidity']:
            ratio=o['liquidity']/reference['liquidity']
            if ratio<=.85 and now-state.get('liquidity_notice',0)>=self.c['cooldown_seconds']:
                alert('liquidity','LIQUIDITY REVIEW — USD pool liquidity fell '+
                      format((1-ratio)*100,'.1f')+'% in about 5 minutes.\n'+
                      'Valuation changes can cause this; LP removal is NOT verified.')
                state['liquidity_notice']=now
        if t['levels'] and reference and all(o.get(k) is not None for k in ['volume5m','buys5m','sells5m','liquidity']):
            total=o['buys5m']+o['sells5m']
            prior_volume=reference.get('volume5m')
            activity=(prior_volume and prior_volume>=100 and o['volume5m']>=2*prior_volume
                and total>=20 and o['buys5m']/total>=.6
                and price>reference['price'] and price>=min(t['levels'])*.95
                and reference['liquidity'] and o['liquidity']>=reference['liquidity']*.95)
            if activity and now-state.get('activity_notice',0)>=self.c['cooldown_seconds']:
                alert('activity','ACTIVITY WATCH — verification pending\n'+
                    'Near/above watch level; rising price, 5m volume ≥2x the earlier 5m window, '+
                    'buy transactions ≥60%, USD liquidity holding.\n'+
                    'Transaction counts are NOT unique buyers. Holders, insiders and security unverified.')
                state['activity_notice']=now
        signature={k:v for k,v in o.items() if k not in ['received_at','source']}
        if signature != old.get('signature') or gap:
            state['last_change']=now
        # Unchanged observations are tracked silently; inactivity alone is not an alert.
        state.update(ts=now,signature=signature)
        recent.append({'ts':now,'liquidity':o['liquidity'],'price':price,'volume5m':o['volume5m']})
        state['recent']=recent
        self.s.put(key,state)
        self.s.db.execute('INSERT INTO observations(identity,ts,data) VALUES (?,?,?)',
                          (key,now,json.dumps(o)))
        health=self.s.get('health|'+key,{})
        if health.get('warned') and t.get('notifications')!='marketcap_only' and self.c.get('notify_recovery',True):
            self.s.enqueue(key+'|recovery|'+str(now),now,600,
                '🛠 MONITOR STATUS — '+t['name']+' feed recovered.\n'+utc(now)+
                '\nCoverage during the gap is unknown; baseline refreshed if gap exceeded 90 seconds.')
        self.s.put('health|'+key,{})
        self.s.commit()
    def failure(self,t,now,reason):
        key=identity(t)
        h=self.s.get('health|'+key,{})
        h.setdefault('since',now)
        h['reason']=reason
        if now-h['since']>=60 and not h.get('warned') and t.get('notifications')!='marketcap_only':
            self.s.enqueue(key+'|outage|'+str(h['since']),now,600,
                '🛠 MONITOR STATUS — '+t['name']+' data unavailable.\n'+reason+
                '\n'+utc(now)+'\nSignals blocked until valid data returns.')
            h['warned']=True
        self.s.put('health|'+key,h)
        self.s.commit()

class Telegram:
    def __init__(self,secrets):
        self.token=secrets['bot_token']
        self.chat=str(secrets['chat_id'])
    def call(self,method,payload=None):
        data,_=request_json('https://api.telegram.org/bot'+self.token+'/'+method,payload or {})
        if not data.get('ok'):
            raise FeedError('Telegram rejected request')
        return data['result']
    def verify(self):
        self.call('getMe')
        chat=self.call('getChat',{'chat_id':self.chat})
        if chat.get('type')!='private' or str(chat.get('id'))!=self.chat:
            raise FeedError('destination must be the paired private chat')
    def send(self,text):
        return self.call('sendMessage',{'chat_id':self.chat,'text':text,
                         'link_preview_options':{'is_disabled':True}})['message_id']

def drain(store,sender,now):
    store.db.execute("UPDATE outbox SET status='expired' WHERE status='pending' AND expires<=?",(now,))
    store.commit()
    rows=store.db.execute("SELECT id,message FROM outbox WHERE status='pending' ORDER BY ts LIMIT 3").fetchall()
    for event,message in rows:
        try:
            message_id=sender.send(message)
        except FeedError as error:
            print(utc(now),'Telegram delivery failed:',str(error),flush=True)
            break
        store.db.execute("UPDATE outbox SET status='sent',message_id=? WHERE id=?",(str(message_id),event))
        store.commit()

def config_load(path):
    c=json.loads(Path(path).read_text())
    if not 15<=c['poll_seconds']<=60:
        raise ValueError('poll_seconds must be 15–60')
    active=[t for t in c['tokens'] if t.get('enabled')]
    if not active or len(active)>20:
        raise ValueError('configure 1–20 enabled tokens')
    for t in active:
        t['provider']=c.get('provider','dexscreener')
        if t['provider'] not in ['dexscreener','geckoterminal']:
            raise ValueError('unsupported market-data provider')
        if any(not t.get(k) for k in ['name','chain','contract','pool','dex','quote']):
            raise ValueError('enabled token needs complete pinned identity')
        for k in ['chain','contract','pool','dex','quote']:
            if not all(x.isalnum() or x in '_-' for x in t[k]):
                raise ValueError('invalid identity characters')
        if t['chain']!='solana':
            raise ValueError('this version only supports Solana')
        for field in ['levels','marketcap_levels']:
            t[field]=sorted(set(number(x,True) for x in t.get(field,[])))
        if not t['levels'] and not t['marketcap_levels'] and not t.get('monitor_only'):
            raise ValueError('enabled token needs price or market-cap targets')
    if c.get('provider')=='geckoterminal' and len(active)>20:
        raise ValueError('GeckoTerminal pool batch limit exceeded')
    return c,active

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default=str(ROOT/'config.json'))
    parser.add_argument('--data-dir',default=str(ROOT/'data'))
    parser.add_argument('--credentials',default=str(ROOT/'credentials.json'))
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--test-alert',action='store_true')
    args=parser.parse_args()
    c,tokens=config_load(args.config)
    os.umask(0o077)
    data_dir=Path(args.data_dir)
    data_dir.mkdir(parents=True,exist_ok=True)
    lock=(data_dir/'monitor.lock').open('w')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Another monitor is already running.')
    sender=None
    if not args.dry_run:
        path=Path(args.credentials)
        if path.stat().st_mode & 0o077:
            raise SystemExit('Credentials must have permissions 600.')
        sender=Telegram(json.loads(path.read_text()))
        sender.verify()
    if args.test_alert:
        if not sender:
            raise SystemExit('Test alert needs Telegram credentials, not dry-run.')
        print('Telegram accepted message ID',sender.send(PREFIX+'TEST ALERT\n'+utc(time.time())+
              '\nDelivery test only. Confirm that you saw this on your phone.'))
        return
    # Dry-run never queues notifications into the live database.
    store=Store(data_dir/('dryrun.sqlite' if args.dry_run else 'monitor.sqlite'))
    engine=Engine(store,c)
    from developer_checks import DeveloperChecks
    developer_checks=DeveloperChecks(store,tokens,ROOT/"developer_watch.json")
    last_prune=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8,len(tokens))) as executor:
        while True:
            start=time.monotonic()
            failures=0
            retry_delay=0
            for t,observation in fetch_cycle(tokens,executor):
                now=time.time()
                try:
                    if isinstance(observation,Exception): raise observation
                    engine.process(t,observation,now)
                    print(utc(now),t['name'],'verified pool; price',observation['price'],flush=True)
                except (FeedError,KeyError,TypeError) as error:
                    failures+=1
                    retry_delay=max(retry_delay,getattr(error,'retry_after',0))
                    reason=str(error) if isinstance(error,FeedError) else 'invalid provider schema'
                    engine.failure(t,now,reason)
                    print(utc(now),t['name'],reason,flush=True)
            now=time.time()
            if sender and c.get('notify_heartbeat',True) and now-store.get('last_heartbeat',0)>=21600:
                store.enqueue('heartbeat|'+str(int(now//21600)),now,600,
                    '🛠 MONITOR STATUS — heartbeat\n'+utc(now)+
                    '\nValid pools this cycle: '+str(len(tokens)-failures)+'/'+str(len(tokens))+
                    '\n20-second target checks; provider and delivery delays still apply.'+
                    '\nIf this heartbeat disappears for more than 6 hours, inspect the service.')
                store.put('last_heartbeat',now)
                store.commit()
            developer_checks.tick(now)
            if sender:
                drain(store,sender,now)
            else:
                for row in store.db.execute("SELECT message FROM outbox WHERE status='pending'"):
                    print('DRY RUN:',row[0],flush=True)
                store.db.execute("UPDATE outbox SET status='dryrun' WHERE status='pending'")
                store.commit()
            if now-last_prune>3600:
                cutoff=now-c['retention_days']*86400
                store.db.execute('DELETE FROM observations WHERE ts<?',(cutoff,))
                store.db.execute('DELETE FROM outbox WHERE ts<?',(cutoff,))
                store.commit()
                last_prune=now
            store.put('runtime',{'last_cycle':now,'failed_pools':failures,'total_pools':len(tokens)})
            store.commit()
            if args.once:
                raise SystemExit(2 if failures else 0)
            time.sleep(max(retry_delay,0,c['poll_seconds']-(time.monotonic()-start)))

if __name__=='__main__':
    try:
        main()
    except (FeedError,ValueError,KeyError,FileNotFoundError) as error:
        # No exception URL/token dumps in service logs.
        print('Monitor stopped:',str(error) if isinstance(error,FeedError) else type(error).__name__)
        raise SystemExit(1)
