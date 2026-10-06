#!/usr/bin/env python3
"""Read-only pilot health. No returns, identities or prices in output."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

BASE = Path('/opt/vivameda-crypto-early-scout')
STATE = Path('/var/lib/vivameda-crypto-pilot-health')
STALE_SECONDS = 600
RETRY_SECONDS = 300
UNITS = ('vivameda-early-scout.service', 'vivameda-scout-learning-v2.service')


def atomic_json(path, value, mode):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.health-')
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, sort_keys=True, allow_nan=False)
            out.write('\n'); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def collect(base=BASE, now=None, services=None):
    now = int(time.time()) if now is None else now
    report = {'checked_at': now, 'status': 'not_activated', 'reason': None,
              'live_execution': False, 'health_only': True}
    if services is None:
        services = {}
        for unit in UNITS:
            try:
                r = subprocess.run(['/usr/bin/systemctl', 'is-active', unit],
                                   capture_output=True, text=True, timeout=5)
                services[unit] = r.stdout.strip() == 'active'
            except Exception:
                services[unit] = False
    report['services'] = services
    directory = base/'data'/'forward_capture'
    database = directory/'capture.sqlite'
    try:
        if not database.exists(): return report
        report['storage_bytes'] = sum(p.stat().st_size for p in directory.glob('capture.sqlite*'))
        con = sqlite3.connect('file:'+str(database)+'?mode=ro', uri=True, timeout=.1)
        started = time.monotonic()
        con.set_progress_handler(lambda: int(time.monotonic()-started > 5), 1000)
        try:
            con.execute('PRAGMA query_only=ON'); con.execute('BEGIN')
            # Deliberately project only timestamps and counts from activation.
            activation, deadline = con.execute("SELECT json_extract(body,'$.activation_ts'),json_extract(body,'$.deadline') FROM fc_activation WHERE id=1").fetchone()
            report.update(activation_ts=activation, deadline=deadline)
            counts = dict(con.execute('SELECT kind,count(*) FROM fc_events GROUP BY kind'))
            report.update(cycles=counts.get('cycle',0), qualified_events=counts.get('cohort',0),
                          screening_events=counts.get('screening',0), timed_observation_rows=counts.get('observation',0))
            last = con.execute("SELECT max(json_extract(body,'$.cycle_ts')) FROM fc_events WHERE kind='cycle'").fetchone()[0]
            report['last_successful_cycle_ts'] = last
            report['seconds_since_last_cycle'] = now-(last if last is not None else activation)
            matched, controls = con.execute("SELECT coalesce(sum(json_array_length(body,'$.controls')>0),0),coalesce(sum(json_array_length(body,'$.controls')),0) FROM fc_events WHERE kind='cohort'").fetchone()
            report.update(matched_events=matched, control_entries=controls)
            # Identity joins remain inside SQLite; never select market caps or returns.
            # Closed windows only. Each control entry counts once per cohort.
            for label, entry_sql in (
                ('qualified', "SELECT json_extract(body,'$.alert_input') AS entry,json_extract(body,'$.index_ts') AS index_ts FROM fc_events WHERE kind='cohort'"),
                ('control', "SELECT c.value AS entry,json_extract(e.body,'$.index_ts') AS index_ts FROM fc_events e,json_each(e.body,'$.controls') c WHERE e.kind='cohort'")):
                total, covered = con.execute("WITH entries AS ("+entry_sql+") SELECT count(*),coalesce(sum(EXISTS(SELECT 1 FROM fc_events o WHERE o.kind='observation' AND json_extract(o.body,'$.mint')=json_extract(entries.entry,'$.mint') AND json_extract(o.body,'$.pair')=json_extract(entries.entry,'$.pair') AND json_extract(o.body,'$.received_ts') BETWEEN entries.index_ts+3600 AND entries.index_ts+3780)),0) FROM entries WHERE index_ts+3780 < ?", (now,)).fetchone()
                report[label+'_closed_windows'] = total
                report[label+'_covered_windows'] = covered
                report[label+'_missing_windows'] = total-covered
                report[label+'_coverage_pct'] = round(100*covered/total,2) if total else None
        finally:
            con.rollback(); con.close()
        report['status'] = 'stopped' if now >= deadline else 'collecting'
        if (directory/'PAUSED.json').exists():
            report.update(status='paused', reason='pilot_pause_marker')
        elif not all(services.values()):
            report.update(status='unhealthy', reason='production_service_inactive')
        elif now < deadline and report['seconds_since_last_cycle'] > STALE_SECONDS:
            report.update(status='stalled', reason='no_successful_cycle_for_10_minutes')
    except Exception:
        # Never publish exception text, private paths, rows or credentials.
        report.update(status='unavailable', reason='health_read_failed')
    return report


def message(report, recovery=False):
    prefix = 'Crypto pilot health recovered' if recovery else 'Crypto pilot health incident'
    return (prefix+'\nState: '+report['status']+'\nReason: '+str(report['reason'])+
            '\nChecked UTC epoch: '+str(report['checked_at'])+
            '\nCycles: '+str(report.get('cycles','unavailable'))+
            '\nMatched events: '+str(report.get('matched_events','unavailable'))+
            '\nNo prices, returns or token identities included.')


def send_telegram(text, credentials=BASE/'credentials.json'):
    # Same configured bot and destination as the existing scanner. No output/logging.
    c = json.loads(credentials.read_text())
    body = urllib.parse.urlencode({'chat_id': str(c['chat_id']), 'text': text,
                                  'disable_web_page_preview': 'true'}).encode()
    request = urllib.request.Request('https://api.telegram.org/bot'+c['bot_token']+'/sendMessage', data=body, method='POST')
    with urllib.request.urlopen(request, timeout=12) as response:
        result = json.load(response)
    if result.get('ok') is not True: raise ValueError('notification rejected')


def notify(report, state, sender=send_telegram):
    """One message per incident transition, retry failures after five minutes."""
    now = report['checked_at']
    incident = report['status'] if report['status'] in ('paused','stalled','unhealthy','unavailable') else None
    current = dict(state)
    desired = incident or ('recovered' if report['status']=='collecting' and current.get('sent_incident') else None)
    if desired is None or (incident and current.get('sent_incident') == incident):
        return current, 'idle'
    if now < current.get('last_attempt',0)+RETRY_SECONDS:
        return current, 'retry_wait'
    if current.get('pending') == desired and now < current.get('retry_at',0):
        return current, 'retry_wait'
    try:
        current['last_attempt'] = now
        sender(message(report, recovery=incident is None))
    except Exception:
        current.update(pending=desired, retry_at=now+RETRY_SECONDS)
        return current, 'delivery_failed'
    current.update(sent_incident=incident, pending=None, retry_at=0)
    return current, 'sent'


def run():
    report = collect()
    path = STATE/'notification_state.json'
    try: state = json.loads(path.read_text())
    except FileNotFoundError: state = {}
    except Exception:
        # Corrupt dedup state must not cause notification floods.
        report['notification'] = 'state_unreadable'
        atomic_json(STATE/'status.json',report,0o644)
        return
    # Publish health before network delivery so a Telegram outage cannot hide it.
    report['notification'] = 'pending_check'
    atomic_json(STATE/'status.json',report,0o644)
    state, result = notify(report,state)
    atomic_json(path,state,0o600)
    report['notification'] = result
    atomic_json(STATE/'status.json',report,0o644)


if __name__ == '__main__': run()
