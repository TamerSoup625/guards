from guards import *
import pytest


class MyException(BaseException): pass


@pytest.fixture
def exc():
    return MyException('something wrong')


def test_outcome_collect(exc):
    from typing import Any
    iterable1: tuple[Any, ...] = (Ok(1), Ok("2"), Ok(3), Ok(False))
    iterable2: tuple[Any, ...] = (Ok(1), Ok("2"), Error(exc), Ok(False))
    assert outcome_collect(iterable1) == Ok([1, "2", 3, False])
    assert outcome_collect(iter(iterable1)) == Ok([1, "2", 3, False])
    assert outcome_collect(iterable2) == Error(exc)
    assert outcome_collect(iter(iterable2)) == Error(exc)

    assert outcome_collect([]) == Ok([])
    assert outcome_collect(iter([])) == Ok([])

    iterable_wrong: tuple[Any, ...] = (Ok(3), Ok(1), 2, Ok(5))
    with pytest.raises(TypeError): outcome_collect(iterable_wrong)
    with pytest.raises(TypeError): outcome_collect(5) # type: ignore

    # Iteration should stop on the first error each time, or consume the whole iterator
    exc2 = ValueError()
    my_iter = iter([Ok(False), Ok(True), Error(exc), Ok(25), Error(exc2), Ok("Final")])
    assert outcome_collect(my_iter) == Error(exc) # type: ignore
    assert outcome_collect(my_iter) == Error(exc2) # type: ignore
    assert outcome_collect(my_iter) == Ok(["Final"]) # type: ignore
    assert list(my_iter) == []


def test_outcome_partition(exc):
    exc2 = ValueError()
    from typing import Any
    iterable1: tuple[Any, ...] = (Ok([]), Ok(()), Error(exc), Ok({}), Error(exc2))
    iterable2: tuple[Any, ...] = (Error(exc), Error(exc2), Ok([]), Ok(()), Ok({}))
    ok1, err1 = outcome_partition(iterable1)
    assert list(ok1) == [[], (), {}] and list(err1) == [exc, exc2]
    ok1, err1 = outcome_partition(iter(iterable1))
    assert list(ok1) == [[], (), {}] and list(err1) == [exc, exc2]
    ok1, err1 = outcome_partition(iter(iterable1))
    ok2, err2 = outcome_partition(iterable2)
    assert tuple(ok1) == tuple(ok2) and tuple(err1) == tuple(err2)

    ok3, err3 = outcome_partition([Ok(False), Ok(True)])
    assert list(ok3) == [False, True] and list(err3) == []
    ok3, err3 = outcome_partition([Error(exc), Error(exc2)])
    assert list(ok3) == [] and list(err3) == [exc, exc2]
    ok3, err3 = outcome_partition([])
    assert list(ok3) == [] and list(err3) == []

    okwrong, errwrong = outcome_partition("Ok, Error") # type: ignore
    with pytest.raises(TypeError): next(okwrong)
    with pytest.raises(TypeError): next(errwrong)
    okwrong, errwrong = outcome_partition(21) # type: ignore
    with pytest.raises(TypeError): next(okwrong)
    with pytest.raises(TypeError): next(errwrong)

    # iterators should be independent of eachother
    okdet, errdet = outcome_partition(iter(iterable1))
    assert next(okdet) == []
    assert next(errdet) == exc
    assert next(okdet) == ()
    assert next(errdet) == exc2
    assert next(okdet) == {}
    okdet, errdet = outcome_partition(iterable1)
    assert next(okdet) == []
    assert next(errdet) == exc
    assert next(okdet) == ()
    assert next(errdet) == exc2
    assert next(okdet) == {}


def assert_error_type(outcome: Outcome, typ: type):
    assert type(outcome.error) == typ # type: ignore


def test_outcome_do(exc):
    assert outcome_do(x + y for x in Ok([1, 2]) for y in Ok(x + [3, 4])) == Ok([1, 2, 1, 2, 3, 4])
    assert_error_type(outcome_do(pytest.fail("outcome_do run on error value") for x in Ok(None) for y in Error(exc)), MyException)
    assert_error_type(outcome_do(
            pytest.fail("outcome_do run on error value")
            for x in Error(exc)
            for y in Ok(pytest.fail("No shortcircuit on error value"))
    ), MyException)

    with pytest.warns(RuntimeWarning): outcome_do(None for y in Ok(1) for x in [1, 2])
    with pytest.warns(RuntimeWarning): outcome_do(None for x in [1, 2] for y in Ok(1))
    with pytest.raises(TypeError): outcome_do(None for y in Ok(1) for x in [])
    with pytest.raises(TypeError): outcome_do(None for x in [] for y in Ok(1))
    with pytest.raises(TypeError): outcome_do(None)


def test_let_ok(exc):
    if let_ok(x := Ok({1: "1"}).let):
        assert x == {1: "1"}
    else: pytest.fail("let_ok returned the wrong value")
    if let_ok(x := Error(exc).let): pytest.fail("let_ok returned the wrong value")

    with pytest.warns(SyntaxWarning): let_ok(Ok(1))
    with pytest.warns(SyntaxWarning): let_ok(Error(exc))


def test_let_not_ok(exc):
    if let_not_ok(x := Ok(False).let):
        pytest.fail("let_not_ok returned the wrong value")
    assert x == False
    if let_not_ok(x := Error(exc).let):
        pass
    else:
        pytest.fail("let_not_ok returned the wrong value")

    with pytest.warns(SyntaxWarning): let_not_ok(Ok(1))
    with pytest.warns(SyntaxWarning): let_not_ok(Error(exc))


def test_pattern_match(exc):
    match Ok({1, 2, 3}):
        case Ok(x): assert x == {1, 2, 3}
        case what: pytest.fail(f"{what} failed pattern match")
    match Error(exc):
        case Error(x): assert x == exc
        case what: pytest.fail(f"{what} failed pattern match")