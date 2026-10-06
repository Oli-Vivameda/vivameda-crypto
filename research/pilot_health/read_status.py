#!/usr/bin/env python3
"""Read sanitized report only, never the protected pilot database."""
import json
from pathlib import Path
import time

if __name__ == '__main__':
    p=Path('/var/lib/vivameda-crypto-pilot-health/status.json')
    if not p.exists():
        print(json.dumps({'status':'monitor_not_installed'}))
    else:
        report=json.loads(p.read_text())
        age=int(time.time())-report['checked_at']
        report['report_age_seconds']=age
        if age>300 or age<0:
            report['capture_status_last_report']=report['status']
            report['status']='monitor_stale'
        print(json.dumps(report,sort_keys=True))
