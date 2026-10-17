import sys
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from abstractions import SignSet, Abstraction

import jpamb
import sexpr
from jpamb import jvm
from jvm.state import PC, StackInt


@dataclass(frozen=True)
class State(sexpr.AsSExpr):
    locals: tuple[SignSet, ...]
    stack: tuple[SignSet | int, ...]

    def __post_init__(self):
        assert isinstance(self.locals, tuple)
        assert isinstance(self.stack, tuple)

    def __str__(self):
        return f"{', '.join(map(str, self.locals))}/{':'.join(map(str, self.stack))}"

    def __or__(self, other):
        assert isinstance(other, State), f"Expected State but got {other!r}"
        assert len(self.stack) == len(other.stack), "Stacks should be equal lenght"
        assert len(self.locals) == len(other.locals), "Locals should be equal lenght"

        return State(
            tuple(s1 | s2 for s1, s2 in zip(self.locals, other.locals)),
            tuple(s1 | s2 for s1, s2 in zip(self.stack, other.stack)),
        )

    def __and__(self, other):
        assert isinstance(other, State), f"Expected State but got {other!r}"
        assert len(self.stack) == len(other.stack), "Stacks should be equal lenght"
        assert len(self.locals) == len(other.locals), "Locals should be equal lenght"

        return State(
            tuple(s1 & s2 for s1, s2 in zip(self.locals, other.locals)),
            tuple(s1 & s2 for s1, s2 in zip(self.stack, other.stack)),
        )

    def push(self, value: SignSet):
        assert isinstance(value, SignSet), f"Expected sign set but got {value}"
        return State(self.locals, self.stack + (value,))

    def pop(self, number=1):
        return self.stack[-number:], State(self.locals, self.stack[:-number])

    def load(self, index):
        return self.locals[index]

    def store(self, index, value):
        return State(
            tuple(self.locals[:index]) + (value,) + tuple(self.locals[index + 1 :]),
            self.stack,
        )

    # @classmethod
    # def abstract(cls, values: Iterable[jvms.StackValue]) -> Self:
    #     
    #     return cls()
    #
    # def __contains__(self, value: jvms.StackValue) -> bool:
    #     raise NotImplementedError 
    # def __le__(self, other):
    #     raise NotImplementedError


def manystep(
    bc: jpamb.Bytecode,
    pc: PC,
    state: State,
) -> Iterable[tuple[PC, object] | str]:
    opr = bc[pc]

    match opr:
        case jvm.Get(static=True, field=field): # villeicht auch fuer nonstatic, hohlt naenmlich sachen vom heap, was 0pointer resulten kann!
            # Hack - Only handle the assertion case
            assert field.extension.name == "$assertionsDisabled"

            # Hack - Assuming assertions are never disabled
            va = SignSet.abstract([StackInt(0)])

            yield (pc + 1, state.push(va))

        case jvm.Ifz(condition=op, target=target):
            [val], after = state.pop(1)

            for res in SignSet.compare(val, SignSet.abstract([StackInt(0)]), op):
                match res:
                    case True:
                        yield (pc % target, after)
                    case False:
                        yield (pc + 1, after)
                    case err:
                        yield err

        case jvm.Load(index=i):
            va = state.load(i)
            yield (pc + 1, state.push(va))

        case jvm.Goto(target=t):
            yield (pc % t, state)

        case jvm.Binary(type=jvm.Int(), operant=op):
            [v1, v2], after = state.pop(2)
            res, err = SignSet.arithmetic(v1, v2, op)
            for s in err:
                yield s
            yield (pc + 1, after.push(res))

        case jvm.Return(type=None):
            yield "ok"

        case jvm.Return(type=t):
            # Hack -- we assume that we always return.
            yield "ok"

        case jvm.New(classname=jvm.ClassName("java.lang.AssertionError")):
            # Hack -- if we create an assertion error, we probably also throw it.
            yield "assertion error"
        case jvm.Push(type=t, value=v):
            if t is jvm.Int():
                assert isinstance(v, int)
                after = state.push(SignSet.abstract([StackInt(v)]))
            elif t is jvm.Reference():
                assert isinstance(v, int), f"expected reference, but got {v}"
                after = state.push(SignSet.from_sign('+'))
            else:
                raise NotImplementedError(f"Error for {t!r}")

            yield (pc + 1, after)
        case jvm.If(condition=op, target=target):
            [v1, v2], after = state.pop(2)
            for res in SignSet.compare(v1, v2, op):
                match res:
                    case True:
                        yield (pc % target, after)
                    case False:
                        yield (pc + 1, after)
        case jvm.NewArray(type=jvm.Int(), dim=1):
            [val], after = state.pop(1)
            if -1 in val.signs:
                raise RuntimeError("Negative Array Size")
            yield (pc + 1, after.push(SignSet.from_sign('+')))
        case jvm.Dup(words=1):
            [val], after = state.pop(1)
            yield (pc + 1, after.push(val).push(val)) 
        case jvm.ArrayStore(type=jvm.Int()):
            [array, index, _v], after = state.pop(3)
            if 0 in array.signs or -1 in array.signs:
                yield "null pointer"
            if -1 in index.signs:
                yield "out of bounds"
            if array.signs - {0, -1} and index.signs - {-1}:
                yield (pc + 1, after)
        case jvm.Store(index=i):
            [val], after = state.pop(1)
            yield (pc + 1, after.store(i, val))
        case jvm.ArrayLength():
            [array], after = state.pop(1)
            if 0 in array.signs or -1 in array.signs:
                yield "null pointer"
            if array.signs - {0, -1}:
                yield (pc + 1, after.push(SignSet.from_sign('0+')))
        case jvm.ArrayLoad(type=t):
            [array, index], after = state.pop(2)
            if 0 in array.signs or -1 in array.signs:
                yield "null pointer"
            if -1 in index.signs:
                yield "out of bounds"
            if array.signs - {0, -1} and index.signs - {-1}:
                yield (pc + 1, after.push(SignSet.top() if t is jvm.Int() else SignSet.from_sign('01')))
        case jvm.Incr(index=i, amount=amount):
            old: SignSet = state.load(i)
            amountSign: SignSet = SignSet.abstract([StackInt(amount)])
            new, _err = SignSet.arithmetic(old, amountSign, jvm.BinaryOpr.Add)
            assert isinstance(new, SignSet), f"got: {new!r}"
            updated: State = state.store(i, new)
            yield (pc + 1, updated)
        case jvm.Negate():
            [val], after = state.pop(1)
            yield (pc + 1, after.push(SignSet.top - val)) #props not right
        case a:
            raise NotImplementedError(f"still to be done: {a!r}")


def initialstate(
    bc: jpamb.Bytecode,
    methodid: jvm.AbsMethodID,
    inputs: jpamb.Input | None,
) -> dict[PC, State]:
    method = bc.getmethod(methodid)
    locals = [SignSet.bot()] * method.max_locals

    if inputs is None:
        for i, p in enumerate(methodid.extension.params):
            locals[i] = SignSet.top()
    else:
        for i, x in enumerate(inputs.values):
            match x:
                case jpamb.case.Boolean(value=value):
                    locals[i] = SignSet.abstract([StackInt(int(value))])
                case jpamb.case.Int(value=value):
                    locals[i] = SignSet.abstract([StackInt(int(value))])
                case jpamb.case.Array():
                    locals[i] = SignSet.from_sign("+")
                case _:
                    raise NotImplementedError(f"Unsupported value {x!r}")

    state = State(tuple(locals), ())
    return {PC(methodid, 0): state}


@dataclass
class AbstractInterpreter:
    bc: jpamb.Bytecode
    worklist: deque[PC]
    states: dict[PC, State]

    @staticmethod
    def initial(bc: jpamb.Bytecode, methodid: jvm.AbsMethodID, inputs):
        states = initialstate(bc, methodid, inputs)
        worklist = deque(states.keys())

        return AbstractInterpreter(bc, worklist, states)

    def step(self) -> tuple[PC, set[str]]:
        pc = self.worklist.pop()

        print(f"Stepping {pc}:\n > {self.bc[pc]}", file=sys.stderr)

        finals = set()

        for res in manystep(self.bc, pc, self.states[pc]):
            if isinstance(res, str):
                finals.add(res)
            else:
                pc_, st = res

                before = self.states.get(pc_, None)
                if before is None:
                    after = st
                else:
                    after = before | st
                if before is None or after != before:
                    self.states[pc_] = after
                    self.worklist.append(pc_)

        return pc, finals


def interpret():
    """The static analysis"""
    methodid, input, steps = jpamb.getcase(
        "static",
        "1.0",
        "Fripp",
        ["static", "python"],
        for_science=True,
    )
    suite, eff = jpamb.setup()
    bc = jpamb.Bytecode(suite, eff, {})

    ai = AbstractInterpreter.initial(bc, methodid, input)

    x = jpamb.emit_init(ai.states)

    while steps > 0 and ai.worklist:
        pc, final = ai.step()
        for f in final:
            jpamb.emit_step(x, pc, f, depth=1)
            steps -= 1

        x = jpamb.emit_step(x, pc, ai.states, depth=1)
        steps -= 1


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

    steps = 300

    ai = AbstractInterpreter.initial(bc, methodid, None)

    final = set()
    while steps > 0 and ai.worklist:
        _pc, finals = ai.step()
        final |= finals
        steps -= 1

    for f in jpamb.QUERIES:
        if f not in final:
            print(f"{f};no")
        else:
            print(f"{f};maybe")
