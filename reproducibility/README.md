# HyShield paper reproducibility artifacts

This directory contains only artifacts directly supporting the paper's reported log-integrity and SIEM-ingestion experiments.

- `scripts/fault_harness.py`: seeded 500-trace synthetic fault experiment.
- `scripts/ingestor_harness.py`: 200-trace-per-fault experiment against the actual SIEM ingestor.
- `scripts/real_trace_checks.py`: checks on the supplied Cowrie trace.
- `scripts/targeted_ts_naive_check.py`: targeted timestamp-naive reproduction.
- `scripts/timestamp_validation.patch`: prototype per-record timestamp validation patch.
- `inputs/cowrie_supplied_trace.json`: input trace used for the real-trace checks.
- `scripts/expected/` and `outputs/`: expected results and recorded experiment outputs.
- `SHA256SUMS.txt`: hashes supplied with the evidence bundle.

The synthetic fault harness does not run the actual SIEM ingestor or Docker/Cowrie stack. The ingestor experiment covers `Ingestor.poll()` and SQLite only; it is not a full live-dashboard or Docker end-to-end validation. See the paper's Materials and methods section for scope and limitations.
