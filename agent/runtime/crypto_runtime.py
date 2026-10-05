"""Crypto-only durable queue with an authenticated local Unix transport."""
import fcntl,json,os,pathlib,pwd,re,secrets,socket,socketserver,sqlite3,struct,threading,time
import crypto_agent
from runtime_gateway import selected

STATE=pathlib.Path('/var/lib/vivameda-crypto-runtime')
SOCKET='/run/vivameda-crypto-runtime/agent.sock'
WAKE=threading.Event()

class Queue:
    def __init__(self,state=STATE,runner=None):
        self.state=pathlib.Path(state);self.state.mkdir(mode=0o700,exist_ok=True)
        self.db=self.state/'jobs.sqlite3';self.runner=runner or self.run_agent
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, request_id TEXT UNIQUE, owner INTEGER, session TEXT, question TEXT, status TEXT, created REAL, started REAL, finished REAL, answer TEXT, error_code TEXT)')
            c.execute("UPDATE jobs SET status='interrupted', finished=?, error_code='WORKER_RESTARTED' WHERE status='running'",(time.time(),))
        os.chmod(self.db,0o600)
    def connect(self):
        c=sqlite3.connect(self.db,timeout=5);c.row_factory=sqlite3.Row;return c
    def owner(self,data):
        if type(data.get('owner')) is not int or data['owner']!=2:raise ValueError('Owner unavailable')
    def dispatch(self,data):
        self.owner(data);op=data.get('op')
        if op=='submit':
            session=data.get('session');q=data.get('question');rid=data.get('request_id')
            if not isinstance(session,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',session) or selected(session,'')!=session:raise ValueError('Dedicated crypto session required')
            if not isinstance(q,str) or not 1<=len(q)<=2000 or not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',rid):raise ValueError('Invalid request')
            with self.connect() as c:
                c.execute('BEGIN IMMEDIATE');prior=c.execute('SELECT * FROM jobs WHERE request_id=?',(rid,)).fetchone()
                if prior:
                    if prior['question']!=q or prior['session']!=session:raise ValueError('Request ID conflict')
                    return dict(prior)
                if c.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]>=30:raise ValueError('Crypto queue full')
                if self.db.stat().st_size>100*1024*1024:raise ValueError('Crypto queue storage limit reached')
                jid=secrets.token_hex(16);c.execute('INSERT INTO jobs(id,request_id,owner,session,question,status,created) VALUES(?,?,?,?,?,?,?)',(jid,rid,2,session,q,'queued',time.time()))
                row=dict(c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
            WAKE.set();return row
        if op=='jobs':
            session=data.get('session','')
            if not isinstance(session,str) or len(session)>64:raise ValueError('Invalid session')
            with self.connect() as c:
                rows=c.execute('SELECT * FROM jobs WHERE (?="" OR session=?) ORDER BY created DESC LIMIT 50',(session,session))
                return [dict(r) for r in rows]
        if op in ('get','cancel'):
            jid=data.get('id')
            if not isinstance(jid,str) or not re.fullmatch('[a-f0-9]{32}',jid):raise ValueError('Invalid job')
            with self.connect() as c:
                row=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
                if op=='get':return dict(row) if row else None
                if row is None:return None
                changed=c.execute("UPDATE jobs SET status='cancelled',finished=? WHERE id=? AND status='queued'",(time.time(),jid)).rowcount
                return {'ok':bool(changed),'error':None if changed else 'Only queued requests can be cancelled.'}
        if op=='history':
            session=data.get('session')
            if not isinstance(session,str) or selected(session,'')!=session:raise ValueError('Dedicated crypto session required')
            return crypto_agent.run('',session,self.state/'conversations',history_only=True)
        if op=='health':
            try:
                with socket.socket(socket.AF_INET):pass
                inet_blocked=False
            except OSError:inet_blocked=True
            paths=['/var/lib/vivameda-agent','/opt/vivameda-workspace','/opt/vivameda-conversations-v2','/opt/vivameda-connect','/mnt/HC_Volume_104237945']
            return {'domain':'crypto','queue':'separate','shared_inference_engine':True,'live_execution':False,'inet_socket_blocked':inet_blocked,'company_paths_visible':any(pathlib.Path(p).exists() for p in paths),'uid':os.getuid()}
        raise ValueError('Operation unavailable')
    def run_agent(self,row):
        result=crypto_agent.run(row['question'],row['session'],self.state/'conversations',history_only=row['question']=='/history',model_call=proxy_model)
        if result.get('domain')!='crypto':raise ValueError('Invalid result domain')
        return result
    def step(self):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');r=c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created,id LIMIT 1").fetchone()
            if not r:return False
            c.execute("UPDATE jobs SET status='running',started=? WHERE id=?",(time.time(),r['id']))
        try:
            answer=json.dumps(self.runner(dict(r)),allow_nan=False)
            if len(answer)>200000:raise ValueError('Response limit')
            status,error='succeeded',None
        except Exception as e:
            answer=None;status='failed';error='MODEL_MODE_UNSUPPORTED' if 'MODEL_MODE_UNSUPPORTED' in str(e) else 'CRYPTO_REQUEST_FAILED'
        with self.connect() as c:c.execute('UPDATE jobs SET status=?,finished=?,answer=?,error_code=? WHERE id=?',(status,time.time(),answer,error,r['id']))
        return True

class ProxyOpener:
    def open(self,request,timeout):
        import io
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(timeout);s.connect('/run/vivameda-crypto-model/model.sock');s.sendall(request.data+b'\n')
            with s.makefile('rb') as f:raw=f.readline(100002)
        if len(raw)>100001:raise ValueError('Proxy response too large')
        data=json.loads(raw)
        if 'proxy_error' in data:raise ValueError(data['proxy_error'])
        return io.BytesIO(raw)

def proxy_model(question,packet,history):
    return crypto_agent.ask_model(question,packet,history,opener=ProxyOpener())

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        _,uid,_=struct.unpack('3i',self.request.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        if uid!=self.server.authorized_uid:return
        try:
            raw=self.rfile.readline(12001)
            if len(raw)>12000 or not raw.endswith(b'\n'):raise ValueError('Request limit')
            result=self.server.queue.dispatch(json.loads(raw));reply={'ok':True,'result':result}
        except Exception:reply={'ok':False,'error':'Crypto runtime request rejected'}
        self.wfile.write(json.dumps(reply,allow_nan=False).encode()+b'\n')

def main():
    os.umask(0o077);state=STATE
    state.mkdir(mode=0o700,exist_ok=True)
    with (state/'runtime.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);q=Queue()
        def worker():
            try:
                while True:
                    if not q.step():WAKE.wait(2);WAKE.clear()
            except BaseException:os._exit(1)
        threading.Thread(target=worker,daemon=True).start()
        pathlib.Path(SOCKET).unlink(missing_ok=True)
        with socketserver.ThreadingUnixStreamServer(SOCKET,Handler) as server:
            server.daemon_threads=True;server.queue=q;server.authorized_uid=pwd.getpwnam('vivameda-agent').pw_uid
            os.chmod(SOCKET,0o666);server.serve_forever()

if __name__=='__main__':main()
