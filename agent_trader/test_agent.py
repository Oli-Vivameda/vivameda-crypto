import json, tempfile, unittest
from pathlib import Path
from agent import init,draft,feedback,list_open

class AgentTests(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory();self.db=str(Path(self.tmp.name)/'agent.sqlite3');init(self.db)
 def tearDown(self): self.tmp.cleanup()
 def ev(self,verified=True): return {'evidence_id':'ev-1','verified':verified,'status':'PASS'}
 def test_unknown_evidence_blocked(self):
  with self.assertRaises(ValueError): draft(self.db,'solana_meme','mint','BUY',1,10,self.ev(False),'x','y')
 def test_draft_feedback_and_playbook(self):
  r=draft(self.db,'solana_meme','mint','BUY',1,10,self.ev(),'x','exit');self.assertEqual(r['state'],'DRAFT');self.assertFalse(r['live_execution'])
  f=feedback(self.db,r['proposal_id'],'EDIT','reduce size',{'quantity':'0.5'});self.assertEqual(f['state'],'DRAFT');self.assertEqual(f['playbook_version'],1)
  self.assertEqual(len(list_open(self.db)),1)
 def test_reject(self):
  r=draft(self.db,'equity','ABC','BUY',2,10,self.ev(),'x','exit');self.assertEqual(feedback(self.db,r['proposal_id'],'REJECT','insufficient evidence')['state'],'REJECTED')
if __name__=='__main__': unittest.main()
