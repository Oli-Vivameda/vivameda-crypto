"""Exact-venue public market observations; no orders, account APIs or API keys."""
import asyncio
from datetime import datetime
import importlib.util
import json
import math
import re
import time
import uuid
from urllib.parse import quote
import httpx
from core import atomic, crypto_symbol, observe

ENDPOINTS = {
 'BINANCE:spot': ('https://data-api.binance.vision','/api/v3'),
 'BINANCE:perpetual': ('https://fapi.binance.com','/fapi/v1'),
 'COINBASE:spot': ('https://api.exchange.coinbase.com',''),
 'BYBIT:spot': ('https://api.bybit.com','/v5/market'),
 'BYBIT:perpetual': ('https://api.bybit.com','/v5/market'),
}
SAFE = {'provider_cooldown','provider_rate_limited','provider_unavailable',
 'provider_shape','stale_trade','invalid_trade','no_trade','catalog_unavailable',
 'unsupported_venue','unsupported_instrument','pair_not_listed','pair_inactive','ambiguous_pair'}
def reason(error):
    code=str(error)
    return code if code in SAFE else 'provider_unavailable'

def identity(value):
    if not isinstance(value,str) or value.count(':')!=1:raise ValueError('unsupported_instrument')
    venue,pair=value.upper().split(':')
    kind='perpetual' if pair.endswith('.P') else 'spot'
    if kind=='perpetual':pair=pair[:-2]
    if not re.fullmatch('[A-Z0-9]{2,40}',pair):raise ValueError('unsupported_instrument')
    key=venue+':'+kind
    if key not in ENDPOINTS:raise ValueError('unsupported_venue')
    return key,pair

def catalog_rows(key,data):
    rows=[]
    if key.startswith('BINANCE:'):
        for r in data['symbols']:
            if key.endswith('perpetual') and r.get('contractType')!='PERPETUAL':continue
            rows.append({'symbol':r['symbol'],'base':r['baseAsset'],'quote':r['quoteAsset'],
                'active':r.get('status')=='TRADING' and (key.endswith('perpetual') or r.get('isSpotTradingAllowed') is True),
                'category':'perpetual' if key.endswith('perpetual') else 'spot'})
    elif key.startswith('COINBASE:'):
        for r in data:
            rows.append({'symbol':r['id'],'tv_pair':r['base_currency']+r['quote_currency'],
                'base':r['base_currency'],'quote':r['quote_currency'],
                'active':r.get('status')=='online' and not r.get('trading_disabled',False),'category':'spot'})
    else:
        if data.get('retCode')!=0:raise ValueError('provider_unavailable')
        for r in data['result']['list']:
            if key.endswith('perpetual') and r.get('contractType') not in ('LinearPerpetual','InversePerpetual'):continue
            rows.append({'symbol':r['symbol'],'base':r['baseCoin'],'quote':r['quoteCoin'],
                'active':r.get('status')=='Trading','category':data['result']['category']})
    return rows

def resolve(value,catalog):
    key,pair=identity(value)
    matches=[r for r in catalog if r.get('tv_pair',r['symbol'])==pair]
    if len(matches)>1:raise ValueError('ambiguous_pair')
    if not matches:raise ValueError('pair_not_listed')
    r=matches[0]
    if not r['active']:raise ValueError('pair_inactive')
    return dict(r,provider=key,instrument=key.split(':')[1])

def tick_payload(mapping,data,now):
    key=mapping['provider']
    if key.startswith('BINANCE:'):
        if not isinstance(data,list) or not data:raise ValueError('no_trade')
        r=max(data,key=lambda r:float(r['T']))
        price,stamp=r['p'],float(r['T'])/1000
    elif key.startswith('COINBASE:'):
        price=data['price']
        dt=datetime.fromisoformat(data['time'].replace('Z','+00:00'))
        if dt.tzinfo is None:raise ValueError('invalid_trade')
        stamp=dt.timestamp()
    else:
        if data.get('retCode')!=0:raise ValueError('provider_unavailable')
        if data['result'].get('category')!=mapping['category']:raise ValueError('provider_shape')
        rows=data['result']['list']
        if not rows:raise ValueError('no_trade')
        if any(r['symbol']!=mapping['symbol'] for r in rows):raise ValueError('provider_shape')
        r=max(rows,key=lambda r:float(r['time']))
        price,stamp=r['price'],float(r['time'])/1000
    price=float(price)
    if not math.isfinite(price) or price<=0 or not math.isfinite(stamp):raise ValueError('invalid_trade')
    if not -5<=now-stamp<=120:raise ValueError('stale_trade')
    return {'ts':int(now),'source_ts':stamp,'price':price}

def delegated(mapping):
    # Core USD spot alarms already run independently; no second alarm for equivalent stablecoin spot pairs.
    return mapping['instrument']=='spot' and mapping['base'] in ('BTC','SOL') and mapping['quote'] in ('USD','USDT','USDC')

def message(value,mapping,event,test=False):
    return (('VIVAMEDA TEST — synthetic movement; not a market signal\n' if test else '🚨 VIVAMEDA MARKET MOVE\n')+
        f"{value}: {event['pct']:+.2f}% over {event['elapsed_seconds']/60:.1f} minutes\n"+
        f"Price: {event['price']:.8g} {mapping['quote']}\n"+
        f"Source: {mapping['provider']} / {mapping['symbol']} ({mapping['instrument']}); public trade timestamp {event['source_ts']}\n"+
        'https://www.tradingview.com/chart/?symbol='+quote(value,safe='')+'\nNo order executed.')

def send_existing(text):
    spec=importlib.util.spec_from_file_location('movement_sender','/opt/vivameda-market-moves/monitor.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod.send(text)

def record_alarm(directory,attempt,observed,result,ack=None):
    try:
        spec=importlib.util.spec_from_file_location('movement_audit','/opt/vivameda-market-moves/monitor.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        return mod.alarm_log(directory/'alarm_delivery.jsonl',attempt,observed,result,ack)
    except Exception:return False


class ExchangeMonitor:
    def __init__(self,directory,sender=send_existing):
        self.directory=directory;self.sender=sender;self.catalog={};self.retry={};self.failures={}
        self.lock=asyncio.Lock();self.semaphore=asyncio.Semaphore(4);self.request_lock=asyncio.Lock()
        self.next_request=0;self.report={'status':'starting','live_execution':False}
    async def get(self,client,key,path,params=None):
        if time.time()<self.retry.get(key,0):raise ValueError('provider_cooldown')
        async with self.semaphore:
            async with self.request_lock:
                await asyncio.sleep(max(0,self.next_request-time.monotonic()))
                self.next_request=time.monotonic()+0.15
            if time.time()<self.retry.get(key,0):raise ValueError('provider_cooldown')
            try:
                async with client.stream('GET',ENDPOINTS[key][0]+path,params=params) as r:
                    if r.status_code in (418,429):
                        try:wait=float(r.headers.get('Retry-After','300'))
                        except ValueError:wait=300
                        self.retry[key]=time.time()+max(300,min(wait,259200))
                        raise ValueError('provider_rate_limited')
                    if r.status_code!=200:raise ValueError('provider_unavailable')
                    raw=bytearray()
                    async for chunk in r.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw)>8*1024*1024:raise ValueError('provider_shape')
                    data=json.loads(raw)
                self.failures[key]=0
                return data
            except asyncio.CancelledError:raise
            except Exception:
                if self.retry.get(key,0)<=time.time():
                    self.failures[key]=self.failures.get(key,0)+1
                    self.retry[key]=time.time()+min(300,30*2**min(self.failures[key]-1,4))
                raise
    async def products(self,client,key):
        if key in self.catalog and time.time()-self.catalog[key][0]<3600:return self.catalog[key][1]
        prefix=ENDPOINTS[key][1]
        if key.startswith('BINANCE:'):rows=catalog_rows(key,await self.get(client,key,prefix+'/exchangeInfo',
            {'permissions':'SPOT','showPermissionSets':'false'} if key.endswith('spot') else None))
        elif key.startswith('COINBASE:'):rows=catalog_rows(key,await self.get(client,key,'/products'))
        else:
            rows=[]
            for category in (('linear','inverse') if key.endswith('perpetual') else ('spot',)):
                cursor=''
                for page in range(10):
                    params={'category':category,'limit':1000}
                    if cursor:params['cursor']=cursor
                    data=await self.get(client,key,prefix+'/instruments-info',params)
                    rows.extend(catalog_rows(key,data));cursor=data['result'].get('nextPageCursor','')
                    if not cursor:break
                else:raise ValueError('provider_shape')
        self.catalog[key]=(time.time(),rows)
        return rows
    async def fetch(self,client,mapping):
        key=mapping['provider'];prefix=ENDPOINTS[key][1]
        if key.startswith('BINANCE:'):data=await self.get(client,key,prefix+'/aggTrades',{'symbol':mapping['symbol'],'limit':1})
        elif key.startswith('COINBASE:'):data=await self.get(client,key,'/products/'+mapping['symbol']+'/ticker')
        else:data=await self.get(client,key,prefix+'/recent-trade',{'category':mapping['category'],'symbol':mapping['symbol'],'limit':1})
        return tick_payload(mapping,data,int(time.time()))
    async def collect(self,watch,observed_at,client=None):
        async with self.lock:
            if client is None:
                async with httpx.AsyncClient(timeout=8,trust_env=False,follow_redirects=False,
                    headers={'User-Agent':'Vivameda-Watchlist-Monitor/1.0'}) as own:
                    return await self._collect(watch,observed_at,own)
            return await self._collect(watch,observed_at,client)
    async def _collect(self,watch,observed_at,client):
        start=time.monotonic();now=int(time.time())
        universe=list(dict.fromkeys(s for w in watch for s in w['symbols']))
        path=self.directory/'exchange_state.json'
        state=json.loads(path.read_text()) if path.exists() else {'items':{},'delivery':{}}
        statuses={};valid={}
        if now-observed_at>86400 or observed_at>now+5:
            self.report={'checked_at':now,'status':'watchlist_stale','live_execution':False,'fresh_prices':0}
            atomic(self.directory/'exchange_status.json',self.report);return self.report
        if len(universe)>1000 or sum(crypto_symbol(s) for s in universe)>60:raise ValueError('watchlist_capacity_exceeded')
        for value in universe:
            if not crypto_symbol(value):statuses[value]={'status':'non_crypto_not_monitored'};continue
            try:key,pair=identity(value);valid[value]=key
            except ValueError as e:statuses[value]={'status':'unavailable','reason':reason(e)}
        catalogs={}
        for key in set(valid.values()):
            try:catalogs[key]=await self.products(client,key)
            except Exception as e:catalogs[key]=None;statuses.update({v:{'status':'unavailable','reason':reason(e)} for v,k in valid.items() if k==key})
        async def one(value,key):
            if catalogs[key] is None:return
            try:
                mapping=resolve(value,catalogs[key]);tick=await self.fetch(client,mapping)
                fingerprint=key+':'+mapping['category']+':'+mapping['symbol']
                item=state['items'].setdefault(value,{'identity':fingerprint,'samples':[]})
                if item.get('identity')!=fingerprint:item.clear();item.update(identity=fingerprint,samples=[])
                rows=item['samples']
                if rows and tick['source_ts']<rows[-1].get('source_ts',0):raise ValueError('invalid_trade')
                event=observe(item,tick)
                row={'status':'measuring' if event else 'warming_or_gap','mapping':mapping,
                    'last_observed_ts':tick['ts'],'source_ts':tick['source_ts'],'samples':len(item['samples']),
                    'movement_pct':event['pct'] if event else None}
                statuses[value]=row
                if delegated(mapping):row['notification']='existing_btc_sol_monitor';return
                if event and abs(event['pct'])+1e-9 >= (1.0 if mapping['base']=='BTC' else 2.0):
                    # Stable identity deduplicates the same pair across lists.
                    delivery=state['delivery'].setdefault(fingerprint,{})
                    if now-delivery.get('last_attempt',0)<1800:row['notification']='cooldown';return
                    delivery['last_attempt']=now;delivery['status']='pending';atomic(path,state)
                    attempt=uuid.uuid4().hex
                    logged=record_alarm(self.directory,attempt,event['observed_ts'],'pending')
                    row['audit_log']='available' if logged else 'unavailable'
                    try:
                        event['source_ts']=tick['source_ts']
                        ack=await asyncio.to_thread(self.sender,message(value,mapping,event))
                        logged=record_alarm(self.directory,attempt,event['observed_ts'],'sent',ack)
                        row['audit_log']='available' if logged else 'unavailable'
                        delivery.update(status='sent',last_sent=now);row['notification']='sent'
                    except Exception:
                        record_alarm(self.directory,attempt,event['observed_ts'],'failed')
                        delivery['status']='failed';row['notification']='delivery_failed'
            except asyncio.CancelledError:raise
            except Exception as e:statuses[value]={'status':'unavailable','reason':reason(e)}
        tasks={asyncio.create_task(one(v,k)):v for v,k in valid.items()}
        if tasks:
            done,pending=await asyncio.wait(tasks,timeout=45)
            for task in pending:
                task.cancel();statuses[tasks[task]]={'status':'unavailable','reason':'cycle_timeout'}
            await asyncio.gather(*tasks,return_exceptions=True)
        # Removed symbols lose their windows; re-addition starts forward observation again.
        state['items']={k:v for k,v in state['items'].items() if k in universe}
        active_ids={v['identity'] for v in state['items'].values()}
        state['delivery']={k:v for k,v in state['delivery'].items() if k in active_ids}
        atomic(path,state)
        fresh=sum('last_observed_ts' in r for r in statuses.values())
        crypto=sum(crypto_symbol(s) for s in universe)
        self.report={'checked_at':int(time.time()),'status':'active' if fresh==crypto else 'active_partial',
            'watchlist_observed_at':observed_at,'watchlist_age_seconds':now-observed_at,
            'watchlist_count':len(watch),'symbol_count':len(universe),'crypto_count':crypto,
            'fresh_prices':fresh,'unavailable_crypto':crypto-fresh,
            'non_crypto_count':len(universe)-crypto,'cycle_seconds':round(time.monotonic()-start,3),
            'live_execution':False,'telegram_test':state.get('telegram_test','not_run'),
            'symbols':statuses}
        atomic(self.directory/'exchange_status.json',self.report)
        return self.report
    async def test_delivery(self):
        async with self.lock:
            path=self.directory/'exchange_state.json'
            state=json.loads(path.read_text()) if path.exists() else {'items':{},'delivery':{}}
            if state.get('telegram_test') in ('sent','attempted'):return state['telegram_test']
            state['telegram_test']='attempted';atomic(path,state)
            # Isolated synthetic samples exercise the same movement evaluator and formatter.
            item={};event=None
            for i in range(16):event=observe(item,{'ts':1000+i*60,'price':100 if i<15 else 103})
            if not event or event['pct']<2:raise ValueError('synthetic_test_failed')
            event['source_ts']=int(time.time())
            mapping={'provider':'SYNTHETIC:spot','symbol':'TESTUSD','quote':'USD','instrument':'spot'}
            try:
                await asyncio.to_thread(self.sender,message('SYNTHETIC:TESTUSD',mapping,event,test=True))
                state['telegram_test']='sent'
            except Exception:state['telegram_test']='failed'
            atomic(path,state);return state['telegram_test']
