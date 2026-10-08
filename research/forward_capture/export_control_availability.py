"""Read-only availability aggregates. Never select observations or endpoint values."""
import argparse, collections, datetime, hashlib, json, pathlib, sqlite3
DB=pathlib.Path('/opt/vivameda-crypto-early-scout/data/forward_capture/capture.sqlite')
def collect(path=DB):
 con=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=2)
 con.execute('PRAGMA query_only=ON');con.execute('BEGIN')
 try:
  exposure=con.execute("SELECT json_extract(body,'$.activation_ts'),json_extract(body,'$.deadline') FROM fc_activation WHERE id=1").fetchone()
  rows=con.execute("SELECT strftime('%Y-%m-%d',json_extract(body,'$.cycle_ts'),'unixepoch'),strftime('%Y-%m-%dT%H:00Z',json_extract(body,'$.cycle_ts'),'unixepoch'),count(*),sum(json_extract(body,'$.selected')),sum(json_extract(body,'$.pair_unavailable')),sum(json_extract(body,'$.scored_discarded')) FROM fc_events WHERE kind='rejected_cycle' GROUP BY 1,2").fetchall()
  hourly=[dict(zip(('utc_day','utc_hour','cycles','candidate_pairs','unavailable_pairs','discarded_batch_entries'),r)) for r in rows]
  daily={}
  for r in hourly:
   d=daily.setdefault(r['utc_day'],dict(cycles=0,candidate_pairs=0,unavailable_pairs=0,discarded_batch_entries=0))
   for k in d:d[k]+=r[k] or 0
  # Identities remain inside SQLite joins. Project only counts of each rule.
  sql='''WITH events AS (SELECT event_key,body,json_extract(body,'$.cycle_id') cid FROM fc_events WHERE kind='cohort'),
  candidates AS (SELECT e.event_key,e.body alert,c.value row,
    EXISTS(SELECT 1 FROM fc_excluded x WHERE x.mint=json_extract(c.value,'$.mint')) excluded,
    EXISTS(SELECT 1 FROM fc_events z WHERE z.kind='cohort' AND z.seq<cy.seq AND z.event_key=json_extract(c.value,'$.mint')) qualified_before
    FROM events e JOIN fc_events cy ON cy.kind='cycle' AND cy.event_key=e.cid,json_each(cy.body,'$.rows') c
    WHERE json_extract(c.value,'$.mint')!=e.event_key),
  rules AS (SELECT *,json_extract(row,'$.score')<8 s,
    json_extract(row,'$.points')>=4 AND json_extract(row,'$.history_seconds')>=600 AND json_extract(row,'$.mc') BETWEEN 30000 AND 750000 AND json_extract(row,'$.liq')>=25000 AND json_extract(row,'$.vol1')>=20000 b,
    abs((json_extract(row,'$.captured_ts')-json_extract(row,'$.created_ts'))-(json_extract(alert,'$.alert_input.captured_ts')-json_extract(alert,'$.alert_input.created_ts')))<=900 a,
    json_extract(row,'$.mc')/json_extract(alert,'$.alert_input.mc') BETWEEN .5 AND 2 AND json_extract(row,'$.liq')/json_extract(alert,'$.alert_input.liq') BETWEEN .5 AND 2 m,
    json_extract(row,'$.prior_alert_level')=0 p FROM candidates)
  SELECT count(*),coalesce(sum(s),0),coalesce(sum(s AND b),0),coalesce(sum(s AND b AND NOT excluded AND NOT qualified_before AND p),0),coalesce(sum(s AND b AND NOT excluded AND NOT qualified_before AND p AND a),0),coalesce(sum(s AND b AND NOT excluded AND NOT qualified_before AND p AND a AND m),0),count(DISTINCT CASE WHEN s AND b AND NOT excluded AND NOT qualified_before AND p THEN event_key END) FROM rules'''
  n=con.execute(sql).fetchone();names=('other_same_cycle_entries','score_below_8','basic_eligible','not_excluded_not_prequalified_no_prior_alert','age_within_15_minutes','cap_liquidity_factor_2','events_with_eligible_candidate_before_age_size_matching')
  funnel=dict(zip(names,n))
  qualified,matched,controls=con.execute("SELECT count(*),coalesce(sum(json_array_length(body,'$.controls')>0),0),coalesce(sum(json_array_length(body,'$.controls')),0) FROM fc_events WHERE kind='cohort'").fetchone()
  unique=con.execute("SELECT count(DISTINCT json_extract(c.value,'$.mint')) FROM fc_events e,json_each(e.body,'$.controls') c WHERE e.kind='cohort'").fetchone()[0]
  accepted=con.execute("SELECT count(*) FROM fc_events WHERE kind='cycle'").fetchone()[0]
  return dict(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),activation_ts=exposure[0],deadline=exposure[1],accepted_cycles=accepted,qualified_events=qualified,matched_events=matched,control_entries=controls,unique_control_tokens=unique,reused_control_entries=controls-unique,reuse_rule='allowed; no control-reuse rejection in frozen code',funnel=funnel,rejected_by_utc_hour=hourly,rejected_by_utc_day=daily,counterfactual=dict(exact_extra_events=None,exact_extra_controls=None,reason='rejected_cycle_does_not_retain_scored_rows',discarded_batch_entries=sum((r['discarded_batch_entries'] or 0) for r in hourly),lower_bound_extra_events=0,lower_bound_extra_controls=0),pilot_modified=False,outcomes_read=False,endpoint_values_read=False,identities_exported=False,provider_requests=0)
 finally:con.rollback();con.close()
def main():
 p=argparse.ArgumentParser();p.add_argument('--expected-sha256',required=True);a=p.parse_args()
 if hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()!=a.expected_sha256:raise SystemExit('Reviewed exporter hash mismatch')
 try:out=collect()
 except (sqlite3.Error,OSError):out=dict(available=False,reason='private_source_unavailable',permissions_changed=False,pilot_modified=False,provider_requests=0)
 print(json.dumps(out,sort_keys=True,allow_nan=False))
if __name__=='__main__':main()
