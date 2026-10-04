import copy
import hashlib
import struct
import unittest
from dflow_decoder import decode_route, PROGRAM, Reader, DecodeError
from protocol_screening import b58encode, b58decode, SPL

ATA='ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL'
SYSTEM='11111111111111111111111111111111'
USER=b58encode(bytes([7])*32)

def fixture(name='swap'):
    disc=hashlib.sha256(('global:'+name).encode()).digest()[:8]
    # One PumpFunAmmSell action: amount u64, orchestrator flags u8.
    data=disc+struct.pack('<IBQBQHH',1,13,100,0,90,100,0)
    if name.startswith('swap2'):data+=b'\0'
    accounts=[SPL,ATA,SYSTEM,USER]
    if name.endswith('_native'):accounts += [b58encode(bytes([8])*32)]
    elif name.endswith('_destination'):accounts += [b58encode(bytes([8])*32),USER,b58encode(bytes([9])*32)]
    accounts += [b58encode(bytes([10])*32),PROGRAM]
    return {'version':0,'meta':{'err':None},'transaction':{'message':{'accountKeys':[{'pubkey':USER,'signer':True}],
            'instructions':[{'programId':PROGRAM,'accounts':accounts,'data':b58encode(data)}]}}}

class DecoderTests(unittest.TestCase):
    def test_six_swap_layouts(self):
        for name in ['swap','swap2','swap_with_destination','swap_with_destination_native','swap2_with_destination','swap2_with_destination_native']:
            with self.subTest(name=name):
                row=decode_route(fixture(name),0)
                self.assertEqual(row['status'],'LAYOUT_DECODED');self.assertEqual(row['actions'],['PumpFunAmmSell'])
                self.assertFalse(row['history_coverage_complete']);self.assertEqual(row['execution_semantics'],'UNKNOWN')
    def test_truncation_and_trailing_bytes(self):
        tx=fixture();raw=b58decode(tx['transaction']['message']['instructions'][0]['data'])
        for bad in [raw[:i] for i in range(len(raw))]+[raw+b'\0']:
            tx['transaction']['message']['instructions'][0]['data']=b58encode(bad)
            self.assertEqual(decode_route(tx,0)['status'],'UNKNOWN')
    def test_wrong_program_and_account(self):
        tx=fixture();tx['transaction']['message']['instructions'][0]['programId']=SYSTEM
        self.assertEqual(decode_route(tx,0)['reason'],'different_program')
        tx=fixture();tx['transaction']['message']['instructions'][0]['accounts'][0]=SYSTEM
        self.assertEqual(decode_route(tx,0)['reason'],'fixed_account_mismatch')
    def test_missing_signer(self):
        tx=fixture();tx['transaction']['message']['accountKeys'][0]['signer']=False
        self.assertEqual(decode_route(tx,0)['reason'],'missing_signer')
    def test_failed_and_missing_meta(self):
        for meta in [None,{}, {'err':{'InstructionError':[0,'failure']}}]:
            tx=fixture();tx['meta']=meta;self.assertEqual(decode_route(tx,0)['status'],'UNKNOWN')
    def test_unknown_discriminator_and_variant(self):
        for pos in [0,12]:
            tx=fixture();ins=tx['transaction']['message']['instructions'][0];data=bytearray(b58decode(ins['data']));data[pos]=255;ins['data']=b58encode(data)
            self.assertEqual(decode_route(tx,0)['status'],'UNKNOWN')
    def test_bounds_and_bool(self):
        with self.assertRaises(DecodeError):Reader(b'\xff'*4).value({'vec':'u8'})
        with self.assertRaises(DecodeError):Reader(b'\x02').value('bool')
        with self.assertRaises(DecodeError):Reader(b'\x02').value({'option':'u64'})
    def test_invalid_index_and_version(self):
        for idx in [-1,False,999,None]:self.assertEqual(decode_route(fixture(),idx)['status'],'UNKNOWN')
        for version in [True,0.0,2,{},[]]:
            tx=fixture();tx['version']=version;self.assertEqual(decode_route(tx,0)['status'],'UNKNOWN')
    def test_impossible_fee(self):
        tx=fixture();ins=tx['transaction']['message']['instructions'][0];raw=b58decode(ins['data']);ins['data']=b58encode(raw[:-2]+struct.pack('<H',10001))
        self.assertEqual(decode_route(tx,0)['reason'],'invalid_fee_or_slippage')
    def test_read_only(self):
        tx=fixture();before=copy.deepcopy(tx);decode_route(tx,0);self.assertEqual(tx,before)

if __name__=='__main__':unittest.main()
