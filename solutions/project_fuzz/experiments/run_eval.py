#!/usr/bin/env python3
"""Evaluation driver: every benchmark method x every fuzzing mode x every seed.

Run from the repository root with the project_fuzz environment:

    # quick check (a minute or two)
    uv run --project solutions/project_fuzz python solutions/project_fuzz/experiments/run_eval.py --seeds 2 --execs 2000 --out results_test.csv

    # the real experiment
    uv run --project solutions/project_fuzz python solutions/project_fuzz/experiments/run_eval.py --seeds 10 --execs 10000 --out results.csv

The modes are the same as FUZZ_MODE in fuzzer.analyse():
    random     - fresh random input every time, no feedback
    dictionary - fresh random input every time, but values also drawn from the
                 constant dictionary (no coverage feedback)
    coverage   - coverage-guided (corpus + mutation), no dictionary
    full       - coverage-guided + constants/strings from syntaxAnalyser

The budget is a number of executions (--execs), not seconds, so results do not
depend on how fast the machine is. --time is only a safety cap.

Writes one CSV row per (method, mode, seed, outcome). The outcomes are every
outcome the method CAN have (from its @Case annotations) plus anything else the
fuzzer reported, so a missed failure is a row with found=0.
"""

import argparse
import csv
import logging
import multiprocessing as mp
import os
import random
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "solutions" / "project_fuzz" / "src"))

MODES = ["random", "dictionary", "coverage", "full"]

COLUMNS = [
    "method", "mode", "seed", "outcome", "possible", "found",
    "first_exec", "first_seconds", "total_execs", "total_seconds",
    "crashes", "dict_size", "status",
]

# Worker globals, set once per process by init_worker().
_bc = None
_dicts: dict = {}


def possible_outcomes() -> dict[str, set[str]]:
    """method id -> outcomes it can have, read from JPAMB's case list."""
    out: dict[str, set[str]] = {}
    for line in (REPO_ROOT / "target" / "stats" / "cases.txt").read_text().splitlines():
        if line.strip():
            method, rest = line.split(None, 1)
            out.setdefault(method, set()).add(rest.rsplit(" -> ", 1)[1].strip())
    return out


def init_worker():
    global _bc
    os.chdir(REPO_ROOT)  # jpamb and syntaxAnalyser expect the repo root
    # syntaxAnalyser calls logging.basicConfig(level=DEBUG); configuring logging
    # first turns that into a no-op so the workers stay quiet.
    logging.basicConfig(level=logging.WARNING)
    import jpamb
    import fuzzer

    fuzzer.TRACE = False
    suite, eff = jpamb.setup()
    _bc = jpamb.Bytecode(suite, eff, {})


def dictionary(methodid) -> tuple[list[int], list[str], str]:
    """Constant dictionary for full mode, built the same way as fuzzer.analyse().
    Cached per method, since it does not depend on the seed."""
    import syntaxAnalyser

    key = str(methodid)
    if key not in _dicts:
        try:
            ints, strs = syntaxAnalyser.getDictFromMethodIdTS(methodid)
            _dicts[key] = (sorted(syntaxAnalyser.augmentWithBoundryValues(ints)), list(strs), "ok")
        except BaseException as e:  # syntaxAnalyser calls sys.exit on failure
            _dicts[key] = ([], [], f"no-dict:{type(e).__name__}")
    return _dicts[key]


def fuzz_session(task):
    """One fuzzing session. Returns CSV rows."""
    import fuzzer
    import jvm

    method, possible, mode, seed, max_execs, time_cap = task
    methodid = jvm.AbsMethodID.decode(method)

    int_dict, str_dict, status = ([], [], "ok")
    if mode in ("full", "dictionary"):
        int_dict, str_dict, status = dictionary(methodid)

    first: dict[str, tuple[int, float]] = {}

    class TimedFuzzer(fuzzer.CoverageFuzzer):
        """Records when each outcome was first seen (execution number, seconds)."""

        def run_one(self, values):
            outcome, cov = super().run_one(values)
            if outcome is not None and outcome not in first:
                first[outcome] = (self.execs, time.monotonic() - start)
            return outcome, cov

    fz = TimedFuzzer(
        _bc, methodid, random.Random(seed),
        int_dict=int_dict, str_dict=str_dict, use_coverage=mode in ("coverage", "full"),
    )
    start = time.monotonic()
    try:
        fz.run(time_cap, max_execs)
    except NotImplementedError:
        status = "unsupported"  # e.g. a parameter type the fuzzer cannot generate
    total = time.monotonic() - start
    if status == "ok" and fz.execs > 0 and fz.crashes == fz.execs:
        status = "all-crashed"  # the interpreter cannot run this method at all

    rows = []
    for outcome in sorted(possible | set(first)):
        hit = first.get(outcome)
        rows.append({
            "method": method, "mode": mode, "seed": seed, "outcome": outcome,
            "possible": int(outcome in possible), "found": int(hit is not None),
            "first_exec": hit[0] if hit else "",
            "first_seconds": f"{hit[1]:.4f}" if hit else "",
            "total_execs": fz.execs, "total_seconds": f"{total:.4f}",
            "crashes": fz.crashes, "dict_size": len(int_dict) + len(str_dict),
            "status": status,
        })
    return rows


def worker(task_q, result_q, wid):
    init_worker()
    while (item := task_q.get()) is not None:
        idx, task = item
        result_q.put(("start", wid, idx, time.monotonic()))
        result_q.put(("done", wid, idx, fuzz_session(task)))


def hung_rows(task):
    """A session killed by the hard timeout counts as finding nothing."""
    method, possible, mode, seed, max_execs, time_cap = task
    return [{"method": method, "mode": mode, "seed": seed, "outcome": o, "possible": 1,
             "found": 0, "first_exec": "", "first_seconds": "", "total_execs": "",
             "total_seconds": "", "crashes": "", "dict_size": "", "status": "hung"}
            for o in sorted(possible)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, default=10, help="seeds per method and mode")
    ap.add_argument("--first-seed", type=int, default=0)
    ap.add_argument("--execs", type=int, default=10000, help="executions per session")
    ap.add_argument("--time", type=float, default=10.0, help="time cap in seconds per session")
    ap.add_argument("--hard-timeout", type=float, default=None,
                    help="kill a session after this many seconds (default: 2 x --time + 10). "
                         "Needed because one execution can hang, e.g. allocating a huge array")
    ap.add_argument("--modes", nargs="+", default=MODES, choices=MODES)
    ap.add_argument("--filter", default=".*", help="only methods matching this regular expression")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default="results.csv")
    args = ap.parse_args()
    hard = args.hard_timeout or 2 * args.time + 10

    methods = {m: o for m, o in sorted(possible_outcomes().items()) if re.search(args.filter, m)}
    seeds = range(args.first_seed, args.first_seed + args.seeds)
    tasks = [(m, o, mode, s, args.execs, args.time)
             for m, o in methods.items() for mode in args.modes for s in seeds]
    print(f"{len(methods)} methods x {len(args.modes)} modes x {args.seeds} seeds = "
          f"{len(tasks)} sessions of up to {args.execs} executions / {args.time:g} s, "
          f"{args.workers} workers", flush=True)

    task_q, result_q = mp.Queue(), mp.Queue()
    for item in enumerate(tasks):
        task_q.put(item)
    for _ in range(args.workers):
        task_q.put(None)

    procs, running = {}, {}  # worker id -> Process / (task index, start time)
    next_wid = 0

    def spawn():
        nonlocal next_wid
        p = mp.Process(target=worker, args=(task_q, result_q, next_wid), daemon=True)
        p.start()
        procs[next_wid] = p
        next_wid += 1

    for _ in range(args.workers):
        spawn()

    import queue

    start, done, hung, shown = time.monotonic(), 0, [], 0
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        while done < len(tasks):
            try:
                kind, wid, idx, payload = result_q.get(timeout=1.0)
                if kind == "start":
                    running[wid] = (idx, payload)
                    continue
                running.pop(wid, None)
                writer.writerows(payload)
                done += 1
            except queue.Empty:
                pass
            now = time.monotonic()
            for wid, (idx, t0) in list(running.items()):
                if now - t0 > hard:  # stuck in a single execution: kill and replace
                    procs.pop(wid).terminate()
                    del running[wid]
                    writer.writerows(hung_rows(tasks[idx]))
                    hung.append(tasks[idx])
                    done += 1
                    spawn()
            if done != shown and (done % 25 == 0 or done == len(tasks)):
                shown = done
                f.flush()
                el = now - start
                print(f"  {done}/{len(tasks)} sessions, {el:.0f} s, "
                      f"~{el / done * (len(tasks) - done):.0f} s left", flush=True)

    for p in procs.values():
        p.terminate()
    print(f"Wrote {args.out} in {time.monotonic() - start:.0f} s")
    if hung:
        print(f"{len(hung)} sessions hung and were killed after {hard:g} s (counted as nothing found):")
        for m, _, mode, s, *_ in hung:
            print(f"  {m} {mode} seed {s}")


if __name__ == "__main__":
    main()
