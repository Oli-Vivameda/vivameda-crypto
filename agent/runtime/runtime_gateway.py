"""Fixed Unix-socket crypto gateway; no local fallback or company imports."""
import argparse, hashlib, json, re, socket, time, secrets

SOCKET = '/run/vivameda-crypto-runtime/agent.sock'

def selected(session, question):
    if not isinstance(session, str) or not isinstance(question, str):
        return None
    if re.match(r'^crypto(?:[-_]|$)', session, re.I):
        return session
    if re.match(r'^\s*crypto\b', question, re.I):
        return 'crypto-'+hashlib.sha256(session.encode()).hexdigest()[:32]
    return None

def call(op, **args):
    raw = json.dumps(dict(op=op, **args), allow_nan=False).encode()+b'\n'
    with socket.socket(socket.AF_UNIX) as stream:
        stream.settimeout(5); stream.connect(SOCKET); stream.sendall(raw)
        with stream.makefile('rb') as f:
            result = f.readline(250001)
    if len(result)>250000 or not result.endswith(b'\n'):
        raise ValueError('Invalid crypto runtime response')
    response=json.loads(result)
    if not response.get('ok'):
        raise ValueError(response.get('error','Crypto runtime unavailable'))
    return response['result']

def enqueue(owner, data):
    original=data.get('session');question=data.get('question')
    if not isinstance(original,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',original) or not isinstance(question,str) or not 1<=len(question)<=2000:
        raise ValueError('Invalid crypto request')
    session=selected(data.get('session'),data.get('question'))
    if session is None:
        raise ValueError('Not a crypto request')
    return call('submit',owner=owner,request_id=data.get('request_id'),session=session,question=data.get('question'))

def jobs(owner, session=''):
    # Explicit crypto requests from a company-named UI session have a hashed namespace.
    effective=selected(session,'Crypto status') if session else ''
    return call('jobs',owner=owner,session=effective)

def merged(owner, rows, session='', limit=50):
    # Company listings remain usable if the dedicated runtime is unavailable.
    try: extra=jobs(owner, session)
    except (OSError,ValueError): extra=[]
    return sorted([*rows,*extra],key=lambda x:x['created'],reverse=True)[:limit]

def maybe_run(argv):
    p=argparse.ArgumentParser(add_help=False);p.add_argument('--session',default='default');p.add_argument('--history',action='store_true');p.add_argument('question',nargs='*')
    args,unknown=p.parse_known_args(argv);q=' '.join(args.question).strip();session=selected(args.session,q)
    if session is None:return False
    if unknown:raise ValueError('Unsupported crypto arguments')
    if args.history:
        result=call('history',owner=2,session=session)
    else:
        row=call('submit',owner=2,session=session,question=q,request_id='crypto-cli-'+secrets.token_hex(16))
        deadline=time.monotonic()+180
        while row['status'] in ('queued','running'):
            if time.monotonic()>deadline:raise ValueError('Crypto job continues in its dedicated queue: '+row['id'])
            time.sleep(.2);row=call('get',owner=2,id=row['id'])
        if row['status']!='succeeded':raise ValueError(row.get('error_code') or 'Crypto job failed')
        result=json.loads(row['answer'])
    print(json.dumps(result,allow_nan=False));return True
