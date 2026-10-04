import copy
import unittest
from dflow_reconcile_candidate import reconcile, PUMP_AMM, PUMP_CLOSE, SYSTEM, ATA, WSOL, SPL
from protocol_screening import b58encode
from test_dflow_reconcile import sample, USER, CLOSE, SPONSOR

def close_sample():
    tx=sample();msg=tx['transaction']['message'];keys=msg['accountKeys']
    keys.append({'pubkey':PUMP_AMM,'signer':False,'writable':False})
    tx['meta']['preBalances'].append(100);tx['meta']['postBalances'].append(100)
    for k in keys:k['writable']=k['pubkey'] in (USER,CLOSE)
    names=[k['pubkey'] for k in keys];v=names.index(CLOSE)
    tx['meta']['preBalances'][v]=tx['meta']['postBalances'][v]=0
    group=tx['meta']['innerInstructions'][0]['instructions']
    group.extend([
      {'programId':SYSTEM,'stackHeight':2,'parsed':{'type':'createAccount','info':{'source':USER,'newAccount':CLOSE,'lamports':100,'owner':PUMP_AMM,'space':137}}},
      {'programId':PUMP_AMM,'stackHeight':2,'accounts':[USER,CLOSE,SPONSOR,PUMP_AMM],'data':b58encode(PUMP_CLOSE)}])
    return tx

class CandidateTests(unittest.TestCase):
    def test_close_refund_keeps_semantic_hold(self):
        tx=close_sample();before=copy.deepcopy(tx);r=reconcile(tx)
        self.assertEqual(r['status'],'ENDPOINT_AMOUNTS_MATCH')
        self.assertEqual(r['receipts'][-1]['raw_amount'],'100')
        self.assertEqual(r['receipts'][-1]['kind'],'program_account_close_refund')
        self.assertIn('pump_close_pda_and_deployed_version_unverified',r['blockers'])
        self.assertFalse(r['history_coverage_complete']);self.assertEqual(tx,before)
    def test_bad_close_rejected(self):
        for kind in ('data','program','signer','writable','owner','endpoint','duplicate'):
            tx=close_sample();g=tx['meta']['innerInstructions'][0]['instructions'];keys=tx['transaction']['message']['accountKeys']
            if kind=='data':g[-1]['data']=b58encode(PUMP_CLOSE+b'\0')
            if kind=='program':g[-1]['accounts'][-1]=SYSTEM
            if kind=='signer':keys[0]['signer']=False
            if kind=='writable':keys[0]['writable']=False
            if kind=='owner':g[-2]['parsed']['info']['owner']=SYSTEM
            if kind=='endpoint':tx['meta']['postBalances'][[k['pubkey'] for k in keys].index(CLOSE)]=1
            if kind=='duplicate':g.append(copy.deepcopy(g[-1]))
            with self.subTest(kind=kind):self.assertEqual(reconcile(tx)['status'],'UNKNOWN')
    def test_no_creation_rejected(self):
        tx=close_sample();del tx['meta']['innerInstructions'][0]['instructions'][-2]
        self.assertEqual(reconcile(tx)['status'],'UNKNOWN')
    def test_existing_sample_unchanged(self):
        self.assertEqual(reconcile(sample())['status'],'ENDPOINT_AMOUNTS_MATCH')

def sync_sample():
    tx=sample();msg=tx['transaction']['message'];keys=msg['accountKeys']
    for a in (ATA,WSOL):
        if a not in [k['pubkey'] for k in keys]:
            keys.append({'pubkey':a,'signer':False});tx['meta']['preBalances'].append(100);tx['meta']['postBalances'].append(100)
    v=[k['pubkey'] for k in keys].index(CLOSE)
    tx['meta']['preBalances'][v]=tx['meta']['postBalances'][v]=0
    tx['meta']['innerInstructions'][0]['instructions'].extend([
      {'programId':ATA,'stackHeight':2,'parsed':{'type':'create','info':{'account':CLOSE,'source':USER,'mint':WSOL,'wallet':USER,'tokenProgram':SPL,'systemProgram':SYSTEM}}},
      {'programId':SYSTEM,'stackHeight':3,'parsed':{'type':'createAccount','info':{'newAccount':CLOSE,'source':USER,'lamports':100,'space':165,'owner':SPL}}},
      {'programId':SPL,'stackHeight':3,'parsed':{'type':'initializeAccount3','info':{'account':CLOSE,'mint':WSOL,'owner':USER}}},
      {'programId':SYSTEM,'stackHeight':2,'parsed':{'type':'transfer','info':{'source':USER,'destination':CLOSE,'lamports':7}}},
      {'programId':SPL,'stackHeight':2,'parsed':{'type':'syncNative','info':{'account':CLOSE}}},
      {'programId':SPL,'stackHeight':2,'parsed':{'type':'closeAccount','info':{'account':CLOSE,'destination':USER,'owner':USER}}}])
    return tx

class SyncNativeCandidateTests(unittest.TestCase):
    def test_conditional_sync_preserves_hold(self):
        tx=sync_sample();before=copy.deepcopy(tx);r=reconcile(tx)
        self.assertEqual(r['status'],'ENDPOINT_AMOUNTS_MATCH')
        self.assertEqual(r['state_updates'][0]['raw_amount'],'7')
        self.assertEqual(r['state_updates'][0]['reserve_lamports'],'100')
        self.assertFalse(r['history_coverage_complete']);self.assertEqual(tx,before)
        self.assertIn('ata_rent_and_historical_program_semantics_unverified',r['blockers'])
    def test_wrong_parent_refused(self):
        tx=sync_sample();tx['meta']['innerInstructions'][0]['instructions'][-6]['programId']=SYSTEM
        self.assertEqual(reconcile(tx)['status'],'UNKNOWN')
    def test_bad_funding_refused(self):
        for field,value in [('owner',SYSTEM),('space',166),('space',True),('lamports',1)]:
            tx=sync_sample();tx['meta']['innerInstructions'][0]['instructions'][-5]['parsed']['info'][field]=value
            with self.subTest(field=field,value=value):self.assertEqual(reconcile(tx)['status'],'UNKNOWN')
    def test_preexisting_balance_refused(self):
        tx=sync_sample();names=[k['pubkey'] for k in tx['transaction']['message']['accountKeys']]
        tx['meta']['preBalances'][names.index(CLOSE)]=1
        self.assertEqual(reconcile(tx)['status'],'UNKNOWN')
    def test_initialization_identity_refused(self):
        tx=sync_sample();tx['meta']['innerInstructions'][0]['instructions'][-4]['parsed']['info']['owner']=SPONSOR
        self.assertIn('sync_native_historical_reserve_missing',reconcile(tx)['blockers'])
    def test_sync_is_state_update_not_transfer(self):
        r=reconcile(sync_sample());self.assertEqual(len(r['state_updates']),1)
        self.assertFalse(any(x['kind']=='sync_native' for x in r['receipts']))

class LifecycleAndSupplyTests(unittest.TestCase):
    def test_closed_account_can_start_new_lifecycle(self):
        tx=sync_sample();g=tx['meta']['innerInstructions'][0]['instructions'];g.extend(copy.deepcopy(g[-6:]))
        r=reconcile(tx);self.assertEqual(r['status'],'ENDPOINT_AMOUNTS_MATCH')
        self.assertEqual(len(r['lifecycle_events']),1);self.assertEqual(len(r['state_updates']),2)
        self.assertFalse(r['history_coverage_complete'])
    def test_recreation_without_close_rejected(self):
        tx=sync_sample();g=tx['meta']['innerInstructions'][0]['instructions'];second=copy.deepcopy(g[-6:]);g.pop();g.extend(second)
        self.assertEqual(reconcile(tx)['status'],'UNKNOWN')
    def test_recreation_wrong_program_rejected(self):
        tx=sync_sample();g=tx['meta']['innerInstructions'][0]['instructions'];second=copy.deepcopy(g[-6:]);second[1]['parsed']['info']['owner']=SYSTEM;g.extend(second)
        self.assertEqual(reconcile(tx)['status'],'UNKNOWN')
    def test_mint_burn_accounting_not_transfer_or_authority_proof(self):
        from test_dflow_reconcile import SRC,MINT
        tx=sample();g=tx['meta']['innerInstructions'][0]['instructions']
        for kind in ('mintTo','burn'):
            g.append({'programId':SPL,'stackHeight':2,'parsed':{'type':kind,'info':{'account':SRC,'mint':MINT,'amount':'7'}}})
        r=reconcile(tx);self.assertEqual(r['status'],'ENDPOINT_AMOUNTS_MATCH')
        self.assertEqual(len(r['receipts']),1);self.assertEqual(len(r['state_updates']),2)
        self.assertIn('mint_burn_authority_and_supply_unverified',r['blockers'])
    def test_burn_underflow_and_wrong_mint_refused(self):
        from test_dflow_reconcile import SRC,MINT
        for mint,amount in ((MINT,'999999'),(WSOL,'1')):
            tx=sample();tx['meta']['innerInstructions'][0]['instructions'].append({'programId':SPL,'stackHeight':2,'parsed':{'type':'burn','info':{'account':SRC,'mint':mint,'amount':amount}}})
            self.assertEqual(reconcile(tx)['status'],'UNKNOWN')

if __name__=='__main__':unittest.main()
