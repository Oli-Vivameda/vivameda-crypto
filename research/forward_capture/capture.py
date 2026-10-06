"""Private, passive candidate capture. No network, production imports or trading.

Caller supplies exact scanner inputs and provider-response receipt times.
This module is an engineering candidate; no runtime integration is activated.
"""
import hashlib
import json
import math
import sqlite3

SIGNALS = ('liq25k', 'vol_mc25', 'buy52', 'h1_not_extended',
           'm5_not_extended', 'band_compact', 'net_constructive',
           'higher_low', 'liq_stable', 'volume_accel', 'txns100')
FIELDS = {'mint', 'pair', 'created_ts', 'captured_ts', 'snapshot_ts',
          'points', 'history_seconds', 'mc', 'liq', 'vol1', 'score', 'signals',
          'prior_alert_level', 'input_sha256'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def number(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def validate(row, cycle_ts):
    if set(row) != FIELDS:
        raise ValueError('unexpected or missing decision fields')
    for key in ('mint', 'pair'):
        if not isinstance(row[key], str) or not 1 <= len(row[key]) <= 100:
            raise ValueError(key)
    for key in ('created_ts', 'captured_ts', 'snapshot_ts', 'points',
                'history_seconds', 'score', 'prior_alert_level'):
        if not integer(row[key]):
            raise ValueError(key)
    if not row['created_ts'] <= row['captured_ts'] <= cycle_ts:
        raise ValueError('future decision or creation')
    if not 1800 <= row['captured_ts'] - row['created_ts'] <= 21600:
        raise ValueError('outside current scanner age universe')
    if not 0 <= row['captured_ts'] - row['snapshot_ts'] <= 120:
        raise ValueError('stale or future snapshot')
    if cycle_ts - row['captured_ts'] > 120:
        raise ValueError('cycle inputs not contemporaneous')
    for key in ('mc', 'liq', 'vol1'):
        if not number(row[key]):
            raise ValueError(key)
    s = row['signals']
    if (not isinstance(s, dict) or set(s) != set(SIGNALS)
            or any(type(v) is not bool for v in s.values())
            or row['score'] != sum(s.values())):
        raise ValueError('exact emitted signal vector required')
    h = row['input_sha256']
    if not isinstance(h, str) or len(h) != 64 or any(c not in '0123456789abcdef' for c in h):
        raise ValueError('input hash')
    return row


def eligible(row):
    return (row['points'] >= 4 and row['history_seconds'] >= 600
            and 30000 <= row['mc'] <= 750000 and row['liq'] >= 25000
            and row['vol1'] >= 20000)


def matched_controls(alert, rows):
    """Same-cycle, outcome-blind controls; do not match score components."""
    age = alert['captured_ts'] - alert['created_ts']
    possible = []
    for row in rows:
        if (row['mint'] == alert['mint'] or not eligible(row)
                or row['score'] >= 8 or row['prior_alert_level'] != 0):
            continue
        control_age = row['captured_ts'] - row['created_ts']
        if abs(control_age - age) > 900:
            continue
        if not (0.5 <= row['mc'] / alert['mc'] <= 2
                and 0.5 <= row['liq'] / alert['liq'] <= 2):
            continue
        distance = (abs(control_age - age) / 900
                    + abs(math.log(row['mc'] / alert['mc']))
                    + abs(math.log(row['liq'] / alert['liq'])))
        possible.append((distance, row['mint'], row))
    return [r for _, _, r in sorted(possible)[:3]]


def initialize(con, activation_ts, excluded_mints, protocol_sha256, runtime_binding=None):
    """Explicit initialization only. Runtime lives outside the git checkout."""
    if (not integer(activation_ts) or not isinstance(protocol_sha256, str)
            or len(protocol_sha256) != 64
            or any(c not in '0123456789abcdef' for c in protocol_sha256)):
        raise ValueError('activation')
    con.executescript('''
    CREATE TABLE IF NOT EXISTS fc_activation(id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS fc_excluded(mint TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS fc_events(seq INTEGER PRIMARY KEY, kind TEXT NOT NULL,
      event_key TEXT NOT NULL, body TEXT NOT NULL, previous_hash TEXT NOT NULL,
      hash TEXT NOT NULL, UNIQUE(kind,event_key));
    ''')
    for table in ('fc_activation', 'fc_events', 'fc_excluded'):
        for op in ('UPDATE', 'DELETE'):
            con.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'capture append only'); END")
    exclusions = sorted(set(excluded_mints))
    if any(not isinstance(m, str) or not m for m in exclusions):
        raise ValueError('exclusions')
    con.execute("CREATE TRIGGER IF NOT EXISTS fc_excluded_frozen BEFORE INSERT ON fc_excluded WHEN EXISTS(SELECT 1 FROM fc_activation) BEGIN SELECT RAISE(ABORT,'exclusions frozen'); END")
    body_value = {'activation_ts': activation_ts, 'deadline': activation_ts + 14 * 86400,
                  'excluded_count': len(exclusions), 'excluded_sha256': digest(exclusions),
                  'protocol_sha256': protocol_sha256, 'schema': 1}
    if runtime_binding is not None:
        if set(runtime_binding) != {'scanner_sha256', 'tracker_sha256'}:
            raise ValueError('runtime binding fields')
        if any(not isinstance(v, str) or len(v) != 64 or any(ch not in '0123456789abcdef' for ch in v)
               for v in runtime_binding.values()):
            raise ValueError('runtime binding hashes')
        body_value.update(runtime_binding)
    body = canonical(body_value)
    existing = con.execute('SELECT body FROM fc_activation').fetchone()
    if existing and existing[0] != body:
        raise ValueError('activation cannot change')
    if not existing:
        con.executemany('INSERT INTO fc_excluded VALUES(?)', [(m,) for m in exclusions])
        con.execute('INSERT INTO fc_activation VALUES(1,?)', (body,))
    con.commit()


def activation(con):
    row = con.execute('SELECT body FROM fc_activation').fetchone()
    if not row:
        raise ValueError('not activated')
    return json.loads(row[0])


def append(con, kind, key, payload):
    body = canonical(payload)
    existing = con.execute('SELECT body,hash FROM fc_events WHERE kind=? AND event_key=?', (kind, key)).fetchone()
    if existing:
        if existing[0] != body:
            raise ValueError('conflicting replay')
        return existing[1]
    last = con.execute('SELECT seq,hash FROM fc_events ORDER BY seq DESC LIMIT 1').fetchone()
    seq, previous = (last[0] + 1, last[1]) if last else (1, '0' * 64)
    h = digest([seq, kind, key, body, previous])
    con.execute('INSERT INTO fc_events VALUES(?,?,?,?,?,?)', (seq, kind, key, body, previous, h))
    return h


def verify(con):
    previous = '0' * 64
    for expected, (seq, kind, key, body, prev, h) in enumerate(con.execute(
            'SELECT * FROM fc_events ORDER BY seq'), 1):
        if seq != expected or prev != previous or h != digest([seq, kind, key, body, prev]):
            raise ValueError('capture integrity failed')
        previous = h
    return previous


def record_cycle(con, cycle_id, cycle_ts, rows, scanner_sha256, verifier=verify):
    """Atomic complete evaluated cycle; capture before screening/delivery.

    Input errors reject the whole cycle. Outcome fields are not accepted.
    The adapter must pass EVERY successfully scored input, not a score subset.
    """
    if not integer(cycle_ts) or not isinstance(cycle_id, str) or not cycle_id:
        raise ValueError('cycle')
    if (not isinstance(scanner_sha256, str) or len(scanner_sha256) != 64
            or any(c not in '0123456789abcdef' for c in scanner_sha256)):
        raise ValueError('scanner hash')
    a = activation(con)
    if cycle_ts < a['activation_ts']:
        raise ValueError('preactivation cycle')
    if cycle_ts >= a['deadline']:
        raise ValueError('pilot enrollment stopped')
    checked = sorted([validate(dict(r), cycle_ts) for r in rows], key=lambda r: r['mint'])
    if len({r['mint'] for r in checked}) != len(checked):
        raise ValueError('duplicate mint in cycle')
    if any(r['captured_ts'] < a['activation_ts'] for r in checked):
        raise ValueError('preactivation input')
    if len(checked) > 60:
        raise ValueError('cycle exceeds current scanner cap')
    if any(eligible(r) and not r['signals']['liq25k'] for r in checked):
        raise ValueError('eligible row contradicts liquidity signal')
    excluded = {r['mint'] for r in checked if con.execute('SELECT 1 FROM fc_excluded WHERE mint=?', (r['mint'],)).fetchone()}
    with con:
        verifier(con)
        key = str(cycle_id)
        payload = {'cycle_ts': cycle_ts, 'scanner_sha256': scanner_sha256, 'rows': checked}
        existing = con.execute("SELECT body FROM fc_events WHERE kind='cycle' AND event_key=?", (key,)).fetchone()
        if existing:
            append(con, 'cycle', key, payload)
            return []
        append(con, 'cycle', key, payload)
        enrolled = {json.loads(r[0])['mint'] for r in con.execute("SELECT body FROM fc_events WHERE kind='cohort'")}
        added = []
        for row in checked:
            if (row['mint'] in excluded or row['mint'] in enrolled or not eligible(row)
                    or row['score'] < 8 or row['prior_alert_level'] != 0):
                continue
            controls = matched_controls(row, [r for r in checked if r['mint'] not in excluded and r['mint'] not in enrolled])
            cohort = {'mint': row['mint'], 'cycle_id': key, 'index_ts': cycle_ts,
                      'alert_input': row, 'controls': controls, 'screening': 'not_yet_observed'}
            append(con, 'cohort', row['mint'], cohort)
            added.append(cohort)
        return added


def record_screening(con, mint, cycle_id, observed_ts, verdict, delivered, verifier=verify):
    if verdict not in ('PASS', 'HOLD', 'REJECT', 'ERROR') or type(delivered) is not bool:
        raise ValueError('screening')
    if delivered and verdict != 'PASS':
        raise ValueError('delivery without pass')
    row = con.execute("SELECT body FROM fc_events WHERE kind='cohort' AND event_key=?", (mint,)).fetchone()
    if not row:
        raise ValueError('cohort missing')
    cohort = json.loads(row[0])
    if cycle_id != cohort['cycle_id'] or not integer(observed_ts) or observed_ts < cohort['index_ts']:
        raise ValueError('screening timing')
    with con:
        verifier(con)
        return append(con, 'screening', mint, {'observed_ts': observed_ts, 'verdict': verdict,
                                             'delivered': delivered})


def record_observation(con, mint, pair, received_ts, mc, verifier=verify):
    if any(not isinstance(s, str) or not 1 <= len(s) <= 100 for s in (mint, pair)):
        raise ValueError('observation identity')
    if not integer(received_ts) or not number(mc, 0.000001):
        raise ValueError('observation')
    a = activation(con)
    if received_ts < a['activation_ts']:
        raise ValueError('preactivation observation')
    if received_ts > a['deadline'] + 3780:
        raise ValueError('pilot follow-up stopped')
    with con:
        verifier(con)
        return append(con, 'observation', canonical([mint, pair, received_ts]),
                      {'mint': mint, 'pair': pair, 'received_ts': received_ts, 'mc': mc})


def endpoint(con, entry, index_ts, now):
    """Pure read after window closes. Earliest valid same-pair local receipt."""
    if not integer(now) or now <= index_ts + 3780:
        raise ValueError('endpoint window still open')
    verify(con)
    observations = [json.loads(r[0]) for r in con.execute("SELECT body FROM fc_events WHERE kind='observation'")]
    rows = sorted((r for r in observations if r['mint'] == entry['mint']
                   and r['pair'] == entry['pair']
                   and index_ts + 3600 <= r['received_ts'] <= index_ts + 3780),
                  key=lambda r: r['received_ts'])
    if not rows:
        return {'eligible': False, 'reason': 'missing_timed_same_pair_endpoint', 'multiple': None}
    r = rows[0]
    return {'eligible': True, 'received_ts': r['received_ts'],
            'lateness': r['received_ts'] - index_ts - 3600, 'multiple': r['mc'] / entry['mc']}
