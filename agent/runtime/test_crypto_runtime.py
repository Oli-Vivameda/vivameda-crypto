import ast,io,json,os,pathlib,socket,socketserver,sqlite3,sys,tempfile,threading,unittest
from unittest.mock import patch
import crypto_runtime as runtime
import model_proxy,runtime_gateway,integration_patch

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.q=runtime.Queue(self.tmp.name)
    def request(self,**kwargs):
        return dict(op='submit',owner=2,session='crypto-test',question='Crypto status',request_id='crypto-runtime-test-0001',**kwargs)
    def test_company_sessions_and_other_owners_rejected(self):
        for key,value in [('session','company'),('owner',3),('owner',True),('question',''),('request_id','short')]:
            d=self.request();d[key]=value
            with self.assertRaises(ValueError):self.q.dispatch(d)
    def test_idempotence_and_conflict(self):
        d=self.request();a=self.q.dispatch(d);self.assertEqual(a['id'],self.q.dispatch(d)['id'])
        d['question']='Crypto rules'
        with self.assertRaises(ValueError):self.q.dispatch(d)
    def test_status_has_no_model_or_company_tool(self):
        a=self.q.dispatch(self.request());self.assertTrue(self.q.step());r=self.q.dispatch(dict(op='get',owner=2,id=a['id']));out=json.loads(r['answer']);self.assertFalse(out['answer']['company_tools']);self.assertEqual(out['domain'],'crypto')
    def test_pinned_company_query_blocked(self):
        d=self.request();d['question']='Analyst: Microsoft | workforce';a=self.q.dispatch(d);self.q.step();r=self.q.dispatch(dict(op='get',owner=2,id=a['id']));self.assertEqual(json.loads(r['answer'])['action'],'blocked')
    def test_queue_limits_and_cancellation(self):
        for i in range(30):
            d=self.request();d['request_id']='crypto-limit-test-'+str(i);self.q.dispatch(d)
        d=self.request()
        with self.assertRaises(ValueError):self.q.dispatch(d)
        a=self.q.dispatch(dict(op='jobs',owner=2))[0];self.assertTrue(self.q.dispatch(dict(op='cancel',owner=2,id=a['id']))['ok'])
        self.assertFalse(self.q.dispatch(dict(op='cancel',owner=2,id=a['id']))['ok'])
    def test_restart_does_not_replay_running_job(self):
        a=self.q.dispatch(self.request())
        with self.q.connect() as c:c.execute("UPDATE jobs SET status='running' WHERE id=?",(a['id'],))
        q=runtime.Queue(self.tmp.name);r=q.dispatch(dict(op='get',owner=2,id=a['id']));self.assertEqual(r['status'],'interrupted');self.assertFalse(q.step())
    def test_slow_inference_does_not_block_queue_reads(self):
        entered=threading.Event();release=threading.Event()
        def slow(row):entered.set();release.wait(3);return {'domain':'crypto'}
        self.q.runner=slow;self.q.dispatch(self.request());t=threading.Thread(target=self.q.step);t.start();self.addCleanup(lambda:release.set());self.assertTrue(entered.wait(1))
        self.assertEqual(self.q.dispatch(dict(op='jobs',owner=2))[0]['status'],'running');release.set();t.join(2);self.assertFalse(t.is_alive())
    def test_unsupported_model_has_explicit_error_and_no_partial_answer(self):
        def fail(row):raise ValueError('MODEL_MODE_UNSUPPORTED')
        self.q.runner=fail;a=self.q.dispatch(self.request());self.q.step();r=self.q.dispatch(dict(op='get',owner=2,id=a['id']));self.assertEqual(r['error_code'],'MODEL_MODE_UNSUPPORTED');self.assertIsNone(r['answer'])
    def test_unknown_ops_cannot_execute(self):
        with self.assertRaises(ValueError):self.q.dispatch(dict(op='execute',owner=2,argv=['bash']))
    def test_storage_private(self):self.assertEqual(self.q.db.stat().st_mode&0o777,0o600)

class GatewayTests(unittest.TestCase):
    def test_routes_explicit_and_pinned_only(self):
        self.assertIsNone(runtime_gateway.selected('company','status'))
        self.assertEqual(runtime_gateway.selected('crypto-a','Analyst: workforce'),'crypto-a')
        self.assertTrue(runtime_gateway.selected('company','Crypto status').startswith('crypto-'))
    def test_no_local_fallback_when_runtime_unavailable(self):
        with patch('runtime_gateway.call',side_effect=OSError('offline')):
            with self.assertRaises(OSError):runtime_gateway.enqueue(2,dict(session='crypto-a',question='status',request_id='test-request-12345'))
            self.assertEqual(runtime_gateway.merged(2,[dict(created=1)]),[dict(created=1)])
    def test_explicit_crypto_cannot_bypass_session_validation(self):
        with self.assertRaises(ValueError):runtime_gateway.enqueue(2,dict(session='../company',question='Crypto status',request_id='test-request-12345'))

class ModelTests(unittest.TestCase):
    def body(self):
        return dict(model='qwen3:4b',messages=[dict(role='system',content='Crypto'),dict(role='user',content='Evidence')],think=False,stream=False,keep_alive='2m',options=dict(temperature=0,num_ctx=8192,num_predict=700,num_thread=4))
    def test_model_administration_and_arbitrary_settings_rejected(self):
        for key,value in [('model','other'),('tools',[]),('options',{'num_predict':100000}),('messages',[{'role':'tool','content':'bad'}])]:
            d=self.body();d[key]=value
            with self.assertRaises(ValueError):model_proxy.validate(d)
    def test_thinking_only_model_never_generates(self):
        calls=[]
        class Opener:
            def open(self,req,timeout):calls.append(req.full_url);return io.BytesIO(json.dumps({'thinking':{'values':[True]}}).encode())
        with self.assertRaisesRegex(ValueError,'MODEL_MODE_UNSUPPORTED'):model_proxy.infer(self.body(),Opener())
        self.assertEqual(calls,['http://127.0.0.1:11434/api/show'])
    def test_full_messages_preserved_for_compatible_model(self):
        calls=[]
        class Opener:
            def open(self,req,timeout):
                calls.append(req);return io.BytesIO(json.dumps({'thinking':{'values':[True,False]}} if len(calls)==1 else {'done':True,'message':{'content':'ok'}}).encode())
        b=self.body();model_proxy.infer(b,Opener());self.assertEqual(json.loads(calls[1].data),b)

class PatchTests(unittest.TestCase):
    def test_unknown_sources_and_duplicate_install_rejected(self):
        for fn in [integration_patch.patch_main,integration_patch.patch_workspace,integration_patch.patch_helper]:
            with self.assertRaises(ValueError):fn('def main(): pass\n')
        s='def main():\n    from crypto_boundary import maybe_run\n';p=integration_patch.patch_main(s);ast.parse(p)
        with self.assertRaises(ValueError):integration_patch.patch_main(p)

class TransportTests(unittest.TestCase):
    def test_peer_credentials_and_worker_remain_separate(self):
        with tempfile.TemporaryDirectory() as root:
            path=str(pathlib.Path(root)/'agent.sock');q=runtime.Queue(pathlib.Path(root)/'state')
            with socketserver.ThreadingUnixStreamServer(path,runtime.Handler) as server:
                server.queue=q;server.authorized_uid=os.getuid();server.daemon_threads=True
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                with patch('runtime_gateway.SOCKET',path):
                    row=runtime_gateway.enqueue(2,dict(session='crypto-transport',question='status',request_id='crypto-transport-test-001'))
                    self.assertEqual(row['status'],'queued');q.step();self.assertEqual(runtime_gateway.jobs(2)[0]['status'],'succeeded')
                    server.authorized_uid=os.getuid()+1
                    with self.assertRaises((OSError,ValueError)):runtime_gateway.call('health',owner=2)
                server.shutdown();thread.join(2)

if __name__=='__main__':unittest.main()
