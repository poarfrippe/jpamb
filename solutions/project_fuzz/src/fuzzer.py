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
        "Fripp",
        ["static", "python"],
        for_science=True,
    )

    suite, eff = jpamb.setup()
    bc = jpamb.Bytecode(suite, eff, {})


    print("Hello :)")
    print(f"bc: {bc!r}")
