import sys
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

import jpamb
import sexpr
from jpamb import jvm
from jvm.state import PC, StackInt

def analyse():
    """The static analysis"""

    methodid = jpamb.getmethodid(
        "static",
        "1.0",
        "the coverage based fuzzer cookers",
        ["static", "python"],
        for_science=True,
    )

    suite, eff = jpamb.setup()
    bc = jpamb.Bytecode(suite, eff, {})

    method = bc.getmethod(methodid)
    print(f"{methodid}  (max_locals={method.max_locals})")
    for offset, opr in enumerate(method.opcodes):
        print(f"{offset:3}: {opr}")

#just to test the hypothesis tests
def n_larger_5(n):
    return n > 5
