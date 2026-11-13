"""The project's fuzzer, run through JPAMB like the assignment tools.

Usage (from the repository root, with this project's environment active):
    jpamb -vv analyse --iterations 1 fuzz-analysis
    jpamb -vv analyse --report report.sexp fuzz-analysis

It runs inputs on our own interpreter (solutions/dynamic/src/dynamic.py) and
reports which outcomes it found for each method.

This first version is the BASELINE: random inputs, biased towards
"interesting" values. The analysis-guided parts (constant extraction, runtime
comparison values, coverage) are added on top of `fuzz()` later.
"""

import random
import string
import time
from dataclasses import dataclass, field

import dynamic
import jpamb
import jvm

MAX_RUNS = 2000  # inputs tried per method at most
TIME_BUDGET = 1.0  # seconds per method at most
MAX_STEPS = 1000  # interpreter steps per run before we call it "*"
SEED = 0  # fixed, so every run of the analysis gives the same result

INT_MIN, INT_MAX = -(2**31), 2**31 - 1
INTERESTING_INTS = [0, 1, -1, 2, -2, 10, -10, 100, -100, INT_MIN, INT_MAX]
ALPHABET = string.ascii_letters + string.digits  # no "'": JPAMB's syntax cannot hold it


# --- Input generation ---------------------------------------------------------

def random_int(rand: random.Random) -> int:
    """70% an interesting value, 30% any int."""
    if rand.random() < 0.7:
        return rand.choice(INTERESTING_INTS)
    return rand.randint(INT_MIN, INT_MAX)


def random_value(rand: random.Random, param: jvm.Type) -> jpamb.case.Value:
    match param:
        case jvm.Int():
            return jpamb.case.Int(random_int(rand))
        case jvm.Boolean():
            return jpamb.case.Boolean(rand.random() < 0.5)
        case jvm.Char():
            return jpamb.case.Char(rand.choice(ALPHABET))
        case jvm.Object(name=jvm.ClassName("java.lang.String")):
            length = rand.choice([0, 1, 2, 3, 5, 8])
            return jpamb.case.String("".join(rand.choice(ALPHABET) for _ in range(length)))
        case jvm.Array(contains=jvm.Int()):
            length = rand.choice([0, 1, 2, 3, 5])
            return jpamb.case.Array(jvm.Int(), tuple(random_int(rand) for _ in range(length)))
        case jvm.Array(contains=jvm.Char()):
            length = rand.choice([0, 1, 2, 3, 5])
            return jpamb.case.Array(jvm.Char(), tuple(rand.choice(ALPHABET) for _ in range(length)))
        case _:
            raise NotImplementedError(f"no random values for {param!r} yet")


def random_input(rand: random.Random, methodid: jvm.AbsMethodID) -> jpamb.case.Input:
    return jpamb.case.Input(tuple(random_value(rand, p) for p in methodid.extension.params))


# --- The fuzzing loop -----------------------------------------------------------

@dataclass
class Config:
    """Which parts of the fuzzer are switched on. The evaluation compares these.
    The baseline ignores them all; each part starts to matter once it is built."""
    use_coverage: bool = True  # keep inputs that reach new code, mutate them
    use_static_constants: bool = True  # dictionary from the bytecode
    use_runtime_values: bool = True  # dictionary from values compared while running


@dataclass
class Found:
    """When an outcome was first seen."""
    input: jpamb.case.Input
    run: int  # 1 = the first input tried
    seconds: float  # since the start of fuzzing


@dataclass
class Result:
    found: dict[str, Found] = field(default_factory=dict)  # outcome -> first time seen
    runs: int = 0  # inputs tried in total
    seconds: float = 0.0  # time spent in total


def fuzz(bc: jpamb.Bytecode, methodid: jvm.AbsMethodID, seed: int, max_runs: int,
         config: Config = Config(), time_budget: float | None = None) -> Result:
    """Try up to `max_runs` inputs (and at most `time_budget` seconds, if given).
    The same seed always gives the same inputs, so a result can be repeated."""
    rand = random.Random(seed)
    result = Result()
    has_params = len(methodid.extension.params) > 0
    start = time.monotonic()
    while result.runs < max_runs:
        if time_budget is not None and time.monotonic() - start > time_budget:
            break
        inp = random_input(rand, methodid)
        outcome = dynamic.run(bc, methodid, inp, MAX_STEPS)
        result.runs += 1
        if outcome not in result.found:
            result.found[outcome] = Found(inp, result.runs, time.monotonic() - start)
        if not has_params:  # same input every time: one run says it all
            break
    result.seconds = time.monotonic() - start
    return result


def analyse():
    """Entry point for `jpamb analyse ... fuzz-analysis`."""
    methodid = jpamb.getmethodid(
        "fuzz-analysis",
        "0.1",
        "Group 16",
        ["dynamic", "python"],
        for_science=True,
    )

    suite, eff = jpamb.setup()
    bc = jpamb.Bytecode(suite, eff, {})
    dynamic.TRACE = False  # no per-instruction printing while fuzzing

    try:
        found = fuzz(bc, methodid, SEED, MAX_RUNS, time_budget=TIME_BUDGET).found
    except NotImplementedError:
        # The interpreter cannot run this method (e.g. method calls): we know nothing.
        for query in jpamb.QUERIES:
            print(f"{query};unsupported")
        return

    for query in jpamb.QUERIES:
        if query not in found:
            print(f"{query};not-found")
        elif query == "*":
            # Hitting the step limit does not prove a loop is infinite: a long
            # but finite run (e.g. Tricky.collatz) looks the same. So "*" gets
            # its own, weaker category instead of "found".
            print(f"{query};timeout")
        else:
            print(f"{query};found")


def show_bytecode():
    """Philipp's helper: print a method's bytecode, one instruction per line.
    Usage: python -c "import fuzzer; fuzzer.show_bytecode()" <method id>"""
    methodid = jpamb.getmethodid("show-bytecode", "1.0", "Group 16", ["static", "python"], for_science=True)
    suite, eff = jpamb.setup()
    method = jpamb.Bytecode(suite, eff, {}).getmethod(methodid)
    print(f"{methodid}  (max_locals={method.max_locals})")
    for offset, opr in enumerate(method.opcodes):
        print(f"{offset:3}: {opr}")


# Kept for the existing test in tests/test_fuzzer.py
def n_larger_5(n):
    return n > 5
