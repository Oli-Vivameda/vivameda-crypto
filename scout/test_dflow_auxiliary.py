import copy
import unittest
from dflow_auxiliary import decode_layout, WRAP, UNWRAP, WSOL, SPL, ATA, SYSTEM, PROGRAM
from protocol_screening import b58encode


def fixture(wrap=True):
    keys = [b58encode(bytes([7])*32), b58encode(bytes([8])*32)] + ([WSOL, SPL, ATA, SYSTEM] if wrap else [SPL])
    return {'version': 0, 'meta': {'err': None}, 'transaction': {'message': {
        'accountKeys': [{'pubkey': k, 'signer': False} for k in keys],
        'instructions': [{'programId': PROGRAM, 'accounts': keys,
                          'data': b58encode(WRAP + (100).to_bytes(8, 'little') if wrap else UNWRAP)}]}}}

class AuxiliaryTests(unittest.TestCase):
    def test_both_layouts_without_semantic_promotion(self):
        for wrap in (True, False):
            tx = fixture(wrap); before = copy.deepcopy(tx); result = decode_layout(tx, 0)
            self.assertEqual(result['status'], 'LAYOUT_DECODED')
            self.assertFalse(result['history_coverage_complete'])
            self.assertFalse(result['account_roles_verified'])
            self.assertEqual(result['execution_semantics'], 'UNKNOWN')
            self.assertEqual(tx, before)
    def test_data_length(self):
        for data in (WRAP, WRAP + bytes(9), UNWRAP + bytes(1)):
            tx = fixture(); tx['transaction']['message']['instructions'][0]['data'] = b58encode(data)
            self.assertEqual(decode_layout(tx, 0)['status'], 'UNKNOWN')
    def test_wrong_fixed_account(self):
        tx = fixture(); tx['transaction']['message']['instructions'][0]['accounts'][2] = SYSTEM
        self.assertEqual(decode_layout(tx, 0)['status'], 'UNKNOWN')
    def test_missing_message_account(self):
        tx = fixture(); tx['transaction']['message']['accountKeys'].pop()
        self.assertEqual(decode_layout(tx, 0)['status'], 'UNKNOWN')
    def test_failed_transaction(self):
        tx = fixture(); tx['meta']['err'] = 'failed'
        self.assertEqual(decode_layout(tx, 0)['status'], 'UNKNOWN')
    def test_invalid_version_and_index(self):
        for index in (True, -1, 99): self.assertEqual(decode_layout(fixture(), index)['status'], 'UNKNOWN')
        tx = fixture(); tx['version'] = True
        self.assertEqual(decode_layout(tx, 0)['status'], 'UNKNOWN')

if __name__ == '__main__': unittest.main()
