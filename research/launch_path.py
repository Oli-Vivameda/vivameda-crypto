"""Passive append-only launch receipts, for a separately reviewed post-stop hook."""
import datetime, fcntl, json, math, os, pathlib, re, shutil, sqlite3

ROOT=pathlib.Path('/var/lib/vivameda-crypto-earlier-entry/launch_path')
CAP=512*1024*1024
FREE=3*1024**3
RESERVE=1024*1024
RETENTION_DAYS=30

def value(x):return float(x) if type(x) in (int,float) and math.isfinite(x) and x>0 else None
def notice(root,ts,reason,dropped):
    # Local append-only aggregate only; never Telegram, mint or provider payload.
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(root/'incidents.jsonl',os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
    with os.fdopen(fd,'a') as out:
        out.write(json.dumps({'ts':ts,'reason':reason,'dropped_rows':dropped},sort_keys=True)+'\n');out.flush();os.fsync(out.fileno())

def normalize(rows,ts):
    by={};conflicts=set();invalid=0
    for x in rows:
        mint=x.get('mint');created=x.get('created_timestamp')
        if not isinstance(mint,str) or not re.fullmatch(r'[1-9A-HJ-NP-Za-km-z]{32,44}',mint) or type(created) is not int or not 0<created<=ts:
            invalid+=1;continue
        trade=x.get('last_trade_timestamp')
        row=(mint,ts,value(x.get('market_cap_usd')),value(x.get('ath_market_cap')),1 if x.get('complete') is True else 0,trade if type(trade) is int and 0<=trade<=ts else None)
        if mint in by and by[mint]!=row:conflicts.add(mint)
        by[mint]=row
    return [r for m,r in by.items() if m not in conflicts],invalid,len(conflicts)

def append_rows(rows,ts,root=ROOT,cap=CAP,min_free=FREE):
    root=pathlib.Path(root);root.mkdir(parents=True,exist_ok=True,mode=0o700)
    accepted,invalid,conflicts=normalize(rows,ts)
    day=datetime.datetime.fromtimestamp(ts/1000,datetime.timezone.utc).date().isoformat()
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if conflicts:notice(root,ts,'conflicting_batch_duplicates',conflicts)
        if invalid:notice(root,ts,'invalid_launch_identity_or_creation',invalid)
        partitions=sorted(root.glob('launch_path-*.sqlite'))
        oldest=partitions[0].stem.replace('launch_path-','') if partitions else day
        if (datetime.date.fromisoformat(day)-datetime.date.fromisoformat(oldest)).days>=RETENTION_DAYS:
            notice(root,ts,'retention_archive_review_required',len(accepted));return {'appended':0,'dropped':len(accepted),'reason':'retention_archive_review_required'}
        used=sum(p.stat().st_size for p in root.glob('launch_path-*.sqlite*'))
        # Conservatively reserve existing DB bytes again for a possible DELETE journal.
        if used*2+len(accepted)*4096+RESERVE>=cap or shutil.disk_usage(root).free<min_free:
            notice(root,ts,'storage_guard',len(accepted));return {'appended':0,'dropped':len(accepted),'reason':'storage_guard'}
        path=root/f'launch_path-{day}.sqlite';con=sqlite3.connect(path,timeout=.1)
        try:
            con.execute('PRAGMA journal_mode=DELETE');con.execute('PRAGMA synchronous=FULL')
            max_pages=max(1,(cap-used-RESERVE)//(2*4096));con.execute(f'PRAGMA max_page_count={max_pages}')
            con.executescript('''CREATE TABLE IF NOT EXISTS launch_path(mint TEXT NOT NULL,ts INTEGER NOT NULL,
              mc REAL,ath_mc REAL,complete INTEGER NOT NULL,last_trade_ts INTEGER,PRIMARY KEY(mint,ts));
              CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON launch_path BEGIN SELECT RAISE(ABORT,'append only'); END;
              CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON launch_path BEGIN SELECT RAISE(ABORT,'append only'); END;''')
            n=0;conflict=0
            with con:
                for row in accepted:
                    old=con.execute('SELECT * FROM launch_path WHERE mint=? AND ts=?',row[:2]).fetchone()
                    if old:
                        if old!=row:conflict+=1
                        continue
                    con.execute('INSERT INTO launch_path VALUES(?,?,?,?,?,?)',row);n+=1
            if conflict:notice(root,ts,'conflicting_persisted_duplicate',conflict)
            return {'appended':n,'duplicates':len(accepted)-n-conflict,'dropped':invalid+conflicts+conflict,'reason':'complete'}
        except (sqlite3.Error,OSError):
            con.rollback();notice(root,ts,'path_write_failed',len(accepted));return {'appended':0,'dropped':len(accepted),'reason':'path_write_failed'}
        finally:con.close()

