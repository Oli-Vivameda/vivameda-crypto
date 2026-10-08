"""Owner-run, sanitized read-only installer diagnosis. No database access or install."""
import argparse,hashlib,json,os,pathlib,pwd,grp,subprocess,sys,tempfile,time
HERE=pathlib.Path(__file__).resolve().parent
BUNDLE='012afbd8d1fd635c89edafe11cbb895d899e0c539bb0f2230b5b438493cdd73b'
class Gate(Exception):
    def __init__(self,details):self.details=details

def command(argv):return subprocess.run(argv,capture_output=True,text=True,check=True,timeout=60)
def check(stage,fn,rows):
    try:
        detail=fn();rows.append({'stage':stage,'passed':True,'detail':detail});return detail
    except Exception as exc:
        detail=exc.details if isinstance(exc,Gate) else {'error_category':type(exc).__name__}
        rows.append({'stage':stage,'passed':False,'detail':detail});raise Gate({'blocker':stage})
def require(ok,detail):
    if not ok:raise Gate(detail)
    return detail

def diagnose():
    import install_archiver as i,archiver as a
    rows=[];out={'production_changed':False,'permissions_changed':False,'pilot_modified':False,'provider_requests':0,'alarm_sent':False,'production_database_opened':False,'checks':rows}
    try:
        check('owner_python',lambda:require(os.geteuid()==0 and sys.version_info[:2]==(3,12),{'root':os.geteuid()==0,'python_3_12':sys.version_info[:2]==(3,12)}),rows)
        check('candidate_bundle',lambda:require(i.bundle()==BUNDLE,{'expected_sha256':BUNDLE,'actual_sha256':i.bundle()}),rows)
        check('scanner_source',lambda:require(i.sha(a.SOURCE.parent.parent/'early_scout.py')==i.SCANNER_SHA,{'expected_sha256':i.SCANNER_SHA,'actual_sha256':i.sha(a.SOURCE.parent.parent/'early_scout.py')}),rows)
        check('status_route',lambda:require(i.sha(a.STATUS)==a.STATUS_SHA,{'expected_sha256':a.STATUS_SHA,'actual_sha256':i.sha(a.STATUS)}),rows)
        def user_gate():
            user=command(['/usr/bin/systemctl','show','vivameda-crypto-pilot-health.service','--property=User','--value']).stdout.strip()
            require(bool(user) and user not in ('root','vivameda-engineer'),{'nonroot_nonengineering_user':bool(user) and user not in ('root','vivameda-engineer')})
            account=pwd.getpwnam(user);grp.getgrgid(account.pw_gid)
            return user
        user=check('existing_health_user',user_gate,rows)
        def access():
            paths=[str(a.SOURCE),str(a.STATUS),str(a.AUDIT)]
            script='import os,sys,json; print(json.dumps([os.access(p,os.R_OK) for p in sys.argv[1:]]))'
            flags=json.loads(command(['/usr/sbin/runuser','-u',user,'--','/usr/bin/python3','-c',script,*paths]).stdout)
            return require(all(flags),dict(zip(('scanner_db_readable','status_route_readable','health_audit_readable'),flags)))
        check('service_user_path_access',access,rows)
        def health():
            data=json.loads(command(['/usr/sbin/runuser','-u',user,'--','/usr/bin/python3',str(a.STATUS)]).stdout)
            state=data.get('status');state=state if state in ('collecting','paused','stalled','unhealthy','unavailable','monitor_stale','monitor_not_installed','not_activated') else 'other'
            age=int(time.time())-data.get('checked_at',0)
            return require(state=='collecting' and 0<=age<=300,{'status':state,'report_age_seconds':age,'fresh_collecting':state=='collecting' and 0<=age<=300})
        check('fresh_health_baseline',health,rows)
        def frozen():
            base=a.SOURCE.parent.parent;paths=[base/n for n in ('early_scout.py','scout_learning_v2.py')]+[pathlib.Path('/etc/systemd/system')/n for n in ('vivameda-early-scout.service','vivameda-scout-learning-v2.service','vivameda-crypto-pilot-health.service','vivameda-crypto-pilot-health.timer')]
            for p in paths:
                try:i.sha(p)
                except Exception as exc:raise Gate({'file':p.name,'error_category':type(exc).__name__})
            return {'source_and_unit_files_readable':len(paths)}
        check('frozen_source_unit_paths',frozen,rows)
        def absent():
            flags={'destination_exists':i.DEST.exists(),'state_exists':i.STATE.exists(),'service_exists':pathlib.Path('/etc/systemd/system/vivameda-snapshot-archive.service').exists(),'timer_exists':pathlib.Path('/etc/systemd/system/vivameda-snapshot-archive.timer').exists()}
            return require(not any(flags.values()),flags)
        check('new_component_absent',absent,rows)
        def tests():
            for n in i.FILES:
                if n.endswith('.py'):compile((HERE/n).read_text(),n,'exec')
            r=command(['/usr/sbin/runuser','-u','vivameda-engineer','--','/usr/bin/python3','-m','unittest','discover','-s',str(HERE),'-p','test_archiver.py'])
            return {'compile_passed':True,'test_exit_code':r.returncode}
        check('synthetic_tests',tests,rows)
        def units():
            account=pwd.getpwnam(user);group=grp.getgrgid(account.pw_gid).gr_name
            with tempfile.TemporaryDirectory() as d:
                temp=pathlib.Path(d)
                for n in i.FILES[4:6]:(temp/n).write_text((HERE/n).read_text().replace('@USER@',user).replace('@GROUP@',group))
                command(['/usr/bin/systemd-analyze','verify',*[str(temp/n) for n in i.FILES[4:6]]])
            return {'syntax_verified':True}
        check('unit_syntax',units,rows);out['passed']=True
    except Gate as exc:out.update(passed=False,**exc.details)
    except Exception as exc:out.update(passed=False,blocker='diagnostic_import_or_structure',error_category=type(exc).__name__)
    # Fixed new-unit metadata only, even when a prior install failed part-way.
    out['new_timer']={}
    for field in ('ActiveState','UnitFileState'):
        try:
            raw=command(['/usr/bin/systemctl','show','vivameda-snapshot-archive.timer','--property='+field,'--value']).stdout.strip()
            out['new_timer'][field]=raw if raw in ('active','inactive','failed','enabled','disabled','static','masked','not-found','') else 'other'
        except Exception:out['new_timer'][field]='unavailable'
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expected-sha256',required=True);args=p.parse_args()
    if hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()!=args.expected_sha256:raise SystemExit('Diagnostic source hash mismatch')
    print(json.dumps(diagnose(),sort_keys=True))
