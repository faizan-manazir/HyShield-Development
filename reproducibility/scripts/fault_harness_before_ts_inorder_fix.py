"""
Synthetic fault-injection harness for log-validation checks (HyShield study).

What it does
  1. Generates N known-good, Cowrie-style JSON-lines traces (synthetic, seeded).
  2. Records a baseline for each (SHA-256, record/command/session counts).
  3. Applies one fault at a time to a copy of each trace.
  4. Runs four checks and records which ones react:
       structural   - malformed lines, missing eventid/timestamp, invalid or
                      timezone-naive timestamps
       chronology   - backward timestamp steps in file order
       hash         - SHA-256 differs from baseline
       counts       - record, command or session counts differ from baseline
  5. Reports detection rate per fault and check, plus false alarms on
     fault-free traces.

Scope: this tests the CHECKS described in the paper on synthetic traces. It does
not run the real HyShield SIEM ingestor or touch SQLite.

Usage:  python3 fault_harness.py --n 500 --seed 20261021 --out results
"""
import argparse
import csv
import hashlib
import json
import random
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
TS_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"
COMMANDS = ["uname -a", "whoami", "ls -la", "cat /etc/passwd", "pwd", "id",
            "ps aux", "ifconfig", "wget http://example.invalid/x", "exit"]


# ---------------------------------------------------------------- generation
def make_trace(rng, benign_skew=False):
    """Return a list of JSON strings (one per line) in file (= time) order."""
    t0 = datetime(2026, 5, 18, 21, 58, 44, tzinfo=UTC)
    events = []
    for _ in range(rng.randint(4, 10)):
        sid = "%012x" % rng.getrandbits(48)
        ip = "192.0.2.%d" % rng.randint(1, 254)  # TEST-NET-1, synthetic
        t = t0 + timedelta(seconds=rng.uniform(0, 900))

        def add(eventid, **extra):
            nonlocal t
            t += timedelta(seconds=rng.uniform(0.001, 8))
            ev = {"eventid": eventid, "timestamp": t.strftime(TS_FMT),
                  "session": sid, "src_ip": ip}
            ev.update(extra)
            events.append((t, ev))

        add("cowrie.session.connect")
        add("cowrie.client.version")
        add("cowrie.client.kex")
        if rng.random() < 0.2:
            add("cowrie.login.failed", username="root", password="<redacted>")
        if rng.random() < 0.8:
            add("cowrie.login.success", username="root", password="<redacted>")
            for _ in range(rng.randint(0, 8)):
                add("cowrie.command.input", input=rng.choice(COMMANDS))
        add("cowrie.session.closed")
    events.sort(key=lambda x: x[0])
    lines = [json.dumps(e, separators=(",", ":")) for _, e in events]
    if benign_skew:  # legitimate concurrent-write skew present at acquisition
        idx = [i for i in range(len(events) - 1)
               if events[i][1]["session"] != events[i + 1][1]["session"]
               and events[i][0] != events[i + 1][0]]
        if idx:
            i = rng.choice(idx)
            lines[i], lines[i + 1] = lines[i + 1], lines[i]
    return lines


def to_bytes(lines):
    return ("\n".join(lines) + "\n").encode("utf-8")


# -------------------------------------------------------------------- audit
def parse_ts(value):
    """Return aware datetime or None (missing/invalid/timezone-naive)."""
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else None


def audit(data):
    """Read-only audit with chronology checked separately per session."""
    r = {"sha256": hashlib.sha256(data).hexdigest(), "records": 0, "malformed": 0,
         "missing_eventid": 0, "bad_ts": 0, "decreases": 0, "commands": 0}

    sessions = set()
    previous_by_session = {}

    for raw in data.split(b"\n"):
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            r["malformed"] += 1
            continue

        if not isinstance(obj, dict):
            r["malformed"] += 1
            continue

        r["records"] += 1

        if not obj.get("eventid"):
            r["missing_eventid"] += 1

        if obj.get("eventid") == "cowrie.command.input":
            r["commands"] += 1

        session = obj.get("session")
        if session:
            sessions.add(session)

        ts = parse_ts(obj.get("timestamp"))
        if ts is None:
            r["bad_ts"] += 1
        elif session:
            previous = previous_by_session.get(session)
            if previous is not None and ts < previous:
                r["decreases"] += 1
            previous_by_session[session] = ts

    r["sessions"] = len(sessions)
    return r


def run_checks(data, baseline):
    a = audit(data)
    structural = bool(a["malformed"] or a["missing_eventid"] or a["bad_ts"])
    chronology = a["decreases"] > 0
    hash_ = a["sha256"] != baseline["sha256"]
    counts = any(a[k] != baseline[k] for k in ("records", "commands", "sessions"))
    return {"structural": structural, "chronology": chronology, "hash": hash_,
            "counts": counts,
            "any_no_baseline": structural or chronology,
            "any_with_baseline": structural or chronology or hash_ or counts}


# ------------------------------------------------------------------- faults
def _ts(line):
    return parse_ts(json.loads(line).get("timestamp"))


def _edit(line, **changes):
    obj = json.loads(line)
    for k, v in changes.items():
        if v is None:
            obj.pop(k, None)
        else:
            obj[k] = v
    return json.dumps(obj, separators=(",", ":"))


def f_append_marker(rng, L):
    return to_bytes(L + ["# appended marker"])

def f_append_forged(rng, L):
    forged = _edit(L[-1], eventid="cowrie.command.input", input="forged",
                   timestamp=(_ts(L[-1]) + timedelta(seconds=1)).strftime(TS_FMT))
    return to_bytes(L + [forged])

def f_delete_any(rng, L):
    i = rng.randrange(len(L)); return to_bytes(L[:i] + L[i + 1:])

def f_delete_command(rng, L):
    idx = [i for i, x in enumerate(L) if json.loads(x)["eventid"] == "cowrie.command.input"]
    if not idx: return None
    i = rng.choice(idx); return to_bytes(L[:i] + L[i + 1:])

def f_duplicate(rng, L):
    i = rng.randrange(len(L)); return to_bytes(L[:i + 1] + [L[i]] + L[i + 1:])

def f_reorder_adjacent(rng, L):
    idx = [i for i in range(len(L) - 1) if _ts(L[i]) != _ts(L[i + 1])]
    i = rng.choice(idx); M = L[:]; M[i], M[i + 1] = M[i + 1], M[i]
    return to_bytes(M)

def f_ts_backward(rng, L):
    """Move an event backwards relative to the previous event in its session."""
    previous_by_session = {}
    candidates = []

    for i, line in enumerate(L):
        obj = json.loads(line)
        session = obj.get("session")
        ts = _ts(line)

        if not session or ts is None:
            continue

        if session in previous_by_session:
            candidates.append((i, previous_by_session[session]))

        previous_by_session[session] = ts

    if not candidates:
        return None

    i, previous_ts = rng.choice(candidates)
    M = L[:]
    M[i] = _edit(
        M[i],
        timestamp=(previous_ts - timedelta(milliseconds=5)).strftime(TS_FMT)
    )
    return to_bytes(M)


def f_ts_inorder(rng, L):
    for _ in range(50):
        i = rng.randrange(1, len(L) - 1)
        a, b, c = _ts(L[i - 1]), _ts(L[i]), _ts(L[i + 1])
        mid = a + (c - a) / 2
        new = mid.strftime(TS_FMT)
        if a < mid < c and new != json.loads(L[i])["timestamp"]:
            M = L[:]; M[i] = _edit(M[i], timestamp=new); return to_bytes(M)
    return None

def f_ts_missing(rng, L):
    i = rng.randrange(len(L)); M = L[:]; M[i] = _edit(M[i], timestamp=None)
    return to_bytes(M)

def f_ts_naive(rng, L):
    i = rng.randrange(len(L)); M = L[:]
    M[i] = _edit(M[i], timestamp=json.loads(M[i])["timestamp"].rstrip("Z"))
    return to_bytes(M)

def f_malformed(rng, L):
    i = rng.randrange(len(L)); M = L[:]; M[i] = M[i][:-1]
    return to_bytes(M)

def f_truncate_midline(rng, L):
    data = to_bytes(L); cut = rng.randint(int(len(data) * 0.7), len(data) - 2)
    return data[:cut] if data[cut - 1:cut] != b"\n" else data[:cut - 1]

def f_truncate_tail(rng, L):
    k = rng.randint(1, 3); return to_bytes(L[:-k])

def f_edit_content(rng, L):
    idx = [i for i, x in enumerate(L) if json.loads(x)["eventid"] == "cowrie.command.input"]
    if not idx: return None
    i = rng.choice(idx); M = L[:]
    cur = json.loads(M[i])["input"]
    M[i] = _edit(M[i], input=("ls" if cur != "ls" else "id"))
    return to_bytes(M)

FAULTS = [
    ("append_marker", "Append non-JSON marker line", f_append_marker),
    ("append_forged", "Append forged well-formed event", f_append_forged),
    ("delete_any", "Delete one random record", f_delete_any),
    ("delete_command", "Delete one command-input record", f_delete_command),
    ("duplicate", "Duplicate one record", f_duplicate),
    ("reorder_adjacent", "Swap two adjacent records", f_reorder_adjacent),
    ("ts_backward", "Timestamp set earlier than predecessor", f_ts_backward),
    ("ts_inorder", "Timestamp altered, order preserved", f_ts_inorder),
    ("ts_missing", "Timestamp field removed", f_ts_missing),
    ("ts_naive", "Timezone removed from timestamp", f_ts_naive),
    ("malformed", "Corrupt one JSON line", f_malformed),
    ("truncate_midline", "Truncate file mid-record", f_truncate_midline),
    ("truncate_tail", "Remove last 1-3 whole records", f_truncate_tail),
    ("edit_content", "Change command text (same count)", f_edit_content),
]
CHECKS = ["structural", "chronology", "hash", "counts", "any_no_baseline", "any_with_baseline"]


# --------------------------------------------------------------------- main
def pct(x, n):
    return 100.0 * x / n if n else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500, help="traces per condition")
    ap.add_argument("--seed", type=int, default=20261021)
    ap.add_argument("--benign-rate", type=float, default=0.10,
                    help="share of clean traces containing legitimate order skew")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    traces = []
    for _ in range(args.n):
        lines = make_trace(rng, benign_skew=rng.random() < args.benign_rate)
        data = to_bytes(lines)
        traces.append((lines, audit(data)))

    rows = []

    # Fault-free control
    hits = {c: 0 for c in CHECKS}
    for lines, base in traces:
        res = run_checks(to_bytes(lines), base)
        for c in CHECKS:
            hits[c] += res[c]
    rows.append(["clean", "Fault-free copy (incl. benign order skew)", args.n]
                + [round(pct(hits[c], args.n), 1) for c in CHECKS])

    # Single faults
    for key, label, fn in FAULTS:
        hits, n = {c: 0 for c in CHECKS}, 0
        for lines, base in traces:
            if any(_ts(x) is None for x in lines):
                continue
            data = fn(rng, lines)
            if data is None:
                continue
            n += 1
            res = run_checks(data, base)
            for c in CHECKS:
                hits[c] += res[c]
        rows.append([key, label, n] + [round(pct(hits[c], n), 1) for c in CHECKS])

    # Tamper + attacker replaces baseline (hash/counts recomputed on tampered file)
    hits, n = {c: 0 for c in CHECKS}, 0
    for lines, base in traces:
        data = f_delete_command(rng, lines)
        if data is None:
            continue
        n += 1
        res = run_checks(data, audit(data))  # baseline replaced
        for c in CHECKS:
            hits[c] += res[c]
    rows.append(["delete_command_rebaselined",
                 "Command deleted AND baseline recomputed by attacker", n]
                + [round(pct(hits[c], n), 1) for c in CHECKS])

    header = ["fault", "description", "n"] + CHECKS
    with open(args.out + ".csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(header); w.writerows(rows)
    with open(args.out + ".json", "w") as fh:
        json.dump({"seed": args.seed, "n": args.n, "benign_rate": args.benign_rate,
                   "header": header, "rows": rows}, fh, indent=1)

    print("%-28s %5s " % ("fault", "n") + " ".join("%12s" % c for c in CHECKS))
    for r in rows:
        print("%-28s %5d " % (r[0], r[2]) + " ".join("%11.1f%%" % v for v in r[3:]))


if __name__ == "__main__":
    main()