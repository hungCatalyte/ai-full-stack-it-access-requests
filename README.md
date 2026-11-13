# Northstar access-request intake

A Python 3.11+ CLI prepares access requests for human review. It extracts facts through a configurable OpenAI Responses adapter or saved mock replies, validates them against snapshot.schema.json, and applies the five office-policy rules. It never grants access or approves a request. A named manager is a contact; Security Review recommends a decision to the System Owner.

## Setup

Use Linux, Python 3.11 or newer with sqlite3 and fcntl, and run commands from the repository root. This submission was checked on CPython 3.12.3. No external packages are required: requirements.lock records the empty third-party dependency set. No installation, model account, API key, or network is required for mock intake and tests.

```bash
python3 --version
python3 -m access_requests --help
```

The supplied schema's object, string/null, array, enum, required, and additionalProperties constraints are validated explicitly. The application does not claim to support arbitrary JSON Schema dialects: introducing unknown schema keywords fails explicitly until supported.

## Reproducible mock intake and queue

These commands process the 20 supplied messages plus the independently authored paraphrase. The original 20-file input directory is unchanged. Saved replies are in tests/mock_responses; independent source-derived expectations are in tests/expected/accuracy.json.

```bash
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 --provider mock intake materials/requests materials/paraphrase
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 queue
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 pending
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 history IT-001.json
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 export --output deliverables
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 accuracy --expected tests/expected/accuracy.json --output deliverables/accuracy.md
```

Run queue or pending in a second terminal while intake is active; results are persisted individually as they complete. Each queue entry shows status, owner, and next_action. An unchanged successful rerun reuses results. Omitting a document in a later batch retains its current record. Different filenames remain different documents even when the business request ID is shared. Filename/request-ID mismatches are reported as issues.

An error record has null extraction and status error / IT Service Desk / retry-extraction. Queue output includes a reproducible retry_command. A retry can intentionally refresh a prior success; if it fails, the error becomes current and the earlier valid result remains in history. Unchanged errors are reused on an ordinary rerun and require explicit retry. No automatic retries occur.

```bash
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 --provider mock retry IT-001.json
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 --provider mock resume
```

Use the same provider/model/endpoint/token/timeout settings when resuming pending work. For a changed source, run intake again; use intake with --force to refresh unchanged documents intentionally. A relevant model, prompt, schema, or policy change creates a new processing fingerprint and retains earlier results. Source revisions hash original JSON bytes, including metadata/whitespace changes. Runtime state and immutable attempt history live in the selected SQLite database, outside current JSON exports; do not discard that database when resuming work.

## Tests and accuracy

```bash
env -u API_KEY python3 -m unittest discover -s tests -v
env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 accuracy --expected tests/expected/accuracy.json --output deliverables/accuracy.md
```

Tests read saved mock replies, block sockets, and never read API_KEY. The expected facts were authored from messages and policy before implementation, independently of any measured output. Exact comparison covers 12 scalar extraction fields plus the three routing fields: 15 cells per message and 315 cells for 21 messages. A missing/error extraction counts as 15 unmatched cells. Quotes and issue quality have separate assertions; purpose wording differences require human factual review. There is no invented passing threshold. Mock results verify the procedure and software paths, not live model extraction accuracy.

## Supported live configuration

The implemented provider is OpenAI's Responses API, with configurable model and endpoint. The documented configuration is gpt-5-mini, low reasoning effort, strict supplied JSON Schema output, max_output_tokens 4096, store false, and a 60-second network timeout. Live observations were not performed for this submission. Account access and current model availability must be checked before a live run.

Environment-variable names: API_KEY supplies the provider credential in live mode only; MODEL_ID optionally overrides the default live model. --model overrides MODEL_ID. No .env file is loaded. Mock mode does not read either variable. Credentials are never part of stored settings, cache fingerprints, or example request evidence; provider exceptions redact the credential.

With API_KEY already set securely in your shell:

```bash
python3 -m access_requests --db .state/live.sqlite3 --provider openai --model gpt-5-mini --workers 4 intake materials/requests
python3 -m access_requests --db .state/live.sqlite3 queue
```

The model never receives a credential in its prompt. Message text is passed as user data beneath fixed extraction instructions and the policy. Refusals, interrupted or incomplete responses, malformed JSON, schema violations, invalid quotes, and provider failures become explicit error records. See deliverables/request-evidence.json for the actual implemented request structure and a labelled fake-transport example. For deeper OpenAI implementation documentation, the OpenAI Developers plugin can be useful; it is not a dependency of this application.

Official references: [Responses request/response API](https://developers.openai.com/api/reference/resources/responses/methods/create), [GPT-5 mini](https://developers.openai.com/api/docs/models/gpt-5-mini), and [developer quickstart](https://developers.openai.com/api/docs/quickstart).

## Shared operation, interruption, and exports

Supported shared operation is overlapping processes on one Linux host and local SQLite storage. Admission and work claims use short write transactions; network calls occur outside write transactions. The most recently admitted source/configuration is current; a late older attempt cannot overwrite it. exported_at does not order revisions. --workers defaults to 4 and accepts 1–32; set it lower for shared provider rate limits. The 400/2,000-message workload cases use mocks, with no contractual throughput/latency target or live rate-limit measurement.

When a worker process exits, resume requeues its abandoned running claims after checking that the local PID no longer exists. Completed results remain intact. A live stalled process is not stolen, PID reuse is not leased, and host/power-loss durability and multi-host storage were not verified. Stop an unhealthy process before resuming its work. Use pending to identify unfinished attempts and their owning PID. Malformed input-file rejection happens before model extraction and currently terminates that intake command; correct the export and rerun. A model failure is isolated to its document.

The database is authoritative. Export creates immutable generations under deliverables/.snapshots/ and atomically replaces current.json after writing both files. Programmatic concurrent readers must use access_requests.snapshots.read_export, which pins one manifest and checks matching generation/document/hash/attempt links. Root extractions.jsonl and queue.json are convenience files for inspection after a completed export; separate raw reads during publication are not jointly atomic. A failed publication leaves the previous manifest readable; rerun export to repair convenience files.

History remains separate from current outputs in SQLite; export generations also remain available separately from root files. Keep runtime state and exports backed up together. The detection of subtle source-instruction attacks and semantic extraction reliability beyond the supplied fixture cases have not been established by live evaluation.

## Submission artifacts

The five required files are deliverables/extractions.jsonl, queue.json, accuracy.md, request-evidence.json, and verification.md. The extraction/queue files include document_id, source hashes, attempts, and labelled mock provenance. accuracy.md includes all expected facts and source quotes. verification.md records exact commands, assertions, intended comparisons, observations and limits. Red/green step logs under planning/ preserve the test-first sequence; planning/test-run.txt is the final complete suite log after the build.

Session capture uses the repository's Entire setup. Where hooks did not execute, attach the actual Codex session to the final commit with Entire's native session-attach workflow; verify the checkpoint link and push its refs alongside the default branch. Submit the root repository URL through the facilitator's Classroom assignment. No Classroom submission is claimed merely because a Git push succeeds.
