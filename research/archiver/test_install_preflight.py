import unittest
from unittest.mock import patch
import check_install_preflight as d
class DiagnosticTests(unittest.TestCase):
    def test_exception_text_is_withheld(self):
        rows=[]
        with self.assertRaises(d.Gate):d.check('stage',lambda:(_ for _ in ()).throw(ValueError('private identity')),rows)
        self.assertNotIn('private identity',str(rows));self.assertEqual(rows[0]['detail']['error_category'],'ValueError')
    def test_failed_gate_returns_sanitized_details(self):
        rows=[]
        with self.assertRaises(d.Gate) as caught:d.check('access',lambda:d.require(False,{'readable':False}),rows)
        self.assertEqual(caught.exception.details,{'blocker':'access'});self.assertEqual(rows[0]['detail'],{'readable':False})
    def test_success_gate(self):
        rows=[];self.assertEqual(d.check('stage',lambda:{'passed':True},rows),{'passed':True});self.assertTrue(rows[0]['passed'])
    def test_nonowner_stops_before_production_reads(self):
        with patch.object(d.os,'geteuid',return_value=1000),patch.object(d,'command',return_value=type('Result',(),{'stdout':'inactive'})()):
            out=d.diagnose()
        self.assertEqual(out['blocker'],'owner_python');self.assertFalse(out['production_database_opened']);self.assertFalse(out['production_changed'])
if __name__=='__main__':unittest.main()
