"""Bounded, free public evidence for the separate watchlist. No trading or scoring edits."""
import contextlib, hashlib, html.parser, http.client, ipaddress, json, math
import re, signal, socket, sqlite3, ssl, time, urllib.parse

POLICY='coin-research-v1'
MAX_BYTES=262144
MAX_SECONDS=8
AUTOMATION=re.compile(r'volume\s+bot|boost(?:ing)?\s+(?:your\s+)?volume|volume\s+boost(?:ing|er)?|generat(?:e|ing|ion)\s+(?:trading\s+)?volume|wash\s+trad(?:e|ing)|buy\s+bot',re.I)
FEE_BUYBACK=re.compile(r'creator\s+fees.{0,100}(?:buy|buyback)|(?:auto|automat).{0,30}buyback|buyback.{0,30}(?:bot|automat)',re.I)
def numeric(x):return type(x) in (int,float) and math.isfinite(x) and x>=0
def finite(x):
    if isinstance(x,str):
        try:x=float(x)
        except ValueError:return None
    return x if numeric(x) else None
def tidy(value,words=25):
    value=' '.join(''.join(c for c in str(value) if c.isprintable() or c.isspace()).split())
    return ' '.join(value.split()[:words])[:240]
class Page(html.parser.HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.hidden=0;self.title=False;self.t=[];self.description='';self.visible=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style','noscript'):self.hidden+=1
        if tag=='title':self.title=True
        if tag=='meta' and a.get('name','').lower()=='description':self.description=a.get('content','')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'):self.hidden=max(0,self.hidden-1)
        if tag=='title':self.title=False
    def handle_data(self,data):
        if not self.hidden:
            self.visible.append(data)
            if self.title:self.t.append(data)
def public_target(url,resolver=None):
    if not isinstance(url,str) or len(url)>2048 or any(ord(c)<33 for c in url):raise ValueError('invalid URL')
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):raise ValueError('public HTTPS only')
    host=p.hostname.encode('idna').decode('ascii')
    if len(host)>253 or host.endswith('.local') or host=='localhost':raise ValueError('invalid hostname')
    records=(resolver or socket.getaddrinfo)(host,443,type=socket.SOCK_STREAM)
    addresses={r[4][0] for r in records}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):raise ValueError('non-public DNS')
    # Pin the checked address: a second DNS lookup must not redirect into a private network.
    return host,sorted(addresses)[0],urllib.parse.urlunsplit(('', '', p.path or '/',p.query,''))
class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,ip):super().__init__(host,timeout=2.5,context=ssl.create_default_context());self.ip=ip
    def connect(self):
        raw=socket.create_connection((self.ip,443),timeout=self.timeout)
        try:self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except BaseException:raw.close();raise
def fetch(url,kind):
    host,ip,path=public_target(url);con=PinnedHTTPS(host,ip)
    try:
        con.request('GET',path,headers={'User-Agent':'Vivameda-Research/1.0','Accept':'application/json' if kind=='json' else 'text/html','Accept-Encoding':'identity'})
        response=con.getresponse()
        if response.status!=200:raise ValueError('HTTP status or redirect refused')
        mime=response.getheader('Content-Type','').split(';')[0].lower()
        if mime not in ({'application/json'} if kind=='json' else {'text/html','application/xhtml+xml'}):raise ValueError('unexpected content type')
        if response.getheader('Content-Encoding','identity').lower()!='identity':raise ValueError('compressed response refused')
        raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('response cap')
        return raw.decode('utf-8',errors='replace')
    finally:con.close()
@contextlib.contextmanager
def budget():
    def timeout(*unused):raise TimeoutError('research budget')
    old=signal.getsignal(signal.SIGALRM);timer=signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,MAX_SECONDS)
    try:yield
    finally:signal.setitimer(signal.ITIMER_REAL,*timer);signal.signal(signal.SIGALRM,old)
def history(database,mint,pair,now):
    con=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)
    con.row_factory=sqlite3.Row;started=time.monotonic()
    con.set_progress_handler(lambda:int(time.monotonic()-started>1),1000)
    try:
        con.execute('PRAGMA query_only=ON');con.execute('PRAGMA busy_timeout=200')
        rows=con.execute('SELECT ts,liq,vol_m5,buys_m5,sells_m5 FROM snapshots WHERE mint=? AND pair=? AND ts BETWEEN ? AND ? ORDER BY ts DESC LIMIT 240',(mint,pair,now-1800,now)).fetchall()
        # Five-minute windows overlap: retain only observations at least five minutes apart.
        chosen=[]
        for r in rows:
            r=dict(r)
            if all(numeric(r.get(k)) for k in ('ts','liq','vol_m5','buys_m5','sells_m5')) and (not chosen or chosen[-1]['ts']-r['ts']>=300):chosen.append(r)
        return list(reversed(chosen[:3]))
    finally:con.close()
def activity(observations):
    result={'status':'INSUFFICIENT_HISTORY','observations':observations}
    if len(observations)<3:return result
    first,last=observations[0],observations[-1]
    positive=sum(r['buys_m5']>r['sells_m5'] and r['vol_m5']>0 for r in observations)
    stable=first['liq']>0 and last['liq']>=first['liq']*.9
    result.update(status='ACTIVITY_SUPPORTED' if positive>=2 and stable else 'MIXED_OR_WEAK',buy_heavy_windows=positive,liquidity_change_pct=round((last['liq']/first['liq']-1)*100,1) if first['liq'] else None)
    return result
def empty(row,now):
    return {'policy':POLICY,'mint':row['mint'],'pair':row['pinned_pair'],'checked_at':now,'provider_requests':0,'identity':'UNVERIFIED','project':{'status':'UNAVAILABLE'},'demand':{'status':'INSUFFICIENT_HISTORY','observations':[]},'sources':[],'gaps':[],'tier':'THIN THESIS','why':'No independently supported project thesis yet; existing scanner evidence only.','organic_buyers':'UNVERIFIED','adoption_revenue':'UNVERIFIED','catalyst':'UNVERIFIED','exit_quote':'UNVERIFIED'}
def assess(row,database,now,fetcher=fetch,reader=history):
    result=empty(row,now)
    checks=json.loads(row['review'])['checks']
    developer=checks.get('developer_history',{})
    observed=developer.get('observed_at');fresh=numeric(observed) and 0<=now-observed<=300
    result['developer']={'status':developer.get('status','UNKNOWN') if fresh else 'UNKNOWN','reason':tidy(developer.get('reason','Evidence missing')).replace('_',' ') if fresh else 'Evidence missing or stale','observed_at':observed}
    try:
        with budget():
            try:result['demand']=activity(reader(database,row['mint'],row['pinned_pair'],now))
            except (OSError,sqlite3.Error):result['gaps'].append('History unavailable')
            url='https://api.dexscreener.com/latest/dex/pairs/solana/'+row['pinned_pair']
            result['provider_requests']+=1
            raw=fetcher(url,'json');result['sources'].append({'url':url,'fetched_at':int(time.time()),'sha256':hashlib.sha256(raw.encode()).hexdigest()})
            data=json.loads(raw);pairs=data.get('pairs')
            if not isinstance(pairs,list):raise ValueError('missing pair')
            matches=[p for p in pairs if isinstance(p,dict) and p.get('chainId')=='solana' and p.get('pairAddress')==row['pinned_pair'] and (p.get('baseToken') or {}).get('address')==row['mint']]
            if len(matches)!=1:result['identity']='MISMATCH';return result
            p=matches[0];result['identity']='MATCHED'
            result['current_market']={'mc':finite(p.get('marketCap')),'liquidity':finite((p.get('liquidity') or {}).get('usd')),'price':finite(p.get('priceUsd')),'buys_m5':finite(((p.get('txns') or {}).get('m5') or {}).get('buys')),'sells_m5':finite(((p.get('txns') or {}).get('m5') or {}).get('sells'))}
            websites=(p.get('info') or {}).get('websites') or []
            urls=[w.get('url') for w in websites[:4] if isinstance(w,dict) and isinstance(w.get('url'),str)]
            if urls:
                project_url=urls[0];result['provider_requests']+=1
                page_raw=fetcher(project_url,'html');parser=Page();parser.feed(page_raw)
                visible=' '.join(parser.visible);claim=' '.join(parser.t)+' '+parser.description
                automation=AUTOMATION.search(visible);fee_buyback=FEE_BUYBACK.search(visible+' '+claim)
                found=fee_buyback or automation
                if found:
                    source=visible+' '+claim if fee_buyback else visible
                    claim=source[max(0,found.start()-40):found.end()+160]
                result['project']={'status':'PROJECT_CLAIM_ONLY','claim':tidy(claim),'mint_on_page':row['mint'] in visible,'activity_tooling_claim':bool(automation),'fee_buyback_claim':bool(fee_buyback),'url':project_url}
                result['sources'].append({'url':project_url,'fetched_at':int(time.time()),'sha256':hashlib.sha256(page_raw.encode()).hexdigest()})
            else:result['gaps'].append('No website linked by market provider')
    except Exception as error:
        # Never log untrusted response bodies or exception messages (URLs may contain secrets).
        result['gaps'].append('Public evidence unavailable: '+type(error).__name__)
    if result['project'].get('fee_buyback_claim'):
        result['tier']='THIN THESIS — FEE-FUNDED BUYBACK CLAIM'
        result['why']='Linked site claims creator fees fund repeated token buys. Those buys recycle trading fees; independent user demand and sustainable fee revenue remain unverified.'
    elif result['project'].get('activity_tooling_claim'):
        result['tier']='THIN THESIS — ACTIVITY TOOLING CLAIM'
        result['why']='Linked site describes tools for generating trading activity. Volume cannot establish organic demand; independent users and developer evidence are missing.'
    elif result['identity']=='MATCHED' and result['demand']['status']=='ACTIVITY_SUPPORTED':
        result['tier']='ACTIVITY-SUPPORTED WATCH'
        result['why']='At least two of three separated five-minute windows have more buys than sells, with liquidity holding within 10%. This supports attention to activity, not a business or 100× thesis.'
    elif result['demand']['status']=='MIXED_OR_WEAK':
        result['why']='Recent separated windows show mixed buying pressure or falling liquidity; the scanner alert alone gives a weak case for attention.'
    market=result.get('current_market',{})
    if numeric(market.get('liquidity')) and market['liquidity']<row['liq']*.8:
        result['tier']='THIN THESIS — LIQUIDITY DETERIORATING'
        result['why']='Public liquidity is more than 20% below the alert snapshot; exit capacity is weakening. A stronger activity reading does not resolve this risk.'
    if numeric(market.get('price')) and market['price']>row['price']*2:
        result['gaps'].append('Public price already exceeds 2× the alert snapshot; entry may involve chasing')
    return result
def describe(result):
    project=result['project'];demand=result['demand'];lines=[]
    lines.append('Research: '+result['tier']+'. '+result['why'])
    lines.append('Research UTC: '+time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(result['checked_at'])))
    developer=result.get('developer',{'status':'UNKNOWN','reason':'Evidence missing'})
    lines.append('Developer screen: '+developer['status']+'; '+developer['reason']+'. Independent developer investigation unavailable.')
    if project.get('claim'):
        lines.append('Linked-site claim (not verified): '+project['claim'])
        lines.append('Website displays this mint: '+('YES — association only' if project.get('mint_on_page') else 'NO — association unverified'))
    else:lines.append('What it does: UNVERIFIED; readable project claims unavailable.')
    obs=demand.get('observations',[])
    if obs:
        lines.append('Demand proxy: '+demand['status']+'; '+str(len(obs))+' separated windows; latest '+str(int(obs[-1]['buys_m5']))+' buys / '+str(int(obs[-1]['sells_m5']))+' sells. Transactions are not unique buyers.')
    else:lines.append('Demand proxy: unavailable.')
    lines.append('Organic buyers, adoption/revenue, catalyst and executable exit: UNVERIFIED.')
    lines.append('Invalidate the watch: developer/control rejection, liquidity deterioration or buying pressure fading. Latest screening is checked again before delivery.')
    for s in result['sources']:
        url=s['url']
        if len(url)>300:url='https://'+urllib.parse.urlsplit(url).hostname
        lines.append('Evidence: '+url)
    if result['gaps']:lines.append('Gaps: '+'; '.join(result['gaps']))
    return '\n'.join(lines)
