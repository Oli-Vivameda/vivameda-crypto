import copy
import unittest
from dflow_reconcile import reconcile, instructions, EvidenceError, SYSTEM
from test_dflow_decoder import fixture, USER
from protocol_screening import b58encode, SPL

def key(n): return b58encode(bytes([n])*32)
SRC,DST,MINT,POOL,SPONSOR,CLOSE = [key(n) for n in range(20,26)]

def balance(index, owner, amount):
    return {'accountIndex':index,'owner':owner,'mint':MINT,'programId':SPL,
            'uiTokenAmount':{'amount':str(amount),'decimals':6}}

def sample():
    tx=fixture();msg=tx['transaction']['message'];accounts=msg['instructions'][0]['accounts']
    names=list(dict.fromkeys([USER]+accounts+[SRC,DST,MINT,POOL,SPONSOR,CLOSE]))
    msg['accountKeys']=[{'pubkey':x,'signer':x==USER} for x in names]
    n=len(names);pre=[1000]*n;post=pre.copy();post[0]-=5
    tx['meta'].update(fee=5,preBalances=pre,postBalances=post,
      preTokenBalances=[balance(names.index(SRC),USER,100),balance(names.index(DST),POOL,0)],
      postTokenBalances=[balance(names.index(SRC),USER,40),balance(names.index(DST),POOL,60)],
      innerInstructions=[{'index':0,'instructions':[
       {'programId':POOL,'stackHeight':2,'data':'1','accounts':[SRC,DST]},
       {'programId':SPL,'stackHeight':3,'parsed':{'type':'transferChecked','info':{
         'source':SRC,'destination':DST,'mint':MINT,'authority':SPONSOR,'tokenAmount':{'amount':'60','decimals':6}}}}]}])
    return tx

class ReconcileTests(unittest.TestCase):
    def test_exact_accounting_is_not_history_pass(self):
        r=reconcile(sample());self.assertEqual(r['status'],'ENDPOINT_AMOUNTS_MATCH')
        self.assertFalse(r['history_coverage_complete']);self.assertEqual(r['common_control_edges'],[])
        self.assertIn('downstream_program_semantics_unverified',r['blockers'])
    def test_authority_is_not_owner(self):
        r=reconcile(sample())['receipts'][0]
        self.assertEqual(r['source_owner'],USER);self.assertEqual(r['authority'],SPONSOR)
        self.assertFalse(r['common_control_evidence']);self.assertEqual(r['purpose'],'unverified')
    def test_inner_siblings_keep_distinct_parents(self):
        tx=sample();g=tx['meta']['innerInstructions'][0]['instructions'];g+=copy.deepcopy(g)
        rows=instructions(tx)
        self.assertEqual(rows[2]['parent'],'0.0');self.assertEqual(rows[4]['parent'],'0.2')
    def test_separate_root_not_attributed_to_dflow(self):
        tx=sample();msg=tx['transaction']['message'];msg['instructions'].append({'programId':SYSTEM,'parsed':{'type':'transfer','info':{'source':USER,'destination':CLOSE,'lamports':7}}})
        keys=[k['pubkey'] for k in msg['accountKeys']];tx['meta']['postBalances'][0]-=7;tx['meta']['postBalances'][keys.index(CLOSE)]+=7
        r=reconcile(tx);self.assertEqual(r['status'],'ENDPOINT_AMOUNTS_MATCH')
        self.assertFalse(r['receipts'][-1]['under_dflow']);self.assertEqual(r['receipts'][-1]['root'],1)
    def test_missing_trace_and_invalid_stack(self):
        for change in ['missing','jump','bool','duplicate']:
            tx=sample()
            if change=='missing':tx['meta']['innerInstructions']=None
            elif change=='duplicate':tx['meta']['innerInstructions']*=2
            else:tx['meta']['innerInstructions'][0]['instructions'][0]['stackHeight']=True if change=='bool' else 4
            self.assertEqual(reconcile(tx)['status'],'UNKNOWN')
    def test_omitted_transfer_leaves_residual(self):
        tx=sample();tx['meta']['innerInstructions'][0]['instructions'].pop()
        r=reconcile(tx);self.assertIn('token_balance_residual',r['blockers'])
    def test_fee_accounting(self):
        tx=sample();tx['meta']['fee']=4
        self.assertIn('native_balance_residual',reconcile(tx)['blockers'])
    def test_wrong_checked_mint(self):
        tx=sample();tx['meta']['innerInstructions'][0]['instructions'][1]['parsed']['info']['mint']=POOL
        self.assertIn('checked_mint_mismatch',reconcile(tx)['blockers'])
    def test_missing_balance_side_is_unknown(self):
        tx=sample();tx['meta']['preTokenBalances'].pop()
        self.assertEqual(reconcile(tx)['status'],'UNKNOWN')
    def test_changed_endpoint_owner(self):
        tx=sample();tx['meta']['postTokenBalances'][0]['owner']=SPONSOR
        self.assertIn('endpoint_identity_changed',reconcile(tx)['blockers'])
    def test_close_authority_does_not_change_owner(self):
        tx=sample();tx['meta']['innerInstructions'][0]['instructions'].insert(0,{'programId':SPL,'stackHeight':2,'parsed':{'type':'setAuthority','info':{'account':SRC,'authorityType':'closeAccount','newAuthority':CLOSE}}})
        r=reconcile(tx);self.assertEqual(r['status'],'ENDPOINT_AMOUNTS_MATCH');self.assertEqual(r['receipts'][0]['source_owner'],USER)
    def test_owner_change_stops_before_false_receipt(self):
        tx=sample();tx['meta']['innerInstructions'][0]['instructions'].insert(0,{'programId':SPL,'stackHeight':2,'parsed':{'type':'setAuthority','info':{'account':SRC,'authorityType':'accountOwner','newAuthority':CLOSE}}})
        r=reconcile(tx);self.assertEqual(r['status'],'UNKNOWN');self.assertEqual(r['receipts'],[])
    def test_bad_amounts_and_underflow(self):
        for amount in [True,-1,'-1','1.5','101']:
            tx=sample();tx['meta']['innerInstructions'][0]['instructions'][1]['parsed']['info']['tokenAmount']['amount']=amount
            self.assertEqual(reconcile(tx)['status'],'UNKNOWN')
    def test_failed_transaction_and_bool_version(self):
        tx=sample();tx['meta']['err']='failure';self.assertEqual(reconcile(tx)['receipts'],[])
        tx=sample();tx['version']=True;self.assertEqual(reconcile(tx)['status'],'UNKNOWN')
    def test_close_refund_is_not_a_trade(self):
        tx=sample();meta=tx['meta'];keys=[k['pubkey'] for k in tx['transaction']['message']['accountKeys']]
        meta['preTokenBalances'][0]['uiTokenAmount']['amount']='0'
        meta['postTokenBalances']=[meta['postTokenBalances'][1]]
        meta['postTokenBalances'][0]['uiTokenAmount']['amount']='0'
        meta['postBalances'][keys.index(SRC)]=0
        meta['postBalances'][keys.index(CLOSE)]+=1000
        meta['innerInstructions'][0]['instructions']=[{'programId':SPL,'stackHeight':2,'parsed':{'type':'closeAccount','info':{'account':SRC,'destination':CLOSE,'owner':SPONSOR}}}]
        r=reconcile(tx);self.assertEqual(r['status'],'ENDPOINT_AMOUNTS_MATCH')
        self.assertEqual(r['receipts'][0]['kind'],'close_refund_or_unwrap')
        self.assertEqual(r['receipts'][0]['authority'],SPONSOR)
        self.assertFalse(r['receipts'][0]['common_control_evidence'])
    def test_duplicate_balance_rejected(self):
        tx=sample();tx['meta']['preTokenBalances'].append(tx['meta']['preTokenBalances'][0].copy())
        self.assertIn('duplicate_token_balance',reconcile(tx)['blockers'])
    def test_input_unchanged(self):
        tx=sample();before=copy.deepcopy(tx);reconcile(tx);self.assertEqual(tx,before)

if __name__=='__main__':unittest.main()
