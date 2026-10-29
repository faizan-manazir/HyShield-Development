# HyShield paper reproducibility artifacts

This directory contains the experiment scripts, supplied trace, expected reference outputs, and recorded evidence used for the HyShield paper's reported reproducibility checks. It deliberately excludes full SIEM source snapshots, application databases, credentials, virtual environments, and unrelated project files.

## Contents

- `scripts/fault_harness.py` — seeded synthetic fault experiment (`--n 500 --seed 20261021`).
- `scripts/ingestor_harness.py` — harness for exercising the SIEM ingestor against synthetic records.
- `scripts/run_all.py` — longer comparison runner for the complete experiment set.
- `scripts/real_trace_checks.py` — checks over the supplied Cowrie trace and a separately provided SIEM source directory.
- `scripts/targeted_ts_naive_check.py` — targeted 200-trace timezone-naive timestamp experiment.
- `scripts/live_stall_check_phased.py` — isolated polling-thread regression check; it does not test the live dashboard or full Docker path.
- `scripts/timestamp_validation.patch` — timestamp-validation patch used for patched comparisons.
- `scripts/expected/` — expected reference output files used by the harnesses.
- `inputs/cowrie_supplied_trace.json` — trace input used for the reported real-trace checks.
- `outputs/` — saved console output, result CSV/JSON files, environment details, and comparisons from the recorded runs.

## Requirements and setup

The application source and test suite are **not bundled here**. To run the ingestor and pytest experiments, obtain the matching `python-siem` source snapshot and test suite used in the study, and keep an untouched original copy. The recorded runs used Python 3.13. Install the dependencies listed by the source project's `requirements.txt`; install `pytest` for the test suite if it is not already included.

The synthetic `fault_harness.py` uses the Python standard library and can be run independently:

```bash
python reproducibility/scripts/fault_harness.py --n 500 --seed 20261021 --out /tmp/fault_500
cmp /tmp/fault_500.csv reproducibility/scripts/expected/results.csv
```

No output from `cmp` and exit code 0 indicates a byte-for-byte match.

## Original and patched test suites

Run the original tests from the matching source checkout:

```bash
cd /path/to/python-siem
python -m pytest -q
```

For a patched comparison, make a separate copy; do not patch the original source in place. Apply the included patch from the directory containing the `python-siem` folder, then run tests from the patched copy:

```bash
cp -a python-siem python-siem-patched
patch -p2 -d /path/to/python-siem-patched < /path/to/reproducibility/scripts/timestamp_validation.patch
cd /path/to/python-siem-patched
python -m pytest -q
```

The saved evidence records 64 passing tests for the original snapshot and 65 for the patched snapshot. If patch application reports failures or already-applied hunks, stop and inspect the source rather than forcing it.

## Real trace and targeted timestamp experiment

The real-trace check requires the supplied trace and the separately obtained source directory:

```bash
python reproducibility/scripts/real_trace_checks.py \
  --trace reproducibility/inputs/cowrie_supplied_trace.json \
  --siem-dir /path/to/python-siem \
  > /tmp/real_trace_output.txt
cmp /tmp/real_trace_output.txt reproducibility/scripts/expected/real_trace_output.txt
```

Run the targeted test against original and patched source copies:

```bash
python reproducibility/scripts/targeted_ts_naive_check.py /path/to/python-siem 200
python reproducibility/scripts/targeted_ts_naive_check.py /path/to/python-siem-patched 200
```

The recorded targeted results show the original implementation crashing on 51/200 traces and the patched implementation flagging 200/200 with no poll exception in this targeted condition. These are recorded results, not a guarantee that a different source snapshot will reproduce them exactly.

## Longer comparison runner and live polling check

The complete comparison runner may take several minutes or longer and did not finish within the execution limit in the recorded verification environment. The saved `outputs/full_run_all_status.txt` records that limitation. Do not claim the complete Table 5 was independently reproduced based on the partial targeted run alone.

To attempt the full comparison:

```bash
python reproducibility/scripts/run_all.py \
  --siem-dir /path/to/python-siem \
  --patched-siem-dir /path/to/python-siem-patched \
  --trace reproducibility/inputs/cowrie_supplied_trace.json
```

The original-versus-patched live polling check should only be run against disposable source/data in an isolated test environment:

```bash
python reproducibility/scripts/live_stall_check_phased.py /path/to/python-siem original
python reproducibility/scripts/live_stall_check_phased.py /path/to/python-siem-patched patched
```

This check exercises the ingestion polling thread with temporary data. It does not start the FastAPI dashboard, validate the complete Cowrie-to-Docker-to-SIEM-to-dashboard path, or assess Docker escape resistance. Do not point it at production logs or databases.

## Evidence interpretation and limitations

- `outputs/pytest_original.txt` and `outputs/pytest_patched.txt` contain the recorded test-suite summaries.
- `outputs/fault_500.csv` and `outputs/actual_faults_500.csv` contain the synthetic experiment output; `outputs/fault_harness_console.txt` contains its console summary.
- `outputs/real_trace_checks_actual.txt` records the supplied-trace checks.
- `outputs/targeted_ts_naive_original_200.txt` and `outputs/targeted_ts_naive_patched_200.txt` record the targeted 200-trace experiment.
- `outputs/actual_ingestor_20_original.csv` and `outputs/actual_ingestor_20_patched.csv` are 20-trace smoke samples, not a substitute for a full 200-trace run across all fault conditions.
- `outputs/live_stall_original.txt` and `outputs/live_stall_patched.txt` record the isolated polling-thread test, not a browser/dashboard test.

The trace checks validate calculations over this supplied file; they do not establish that its hash was independently protected before it was provided. Source snapshots are not included, so reproducing source-dependent results requires obtaining the exact corresponding source version. End-to-end dashboard integration and Docker escape resistance were not tested by these artifacts.
