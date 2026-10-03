import unittest
from context import automatic_knowledge_context

class ContextTests(unittest.TestCase):
    def test_forecast_discloses_failed_baseline(self):
        value=automatic_knowledge_context('Predict this Solana token',{})
        self.assertIn('0.11047',value)
        self.assertIn('no production promotion',value)
        self.assertIn('peak_not_profit',value)

    def test_unrelated_query_drops_crypto_history(self):
        value=automatic_knowledge_context('Research Microsoft',{'knowledge_domain':'crypto'})
        self.assertNotIn('peak_not_profit',value)

    def test_followup_retains_domain(self):
        session={}
        automatic_knowledge_context('Crypto forecast',session)
        self.assertIn('peak_not_profit',automatic_knowledge_context('What about its wallet?',session))

    def test_hypotheses_excluded(self):
        value=automatic_knowledge_context('Crypto rules',{})
        self.assertNotIn('compression_gate',value)
        self.assertNotIn('exit_paths',value)

if __name__=='__main__': unittest.main()
