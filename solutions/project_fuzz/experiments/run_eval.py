#!/usr/bin/env python3
"""Run the evaluation: every method x every configuration x every seed.

Run from the repository root, with the project_fuzz environment active:

    python solutions/project_fuzz/experiments/run_eval.py --seeds 2 --runs 200      # quick test
    python solutions/project_fuzz/experiments/run_eval.py --seeds 20 --runs 5000    # the real thing

Writes one CSV row per (method, configuration, seed, outcome). "Outcome" covers
every outcome the method CAN have (from its @Case annotations) plus anything
else the fuzzer reported, so a missed failure shows up as a row with found=0.
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "solutions" / "project_fuzz" / "src"))

import dynamic  # noqa: E402
import fuzzer  # noqa: E402
import jpamb  # noqa: E402
import jvm  # noqa: E402

# The configurations we compare. The baseline fuzzer ignores the switches, so
# until the real fuzzer exists all five give the same numbers. That is expected.
CONFIGS = {
    "random": fuzzer.Config(use_coverage=False, use_static_constants=False, use_runtime_values=False),
    "coverage": fuzzer.Config(use_coverage=True, use_static_constants=False, use_runtime_values=False),
    "coverage+static": fuzzer.Config(use_coverage=True, use_static_constants=True, use_runtime_values=False),
    "coverage+runtime": fuzzer.Config(use_coverage=True, use_static_constants=False, use_runtime_values=True),
    "full": fuzzer.Config(use_coverage=True, use_static_constants=True, use_runtime_values=True),
}

COLUMNS = ["method", "config", "seed", "outcome", "possible", "found",
           "first_run", "first_seconds", "total_runs", "total_seconds"]


def possible_outcomes() -> dict[str, set[str]]:
    """method id -> outcomes it can have, read from JPAMB's case list."""
    cases = REPO_ROOT / "target" / "stats" / "cases.txt"
    out: dict[str, set[str]] = {}
    for line in cases.read_text().splitlines():
        if line.strip():
            method, rest = line.split(None, 1)
            out.setdefault(method, set()).add(rest.rsplit(" -> ", 1)[1].strip())
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, default=20, help="seeds per method and configuration")
    ap.add_argument("--runs", type=int, default=5000, help="budget: inputs per fuzzing session")
    ap.add_argument("--configs", nargs="+", default=list(CONFIGS), choices=list(CONFIGS))
    ap.add_argument("--filter", default=".*", help="only methods matching this regular expression")
    ap.add_argument("--out", default="results.csv")
    args = ap.parse_args()

    import os
    os.chdir(REPO_ROOT)  # jpamb looks for the benchmark in the current folder
    suite, eff = jpamb.setup()
    bc = jpamb.Bytecode(suite, eff, {})
    dynamic.TRACE = False

    methods = {m: o for m, o in sorted(possible_outcomes().items()) if re.search(args.filter, m)}
    sessions = len(methods) * len(args.configs) * args.seeds
    print(f"{len(methods)} methods x {len(args.configs)} configurations x {args.seeds} seeds "
          f"= {sessions} fuzzing sessions, up to {args.runs} inputs each")

    unsupported = set()
    start = time.monotonic()
    done = 0
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for method, possible in methods.items():
            methodid = jvm.AbsMethodID.decode(method)
            for name in args.configs:
                for seed in range(args.seeds):
                    done += 1
                    try:
                        result = fuzzer.fuzz(bc, methodid, seed, args.runs, CONFIGS[name])
                    except NotImplementedError:
                        unsupported.add(method)  # e.g. method calls: skip the method entirely
                        break
                    for outcome in sorted(possible | set(result.found)):
                        hit = result.found.get(outcome)
                        writer.writerow({
                            "method": method, "config": name, "seed": seed, "outcome": outcome,
                            "possible": int(outcome in possible), "found": int(hit is not None),
                            "first_run": hit.run if hit else "",
                            "first_seconds": f"{hit.seconds:.4f}" if hit else "",
                            "total_runs": result.runs, "total_seconds": f"{result.seconds:.4f}",
                        })
                if method in unsupported:
                    break
            elapsed = time.monotonic() - start
            print(f"  [{done}/{sessions}] {method}  ({elapsed:.0f} s so far, "
                  f"about {elapsed / done * (sessions - done):.0f} s left)")

    print(f"\nWrote {args.out} in {time.monotonic() - start:.0f} s")
    if unsupported:
        print(f"Skipped {len(unsupported)} methods the interpreter cannot run:")
        for m in sorted(unsupported):
            print(f"  {m}")


if __name__ == "__main__":
    main()
