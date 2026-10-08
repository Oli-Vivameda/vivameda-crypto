"""Owner-run aggregate diagnosis using retained inventory and at most three existing-feed trades."""
import argparse,asyncio,collections,datetime,hashlib,json,pathlib,sys,time
BASE=pathlib.Path('/var/lib/vivameda-tradingview')
async def collect():
 sys.path.insert(0,'/opt/vivameda-tradingview');import exchange;import httpx
 d=json.loads((BASE/'exchange_status.json').read_text());s=json.loads((BASE/'exchange_state.json').read_text());w=json.loads((BASE/'watchlists.json').read_text())
 universe={v for row in w['watchlists'] for v in row['symbols']}
 sol_inventory=sum(v.split(':',1)[-1] in ('SOLUSD','SOLUSDT','SOLUSDC') for v in universe)
 sol_status=sum(v.split(':',1)[-1] in ('SOLUSD','SOLUSDT','SOLUSDC') for v in d.get('symbols',{}))
 stale=[v for v,r in d.get('symbols',{}).items() if r.get('reason')=='stale_trade'];counts=collections.Counter();ages=[];requests=0
 monitor=exchange.ExchangeMonitor(BASE);original=exchange.tick_payload
 def inspected(mapping,data,now):
  try:return original(mapping,data,now)
  except ValueError as e:
   if str(e)=='stale_trade':
    key=mapping['provider']
    stamp=max(float(r['T']) for r in data)/1000 if key.startswith('BINANCE:') else datetime.datetime.fromisoformat(data['time'].replace('Z','+00:00')).timestamp() if key.startswith('COINBASE:') else max(float(r['time']) for r in data['result']['list'])/1000
    ages.append(round(now-stamp,3))
   raise
 exchange.tick_payload=inspected
 try:
  async with httpx.AsyncClient(timeout=8,trust_env=False) as client:
   for v in stale[:3]:
    fingerprint=s.get('items',{}).get(v,{}).get('identity','');parts=fingerprint.split(':')
    if len(parts)!=4 or ':'.join(parts[:2]) not in exchange.ENDPOINTS:counts['retained_mapping_unavailable']+=1;continue
    mapping=dict(provider=':'.join(parts[:2]),instrument=parts[1],category=parts[2],symbol=parts[3]);requests+=1
    try:await monitor.fetch(client,mapping);counts['now_fresh']+=1
    except Exception as e:counts[exchange.reason(e)]+=1
 finally:exchange.tick_payload=original
 return dict(snapshot_time=d['checked_at'],watchlist_observed_at=w['observed_at'],sol_stablecoin_spot_inventory_count=sol_inventory,sol_stablecoin_spot_status_count=sol_status,current_stale_trade_count=len(stale),diagnosed_count=sum(counts.values()),results=dict(counts),fresh_probe_trade_age_seconds=ages,provider_requests=requests,existing_feeds_only=True,state_modified=False,alarm_sent=False,private_instruments_exported=False,historical_three_instrument_identity_match_verified=False)
def main():
 p=argparse.ArgumentParser();p.add_argument('--expected-sha256',required=True);a=p.parse_args()
 if hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()!=a.expected_sha256:raise SystemExit('Reviewed diagnosis hash mismatch')
 try:out=asyncio.run(collect())
 except Exception:out=dict(available=False,reason='private_source_or_dependency_unavailable',permissions_changed=False,alarm_sent=False)
 print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
