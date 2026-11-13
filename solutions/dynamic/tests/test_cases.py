"""Check the interpreter against every @Case annotation in JPAMB.

Run from solutions/dynamic:
    uv run pytest                     # all cases
    uv run pytest -k Strings          # only methods whose name contains "Strings"
    uv run pytest -k "StringChecks and checkToken"

Each case is one test, named after the method and input, e.g.
    test_case[jpamb.cases.Strings.sayHello:(s'hello') -> ok]
A failing test shows the expected and the actual outcome.
"""

import os
from pathlib import Path

import pytest

import dynamic
import jpamb
from jpamb.case import Case

REPO_ROOT = Path(__file__).resolve().parents[3]
CASES_FILE = REPO_ROOT / "target" / "stats" / "cases.txt"
MAX_STEPS = 10_000  # enough for every terminating case in JPAMB


def load_cases() -> list[Case]:
    return [Case.decode(line) for line in CASES_FILE.read_text().splitlines() if line.strip()]


def case_id(case: Case) -> str:
    m = case.methodid
    return f"{m.classname}.{m.extension.name}:{case.experiment.input.encode()} -> {case.result}"


def run(bc, case: Case) -> str:
    """Interpret one case and return its outcome, e.g. "ok" or "assertion error"."""
    state = dynamic.initial(bc, case.methodid, case.experiment.input)
    for _ in range(MAX_STEPS):
        _, state = dynamic.step(bc, state)
        if isinstance(state, str):
            return state
    return "*"  # did not finish: JPAMB's name for running forever


@pytest.fixture(scope="session")
def bc():
    os.chdir(REPO_ROOT)  # jpamb.setup() looks for the suite in the current folder
    suite, eff = jpamb.setup()
    return jpamb.Bytecode(suite, eff, {})


@pytest.mark.parametrize("case", load_cases(), ids=case_id)
def test_case(bc, case, capsys):
    if case.result == "*":
        pytest.skip("non-terminating case: checked with jpamb interpret instead")
    try:
        outcome = run(bc, case)
    except NotImplementedError as e:
        pytest.fail(f"interpreter does not support this yet: {e}")
    assert outcome == case.result
