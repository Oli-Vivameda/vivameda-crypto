"""Offline checks for the public export's aggregate-only boundary."""
import json
import pathlib
import tempfile
import unittest
from export_monitor_sources import program_blockers, wallet_diagnostics, read_report

class ExportTests(unittest.TestCase):
    def test_program_counts_deduplicate_each_owner_without_exporting_identity(self):
        program='11111111111111111111111111111111'
        result=program_blockers({'wallets':[
            {'wallet':'PRIVATE_OWNER_A','unknown_programs':[program,program]},
            {'wallet':'PRIVATE_OWNER_B','unknown_programs':[program,'unresolved_program']}]})
        self.assertEqual(result['programs'][0],{'program_id':program,'owner_incidences':2})
        self.assertNotIn('PRIVATE_OWNER',json.dumps(result))
        self.assertTrue(result['counts_overlap'])
    def test_invalid_values_are_counted_without_echo(self):
        result=program_blockers({'wallets':[None,{'unknown_programs':'SECRET'},{'unknown_programs':['SECRET',{},False]}]})
        self.assertEqual(result['invalid_entries'],5)
        self.assertNotIn('SECRET',json.dumps(result))
    def test_export_excludes_raw_evidence_and_keeps_numeric_throughput(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);mint='1'*32;program='2'*32
            (root/'capacity_observations.json').write_text(json.dumps([{'observed_at':123,'runs':[{'mint':mint,'index_metrics':{'transaction_attempts':3,'shared_transaction_bodies':42,'indexed_addresses':True,'scope':'PRIVATE_SCOPE'}}]}]))
            (root/(mint+'.json')).write_text(json.dumps({'generated_at':123,'screening_packet':{'history':{'wallets':[{'wallet':'PRIVATE_OWNER','unknown_programs':[program]}],'events':['PRIVATE_TX'],'coverage_summary':{'owners_observed':1}}}}))
            result=wallet_diagnostics(root);encoded=json.dumps(result)
            self.assertNotIn('PRIVATE_',encoded)
            self.assertNotIn(mint,encoded)
            self.assertEqual(result['capacity_observations'][0]['runs'][0]['index_metrics'],{'transaction_attempts':3,'shared_transaction_bodies':42})
            self.assertEqual(result['recent_report_coverage'][0]['program_blockers']['programs'][0]['program_id'],program)
    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);(root/'real').write_text('{}');(root/'link').symlink_to(root/'real')
            with self.assertRaises(ValueError):read_report(root/'link')

if __name__=='__main__':unittest.main()
