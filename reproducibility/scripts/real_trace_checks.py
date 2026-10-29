#!/usr/bin/env python3
"""
Profile a real Cowrie JSON-lines trace, make the three controlled copies used in
the paper (append marker, remove one command, move one timestamp earlier), and
(optionally) pass the original and the copies through the repository's ingestor.

Usage:
  python3 real_trace_checks.py --trace path/to/cowrie.json [--siem-dir path/to/python-siem]
Nothing is written next to your trace; credentials and commands are never printed.
"""
import argparse, json, sys, tempfile, time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fault_harness as fh


def parse(t):
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--siem-dir")
    args = ap.parse_args()

    raw = Path(args.trace).read_bytes()
    lines = raw.decode("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    ev = [json.loads(l) for l in lines]

    order = []
    for e in ev:
        if e.get("session") not in order:
            order.append(e.get("session"))
    label = {s: chr(65 + i) for i, s in enumerate(order)}
    base = fh.audit(raw)
    print("SHA-256      :", base["sha256"].upper())
    print("records      :", base["records"], "| malformed:", base["malformed"],
          "| missing eventid:", base["missing_eventid"], "| bad timestamps:", base["bad_ts"])
    print("commands     :", base["commands"], "| sessions:", base["sessions"],
          "| timestamp decreases:", base["decreases"])
    stamps = [parse(e["timestamp"]) for e in ev]
    print("time range   :", min(stamps).strftime("%Y-%m-%d %H:%M:%S.%f"), "to",
          max(stamps).strftime("%H:%M:%S.%f"), "UTC")
    print("source IPs   :", sorted({e.get("src_ip") for e in ev if e.get("src_ip")}))
    counts = {}
    for e in ev:
        counts[e["eventid"]] = counts.get(e["eventid"], 0) + 1
    print("event types  :", dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))))
    print("\nsession records commands span_s")
    cmds = {}
    for s in order:
        es = [e for e in ev if e.get("session") == s]
        cmds[s] = sum(e["eventid"] == "cowrie.command.input" for e in es)
        span = (parse(es[-1]["timestamp"]) - parse(es[0]["timestamp"])).total_seconds()
        print("  %s   %5d  %6d   %.3f" % (label[s], len(es), cmds[s], span))

    busy = max(order, key=lambda s: cmds[s])
    idx = [i for i, e in enumerate(ev) if e.get("session") == busy and e["eventid"] == "cowrie.command.input"]
    i = idx[0]
    newts = (parse(ev[i - 1]["timestamp"]) - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    e3 = dict(ev[i]); e3["timestamp"] = newts
    L3 = lines[:]; L3[i] = json.dumps(e3, separators=(",", ":"))
    cases = {
        "original": raw,
        "append marker": raw + b"# appended marker\n",
        "omission": ("\n".join(lines[:i] + lines[i + 1:]) + "\n").encode(),
        "timestamp": ("\n".join(L3) + "\n").encode(),
    }
    print("\nmodified Session %s, first command (line %d); new timestamp %s (was %s)"
          % (label[busy], i + 1, newts, ev[i]["timestamp"]))
    print("\ncopy-level checks")
    for name, data in cases.items():
        a = fh.audit(data)
        r = fh.run_checks(data, base)
        fired = [k for k in ("structural", "chronology", "hash", "counts") if r[k]]
        print("  %-13s %s records=%d commands=%d sessions=%d decreases=%d malformed=%d reacted=%s"
              % (name, a["sha256"].upper(), a["records"], a["commands"], a["sessions"],
                 a["decreases"], a["malformed"], fired or "none"))

    if args.siem_dir:
        sys.path.insert(0, args.siem_dir)
        from app import config, db
        from app.ingest import Ingestor
        tmp = Path(tempfile.mkdtemp())
        config.DATA = tmp
        config.SETTINGS_PATH = tmp / "settings.json"
        print("\ningestor outcomes (real Ingestor.poll into temporary SQLite)")
        for name, data in cases.items():
            src = tmp / "cowrie.json"
            src.write_bytes(data)
            config.DB_PATH = tmp / (name.replace(" ", "_") + ".db")
            db.init()
            ing = Ingestor(src, interval=0.01)
            ing._last_retention_cleanup = time.monotonic()
            try:
                ing.poll()
                crashed = False
            except Exception as exc:
                crashed = type(exc).__name__
            conn = db.connect()
            rows = [r["eventid"] for r in conn.execute("SELECT eventid FROM raw_events")]
            sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            conn.close()
            stored = [r for r in rows if not r.startswith("error.")]
            print("  %-13s stored=%d commands=%d sessions=%d error_rows=%d exception=%s"
                  % (name, len(stored), sum(r == "cowrie.command.input" for r in stored),
                     sessions, len(rows) - len(stored), crashed))


if __name__ == "__main__":
    main()
