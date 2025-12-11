from guards import *
import pytest


def assert_error_type(outcome: Outcome, typ: type):
    assert type(outcome.error) == typ # type: ignore


def test_guard():
    assert guard(int, StopIteration, ValueError)("42") == Ok(42)
    assert_error_type(guard(int, StopIteration, ValueError)("nah"), ValueError)
    assert_error_type(guard(int, Exception)("nah"), ValueError)

    with pytest.raises(ValueError): guard(int, StopIteration, TypeError)("nah")
    with pytest.raises(TypeError): guard(int, Exception())("nah") # type: ignore
    with pytest.raises(TypeError): guard("int", Exception)("nah") # type: ignore

    with pytest.warns(SyntaxWarning): guard(int)("25")

    # Test determinism of guarded functions
    safe_int = guard(int, ValueError)
    assert safe_int("1") == Ok(1)
    assert safe_int("2") == Ok(2)
    assert_error_type(safe_int("3.0"), ValueError)
    assert safe_int("4") == Ok(4)


def test_guard_value():
    assert guard_value("42", "1", "", 42) == Ok("42")
    assert_error_type(guard_value("", [1, 2, 3], ""), DefaultAsError)

    with pytest.warns(SyntaxWarning): guard_value("42")


def test_guard_on_none():
    assert guard_on_none(False) == Ok(False)
    assert type(guard_on_none(None).error) == DefaultAsError # type: ignore


def test_guard_assert():
    i = 0
    def f(x, arg1, arg2):
        nonlocal i
        assert arg1 == "arg1"
        assert arg2 == "arg2"
        i += 1
        return len(x) > 0
    assert guard_assert([1, 2, 5], f, "arg1", arg2="arg2") == Ok([1, 2, 5])
    assert type(guard_assert([], f, "arg1", arg2="arg2").error) == GuardAssertError # type: ignore
    assert i == 2


def test_guard_context():
    with guard_context(BaseException) as c1: int("42")
    c1.outcome.or_raise().use()
    with guard_context(StopIteration, ValueError) as c2: int("nah")
    assert_error_type(c2(), ValueError)
    with guard_context(Exception) as c3: int("nah")
    assert_error_type(c3.outcome, ValueError)

    with pytest.raises(ValueError):
        with guard_context(StopIteration, TypeError): int("nah")
    with pytest.raises(TypeError):
        with guard_context(Exception()): raise AssertionError() # type: ignore
    
    with pytest.warns(SyntaxWarning):
        with guard_context() as c4: pass
        c4().or_raise().use()
    
    with guard_context(ArithmeticError, return_must_use=False) as c5: pass
    assert c5.outcome.or_raise() == None


def test_force_guard():
    @force_guard(StopIteration, ValueError)
    def safe_int1(x):
        return int(x)
    @force_guard(Exception)
    def safe_int2(x):
        return int(x)
    @force_guard(StopIteration, TypeError)
    def safe_int3(x):
        return int(x)
    
    assert safe_int1("42") == Ok(42)
    assert_error_type(safe_int1("nah"), ValueError)
    assert_error_type(safe_int2("nah"), ValueError)

    with pytest.raises(ValueError): safe_int3("nah")
    with pytest.raises(TypeError):
        @force_guard(Exception()) # type: ignore
        def f(): pass

    with pytest.warns(SyntaxWarning):
        @force_guard()
        def f(): pass

    # Test determinism of guarded functions
    @force_guard(ValueError)
    def safe_int(x):
        return int(x)
    assert safe_int("1") == Ok(1)
    assert safe_int("2") == Ok(2)
    assert_error_type(safe_int("3.0"), ValueError)
    assert safe_int("4") == Ok(4)