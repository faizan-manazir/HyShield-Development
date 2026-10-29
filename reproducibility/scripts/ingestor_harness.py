#!/usr/bin/env python3
"""
Fault injection through the REAL HyShield ingestor (python-siem/app/ingest.py).

For each synthetic trace and each fault (see fault_harness.py) this script:
  1. writes the faulted JSONL file to a temp directory,
  2. runs the repository's Ingestor.poll() against a fresh temporary SQLite DB,
  3. reads the resulting raw_events / sessions tables,
  4. records which of three signals reacted:
       ingestor_flag   - ingestor itself recorded an error row (error.malformed,
                         error.oversized) or incremented its error counter
       src_db_mismatch - complete source lines that parse as JSON objects differ
                         in number from stored event rows (reconciliation of the
                         faulted source against the database)
       poll_exception  - Ingestor.poll() raised (batch rolled back, checkpoint not
                         advanced); exception_persists = it raised again on retry
       baseline_mismatch - stored record, command-input, or session counts differ
                         from counts recorded for the known-good trace
                         (requires an independent baseline)
     and whether the fault was SILENT (none of the three reacted).

Usage:
  python3 ingestor_harness.py --siem-dir /path/to/python-siem --n 200 --out ingestor_results
"""
import argparse
import csv
import json
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fault_harness as fh  # noqa: E402


def source_object_count(data):
    """Complete (newline-terminated) lines that parse as JSON objects."""
    count = 0
    for raw in data.split(b"\n")[:-1]:
        if not raw.strip():
            continue
        try:
            if isinstance(json.loads(raw.decode("utf-8", errors="replace")), dict):
                count += 1
        except ValueError:
            pass
    return count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--siem-dir", required=True, help="path to the python-siem folder")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20261021)
    ap.add_argument("--benign-rate", type=float, default=0.10)
    ap.add_argument("--out", default="ingestor_results")
    args = ap.parse_args()

    sys.path.insert(0, args.siem_dir)
    from app import config, db  # noqa: E402  (repo code under test)
    from app.ingest import Ingestor  # noqa: E402

    tmp = Path(tempfile.mkdtemp(prefix="hyshield-harness-"))
    config.DATA = tmp
    config.SETTINGS_PATH = tmp / "settings.json"

    def run_ingest(data):
        """Ingest bytes with the real Ingestor; return measurements."""
        src = tmp / "cowrie.json"
        src.write_bytes(data)
        config.DB_PATH = tmp / "run.db"
        for p in tmp.glob("run.db*"):
            p.unlink()
        db.init()
        ing = Ingestor(src, interval=0.01)
        ing._last_retention_cleanup = time.monotonic()
        crashed, persistent = False, False
        try:
            ing.poll()
        except Exception:
            crashed = True
            try:        # does the same batch fail again on the next poll?
                ing.poll()
            except Exception:
                persistent = True
        conn = db.connect()
        try:
            rows = conn.execute("SELECT eventid FROM raw_events").fetchall()
            sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        finally:
            conn.close()
        ev = [r["eventid"] for r in rows]
        stored = [e for e in ev if not (e or "").startswith("error.")]
        errors = len(ev) - len(stored)
        return {"stored": len(stored),
                "commands": sum(e == "cowrie.command.input" for e in stored),
                "sessions": sessions,
                "flag": errors > 0 or ing.stats["errors"] > 0,
                "crash": crashed, "persistent": persistent}

    rng = random.Random(args.seed)
    traces = []
    for _ in range(args.n):
        lines = fh.make_trace(rng, benign_skew=rng.random() < args.benign_rate)
        data = fh.to_bytes(lines)
        traces.append((lines, fh.audit(data)))

    def evaluate(data, base):
        r = run_ingest(data)
        mismatch = source_object_count(data) != r["stored"]
        baseline = (r["stored"], r["commands"], r["sessions"]) != \
                   (base["records"], base["commands"], base["sessions"])
        return {"flag": r["flag"], "src_db": mismatch, "baseline": baseline,
                "crash": r["crash"], "persistent": r["persistent"],
                "silent": not (r["flag"] or mismatch or baseline or r["crash"])}

    cols = ["flag", "src_db", "baseline", "crash", "persistent", "silent"]
    rows = []

    hits = {c: 0 for c in cols}
    for lines, base in traces:
        res = evaluate(fh.to_bytes(lines), base)
        for c in cols:
            hits[c] += res[c]
    rows.append(["clean", "Fault-free copy"] + [args.n] +
                [round(fh.pct(hits[c], args.n), 1) for c in cols])

    for key, label, fn in fh.FAULTS:
        hits, n = {c: 0 for c in cols}, 0
        for lines, base in traces:
            data = fn(rng, lines)
            if data is None:
                continue
            n += 1
            res = evaluate(data, base)
            for c in cols:
                hits[c] += res[c]
        rows.append([key, label, n] + [round(fh.pct(hits[c], n), 1) for c in cols])

    header = ["fault", "description", "n", "ingestor_flag", "src_db_mismatch",
              "baseline_mismatch", "poll_exception", "exception_persists", "silent"]
    with open(args.out + ".csv", "w", newline="") as fh_out:
        w = csv.writer(fh_out)
        w.writerow(header)
        w.writerows(rows)
    print("%-20s %5s %8s %8s %8s %8s %8s %8s" % ("fault", "n", "flag", "src_db", "baseline", "crash", "persist", "silent"))
    for r in rows:
        print("%-20s %5d " % (r[0], r[2]) + " ".join("%7.1f%%" % v for v in r[3:]))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
