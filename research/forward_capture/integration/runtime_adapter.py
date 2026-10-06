"""Embedded into early_scout.py by build_integration.py; no extra imports/files.

Core functions have fc_core_ names. Integration remains dormant unless a
separately reviewed activation creates the private database and binding.
"""
FC_DIRECTORY = BASE / 'data' / 'forward_capture'
FC_PROTOCOL_SHA256 = 'PROTOCOL_HASH_PLACEHOLDER'
FC_SCORER_SHA256 = 'SCORER_HASH_PLACEHOLDER'
FC_MAX_BYTES = 512 * 1024 * 1024
FC_MIN_DISK_BYTES = 2 * 1024 * 1024 * 1024
_fc_connection = None
_fc_verified = (0, '0' * 64)
_fc_paused = False


def fc_guard(con):
    """Full verification on process open; then anchored append verification.

    Old rows are protected by immutable triggers. Privileged rewrite of an
    old prefix is detected at restart/full audit, not guaranteed each append.
    """
    global _fc_verified
    seq, previous = _fc_verified
    if seq:
        anchor = con.execute('SELECT seq,kind,event_key,body,previous_hash,hash FROM fc_events WHERE seq=?', (seq,)).fetchone()
        if not anchor or anchor[-1] != previous or anchor[-1] != fc_core_digest(list(anchor[:-1])):
            raise ValueError('capture anchor changed')
    for row in con.execute('SELECT * FROM fc_events WHERE seq>? ORDER BY seq', (seq,)):
        n, kind, key, body, prev, h = row
        if n != seq + 1 or prev != previous or h != fc_core_digest([n, kind, key, body, prev]):
            raise ValueError('capture append chain changed')
        seq, previous = n, h
    _fc_verified = (seq, previous)
    return previous


def fc_pause(error):
    global _fc_paused
    _fc_paused = True
    logging.error('FORWARD_CAPTURE_PAUSED reason=%s', type(error).__name__)
    try:
        # Count-only health artifact. No identities, endpoints or exception text.
        if FC_DIRECTORY.is_dir():
            p = FC_DIRECTORY / 'PAUSED.json'
            import os
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as out:
                out.write(json.dumps({'paused': True, 'reason': type(error).__name__,
                                      'observed_ts': int(time.time())}))
    except OSError:
        logging.error('FORWARD_CAPTURE_PAUSE_MARKER_FAILED')


def fc_connection():
    global _fc_connection, _fc_verified
    if _fc_paused or (FC_DIRECTORY / 'PAUSED.json').exists():
        return None
    database = FC_DIRECTORY / 'capture.sqlite'
    if not database.exists():
        return None  # No autoactivation, schema creation or private-file writes.
    import shutil
    if sum(p.stat().st_size for p in FC_DIRECTORY.glob('capture.sqlite*')) >= FC_MAX_BYTES:
        raise ValueError('capture storage cap')
    if shutil.disk_usage(FC_DIRECTORY).free < FC_MIN_DISK_BYTES:
        raise ValueError('capture minimum free disk')
    if _fc_connection is None:
        con = sqlite3.connect('file:' + str(database) + '?mode=rw', uri=True, timeout=0.1)
        try:
            con.execute('PRAGMA busy_timeout=100')
            con.execute('PRAGMA synchronous=FULL')
            a = fc_core_activation(con)
            if a['protocol_sha256'] != FC_PROTOCOL_SHA256 or a['scanner_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
                raise ValueError('capture runtime binding')
            if a['tracker_sha256'] != hashlib.sha256(Path(__file__).with_name('scout_learning_v2.py').read_bytes()).hexdigest():
                raise ValueError('capture tracker binding')
            # No runtime trigger installation: reviewed activation owns schema.
            names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
            if not {'fc_activation_no_UPDATE', 'fc_activation_no_DELETE',
                    'fc_events_no_UPDATE', 'fc_events_no_DELETE',
                    'fc_excluded_no_UPDATE', 'fc_excluded_no_DELETE', 'fc_excluded_frozen'} <= names:
                raise ValueError('capture immutability triggers missing')
            exclusions = [r[0] for r in con.execute('SELECT mint FROM fc_excluded ORDER BY mint')]
            if len(exclusions) != a['excluded_count'] or fc_core_digest(exclusions) != a['excluded_sha256']:
                raise ValueError('capture exclusion binding')
            fc_core_verify(con)
            head = con.execute('SELECT seq,hash FROM fc_events ORDER BY seq DESC LIMIT 1').fetchone()
            _fc_verified = tuple(head) if head else (0, '0'*64)
            _fc_connection = con
        except BaseException:
            con.close()
            raise
    return _fc_connection


def fc_emit_cycle(batch, failures, selected_count, cycle_id, cycle_ts):
    """Persist raw exact rows and the admitted common cycle atomically."""
    try:
        con = fc_connection()
        if con is None:
            return {}
        a = fc_core_activation(con)
        if cycle_ts >= a['deadline']:
            return {}
        if selected_count > 60 or len(batch) + len(failures) != selected_count:
            raise ValueError('incomplete candidate accounting')
        if any(reason not in ('history', 'base_gate', 'price_history') for reason in failures):
            raise ValueError('provider or capture failure invalidates cycle')
        rows = []
        for item in batch:
            row, pair, score, metrics, failed, prev, history_rows, captured_ns = item
            mint, created_ms, _, _, _, _ = row
            captured_ts = captured_ns // 1000000000
            if not metrics:
                continue
            exact = [list(r) for r in history_rows]
            signals = {k: k not in failed for k in FC_CORE_SIGNALS}
            record = {'mint': mint, 'pair': pair['pairAddress'], 'created_ts': int(created_ms // 1000),
                      'captured_ts': captured_ts, 'snapshot_ts': int(history_rows[-1][0]),
                      'points': len(history_rows), 'history_seconds': int(history_rows[-1][0]-history_rows[0][0]),
                      'mc': metrics['mc'], 'liq': metrics['liq'], 'vol1': metrics['vol1'],
                      'score': score, 'signals': signals, 'prior_alert_level': prev,
                      'input_sha256': fc_core_digest(exact)}
            fc_core_validate(record, cycle_ts)
            # Validate exact vector against unchanged production scorer.
            actual_score, actual_metrics, actual_failed = score_candidate(exact)
            if actual_score != score or actual_metrics != metrics or actual_failed != failed:
                raise ValueError('exact score replay mismatch')
            rows.append((record, exact))
        con.execute('BEGIN IMMEDIATE')
        try:
            fc_guard(con)
            fc_core_append(con, 'cycle_health', cycle_id, {'cycle_ts': cycle_ts,
                           'selected': selected_count, 'scored': len(rows),
                           'admission_failures': sorted(failures)})
            # Keep immutable raw input evidence private, once per content hash.
            for record, exact in rows:
                fc_core_append(con, 'inputs', record['input_sha256'], exact)
            cohorts = fc_core_record_cycle(con, cycle_id, cycle_ts, [r for r, _ in rows],
                                         a['scanner_sha256'], verifier=fc_guard)
            return {r['mint']: cycle_id for r in cohorts}
        except BaseException:
            con.rollback()
            raise
    except Exception as error:
        fc_pause(error)
        return {}


def fc_emit_screening(mint, cycle_id, verdict, delivered):
    if cycle_id is None:
        return
    try:
        con = fc_connection()
        if con is None:
            return
        con.execute('BEGIN IMMEDIATE')
        fc_core_record_screening(con, mint, cycle_id, int(time.time()), verdict, delivered, verifier=fc_guard)
    except Exception as error:
        if _fc_connection is not None:
            _fc_connection.rollback()
        fc_pause(error)


def fc_count_status():
    """Operational counts only; never probabilities, multiples or identities."""
    try:
        con = fc_connection()
        if con is None:
            return {'status': 'paused' if _fc_paused or (FC_DIRECTORY/'PAUSED.json').exists() else 'not_activated'}
        a = fc_core_activation(con)
        cohorts = [json.loads(r[0]) for r in con.execute("SELECT body FROM fc_events WHERE kind='cohort'")]
        return {'status': 'enrollment_stopped' if int(time.time()) >= a['deadline'] else 'collecting',
                'activation_ts': a['activation_ts'], 'deadline': a['deadline'],
                'cycles': con.execute("SELECT count(*) FROM fc_events WHERE kind='cycle'").fetchone()[0],
                'qualified_events': len(cohorts),
                'matched_events': sum(bool(r['controls']) for r in cohorts),
                'control_entries': sum(len(r['controls']) for r in cohorts),
                'screening_events': con.execute("SELECT count(*) FROM fc_events WHERE kind='screening'").fetchone()[0],
                'timed_observation_rows': con.execute("SELECT count(*) FROM fc_events WHERE kind='observation'").fetchone()[0]}
    except Exception as error:
        fc_pause(error)
        return {'status':'paused'}


def fc_observe_pairs(pairs, received_ts):
    """Accept only already fetched pairs; no new request or polling selection."""
    try:
        con = fc_connection()
        if con is None:
            return
        a = fc_core_activation(con)
        if received_ts > a['deadline'] + 3780:
            return
        # Only store endpoint-window observations relevant to frozen cohorts.
        wanted = set()
        for (body,) in con.execute("SELECT body FROM fc_events WHERE kind='cohort'"):
            cohort = json.loads(body)
            if cohort['index_ts'] + 3600 <= received_ts <= cohort['index_ts'] + 3780:
                for entry in [cohort['alert_input']] + cohort['controls']:
                    wanted.add((entry['mint'], entry['pair']))
        if not wanted:
            return
        con.execute('BEGIN IMMEDIATE')
        try:
            fc_guard(con)
            for pair in pairs:
                mint = (pair.get('baseToken') or {}).get('address')
                identity = (mint, pair.get('pairAddress'))
                mc = pair.get('marketCap')
                # Invalid/unavailable evidence remains missing, never zero.
                if identity not in wanted or not fc_core_number(mc, 0.000001):
                    continue
                fc_core_append(con, 'observation', fc_core_canonical([*identity, received_ts]),
                               {'mint': mint, 'pair': identity[1], 'received_ts': received_ts, 'mc': mc})
            con.commit()
        except BaseException:
            con.rollback()
            raise
    except Exception as error:
        fc_pause(error)
