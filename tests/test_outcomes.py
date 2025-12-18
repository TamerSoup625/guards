from src.guards.guards import *
import pytest


class MyException(BaseException): pass


@pytest.fixture
def exc():
    return MyException('something wrong')


def test_ok_init():
    y = Ok(25)
    assert y.ok == 25


def test_error_init(exc):
    n = Error(exc)
    assert n.error == exc


def test_repr(exc):
    y = Ok("Hello")
    n = Error(exc)
    # repr() should return a representation similar to how you create the object
    assert repr(y) == "Ok('Hello')"
    assert repr(n) == "Error(MyException('something wrong'))"
    assert y == eval(repr(y))
    assert type(eval(repr(n)).error) == MyException


def test_bool(exc):
    assert Ok(False)
    assert not Error(exc)


def test_equality(exc):
    assert Ok([2, 5]) == Ok([2] + [5])
    assert Error(exc) == Error(exc)
    assert Ok(exc) != Error(exc)
    assert Ok([2, 5]) != Ok([2, 4])
    assert Error(Exception()) != Error(Exception())
    assert Ok(1) != 1
    assert not (Ok(1) != Ok(1))
    assert not (Error(Exception()) == Error(Exception()))
    assert Ok(1) != Ok("1")


def test_hash(exc):
    assert len({Ok(42), Ok(42), Error(exc), Ok("42"), Error(exc), Error(AssertionError())}) == 4
    assert len({Ok(exc), Error(exc)}) == 2
    with pytest.raises(TypeError, match="unhashable"): hash(Ok([]))


def test_attributes(exc):
    assert Ok("yeah").ok == "yeah"
    assert Error(exc).error == exc
    assert +Ok("yeah") == "yeah"
    assert -Error(exc) == exc
    with pytest.raises(AttributeError): Ok("yeah").error # type: ignore
    with pytest.raises(AttributeError): Error(exc).ok # type: ignore
    with pytest.raises(TypeError, match="bad operand"): -Ok("yeah") # type: ignore
    with pytest.raises(TypeError, match="bad operand"): +Error(exc) # type: ignore


class TestOrMethods:
    def test_on_ok(self):
        ok_val = [1, 2, 3]
        ok_obj = Ok(ok_val)
        assert ok_obj.or_none() is ok_val
        assert ok_obj.or_raise(ValueError()) is ok_val
        assert ok_obj.or_else("error") is ok_val
        assert ok_obj.or_else_do(lambda _: pytest.fail("or_else_do called on Ok value")) is ok_val
    

    def test_or_none_err(self, exc):
        assert Error(exc).or_none() == None
    

    def test_or_raise_err(self, exc):
        with pytest.raises(MyException) as exc_info: Error(exc).or_raise()
        assert exc_info.value == exc
        with pytest.raises(MyException) as exc_info: Error(exc).or_raise(None)
        assert exc_info.value == exc
        with pytest.raises(MyException) as exc_info: Error(ValueError()).or_raise(exc)
        assert exc_info.value == exc
        assert type(exc_info.value.__cause__) == ValueError
        with pytest.raises(TypeError): Ok(exc).or_raise(False) # type: ignore
    

    def test_or_else_err(self, exc):
        obj = [1, 2, 3, 4]
        assert Error(exc).or_else(obj) is obj
    

    def test_or_else_do_err(self, exc):
        i = 0
        obj = [6, 2, 5]
        def f(e):
            nonlocal i
            assert e == exc
            i += 1
            return obj
        assert Error(exc).or_else_do(f) is obj
        with pytest.raises(TypeError): Ok(obj).or_else_do("function") # type: ignore
        assert i == 1


def test_unpack(exc):
    obj = {"hi": 25}
    assert Ok(obj).unpack() == (obj, None)
    assert Error(exc).unpack() == (None, exc)


def test_run(exc):
    s = ""
    obj = {1, 2, 5}
    def f(t):
        nonlocal s
        assert t is obj
        s += "+"
        return "f"
    def g(e):
        nonlocal s
        assert e is exc
        s += "-"
        return "g"
    assert Ok(obj).run(on_ok=f, on_error=g) == "f"
    assert Error(exc).run(on_ok=f, on_error=g) == "g"
    with pytest.raises(TypeError): Ok(obj).run(on_ok=f, on_error="function") # type: ignore
    with pytest.raises(TypeError): Error(exc).run(on_ok="function", on_error=g) # type: ignore
    assert s == "+-"


def test_then_run(exc):
    i = 0
    obj = [1, [2, [3]]]
    def f(t, return_type, kwarg):
        nonlocal i
        assert t is obj
        assert kwarg == "kwarg"
        i += 1
        return return_type(exc)
    assert Ok(obj).then_run(f, Ok, kwarg="kwarg") == Ok(exc)
    assert Ok(obj).then_run(f, Error, kwarg="kwarg") == Error(exc)
    assert Error(exc).then_run(lambda _: pytest.fail("then_run called on Error value")) == Error(exc)
    with pytest.raises(TypeError): Error(exc).then_run("function") # type: ignore
    assert i == 2


def test_else_run(exc):
    i = 0
    obj = [[[1], 2], 3]
    def f(t, return_type, kwarg):
        nonlocal i
        assert t is exc
        assert kwarg == "kwarg"
        i += 1
        return return_type(t)
    assert Error(exc).else_run(f, Error, kwarg="kwarg") == Error(exc)
    assert Error(exc).else_run(f, Ok, kwarg="kwarg") == Ok(exc)
    assert Ok(obj).else_run(lambda _: pytest.fail("else_run called on Ok value")) == Ok(obj)
    with pytest.raises(TypeError): Ok(obj).then_run("function") # type: ignore
    assert i == 2


def test_then(exc):
    obj = "hello"
    def f(t, arg1, arg2):
        assert t is obj
        assert arg1 == "arg1"
        assert arg2 == "arg2"
        return t + " world"
    assert Ok(obj).then(lambda x: x + " world") == Ok("hello world")
    assert Ok(obj).then(f, "arg1", arg2="arg2") == Ok("hello world")
    assert Error(exc).then(lambda _: pytest.fail("then called on Error value")) == Error(exc)
    with pytest.raises(TypeError): Error(exc).then("function") # type: ignore


def test_map(exc):
    obj = "hello"
    def f(t, arg1, arg2):
        assert t is obj
        assert arg1 == "arg1"
        assert arg2 == "arg2"
        return t + " world"
    assert Ok(obj).map(lambda x: x + " world") == Ok("hello world")
    assert Ok(obj).map(f, "arg1", arg2="arg2") == Ok("hello world")
    assert Error(exc).map(lambda _: pytest.fail("map called on Error value")) == Error(exc)
    with pytest.raises(TypeError): Error(exc).then("function") # type: ignore