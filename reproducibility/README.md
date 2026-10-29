# HyShield Reproducibility Bundle

This directory stores organized reproducibility materials for the HyShield paper and the Python SIEM timestamp-handling investigation, separate from the project source.

## Contents planned for this directory

- `README.md`: this index and scope/limitations.
- `HyShield_reproducibility_test_record.txt`: recent test outputs reported during verification.
- `HyShield_Complete_Reproducibility_Bundle.zip`: complete organized archive, including paper materials, source snapshots, test scripts, evidence outputs, supplied input trace, and checksums.

## Reported checks

- Python SIEM full suite: 65 passed.
- Two focused timestamp/ingestion tests: 2 passed.
- Isolated real-ingestor test with mixed naive/UTC timestamps: 4 events stored and session scored.
- Invalid-timestamp scoring test: passed.
- Invalid timestamp in ingestor pipeline: 3 events stored; repeated poll ingested zero additional events.
- Log-truncation scenario: event written after truncation was ingested.

Some isolated tests reported Windows PermissionError during automatic cleanup because a temporary SQLite database remained locked; the temporary folders were inspected and manually removed. These cleanup errors are recorded separately from test assertions.

## Scope limitations

The synthetic fault harness explicitly does not run the actual SIEM ingestor or SQLite. Full Table 5 reproduction, live dashboard end-to-end verification, and full Docker isolation validation remain outstanding. Recent results are reconstructed from command output shared during the session, not original saved terminal transcripts.

No runtime virtual environments, local SQLite databases, .env files, or local settings should be committed here.
