# Verification

Observation configuration: CPython 3.12.3 on Linux; standard-library runtime; saved mock responses under tests/mock_responses; no real provider/model called and no API_KEY read by tests. Model-response provenance for committed extraction records is `mock`. The separate request-evidence.json example uses an injected saved-response transport with configured request model gpt-5-mini; it is not a live observation.

## Commands and intended comparisons

Run from the repository root:

```bash
env -u API_KEY python3 -m unittest discover -s tests -v
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 --provider mock intake materials/requests materials/paraphrase
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 queue
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 pending
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 export --output deliverables
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 accuracy --expected tests/expected/accuracy.json --output deliverables/accuracy.md
```

The suite compares extracted fixture facts and all five ordered routing outcomes to the independently authored source expectations. Named tests T01–T38 correspond to planning/plan.md. Each step has a failing-test commit before its implementation commit, with planning/step-NN-red.txt and step-NN-green.txt. The full final suite is recorded in planning/test-run.txt. A red import failure is evidence of the missing implementation at that checkpoint, not of a passing functional assertion.

The CLI commands compare original JSON-byte hashes, filename identity, response provenance, current queue links and record counts. An unchanged rerun should not create a second current record or make an unnecessary mock call. Changed input and configuration should retain prior attempts. queue and pending query the authoritative SQLite state while work proceeds; export publishes a generation for later file inspection.

A reviewer can assert the committed outputs directly without a provider:

```bash
python3 - <<'PY'
from pathlib import Path
from access_requests.contracts import load_document, validate_extraction
from access_requests.snapshots import read_export
from access_requests.accuracy import compare
import json
snapshot = read_export('deliverables')
rows = snapshot['extractions']
assert len(rows) == len({r['document_id'] for r in rows}) == 21
assert len(snapshot['queue']) == 21
for row in rows:
    directory = 'materials/paraphrase' if row['document_id'] == 'IT-P01.json' else 'materials/requests'
    source = load_document(Path(directory) / row['document_id'])
    assert row['source_sha256'] == source['source_sha256']
    assert row['response_source'] == 'mock'
    assert row['error'] is None
    validate_extraction(row['extraction'], source['message'])
expected = json.loads(Path('tests/expected/accuracy.json').read_text())
comparison = compare(rows, expected)
assert comparison['matched'] == comparison['denominator'] == 315
assert not comparison['factual_errors']
assert not comparison['supporting_quote_errors']
print('21 current mock records; original hashes, schema, source quotes, links, and 315 comparisons verified')
PY
```

read_export pins one immutable generation and checks matching queue/extraction document, hash and attempt links. Root JSON/JSONL files are convenience exports; read them after export completes, or use the manifest-aware reader for concurrent reads. The queue statuses and human owners must match the office-policy rules, not an automatic access approval.

## Assertions and cases

- T01: saved success/cut-off/error replies, ordered attempts, call tracing, deterministic pause/release, no credential or network dependency.
- T02–T03: UTF-8 message source, filename IDs, original-byte SHA-256, byte-only changes, 200-word input; required keys, scalar/array types, enums, additional properties, and exact substring evidence.
- T04–T09: all source-derived fields, malformed provider JSON/schema, refusal, incomplete response, provider errors, configurable request and redaction; all transports are mocked.
- T10–T20: complete staging/read, missing end date, conflicting environments/managers, override instructions, withdrawal with nulls, production/write/admin risk, explicit corrections, relative dates, mismatch, requested changed permission, completeness/date ordering and policy precedence.
- T21–T25: unchanged-success reuse, new source and retained original hash, failed retry after prior success, settings refresh with retained provenance, incremental batches and independent messages sharing a business request ID.
- T26–T31: two overlapping processes, recovery after an exited process left a running claim, a completed result while another request is gated, provider interruption with unaffected work completing, transactional rollback, and generated 400/2,000-message local mock batches.
- T32–T33: operator commands, visible errors and retry commands, immutable export generations and an injected manifest-publication failure that preserves the prior readable snapshot.
- T34–T36: authored paraphrase, all 21 independent expectation sets, exact counting, null mismatch, wrong facts, missing records and extraction-error denominator handling.
- T37–T38: runnable documented handover, lockfile, all five deliverable files, source hashes, schema and queue joins, request redaction, configuration and response-source labels.

## Operating limits

Shared operation is supported on one Linux host and local SQLite storage. One current pointer per document and immutable attempts are committed transactionally. Workers default to 4 (configurable 1–32); no model call holds a database write transaction. The most recently admitted source/configuration wins; an older finishing attempt cannot overwrite a newer desired version. Export timestamps are metadata, not ordering authorities. Source/configuration fingerprints include prompt, schema, policy, provider and model parameters; credentials are excluded.

The 400/2,000-message cases validate record counts, independent progress and coherent state with generated saved mock replies. There is no promised throughput or latency threshold, no production load test, and no observed live rate budget. Test duration includes setup, durable local storage and fixtures; it should not be treated as provider throughput.

Resume requeues abandoned claims only when the local owning PID is gone; live stalled processes and PID reuse have no lease mechanism. Resume with the original configuration. Host/power-loss durability, multi-host storage and network filesystems are not verified. Completed results and old hashes are retained, including after later failure; current errors do not silently use old successful facts. No automatic provider retry occurs: operators explicitly retry or force refresh, with network timeout 60 seconds by default. Malformed input export rejection currently terminates that intake command before extraction; correct it and rerun. Model/output failures are isolated to individual documents.

All accuracy observations use source-authored mocked replies. The recorded 315-cell score checks the software comparison and fixtures, not live semantic extraction or unseen attack resistance. Correction/override vocabulary beyond the tested cases is not exhaustively established. Purpose exact-string differences need human factual adjudication. The supplied JSON Schema vocabulary is validated directly; unsupported new schema keywords fail rather than being silently ignored. No third-party package installation or model access is needed for these reproducible examples.

## Observed results

The final Step 9 full-suite observation in planning/step-09-green.txt and planning/test-run.txt reports **41 tests in 38.281 seconds, OK**. The previously recorded Step 8 run had 39 tests, also OK. All five required artifacts were present when the final handover/artifact assertions executed.

Executed mock intake and manifest-aware inspection produced 21 current records: 20 supplied messages and authored IT-P01. Observed status counts: 12 review, 9 needs-information. Observed owners: System Owner 5, Security Review 5, IT Service Desk 11. All source hashes matched original bytes; all successful extractions matched the supplied schema and exact source-substring evidence; all provenance labels were mock; queue/extraction generation/document/hash/attempt links agreed.

The executed accuracy command recorded 315/315 exact scalar/routing matches, zero factual mismatches, zero unsupported quotes and zero extraction errors. This is a mock observation with per-record processing fingerprints in accuracy.md and extractions.jsonl. The default live request configuration was exercised only through a fake transport to create the redacted request evidence. No live-model result is reported.

Repairs observed during development: missing modules in the red test-first checkpoints were implemented in the following green commits. The rollback regression test T30 already passed after transactional storage existed and was not deliberately broken. No claim is made that a passing starter schema-name test validates actual extraction behavior.

## Test-run observation index

Every row below is a saved local test observation. Configuration for every row: CPython 3.12.3 on Linux, saved mock replies and fake transports, real provider/model not called, response source mock. The API model names exercised in fake request tests do not denote live observations. Phase red intentionally lacks the new implementation; phase green runs the full suite after that step. T30 was an already-passing regression in step 6.

| Log | Phase | Recorded result | Response source |
| --- | --- | --- | --- |
| planning/step-01-red.txt | red | Ran 4 tests in 0.004s; FAILED (errors=1) | mock |
| planning/step-01-test-run.txt | green | Ran 4 tests in 0.007s; OK | mock |
| planning/step-02-red.txt | red | Ran 6 tests in 0.010s; FAILED (errors=2) | mock |
| planning/step-02-green.txt | green | Ran 6 tests in 0.017s; OK | mock |
| planning/step-03-red.txt | red | Ran 12 tests in 0.020s; FAILED (errors=6) | mock |
| planning/step-03-green.txt | green | Ran 12 tests in 0.041s; OK | mock |
| planning/step-04-red.txt | red | Ran 23 tests in 0.052s; FAILED (errors=11) | mock |
| planning/step-04-green.txt | green | Ran 23 tests in 0.056s; OK | mock |
| planning/step-05-red.txt | red | Ran 28 tests in 0.051s; FAILED (errors=5) | mock |
| planning/step-05-green.txt | green | Ran 28 tests in 0.366s; OK | mock |
| planning/step-06-red.txt | red | Ran 34 tests in 6.633s; FAILED (failures=2, errors=4) | mock |
| planning/step-06-green.txt | green | Ran 34 tests in 38.434s; OK | mock |
| planning/step-07-red.txt | red | Ran 36 tests in 86.422s; FAILED (errors=2) | mock |
| planning/step-07-green.txt | green | Ran 36 tests in 53.273s; OK | mock |
| planning/step-08-red.txt | red | Ran 39 tests in 37.568s; FAILED (errors=3) | mock |
| planning/step-08-green.txt | green | Ran 39 tests in 37.836s; OK | mock |
| planning/step-09-red.txt | red | Ran 2 tests in 0.007s; FAILED (failures=2) | mock |
| planning/step-09-green.txt | green | Ran 41 tests in 38.281s; OK | mock |
