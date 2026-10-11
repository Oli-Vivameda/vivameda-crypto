import json, pathlib, signal, sqlite3, tempfile, time, unittest
from unittest.mock import patch
import research as r
import notifier as n
from test_notifier import good, config, NOW, MINT, PAIR

def observations(buy=12,sell=8,liquidity=30000):
    return [{'ts':NOW-600+i*300,'liq':liquidity,'vol_m5':500,'buys_m5':buy,'sells_m5':sell} for i in range(3)]
def payload(mint=MINT,pair=PAIR,website=None):
    return json.dumps({'pairs':[{'chainId':'solana','pairAddress':pair,'baseToken':{'address':mint},'marketCap':200000,'priceUsd':'.0002','liquidity':{'usd':30000},'info':{'websites':[{'url':website}] if website else []}}]})
class ResearchTests(unittest.TestCase):
    def assess(self,page=None,obs=None,pair=None):
        def fetch(url,kind):return payload(website='https://example.org') if kind=='json' else page
        return r.assess(good(),pathlib.Path('/unused'),NOW,fetcher=fetch if pair is None else lambda *a:pair,reader=lambda *a:observations() if obs is None else obs)
    def test_activity_is_not_organic(self):
        result=self.assess(pair=payload())
        self.assertEqual(result['tier'],'ACTIVITY-SUPPORTED WATCH')
        self.assertEqual(result['organic_buyers'],'UNVERIFIED')
        self.assertEqual(result['adoption_revenue'],'UNVERIFIED')
        self.assertIn('not a business',result['why'])
    def test_project_activity_tooling_weakens_case(self):
        result=self.assess('<title>Launchpad</title><p>Boost volume with our volume bot</p>'+MINT)
        self.assertIn('ACTIVITY TOOLING',result['tier'])
        self.assertTrue(result['project']['mint_on_page'])
        self.assertEqual(result['project']['status'],'PROJECT_CLAIM_ONLY')
        self.assertIn('Volume cannot establish organic demand',result['why'])
    def test_creator_fee_buybacks_are_separate_from_volume_bots(self):
        result=self.assess('<title>Volume Launcher</title><p>Launch on Pump.fun and your creator fees keep buying your token every 2 minutes.</p>'+MINT)
        self.assertEqual(result['tier'],'THIN THESIS — FEE-FUNDED BUYBACK CLAIM')
        self.assertTrue(result['project']['fee_buyback_claim'])
        self.assertFalse(result['project']['activity_tooling_claim'])
        self.assertIn('sustainable fee revenue',result['why'])
    def test_message_fits_telegram_and_discloses_fee_risk(self):
        result=self.assess('<title>Volume Launcher</title><p>Your creator fees keep buying tokens.</p>'+MINT)
        text=n.message(good(),NOW,result)
        self.assertLessEqual(len(text),4096)
        self.assertIn('FEE-FUNDED BUYBACK',text)
    def test_business_metadata_is_not_verified_adoption(self):
        result=self.assess('<title>Wonderful platform</title><meta name="description" content="A launchpad for everyone">')
        self.assertFalse(result['project']['mint_on_page'])
        self.assertIn('association unverified',r.describe(result))
        self.assertEqual(result['adoption_revenue'],'UNVERIFIED')
    def test_script_is_not_project_claim(self):
        result=self.assess('<title>Plain</title><script>volume bot '+MINT+'</script>')
        self.assertFalse(result['project']['activity_tooling_claim'])
        self.assertFalse(result['project']['mint_on_page'])
    def test_identity_mismatch_blocks(self):
        result=self.assess(pair=payload(mint='C'*32))
        self.assertEqual(result['identity'],'MISMATCH')
    def test_no_history_stays_thin(self):
        self.assertEqual(self.assess(pair=payload(),obs=[])['tier'],'THIN THESIS')
    def test_liquidity_drop_weakens_case(self):
        obs=observations();obs[-1]['liq']=20000
        self.assertEqual(self.assess(pair=payload(),obs=obs)['demand']['status'],'MIXED_OR_WEAK')
    def test_sell_heavy_weakens_case(self):
        self.assertEqual(self.assess(pair=payload(),obs=observations(4,12))['demand']['status'],'MIXED_OR_WEAK')
    def test_new_liquidity_loss_overrides_activity(self):
        data=json.loads(payload());data['pairs'][0]['liquidity']['usd']=10000
        result=self.assess(pair=json.dumps(data))
        self.assertEqual(result['tier'],'THIN THESIS — LIQUIDITY DETERIORATING')
    def test_price_chasing_disclosed(self):
        data=json.loads(payload());data['pairs'][0]['priceUsd']='.001'
        result=self.assess(pair=json.dumps(data))
        self.assertIn('chasing',r.describe(result))
    def test_stale_developer_pass_remains_unknown(self):
        row=good();review=json.loads(row['review']);review['checks']['developer_history']={'status':'PASS','reason':'known','observed_at':NOW-301};row['review']=json.dumps(review)
        result=r.assess(row,pathlib.Path('/unused'),NOW,fetcher=lambda *a:payload(),reader=lambda *a:[])
        self.assertEqual(result['developer']['status'],'UNKNOWN')
    def test_public_failure_is_explicit(self):
        def fail(*a):raise TimeoutError('SECRET')
        result=r.assess(good(),pathlib.Path('/unused'),NOW,fetcher=fail,reader=lambda *a:[])
        self.assertEqual(result['tier'],'THIN THESIS');self.assertNotIn('SECRET',json.dumps(result))
        self.assertIn('TimeoutError',r.describe(result))
    def test_budget_restores_handler(self):
        old=signal.getsignal(signal.SIGALRM)
        with patch.object(r,'MAX_SECONDS',.01):
            with self.assertRaises(TimeoutError):
                with r.budget():time.sleep(.05)
        self.assertEqual(signal.getsignal(signal.SIGALRM),old)
    def test_private_dns_and_mixed_dns_rejected(self):
        def resolver(*a,**kw):return [(None,None,None,None,(ip,443)) for ip in ('8.8.8.8','127.0.0.1')]
        with self.assertRaises(ValueError):r.public_target('https://example.org',resolver)
    def test_public_ip_pinned(self):
        host,ip,path=r.public_target('https://example.org/a',lambda *a,**kw:[(None,None,None,None,('8.8.8.8',443))])
        self.assertEqual((host,ip,path),('example.org','8.8.8.8','/a'))
    def test_url_restrictions(self):
        for url in ('http://example.org','https://user:secret@example.org','https://example.org:444','https://localhost','https://example.org/\nsecret'):
            with self.assertRaises(ValueError):r.public_target(url)
    def test_response_limits_and_redirects(self):
        for status,mime,body in ((302,'text/html',b'a'),(200,'application/octet-stream',b'a'),(200,'text/html',b'a'*(r.MAX_BYTES+1))):
            class Response:
                def getheader(self,key,default=None):return mime if key=='Content-Type' else default
                def read(self,limit):return body
            response=Response();response.status=status
            with patch.object(r,'public_target',return_value=('example.org','8.8.8.8','/')),patch.object(r,'PinnedHTTPS') as conn:
                conn.return_value.getresponse.return_value=response
                with self.assertRaises(ValueError):r.fetch('https://example.org','html')
                conn.return_value.close.assert_called_once()
    def test_history_identity_future_and_overlap(self):
        with tempfile.TemporaryDirectory() as d:
            db=pathlib.Path(d)/'db';c=sqlite3.connect(db)
            c.execute('CREATE TABLE snapshots(mint TEXT,pair TEXT,ts INTEGER,liq REAL,vol_m5 REAL,buys_m5 INTEGER,sells_m5 INTEGER)')
            for ts in (NOW-600,NOW-590,NOW-300,NOW-290,NOW,NOW+1):c.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)',(MINT,PAIR,ts,30000,500,12,8))
            c.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)',(MINT,'C'*32,NOW,1,500,100,1));c.commit()
            obs=r.history(db,MINT,PAIR,NOW)
            self.assertEqual([x['ts'] for x in obs],[NOW-600,NOW-300,NOW])
            self.assertEqual(c.execute('SELECT count(*) FROM snapshots').fetchone()[0],7);c.close()
    def test_claim_quote_bounded(self):
        result=self.assess('<title>'+'word '*100+'</title>')
        self.assertLessEqual(len(result['project']['claim'].split()),25)
class DeliveryResearchTests(unittest.TestCase):
    def state(self,d):
        p=pathlib.Path(d);n.atomic(p/'config.json',config());n.atomic(p/'delivery.json',{});return p
    def test_latest_rejection_during_research_prevents_send(self):
        row=good();bad=good();bad['verdict']='REJECT'
        with tempfile.TemporaryDirectory() as d,patch.object(n,'rows',side_effect=[[row],[bad]]):
            sent=[];state=self.state(d)
            report=n.run(state,sender=sent.append,now=NOW,assessor=lambda *a:r.empty(row,NOW))
            self.assertEqual(report['state'],'screening_changed');self.assertEqual(sent,[])
            self.assertTrue((state/'research'/(MINT+'.json')).exists())
    def test_mismatch_no_send_and_rate_limited(self):
        row=good();result=r.empty(row,NOW);result['identity']='MISMATCH'
        with tempfile.TemporaryDirectory() as d,patch.object(n,'rows',return_value=[row]):
            sent=[];state=self.state(d)
            report=n.run(state,sender=sent.append,now=NOW,assessor=lambda *a:result)
            self.assertEqual(report['state'],'research_identity_mismatch');self.assertEqual(sent,[])
            self.assertEqual(n.run(state,now=NOW+1)['state'],'cooldown')
    def test_thin_research_can_be_delivered_with_audit(self):
        row=good()
        with tempfile.TemporaryDirectory() as d,patch.object(n,'rows',return_value=[row]):
            sent=[];state=self.state(d)
            n.run(state,sender=sent.append,now=NOW,assessor=lambda *a:r.empty(row,NOW))
            self.assertIn('THIN THESIS',sent[0]);self.assertTrue(sent[0].startswith('🔥'))
            saved=json.loads((state/'research'/(MINT+'.json')).read_text())
            self.assertEqual(saved['mint'],MINT);self.assertEqual(saved['exit_quote'],'UNVERIFIED')
    def test_stop_during_research(self):
        row=good()
        with tempfile.TemporaryDirectory() as d,patch.object(n,'rows',return_value=[row]):
            state=self.state(d);sent=[]
            def assess(*a):(state/'STOP').touch();return r.empty(row,NOW)
            self.assertEqual(n.run(state,sender=sent.append,now=NOW,assessor=assess)['state'],'stopped')
            self.assertEqual(sent,[])
if __name__=='__main__':unittest.main()
