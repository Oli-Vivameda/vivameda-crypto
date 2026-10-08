"""Review-only shadow installer; refuses incomplete scientific/activation gates."""
import argparse, hashlib, json, os, pathlib, shutil, sqlite3, subprocess, tempfile, time
from earlier_entry import GRID, SOURCE_SHA, require_python
from shadow_scorer import initialize, STOP

ROOT=pathlib.Path('/opt/vivameda-earlier-entry')
STATE=pathlib.Path('/var/lib/vivameda-crypto-earlier-entry/shadow')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--install',action='store_true');p.add_argument('--policy',type=pathlib.Path,required=True)
    p.add_argument('--frozen-rule',type=pathlib.Path,required=True);p.add_argument('--rule-commit',required=True)
    p.add_argument('--expected-sha256',required=True);a=p.parse_args();require_python();bundle=pathlib.Path(__file__).parent
    try:
        if time.time()<STOP+3780:raise ValueError('Post-stop passive pilot follow-up must finish first')
        manifest=bundle/'bundle_manifest.json'
        if sha(manifest)!=a.expected_sha256:raise ValueError('Reviewed bundle digest mismatch')
        m=json.loads(manifest.read_bytes())
        for name,h in m['files'].items():
            if pathlib.PurePosixPath(name).name!=name or sha(bundle/name)!=h:raise ValueError('Reviewed source mismatch')
        raw=a.frozen_rule.read_bytes();rule=json.loads(raw);policy=json.loads(a.policy.read_bytes())
        if rule.get('development_only') is not True or rule.get('g') not in GRID or rule.get('qualification_counts_verified') is not True:raise ValueError('Qualified development freeze required')
        committed=subprocess.run(['git','show',a.rule_commit+':client_learning/crypto_directive3_20261008/research/frozen_rules.json'],capture_output=True,check=True)
        if committed.stdout!=raw:raise ValueError('Rule not committed')
        if policy['g']!=rule['g'] or policy['rule_sha256']!=sha(a.frozen_rule):raise ValueError('Policy/rule disagreement')
        if policy['protocol_sha256']!=sha(bundle/'PROTOCOL_DIRECTIVE3_20261008.md'):raise ValueError('Protocol binding mismatch')
        with sqlite3.connect(':memory:') as con:initialize(con,policy,int(time.time()))
        if STATE.exists() and (STATE/'shadow.sqlite').exists():raise ValueError('No reactivation/reset')
        if ROOT.exists():raise ValueError('Existing installation needs separate review')
        # Read-only access must already be present; never widen private DB permissions.
        check=subprocess.run(['runuser','-u','vivameda-monitor','--','/usr/bin/python3','-c',
            "import sqlite3; c=sqlite3.connect('file:/opt/vivameda-crypto-early-scout/data/early_scout.sqlite?mode=ro',uri=True); c.execute('PRAGMA query_only=ON'); c.execute('SELECT mint FROM pl_predictions LIMIT 0'); c.close(); p=sqlite3.connect('file:/opt/vivameda-crypto-early-scout/data/forward_capture/capture.sqlite?mode=ro',uri=True); p.execute(\"SELECT event_key FROM fc_events WHERE kind='cohort' LIMIT 0\"); p.close()"],capture_output=True)
        if check.returncode:raise ValueError('Existing service-user read access unavailable; no permission widening')
        if not a.install:print(json.dumps({'preflight':True,'production_changed':False,'activated':False}));return
        if os.geteuid()!=0:raise ValueError('Owner root install required')
        if not STATE.exists() or not os.access(STATE,os.W_OK):raise ValueError('Dedicated owner-prepared state directory required')
        backup=pathlib.Path(tempfile.mkdtemp(prefix='crypto-earlier-shadow-',dir='/opt/vivameda-operations'))
        (backup/'receipt.json').write_text(json.dumps({'bundle_sha256':a.expected_sha256,'previous_installation':'absent'}))
        ROOT.mkdir(mode=0o755)
        try:
            for name in ('earlier_entry.py','shadow_scorer.py','frozen_scorer_source.txt'):
                shutil.copy2(bundle/name,ROOT/name);os.chmod(ROOT/name,0o644)
            policy_dest=STATE/'activation_policy.json';shutil.copy2(a.policy,policy_dest)
            import pwd
            user=pwd.getpwnam('vivameda-monitor');os.chown(policy_dest,user.pw_uid,user.pw_gid);os.chmod(policy_dest,0o600)
            activation=subprocess.run(['runuser','-u','vivameda-monitor','--','/usr/bin/python3',str(ROOT/'shadow_scorer.py'),'--activate',str(policy_dest)],capture_output=True)
            if activation.returncode:raise ValueError('Activation failed; reviewed receipt needed')
            units=[]
            for name in ('vivameda-earlier-entry-shadow.service','vivameda-earlier-entry-shadow.timer'):
                dest=pathlib.Path('/etc/systemd/system')/name
                if dest.exists():raise ValueError('Existing unit refused')
                shutil.copy2(bundle/name,dest);units.append(dest)
            subprocess.run(['systemctl','daemon-reload'],check=True)
            # Units remain disabled. Enabling is a separate explicit owner activation step.
            hashes={n:sha(ROOT/n) for n in ('earlier_entry.py','shadow_scorer.py','frozen_scorer_source.txt')}
            if any(hashes[n]!=m['files'][n] for n in hashes):raise ValueError('Source postflight mismatch')
            print(json.dumps({'installed':True,'backup':str(backup),'bundle_sha256':a.expected_sha256,'source_hashes':hashes,
                'timer_enabled':False,'provider_requests':0,'production_changed':False,
                'postflight':'source hashes checked; timer disabled; owner start and first passive decision/endpoint pending'}))
        except BaseException:
            # Preserve failed installation as an inactive backup; never silently delete evidence.
            if ROOT.exists():ROOT.rename(backup/'failed-source')
            raise
    except (ValueError,OSError,KeyError,sqlite3.Error,subprocess.SubprocessError):raise SystemExit('Shadow install refused; frozen development rule, reviewed policy, post-stop time and existing read access required.')
if __name__=='__main__':main()
