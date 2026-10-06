"""Deterministically build the reviewed two-file candidate, without importing it."""
import ast
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('source anchor changed: ' + before[:80])
    return source.replace(before, after, 1)


def build(base_scanner, base_tracker):
    tree = ast.parse((PACKAGE / 'capture.py').read_text())
    names = {n.name: 'fc_core_' + n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    names.update({'SIGNALS':'FC_CORE_SIGNALS', 'FIELDS':'FC_CORE_FIELDS'})
    class Rename(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in names: node.id = names[node.id]
            return node
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            if node.name in names: node.name = names[node.name]
            return node
    embedded = ast.unparse(Rename().visit(tree)) + '\n'
    score_node = next(n for n in ast.parse(base_scanner).body if isinstance(n,ast.FunctionDef) and n.name=='score_candidate')
    score_hash = hashlib.sha256(ast.dump(score_node,include_attributes=False).encode()).hexdigest()
    protocol_hash = hashlib.sha256((PACKAGE/'PROTOCOL.md').read_bytes()).hexdigest()
    adapter = (HERE/'runtime_adapter.py').read_text().replace('PROTOCOL_HASH_PLACEHOLDER',protocol_hash).replace('SCORER_HASH_PLACEHOLDER',score_hash)
    scanner = replace_once(base_scanner, '                out.extend(d)\n',
                           '                fc_observe_pairs(d, int(time.time()))\n                out.extend(d)\n')
    scanner = replace_once(scanner, 'ledger_captured_ns=None):', 'ledger_captured_ns=None, fc_cycle_id=None):')
    scanner = replace_once(scanner, '    if verdict != "PASS":\n',
                           '    if verdict != "PASS":\n        fc_emit_screening(mint, fc_cycle_id, verdict, False)\n')
    scanner = replace_once(scanner, '    except Exception:\n        try: ledger_delivery(con, ledger_seq, False)',
                           '    except Exception:\n        fc_emit_screening(mint, fc_cycle_id, "PASS", False)\n        try: ledger_delivery(con, ledger_seq, False)')
    scanner = replace_once(scanner, '    try: ledger_delivery(con, ledger_seq, True)',
                           '    fc_emit_screening(mint, fc_cycle_id, "PASS", True)\n    try: ledger_delivery(con, ledger_seq, True)')
    start = scanner.index('def enrich_and_score(con):')
    end = scanner.index('# Prospective ledger runtime',start)
    scanner = scanner[:start] + '''def enrich_and_score(con):
    cand = candidates(con)
    if not cand:
        fc_emit_cycle([], [], 0, str(time.time_ns()), int(time.time()))
        return
    by_mint = {}
    for p in dex_pairs([r[0] for r in cand]):
        by_mint.setdefault(p.get("baseToken",{}).get("address"), []).append(p)
    batch, failures = [], []
    for row in cand:
        mint, _, _, _, _, pinned = row
        pair = choose_pair(mint, by_mint.get(mint, []), pinned)
        if not pair:
            failures.append("pair_unavailable")
            continue
        record_pair(con, mint, pair)
        decision_rows = history(con, mint)
        captured_ns = time.time_ns()
        score, metrics, failed = score_candidate(decision_rows)
        prev = con.execute("SELECT alert_level FROM launches WHERE mint=?",(mint,)).fetchone()[0]
        if not metrics:
            failures.extend(failed if len(failed)==1 else ["invalid_score_inputs"])
            continue
        batch.append((row, pair, score, metrics, failed, prev, decision_rows, captured_ns))
    cycle_id, cycle_ts = str(time.time_ns()), int(time.time())
    cohort_ids = fc_emit_cycle(batch, failures, len(cand), cycle_id, cycle_ts)
    for row, pair, score, metrics, failed, prev, decision_rows, captured_ns in batch:
        mint = row[0]
        level = 2 if score >= 10 else (1 if score >= 8 else 0)
        if level > prev:
            try:
                alert(con, row, pair, score, metrics, level, decision_rows, captured_ns,
                      fc_cycle_id=cohort_ids.get(mint))
            except Exception as e:
                logging.exception("alert failed %s: %s", mint, e)

''' + scanner[end:]
    scanner = replace_once(scanner, 'if __name__ == "__main__":\n',
                           '# Passive forward capture: reviewed embedded core + adapter.\n'+embedded+'\n'+adapter+'\n\nif __name__ == "__main__":\n')
    tracker = replace_once(base_tracker, '   if isinstance(d,list):out.extend(d)',
                           '   if isinstance(d,list):\n    prod.fc_observe_pairs(d,int(time.time()))\n    out.extend(d)')
    return scanner, tracker


if __name__ == '__main__':
    scanner, tracker = build((HERE/'base_early_scout.py').read_text(), (HERE/'base_scout_learning_v2.py').read_text())
    (HERE/'early_scout.py').write_text(scanner)
    (HERE/'scout_learning_v2.py').write_text(tracker)
    print('Built dormant two-file integration candidate')
