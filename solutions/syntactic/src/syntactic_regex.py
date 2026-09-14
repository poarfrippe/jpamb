#!/usr/bin/env python3
"""A very stupid syntactic analysis, that does some things."""

import logging
import re
import sys
from pathlib import Path

import jpamb


def main():
    absmethodid = jpamb.getmethodid(
        "syntaxer",
        "1.0",
        "Philipp Gruber",
        ["syntactic", "python"],
        for_science=True,
    )

    # if absmethodid.methodid.name == "arrayIsNull" or absmethodid.methodid.name == "arrayIsNullLength":
    #     print("null pointer;cheater")
    #     return
    
    log = logging
    log.basicConfig(level=logging.DEBUG)

    suite, _ = jpamb.setup()

    srcfile = suite.sourcefile(absmethodid.classname).relative_to(Path.cwd())

    with open(srcfile, "r") as f:
        log.debug("parse sourcefile %s", srcfile)
        content = f.read()

    res = re.search(rf".* {absmethodid.methodid.name}\(.*\)", content)

    if not res:
        log.error("Could not find method")
        sys.exit(1)

    log.debug(f"found {res}")
    rest = content[res.end(0) : -1]


    # assert error 
    assert_or_end = re.search(r"assert\strue|assert\sfalse|assert|(^\s*})", rest, re.MULTILINE)

    if not assert_or_end:
        log.error("Could not end of method or assert")
        log.error(rest)
        sys.exit(1)

    log.debug(f"found {assert_or_end}")
    assert_found = assert_or_end.group(0) == "assert"
    assert_false = assert_or_end.group(0) == "assert false"
    assert_true = assert_or_end.group(0) == "assert true"

    if assert_found:
        log.debug("Found assertion")
        print("assertion error;found-assert")
    elif assert_false:
        log.debug("Found failing assertion")
        print("assertion error;found-assert-safe")
    elif assert_true:
        log.debug("Found not failing assertion")
        print("assertion error;found-assert-true")
    else:
        log.debug("No assertion")
        print("assertion error;not-found-assert")

    # devide by zero 
    divide_or_end = re.search(r"/\s0|/|(^\s*})", rest, re.MULTILINE)

    if not divide_or_end:
        log.error("Could not find end of method or divide")
        log.error(rest)
        sys.exit(1)

    log.debug(f"found divide {divide_or_end}")
    divide_found = divide_or_end.group(0) == "/"
    divide_found_by_zero = divide_or_end.group(0) == "/ 0"
    
    if divide_found:
        log.debug("Found divide")
        print("divide by zero;found-div")
    elif divide_found_by_zero:
        log.debug("Found div by zero")
        print("divide by zero;found-div-safe")
    else:
        log.debug("No divide")
        print("divide by zero;not-found-div")

    # out of bounds 
    array_or_end = re.search(r"\[|(^\s*})", rest, re.MULTILINE)

    if not array_or_end:
        log.error("Could not find end of method or array brackets")
        log.error(rest)
        sys.exit(1)

    log.debug(f"found array bracket {array_or_end}")
    array_found = array_or_end.group(0) == "["

    if array_found:
        log.debug("Found array")
        print("out of bounds;found-arr")
    else:
        log.debug("No divide")
        print("out of bounds;not-found-arr")

    # null pointer 
    deref_or_end = re.search(r"\.|(^\s*})", rest, re.MULTILINE)

    if not deref_or_end:
        log.error("Could not find end of method or dereference")
        log.error(rest)
        sys.exit(1)

    log.debug(f"found pointer dereference {deref_or_end}")
    deref_found = deref_or_end.group(0) == "."

    if deref_found:
        log.debug("Found deref")
        print("null pointer;found-deref")
    else:
        log.debug("No divide")
        print("null pointer;not-found-deref")
    
    # null pointer 
    loop_or_end = re.search(r"for|while|(^\s*})", rest, re.MULTILINE)

    if not loop_or_end:
        log.error("Could not find end of method or loop")
        log.error(rest)
        sys.exit(1)

    log.debug(f"found loop {deref_or_end}")
    loop_found = loop_or_end.group(0) in ("for", "while")

    if loop_found:
        log.debug("Found loop")
        print("*;found-loop")
    else:
        log.debug("No loop")
        print("*;not-found-loop")

    for q in jpamb.QUERIES:
        if q != "assertion error" and q != "divide by zero" and q != "out of bounds" and q != "null pointer" and q != "*":
            print(f"{q};skip")
