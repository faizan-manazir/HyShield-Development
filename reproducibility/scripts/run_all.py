#!/usr/bin/env python3
"""
Runs every automated test for the HyShield forensic paper and compares the output
with the values used in the paper (folder expected/).

  python3 run_all.py --siem-dir REPO/python-siem [--patched-siem-dir PATCHED/python-siem] [--trace cowrie.json]

--siem-dir          your repo exactly as it is now (unpatched)
--patched-siem-dir  a COPY of your repo with timestamp_validation.patch applied
--trace             the Cowrie log analysed in the paper
"""
import argparse, subprocess, sys, tempfile, csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE / "expected"


def run(cmd):
    return subprocess.run([sys.executable] + cmd, capture_output=True, text=True)


def compare_csv(new, expected, name):
    a = list(csv.reader(open(new)))
    b = list(csv.reader(open(expected)))
    if a == b:
        print("  PASS  %s identical to the paper's values" % name)
        return True
    print("  DIFF  %s differs from the paper's values:" % name)
    for ra, rb in zip(a, b):
        if ra != rb:
            print("        new     :", ra)
            print("        paper   :", rb)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--siem-dir", required=True)
    ap.add_argument("--patched-siem-dir")
    ap.add_argument("--trace")
    ap.add_argument("--n-synthetic", type=int, default=500)
    ap.add_argument("--n-ingestor", type=int, default=200)
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp())
    ok = True

    print("1. Synthetic fault injection on the checks (Table 4)")
    r = run([str(HERE / "fault_harness.py"), "--n", str(args.n_synthetic), "--seed", "20261021", "--out", str(tmp / "syn")])
    if r.returncode: print(r.stderr); sys.exit(1)
    ok &= compare_csv(tmp / "syn.csv", EXP / "results.csv", "results.csv")

    print("2. Faults through YOUR ingestor, unpatched (Table 5)")
    r = run([str(HERE / "ingestor_harness.py"), "--siem-dir", args.siem_dir, "--n", str(args.n_ingestor),
             "--seed", "20261021", "--out", str(tmp / "ing")])
    if r.returncode: print(r.stderr); sys.exit(1)
    ok &= compare_csv(tmp / "ing.csv", EXP / "ingestor_results.csv", "ingestor_results.csv")

    if args.patched_siem_dir:
        print("3. Faults through the PATCHED ingestor")
        r = run([str(HERE / "ingestor_harness.py"), "--siem-dir", args.patched_siem_dir, "--n", str(args.n_ingestor),
                 "--seed", "20261021", "--out", str(tmp / "ingp")])
        if r.returncode: print(r.stderr); sys.exit(1)
        ok &= compare_csv(tmp / "ingp.csv", EXP / "ingestor_results_patched.csv", "ingestor_results_patched.csv")
    else:
        print("3. SKIPPED (no --patched-siem-dir given)")

    if args.trace:
        print("4. Real trace profile, copy-level checks, and ingestor outcomes")
        cmd = [str(HERE / "real_trace_checks.py"), "--trace", args.trace, "--siem-dir", args.siem_dir]
        r = run(cmd)
        if r.returncode: print(r.stderr); sys.exit(1)
        expected = (EXP / "real_trace_output.txt").read_text()
        if r.stdout.strip() == expected.strip():
            print("  PASS  output identical to the paper's values")
        else:
            ok = False
            (tmp / "real_trace_output.txt").write_text(r.stdout)
            print("  DIFF  your trace gives different numbers (expected if you generated new events).")
            print("        New output saved to", tmp / "real_trace_output.txt")
            print("        Update Tables 1-3 and the Methods/Results text of the paper from that file.")
    else:
        print("4. SKIPPED (no --trace given)")

    print("\nOVERALL:", "everything matches the paper" if ok else "some values differ - see DIFF lines above")


if __name__ == "__main__":
    main()
