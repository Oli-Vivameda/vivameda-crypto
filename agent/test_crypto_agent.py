import contextlib, io, json, pathlib, sqlite3, tempfile, time, unittest
from unittest.mock import patch
import crypto_agent as agent
import crypto_boundary as boundary

class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name); self.state = self.root/'crypto'; self.evidence = self.root/'evidence'
        self.evidence.mkdir(); self.now = time.time()
        self.cards = {'schema': 'crypto-daily-memory-v1', 'generated_at': self.now, 'live_execution': False,
                      'summary': {'tokens': 3}, 'cases': [{'mint': 'mintA', 'symbol': 'AAA'}],
                      'matched_examples': [], 'limitations': ['Exploratory only']}
        self.save('latest_memory.json', self.cards)
        self.save('paper_summary.json', {'schema': 'crypto-paper-endpoints-v1', 'generated_at': self.now,
                                       'live_execution': False, 'groups': {'WATCH': {'eligible': 0}}})

    def save(self, name, data):
        (self.evidence/name).write_text(json.dumps(data))

    def run_agent(self, question, session='crypto-test', **kwargs):
        return agent.run(question, session, self.state, self.evidence, **kwargs)

    def test_company_and_provider_routes_block_without_model(self):
        for query in ('Analyst: microsoft | workforce', 'Coresignal fetch company', 'Client knowledge: secret'):
            self.assertEqual(self.run_agent(query, model_call=lambda *a: self.fail('model invoked'))['action'], 'blocked')

    def test_execution_training_and_deployment_block(self):
        for query in ('Crypto explain: buy this coin', 'Crypto explain: train weights', 'Crypto explain: deploy patch'):
            self.assertEqual(self.run_agent(query)['action'], 'blocked')

    def test_model_is_never_tool_dispatcher(self):
        answer = self.run_agent('Crypto explain: what does coverage mean?', model_call=lambda *a: '{"tool":"coresignal","execute":true}')
        self.assertEqual(answer['action'], 'explain')
        self.assertFalse(answer['live_execution'])
        self.assertFalse((self.root/'company').exists())

    def test_blocked_company_prompt_excluded_from_model_history(self):
        self.run_agent('Analyst: private-company | workforce')
        def model(query, evidence, history):
            self.assertEqual(history, [])
            return 'Dated crypto observations only'
        self.run_agent('Crypto explain: summarize coverage', model_call=model)

    def test_own_history_only(self):
        self.run_agent('Crypto rules', 'crypto-one'); self.run_agent('Crypto status', 'crypto-two')
        own = self.run_agent('', 'crypto-one', history_only=True)
        self.assertEqual(len(own['turns']), 1); self.assertEqual(own['turns'][0]['question'], 'Crypto rules')
        self.assertEqual((self.state.stat().st_mode & 0o777), 0o700)
        self.assertEqual(((self.state/'conversations.sqlite3').stat().st_mode & 0o777), 0o600)

    def test_company_database_cannot_be_relabelled(self):
        self.state.mkdir(mode=0o700)
        with sqlite3.connect(self.state/'conversations.sqlite3') as db:
            db.execute('CREATE TABLE sessions(name TEXT)'); db.execute("INSERT INTO sessions VALUES ('private-company')")
        with self.assertRaisesRegex(ValueError, 'unlabelled'):
            self.run_agent('Crypto status')

    def test_wrong_domain_marker(self):
        self.state.mkdir(mode=0o700)
        with sqlite3.connect(self.state/'conversations.sqlite3') as db:
            db.execute('CREATE TABLE metadata(domain TEXT)'); db.execute("INSERT INTO metadata VALUES ('company')")
        with self.assertRaisesRegex(ValueError, 'another domain'):
            self.run_agent('Crypto status')

    def test_wrong_evidence_schema(self):
        self.save('latest_memory.json', dict(self.cards, schema='company-memory-v1'))
        self.assertEqual(agent.memory('', self.evidence)['status'], 'UNAVAILABLE')

    def test_stale_future_and_nan_evidence(self):
        for stamp in (self.now-37*3600, self.now+60, float('nan')):
            self.save('latest_memory.json', dict(self.cards, generated_at=stamp))
            self.assertEqual(agent.memory('', self.evidence)['status'], 'UNAVAILABLE')

    def test_missing_memory_does_not_call_model(self):
        (self.evidence/'latest_memory.json').unlink()
        response = self.run_agent('Crypto explain: summarize observations', model_call=lambda *a: self.fail('model invoked'))
        self.assertEqual(response['answer']['status'], 'UNAVAILABLE')

    def test_symlink_evidence_and_state_rejected(self):
        (self.evidence/'latest_memory.json').unlink(); (self.evidence/'latest_memory.json').symlink_to(self.root/'company.json')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            agent.memory('', self.evidence)
        self.state.symlink_to(self.evidence)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.run_agent('Crypto status')

    def test_arbitrary_read_refused(self):
        with self.assertRaises(ValueError):
            agent.read_evidence('../company.json', self.evidence)

    def test_bounded_selection_is_disclosed(self):
        self.save('latest_memory.json', dict(self.cards, cases=[{'mint': 'mint'+str(i)} for i in range(10)]))
        result = agent.memory('', self.evidence)
        self.assertEqual(result['selection']['available_cases'], 10)
        self.assertEqual(result['selection']['selected_cases'], 6)

    def test_context_limit_never_silently_truncates(self):
        with self.assertRaisesRegex(ValueError, 'context limit'):
            agent.ask_model('coverage', {'data': 'x'*19000})

    def test_incomplete_model_response_rejected(self):
        class Opener:
            def open(self, request, timeout):
                return contextlib.closing(io.BytesIO(b'{"done":true,"done_reason":"length","message":{"content":"partial"}}'))
        with self.assertRaisesRegex(ValueError, 'did not complete'):
            agent.ask_model('coverage', {}, opener=Opener())

    def test_crypto_pinning_and_mapped_session(self):
        self.assertEqual(boundary.crypto_session('crypto-lab', 'continue'), 'crypto-lab')
        self.assertEqual(boundary.crypto_session('crypto-lab', 'historical workforce'), 'crypto-lab')
        mapped = boundary.crypto_session('company-session', 'Crypto status')
        self.assertTrue(mapped.startswith('crypto-')); self.assertNotEqual(mapped, 'company-session')
        self.assertIsNone(boundary.crypto_session('company-session', 'Analyst: microsoft'))

    def test_dispatch_before_company_code(self):
        source = "import sys\ndef automatic_knowledge_context(q, session):\n    return 'shared crypto'\ndef main():\n    raise AssertionError('company code opened')\n"
        patched = boundary.patch(source); scope = {'sys': type('Sys', (), {'argv': ['agent', '--session', 'crypto-lab', 'Crypto status']})}
        exec(patched, scope)
        with patch.object(boundary, 'maybe_run', return_value=True) as route:
            scope['main'](); route.assert_called_once()
        self.assertNotIn('shared crypto', scope['automatic_knowledge_context']('wallet', {}))

    def test_company_route_behavior_preserved(self):
        source = "import sys\ndef automatic_knowledge_context(q, session):\n    return 'old'\ndef main():\n    return 'company result'\n"
        scope = {'sys': type('Sys', (), {'argv': ['agent', '--session', 'company', 'Analyst: microsoft']})}
        exec(boundary.patch(source), scope)
        with patch.object(boundary, 'maybe_run', return_value=False):
            self.assertEqual(scope['main'](), 'company result')

    def test_unknown_source_shape_and_duplicate_patch_stop(self):
        with self.assertRaises(ValueError): boundary.patch('def main(): pass')
        source = "def automatic_knowledge_context(q,s): return ''\ndef main(): pass\n"
        with self.assertRaisesRegex(ValueError, 'already installed'):
            boundary.patch(boundary.patch(source))

if __name__ == '__main__': unittest.main()
