"""Root ExecStopPost: disable this new timer only on its local stop marker."""
import json, os, pathlib, stat, subprocess
ROOT=pathlib.Path('/var/lib/vivameda-snapshot-archive')
UNIT='vivameda-snapshot-archive.timer'
def run():
    if os.geteuid()!=0:raise PermissionError('root scoped postflight required')
    import archiver
    if os.environ.get('SERVICE_RESULT','success')!='success':archiver.stop(ROOT,'archiver_service_failed')
    try:
        with os.fdopen(os.open(ROOT/'run_started.json',os.O_RDONLY|os.O_NOFOLLOW)) as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('run marker type')
            started=json.loads(stream.read(4096))['time']
        if archiver.health_alarm_since(started):archiver.stop(ROOT,'health_incident_during_run')
    except Exception:archiver.stop(ROOT,'audit_postflight_unavailable')
    try:
        fd=os.open(ROOT/'STOP.json',os.O_RDONLY|os.O_NOFOLLOW)
    except FileNotFoundError:return
    with os.fdopen(fd) as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('marker type')
        data=json.loads(stream.read(4096))
    # Reason is never interpreted as code, arguments or another service name.
    subprocess.run(['/usr/bin/systemctl','disable','--now',UNIT],capture_output=True,check=True,timeout=10)
    archiver.atomic(ROOT/'timer_disabled.json',{'timer_disabled':True,'reason':data.get('reason','guard_failed')})
if __name__=='__main__':run()
