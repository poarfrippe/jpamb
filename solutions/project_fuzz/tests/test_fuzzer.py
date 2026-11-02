from hypothesis import given, strategies as st
import fuzzer

@given(st.integers(min_value=-(2**31), max_value=2**31 - 1))
def test_int_roundtrip(n):
    # placeholder: replace with a real property of your code
    assert -(2**31) <= n < 2**31


INT32 = st.integers(min_value=-(2**31), max_value=2**31 - 1)


@given(INT32)
def test_returns_bool(n):
    assert isinstance(fuzzer.n_larger_5(n), bool)

@given(st.integers(min_value=6, max_value=2**31 - 1))
def test_true_above_5(n):
    assert fuzzer.n_larger_5(n) is True
