from guards import *
import pytest


class MyException(BaseException): pass


@pytest.fixture
def exc():
    return MyException('something wrong')


def test_isok_iserror(exc):
    assert isok(Ok(False))
    assert not isok(Error(exc))
    assert not iserror(Ok(False))
    assert iserror(Error(exc))


def test_throw(exc):
    with pytest.raises(MyException) as exc_info: throw(exc)
    assert exc_info.value == exc
    with pytest.raises(MyException) as exc_info: throw(exc, from_=ValueError())
    assert exc_info.value == exc
    assert type(exc_info.value.__cause__) == ValueError


def test_must_use():
    mu = MustUse()
    mu.use()
    mu.use()
    mu = MustUse()
    with pytest.warns(RuntimeWarning): del mu