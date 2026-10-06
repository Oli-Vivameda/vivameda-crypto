#!/usr/bin/env python3
"""Reviewed owner-run activation; never reads model-ledger outcomes.

Run only after the matching two-file runtime is deployed. Without --install,
validates hashes/units and opens production SQLite read-only, then exits.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import logging
import math
import os
from pathlib import Path
import pwd
import sqlite3
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
BASE = Path('/opt/vivameda-crypto-early-scout')
BUNDLE_FILES = ('capture.py', 'PROTOCOL.md', 'integration/early_scout.py',
                'integration/scout_learning_v2.py', 'integration/activate_capture.py')


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_hash():
    values={f:hash_file(PACKAGE/f) for f in BUNDLE_FILES}
    return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def service_user(unit):
    r=subprocess.run(['/usr/bin/systemctl','show',unit,'--property=User','--value'],
                     check=True,capture_output=True,text=True,timeout=10)
    user=r.stdout.strip() or 'root'
    return pwd.getpwnam(user)


def count_postflight():
    # Extract reviewed capture functions only; never import production's
    # network session, filesystem/log setup, credential path or main loop.
    source=BASE/'early_scout.py'
    tree=ast.parse(source.read_text())
    nodes=[]
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name.startswith('fc_'):
            nodes.append(node)
        elif isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and
                 (t.id.startswith('FC_') or t.id.startswith('_fc_')) for t in node.targets):
            nodes.append(node)
    values=dict(BASE=BASE,Path=Path,hashlib=hashlib,json=json,math=math,sqlite3=sqlite3,
                time=time,logging=logging,__file__=str(source))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'reviewed-count-postflight','exec'),values)
    try:
        status=values['fc_count_status']()
        if status['status']!='collecting':
            raise ValueError('capture count-only postflight failed')
        return status
    finally:
        if values['_fc_connection'] is not None:values['_fc_connection'].close()


def activate(install, expected_bundle):
    if bundle_hash()!=expected_bundle:
        raise ValueError('activation bundle hash mismatch')
    expected={f:hash_file(HERE/f) for f in ('early_scout.py','scout_learning_v2.py')}
    for f,h in expected.items():
        if hash_file(BASE/f)!=h:
            raise ValueError('reviewed runtime must be deployed before activation: '+f)
    scanner_user=service_user('vivameda-early-scout.service')
    tracker_user=service_user('vivameda-scout-learning-v2.service')
    if scanner_user.pw_uid!=tracker_user.pw_uid:
        raise ValueError('private shared writer identity requires separate review')
    target=BASE/'data'/'forward_capture'
    database=target/'capture.sqlite'
    if database.exists():
        raise ValueError('existing pilot preserved; reactivation prohibited')
    production=sqlite3.connect('file:'+str(BASE/'data'/'early_scout.sqlite')+'?mode=ro',uri=True,timeout=10)
    try:
        # Cutoff precedes the read snapshot; concurrent newly registered tokens
        # may also be conservatively excluded, never admitted as earlier-known.
        now=int(time.time())
        production.execute('PRAGMA query_only=ON');production.execute('BEGIN')
        # Exclude all existing identities, not labels/predictions/results.
        excluded=[r[0] for r in production.execute('SELECT mint FROM launches UNION SELECT mint FROM snapshots UNION SELECT mint FROM v2_cases ORDER BY mint')]
    finally:
        production.rollback();production.close()
    result={'validated':True,'installed':False,'bundle_sha256':expected_bundle,
            'excluded_count':len(excluded),'runtime_hashes':expected,
            'protocol_sha256':hash_file(PACKAGE/'PROTOCOL.md'),
            'live_execution':False,'model_ledger_changed':False}
    if not install:
        return result
    if os.geteuid()!=0:
        raise PermissionError('owner root activation required')
    if target.exists() and any(target.iterdir()):
        raise ValueError('existing private artifacts preserved')
    target.mkdir(mode=0o700,exist_ok=True);target.chmod(0o700)
    fd,name=tempfile.mkstemp(prefix='activation-',suffix='.sqlite',dir=target)
    os.close(fd);private=Path(name)
    try:
        spec=importlib.util.spec_from_file_location('reviewed_capture',PACKAGE/'capture.py')
        core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
        con=sqlite3.connect(private)
        try:
            core.initialize(con,now,excluded,result['protocol_sha256'],
                            {'scanner_sha256':expected['early_scout.py'],
                             'tracker_sha256':expected['scout_learning_v2.py']})
            core.verify(con)
        finally:
            con.close()
        private.chmod(0o600);os.chown(private,scanner_user.pw_uid,scanner_user.pw_gid)
        # Same-directory atomic publication: runtime never sees half activation.
        os.link(private,database)  # Exclusive atomic publication; cannot replace a raced pilot.
        private.unlink()
        os.chown(target,scanner_user.pw_uid,scanner_user.pw_gid)
        result.update(installed=True,activation_ts=now,deadline=now+14*86400,
                      writer_uid=scanner_user.pw_uid,private_runtime_created=True)
        result['postflight']=count_postflight()
        return result
    finally:
        if private.exists():private.unlink()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--install',action='store_true')
    parser.add_argument('--expected-sha256',required=True)
    args=parser.parse_args()
    print(json.dumps(activate(args.install,args.expected_sha256),sort_keys=True))
