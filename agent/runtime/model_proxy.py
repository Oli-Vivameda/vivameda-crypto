"""Restricted crypto inference proxy. No model administration endpoints."""
import json,os,pathlib,pwd,socket,socketserver,struct,urllib.request

SOCKET='/run/vivameda-crypto-model/model.sock'
MODEL='qwen3:4b'

def validate(body):
    if set(body)!={'model','messages','think','stream','keep_alive','options'} or body['model']!=MODEL or body['think'] is not False or body['stream'] is not False or body['keep_alive']!='2m':raise ValueError('Invalid model request')
    if body['options']!={'temperature':0,'num_ctx':8192,'num_predict':700,'num_thread':4}:raise ValueError('Invalid options')
    messages=body['messages']
    if not isinstance(messages,list) or not 2<=len(messages)<=10 or messages[0].get('role')!='system':raise ValueError('Invalid messages')
    for m in messages:
        if set(m)!={'role','content'} or m['role'] not in ('system','user','assistant') or not isinstance(m['content'],str):raise ValueError('Invalid message')
    if sum(len(m['content']) for m in messages)>22000:raise ValueError('Context limit')
    return body

def infer(body,opener=None):
    validate(body);opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req=urllib.request.Request('http://127.0.0.1:11434/api/show',data=json.dumps({'model':MODEL}).encode(),headers={'Content-Type':'application/json'})
    with opener.open(req,timeout=5) as response:meta=json.loads(response.read(200000))
    modes=meta.get('thinking',{}).get('values')
    if modes==[True] or meta.get('model_info',{}).get('general.finetune')=='Thinking':raise ValueError('MODEL_MODE_UNSUPPORTED')
    req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(body,allow_nan=False).encode(),headers={'Content-Type':'application/json'})
    with opener.open(req,timeout=150) as response:raw=response.read(100001)
    if len(raw)>100000:raise ValueError('Response limit')
    return json.loads(raw)

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        _,uid,_=struct.unpack('3i',self.request.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        if uid!=self.server.authorized_uid:return
        try:
            raw=self.rfile.readline(100001)
            if len(raw)>100000 or not raw.endswith(b'\n'):raise ValueError('Request limit')
            answer=infer(json.loads(raw))
        except Exception as e:answer={'proxy_error':'MODEL_MODE_UNSUPPORTED' if 'MODEL_MODE_UNSUPPORTED' in str(e) else 'MODEL_REQUEST_FAILED'}
        self.wfile.write(json.dumps(answer,allow_nan=False).encode()+b'\n')

def main():
    os.umask(0o077);pathlib.Path(SOCKET).unlink(missing_ok=True)
    with socketserver.UnixStreamServer(SOCKET,Handler) as s:
        s.authorized_uid=pwd.getpwnam('vivameda-crypto').pw_uid;os.chmod(SOCKET,0o660);s.serve_forever()

if __name__=='__main__':main()
