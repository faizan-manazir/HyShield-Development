# HyShield forensic paper: tests you can run

Requires Python 3.8+ only (standard library). Nothing here touches your repo or your trace
except by reading them. Credentials and commands from the trace are never printed.

## Contents
| File | What it is |
|---|---|
| `fault_harness.py` | Table 4: damages 500 synthetic logs 14 ways and records which checks notice |
| `ingestor_harness.py` | Table 5: same faults through YOUR real `Ingestor.poll()` into a temporary SQLite DB |
| `real_trace_checks.py` | Profiles your real trace, builds the 3 modified copies, reports digests and ingestor outcomes |
| `run_all.py` | Runs all of the above and compares with the values printed in the paper |
| `timestamp_validation.patch` | Fix for the timezone-naive crash (3 files: ingest.py, correlation.py, one test) |
| `expected/` | The exact outputs the paper was written from |

## A. Automated (about 2 minutes)
1. Make a COPY of your repo and apply the patch to the copy only:
   `cd COPY_OF_REPO && patch -p1 < /path/to/timestamp_validation.patch`   (or `git apply ...`)
2. Run:
```
python3 run_all.py --siem-dir YOUR_REPO/python-siem --patched-siem-dir COPY_OF_REPO/python-siem --trace YOUR_REPO/var/log/cowrie/cowrie.json
```
Each step prints PASS or DIFF. (On Windows use `python` instead of `python3`.)

## B. Tests you must run yourself
1. **Repo test suite, unpatched.** `cd YOUR_REPO/python-siem && pip install -r requirements.txt && python -m pytest -q`
   Expected: **64 passed** (the paper states this).
2. **Repo test suite, patched copy.** Same command in the patched copy. Expected: **65 passed**.
3. **Trace digest.** Linux/macOS: `sha256sum cowrie.json`. Windows PowerShell: `Get-FileHash cowrie.json -Algorithm SHA256`.
   Expected: `5659D50F5F26D7706CE272F138B4533DF63BFE618A67592B124514F864AE49E5`. If different, your log has changed since the paper's numbers.
4. **Live crash check (the one thing my harness cannot do).** On the UNPATCHED repo, in a throw-away folder:
   - copy your log there, set `HYSHIELD_DATA` to that folder and `COWRIE_LOG_PATH` to the copy, start the SIEM (`python run.py`);
   - append two lines to the copy: a normal event with a `Z` timestamp, then an event of the same session whose `timestamp` has no timezone, e.g. `2026-10-28T19:00:00.000000`;
   - watch the console: if the paper's claim is right you will see `ingest poll failed` repeating every few seconds, and new lines after that point never appear in the dashboard.
   Repeat on the patched copy: no crash, and an `error.invalid_timestamp` row appears. Note what you see.
5. **Compile the paper** on your machine: `pdflatex HyShield_paper_fixed.tex` twice. Check there are no `??` marks and the figures fit the page.

## C. After the tests: what to change
| Result | Change in the paper |
|---|---|
| Everything PASS, 64/65, digest matches, live check matches | **Nothing.** Only the TODO items remain (commit hash, audit script, 2 references, author line). |
| Step 1 DIFF | Should not happen (seeded, standard library). Send me the output; Table 4 and its text change. |
| Step 2 or 3 DIFF | Your ingestor code differs from the snapshot I tested. Table 5, the 25.5% / 51 of 200 figures, and the patch paragraph change. |
| Step 4 DIFF or digest differs | Your log changed. Send me `real_trace_output.txt` (path printed by run_all.py). Abstract, Methods, Tables 1-3, Results, Discussion and Conclusion numbers change. |
| pytest counts differ | Edit one sentence in Results ("65 passed, against 64 passed ..."). |
| Live check B4 matches | Optional: change "By code inspection" to "as observed in a live run" in Results. |
| Live check B4 does NOT stall | Soften the sentence about stalled ingestion in Results and Discussion. |
