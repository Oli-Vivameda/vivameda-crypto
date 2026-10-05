import io,json,unittest
import crypto_agent as agent,model_proxy as proxy
class InterpretationTests(unittest.TestCase):
    def body(self):
        return dict(model=agent.MODEL,messages=[dict(role='system',content='Crypto'),dict(role='user',content='Evidence')],think=False,stream=False,keep_alive='2m',options=dict(temperature=0,num_ctx=8192,num_predict=700,num_thread=4))
    def test_model_agreement(self):
        self.assertEqual(agent.MODEL,'qwen3:4b-instruct-2507-q4_K_M');self.assertEqual(agent.MODEL,proxy.MODEL);proxy.validate(self.body())
    def test_company_model_and_administration_rejected(self):
        for change in ({'model':'qwen3:4b'},{'model':'qwen3:8b'},{'think':True},{'tools':[]}):
            b=self.body();b.update(change)
            with self.assertRaises(ValueError):proxy.validate(b)
    def test_thinking_only_rejected_before_generation(self):
        class Opener:
            def open(self,req,timeout):return io.BytesIO(json.dumps({'thinking':{'values':[True]}}).encode())
        with self.assertRaisesRegex(ValueError,'MODEL_MODE_UNSUPPORTED'):proxy.infer(self.body(),Opener())
    def test_instruct_payload_preserved(self):
        calls=[]
        class Opener:
            def open(self,req,timeout):
                calls.append(req)
                return io.BytesIO(json.dumps({'capabilities':['completion']} if len(calls)==1 else {'done':True,'message':{'content':'Evidence missing'}}).encode())
        b=self.body();out=proxy.infer(b,Opener());self.assertEqual(json.loads(calls[1].data),b);self.assertTrue(out['done'])
    def test_partial_answer_rejected(self):
        class Opener:
            def open(self,req,timeout):return io.BytesIO(json.dumps({'done':True,'done_reason':'length','message':{'content':'Partial'}}).encode())
        with self.assertRaisesRegex(ValueError,'did not complete'):agent.ask_model('gaps',{},opener=Opener())
class StartupTests(unittest.TestCase):
    def test_proxy_is_ready_before_worker_starts(self):
        import install_interpretation as i
        from unittest.mock import patch
        calls=[]
        with patch.object(i,'command',side_effect=lambda argv,*args:calls.append(argv[-1])),patch.object(i,'wait_proxy',side_effect=lambda:calls.append('proxy-ready')),patch.object(i.pathlib.Path,'exists',return_value=True):i.start_services()
        self.assertEqual(calls,[i.UNITS[0],'proxy-ready',i.UNITS[1]])
    def test_proxy_retry_handles_slow_start(self):
        import install_interpretation as i
        from unittest.mock import patch
        with patch.object(i,'command',side_effect=[RuntimeError('Not ready'),None]) as c,patch.object(i.time,'sleep'):i.wait_proxy()
        self.assertEqual(c.call_count,2)
        self.assertEqual(c.call_args.args[0][2],'vivameda-crypto')
        compile(c.call_args.args[0][-1],'readiness-probe','exec')
    def test_unavailable_proxy_fails_before_worker_start(self):
        import install_interpretation as i
        from unittest.mock import patch
        with patch.object(i,'command',side_effect=RuntimeError('Missing')),patch.object(i.time,'monotonic',side_effect=[0,31]):
            with self.assertRaisesRegex(ValueError,'did not become ready'):i.wait_proxy()
    def test_child_failure_preserves_stderr(self):
        import install_interpretation as i
        from unittest.mock import patch
        e=i.subprocess.CalledProcessError(1,['check'],stderr='AssertionError: CRYPTO_REQUEST_FAILED')
        with patch.object(i.subprocess,'run',side_effect=e):
            with self.assertRaisesRegex(RuntimeError,'AssertionError: CRYPTO_REQUEST_FAILED'):i.command(['check'])
if __name__=='__main__':unittest.main()
