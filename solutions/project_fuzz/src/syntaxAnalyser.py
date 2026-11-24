from hypothesis.strategies import none
import sys
import re
import logging
from pathlib import Path

import tree_sitter_java as tsjava
from tree_sitter import Language, Node, Parser

import jpamb
from jpamb import jvm


JAVA = Language(tsjava.language())
PARSER = Parser(JAVA)


def _walk(node: Node):
    """Depth-first, document order."""
    yield node
    for child in node.children:
        yield from _walk(child)


def _parse_decimal(node: Node) -> int:
    """Turn a decimal_integer_literal node into an int, including a leading unary minus."""
    text = node.text.decode().replace("_", "").rstrip("lL")
    value = int(text)
    parent = node.parent
    # In tree-sitter-java, "-1" is unary_expression("-", decimal_integer_literal("1"))
    if (
        parent is not None
        and parent.type == "unary_expression"
        and parent.children[0].type == "-"
    ):
        value = -value
    return value


def getIntsFromSrcTS(src: bytes, methodName: str) -> set[int] | None:
    """All decimal int literals inside the first method_declaration called methodName.
    Returns None if the method does not exist."""
    tree = PARSER.parse(src)

    method = next(
        (
            n
            for n in _walk(tree.root_node)
            if n.type == "method_declaration"
            and n.child_by_field_name("name").text.decode() == methodName
        ),
        None,
    )
    if method is None:
        return None

    # method.start_byte/end_byte is the exact span of the declaration,
    # so we cannot overshoot into the next method or stop at an inner '}'.
    return set([
        _parse_decimal(n)
        for n in _walk(method)
        if n.type == "decimal_integer_literal"
    ])

def getDictFromMethodIdTS(absmethodid: jvm.AbsMethodID) -> tuple[set[int], list[str]]:
    log = logging
    log.basicConfig(level=logging.DEBUG)

    suite, _ = jpamb.setup()
    srcfile = suite.sourcefile(absmethodid.classname).relative_to(Path.cwd())

    log.debug("parse sourcefile %s", srcfile)
    with open(srcfile, "rb") as f: 
        src = f.read()

    intConstants = getIntsFromSrcTS(src, absmethodid.methodid.name)
    strLiterals = getStringsFromSrcTS(src, absmethodid.methodid.name)

    if intConstants is None or strLiterals is None:
        log.error("Could not find method %s", absmethodid.methodid.name)
        sys.exit(1)

    return (intConstants, strLiterals)

INT_MIN, INT_MAX = -2**31, 2**31 - 1
def augmentWithBoundryValues(constants: set[int]) -> set[int]:
    base = set(constants) | {INT_MIN, INT_MAX, -1, 0, 1}
    result = base | {x + d for x in base for d in (-1, 1)}
    return {v for v in result if INT_MIN <= v <= INT_MAX}

_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f",
    "s": " ", '"': '"', "'": "'", "\\": "\\",
}
_ESC_RE = re.compile(r"\\(u+[0-9a-fA-F]{4}|[0-7]{1,3}|.)", re.DOTALL)


def _unescape_java(s: str) -> str:
    def repl(m: re.Match) -> str:
        e = m.group(1)
        if e[0] == "u":
            return chr(int(e.lstrip("u"), 16))
        if e[0] in "01234567":
            return chr(int(e, 8))
        return _ESCAPES.get(e, m.group(0))  # unknown escape: leave as is
    return _ESC_RE.sub(repl, s)


def _parse_string(node: Node) -> str:
    text = node.text.decode()
    if text.startswith('"""'):                       # text block (simplified)
        inner = text[3:-3]
        inner = inner.split("\n", 1)[1] if "\n" in inner else inner
    else:
        inner = text[1:-1]                           # strip the quotes
    return _unescape_java(inner)

def _find_method(root: Node, methodName: str) -> Node | None:
    return next(
        (
            n
            for n in _walk(root)
            if n.type == "method_declaration"
            and n.child_by_field_name("name").text.decode() == methodName
        ),
        None,
    )

def _method_body(method: Node) -> Node | None:
    # None for abstract/interface methods without a body
    return method.child_by_field_name("body")


def getStringsFromSrcTS(src: bytes, methodName: str) -> list[str] | None:
    """All string literals inside the first method_declaration called methodName.
    Returns None if the method does not exist."""
    tree = PARSER.parse(src)
    method = _find_method(tree.root_node, methodName)
    if method is None:
        return None
    body = _method_body(method)
    if body is None:
        return []
    return [
        _parse_string(n)
        for n in _walk(body)
        if n.type == "string_literal"
    ]
