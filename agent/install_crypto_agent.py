"""Fixed-path, hash-locked owner installation of isolated crypto routing."""
import argparse, ast, datetime, hashlib, json, os, pathlib, pwd, shutil, subprocess, tempfile
from crypto_boundary import patch

BASE = pathlib.Path(__file__).resolve().parent
LIVE = pathlib.Path('/opt/vivameda-conversations-v2/session_agent.py')
APP = pathlib.Path('/opt/vivameda-crypto-agent')
STATE = pathlib.Path('/var/lib/vivameda-crypto-agent')
FILES = ('crypto_agent.py', 'crypto_boundary.py', 'install_crypto_agent.py', 'test_crypto_agent.py', 'CRYPTO_LAB.md')

def bundle():
    return hashlib.sha256(b''.join(n.encode()+b'\0'+(BASE/n).read_bytes()+b'\0' for n in FILES)).hexdigest()

def checked(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink refused')

def write(path, raw, mode=0o644):
    checked(path)
    fd, name = tempfile.mkstemp(prefix='.crypto-agent-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.chmod(name, mode); os.chown(name, 0, 0); os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true'); parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--expected-live-sha256', required=True)
    args = parser.parse_args()
    if bundle() != args.expected_sha256:
        raise ValueError('Reviewed crypto bundle changed')
    for name in FILES:
        checked(BASE/name)
        if name.endswith('.py'):
            ast.parse((BASE/name).read_text())
    checked(LIVE); source = LIVE.read_bytes()
    if hashlib.sha256(source).hexdigest() != args.expected_live_sha256:
        raise ValueError('Live company agent changed; stop for review, never overwrite concurrent work')
    new = patch(source.decode()).encode()
    if not args.install:
        print(json.dumps({'validated': True, 'installed': False, 'bundle_sha256': bundle(),
                          'live_sha256': args.expected_live_sha256,
                          'patched_live_sha256': hashlib.sha256(new).hexdigest()})); return
    if os.geteuid() != 0:
        raise SystemExit('Owner maintenance terminal required for root-owned routing installation')
    for path in (APP, STATE, LIVE.parent):
        checked(path)
    owner = pwd.getpwnam('vivameda-agent')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = pathlib.Path('/opt/vivameda-operations')/('crypto-agent-backup-'+stamp)
    backup.mkdir(mode=0o700)
    originals = {}
    for path in (LIVE, LIVE.with_name('crypto_agent.py'), LIVE.with_name('crypto_boundary.py')):
        checked(path)
        originals[str(path)] = path.read_bytes() if path.exists() else None
        if path.exists():
            shutil.copy2(path, backup/path.name)
    APP.mkdir(mode=0o755, exist_ok=True); STATE.mkdir(mode=0o700, exist_ok=True)
    os.chmod(STATE, 0o700); os.chown(STATE, owner.pw_uid, owner.pw_gid)
    try:
        for name in FILES:
            write(APP/name, (BASE/name).read_bytes())
        for name in ('crypto_agent.py', 'crypto_boundary.py'):
            write(LIVE.with_name(name), (BASE/name).read_bytes())
        stat = LIVE.stat()
        # Publish dispatcher last, after its dependencies. No company source files bundled publicly.
        write(LIVE, new, stat.st_mode & 0o777); os.chown(LIVE, stat.st_uid, stat.st_gid)
        result = subprocess.run(['/usr/sbin/runuser', '-u', owner.pw_name, '--', '/usr/bin/python3',
                                 str(LIVE), '--session', 'crypto-install-postflight', 'Crypto status'],
                                capture_output=True, text=True, timeout=20, check=True)
        status = json.loads(result.stdout)
        if status['domain'] != 'crypto' or status['answer']['company_tools'] is not False:
            raise ValueError('Crypto postflight failed')
        receipt = {'installed': True, 'bundle_sha256': bundle(), 'backup': str(backup),
                   'previous_live_sha256': args.expected_live_sha256,
                   'live_sha256': hashlib.sha256(LIVE.read_bytes()).hexdigest(),
                   'crypto_state': str(STATE), 'base_model': 'qwen3:4b', 'dedicated_weights': False,
                   'company_tools_available_to_crypto': False, 'history_migrated': False,
                   'scanner_changed': False, 'policy_changed': False, 'weights_updated': False,
                   'live_execution': False, 'requires_new_worker_process': True}
        write(APP/'ACTIVATION.json', (json.dumps(receipt, indent=2)+'\n').encode())
        print(json.dumps(receipt))
    except BaseException:
        for name, raw in originals.items():
            path = pathlib.Path(name)
            if raw is None:
                if path.exists(): path.unlink()
            else:
                shutil.copy2(backup/path.name, path)
        raise

if __name__ == '__main__':
    main()
