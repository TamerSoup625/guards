"""
This module provides tools for converting raised exceptions into typed Outcome values,
enabling functional-style error handling while maintaining Python's exception semantics.

```
file_outcome = guard(open, FileNotFoundError, PermissionError)(PATH)
if isok(file_outcome):
    with file_outcome.ok as file:
        print("File contents:")
        print(file.read())
else: # elif iserror(file_outcome):
    os_error = file_outcome.error
    if isinstance(os_error, PermissionError):
        print("Cannot read the file.")
    else: # elif isinstance(os_error, FileNotFoundError):
        print("The file doesn't exist!")
```

Key functions and classes:
    `guard()` - Convert a function to return `Outcome` instead of raising
    `Ok`/`Error` - The two `Outcome` types
    `isok()`/`iserror()` - Type guard functions
"""
from __future__ import annotations
from typing import TypeVar, Generic, Callable, TypeAlias, Union, NoReturn, Literal, Iterator, ParamSpec, Self, overload, Iterable, Concatenate, Any, Never
from warnings import warn
from typing_extensions import TypeIs
from functools import wraps
from inspect import currentframe
import traceback
from sys import stderr
from collections.abc import Iterator


# Huge thanks to this since I copied like half of its code
# https://github.com/rustedpy/result/blob/main/src/result/result.py


__all__ = ["DefaultAsError", "GuardAssertError", "UnfinishedGuardError", "MustUse", "Ok", "Error", "Outcome", "GuardContextBase",
           "guard", "guard_value", "guard_on_none", "guard_assert", "guard_context",
           "isok", "iserror", "outcome_do", "force_guard", "outcome_collect", "outcome_partition", "throw", "let_ok", "let_not_ok"]


T = TypeVar("T")
E = TypeVar("E", bound=BaseException)
GT = TypeVar("GT")
GE = TypeVar("GE", bound=BaseException)
NT = TypeVar("NT")
NE = TypeVar("NE", bound=BaseException)
R = TypeVar("R")
P = ParamSpec("P")
TT = TypeVar("TT")
TE = TypeVar("TE")
K = TypeVar("K")


class DefaultAsError(Generic[T], Exception):
    """
    A default value considered an error. Returned from `guard_value` and `guard_on_none` wrapped in an `Error` object.
    """
    def __init__(self, value: T) -> None:
        super().__init__(value)
        self.value = value
        """The value which is considered an error."""


class GuardAssertError(Generic[T], Exception):
    """
    A value which failed an assertion. Returned from `guard_assert` wrapped in an `Error` object.
    """
    def __init__(self, value: T) -> None:
        super().__init__(value)
        self.value = value
        """The value which failed the assertion."""


class DoFailure(BaseException):
    def __init__(self, value: BaseException) -> None:
        super().__init__(repr(value))
        self.value = value


class UnfinishedGuardError(RuntimeError): """Attempt to access the outcome of a context guard inside the guard itself."""

class UnhandledWarning(RuntimeWarning): pass
class LetWarning(SyntaxWarning): pass
class NotOutcomeWarning(SyntaxWarning): pass

class LetFailure(): pass
LET_FAILURE = LetFailure()


def _test_callable(f):
    """Raises a TypeError if `f` is not callable"""
    if not callable(f):
        raise TypeError(f"'{type(f).__name__}' object is not callable")


class MustUse:
    """
    Used for functions which can return an `Ok` object with no useful information or an `Error` object to make sure the exception is not silently ignored.

    Such functions instead of returning an `Ok(None)` can instead return an `Ok(MustUse())`. When a `MustUse` object is deinitialized it will throw an `UnhandledWarning` if the `use()` function was never called on it, including a stacktrace of the object at the time of initialization.

    ```python
    @force_guard(ValueError)
    def do_something_important():
        ...
        return MustUse()

    match do_something_important():
        Ok(value): value.use()
        Error(exc): print(repr(exc))
    ```

    Example which raises a warning:

    ```python
    @force_guard(ValueError)
    def do_something_important():
        ...
        return MustUse()

    do_something_important()
    ```

    Outputs:

    ```
    Init traceback (most recent call last):
    File ".../tests.py", line 8, in <module>
        do_something_important()
    ...
    .../guards.py:79: UnhandledWarning: MustUse object not used before deinitialization. Call "MustUse.use()" on the object to remove this warning.
    warn('MustUse object not used before deinitialization. Call "MustUse.use()" on the object to remove this warning.', UnhandledWarning)
    ```
    """
    def __init__(self) -> None:
        self.__used = False
        self.__init_stack = traceback.extract_stack(currentframe())
    

    def use(self) -> None:
        """"Use" this object, making it no longer throw a warning on deinitialization. This method can be called multiple times on the same object."""
        self.__used = True
    

    def __del__(self) -> None:
        if not self.__used:
            formatted_stack = "".join(traceback.format_list(self.__init_stack))
            stderr.write("Init traceback (most recent call last):\n" + formatted_stack)
            warn('MustUse object not used before deinitialization. Call "MustUse.use()" on the object to remove this warning.', UnhandledWarning)


class GuardContextBase(Generic[T, E]):
    """
    A context manager which guards the context it's in. Used by `guard_context`.
    """
    def __init__(self, against: tuple[type[E]], ok_type: type[T]) -> None:
        self.__against = against
        self.__ok_type = ok_type
        self.__current_return: bool | E = False
        """False == not yet done, True == done ok, or else done error"""
        self.__ok_return: T | None = None
    

    def __enter__(self):
        return self


    def __exit__(self, _, exc: BaseException | None, __):
        if exc is None:
            self.__current_return = True
            self.__ok_return = self.__ok_type()
            return True
        elif isinstance(exc, self.__against):
            self.__current_return = exc
            return True
        return False
    

    def __call__(self) -> Outcome[T, E]:
        """
        Alias for `GuardContextBase.outcome`.

        Returns the outcome of the guarded context. Raises an `UnfinishedGuardError` if the context this object manages is not exited yet.
        """
        if self.__current_return is False:
            raise UnfinishedGuardError("Cannot access context guard's Outcome inside of the context itself.")
        elif self.__current_return is True:
            return Ok(self.__ok_return) # type: ignore
        return Error(self.__current_return)
    

    @property
    def outcome(self) -> Outcome[T, E]:
        """Returns the outcome of the guarded context. Raises an `UnfinishedGuardError` if the context this object manages is not exited yet."""
        return self()


    def __getattr__(self: Never, attr) -> Never:
        raise AttributeError(f"'GuardContextBase' object has no attribute '{attr}'.\n" +
                             "Get the context's Outcome with the `.outcome` property:\n" +
                             "\twith guard_context(...) as context: ...\n" +
                             "\toutcome = context.outcome")


class Ok(Generic[T]):
    """
    A successful outcome containing the success value. All methods and some properties of `Ok` are also present in `Error`, so you can think of `Outcome` as an abstract base class inherited by `Ok` and `Error`.

    Initializes a new `Ok` object with its contained value.
    """
    # Match support
    __match_args__ = ("ok",)
    """
    `Outcome`s support pattern matching. The match argument of each outcome is its inner value or exception.

    ```python
    iterator = [1, 1, 1]
    for _ in range(4):
        match guard(next, StopIteration)(iterator):
            case Ok(value): assert value == 1
            case Error(exc): assert isinstance(exc, StopIteration)
    ```
    """
    __slots__ = ("__t",)


    def __init__(self, t: T) -> None:
        self.__t = t


    def __repr__(self) -> str:
        return f"Ok({repr(self.__t)})"
    

    def __bool__(self) -> Literal[True]:
        """
        `Ok`s are always true, `Error`s are always false. This can be used for short-circuiting and type guards as an alternative to methods and functions.

        ```python
        from operator import getitem
        mat = [[0, 1], [2, 3]]
        safe_get = guard(getitem, IndexError)
        # Get the second row, or the first, or None if the matrix is empty
        row_or_none = (safe_get(mat, 1) or safe_get(mat, 0) or Ok(None)).ok
        element_maybe = safe_get(mat, 0).then_run(safe_get, 0)
        if element_maybe:
            assert element_maybe.ok == 0
        ```
        """
        return True


    def __eq__(self, value: object) -> bool:
        """
        Checks for equality by value similarly to dataclasses.

        **Note**: `Exception`s check equality by reference.

        ```python
        assert Ok(42) == Ok(42)
        exc = Exception()
        assert Error(exc) == Error(exc)
        ```
        """
        return type(value) == Ok and self.__t == value.ok


    def __ne__(self, value: object) -> bool:
        """
        Checks for inequality by value similarly to dataclasses.

        **Note**: `Exception`s check equality by reference.

        ```python
        assert Ok(42) != Ok(25)
        assert Error(Exception()) != Error(Exception())
        exc = Exception()
        assert Ok(exc) != Error(exc)
        ```
        """
        return not (self == value)


    def __hash__(self) -> int:
        return hash((True, self.__t))


    def __pos__(self) -> T:
        """
        Alias for `Ok.ok`. The contained `Ok` value.

        `Error` does not implement this operator, meaning trying to use it on an object which can be `Error` raises an issue by the type checker.

        ```python
        def f(x: int):
            outcome = guard([1, 2, 4, 8].index, ValueError)(x)
            if isok(outcome):
                return +outcome
            return None
        ```

        Example which raises a typing issue:

        ```python
        def f(x: int):
            outcome = guard([1, 2, 4, 8].index, ValueError)(x)
            # Type checker reports this issue:
            #   Operator "+" not supported for type "Outcome[int, ValueError]"
            return +outcome
        ```
        """
        return self.__t


    def __iter__(self) -> Iterator[T]:
        """
        Used by `outcome_do`.

        Yields once the contained `Ok` value, otherwise raises a special exception with the contained `Error` value.

        Can be used instead of `Outcome.do`. See `outcome_do`.
        """
        yield self.__t


    def or_none(self) -> T:
        """
        Returns the contained `Ok` value or `None`. Equivalent to `or_else(None)`.

        ```python
        assert Ok(42).or_none() == 42
        assert Error(AssertionError()).or_none() == None
        ```
        """
        return self.__t

    def or_else(self, default) -> T:
        """
        Returns the contained `Ok` value or a default fallback value.

        ```python
        assert Ok(42).or_else("error") == 42
        assert Error(AssertionError()).or_else("error") == "error"
        ```
        """
        return self.__t

    def or_raise(self, exc: BaseException | None = None) -> T:
        """
        Returns the contained `Ok` value or raises an exception `exc`.

        `exc` is raised from the contained `Error` exception, meaning there is still context about the cause on a lower level. This is useful for turning a more abstract error to a specific, more concrete one.

        If `exc` is `None`, the contained `Error` exception is re-raised.

        ```python
        index = get_requested_index()
        item = guard(my_list.index, ValueError)(index).or_raise(ClientError(f"Item at index {index} doesn't exist."))
        ```
        """
        if (not isinstance(exc, BaseException)) and exc is not None:
            raise TypeError("exceptions must derive from BaseException")
        return self.__t

    #                    This ensures lambda arguments are typed
    def or_else_do(self, f: Callable[Concatenate[E, P], R], *args, **kwargs) -> T:
        """
        Returns the contained `Ok` value or the return value of a call to `f`.

        `f` takes the contained `Error` exception as its first argument. Extra arguments can be passed to `f` from this function.

        ```python
        print(Ok(42).or_else_do(repr))
        print(Error(AssertionError()).or_else_do(repr))
        Error(Exception("Something happened").or_else_do(print, "extra text", sep=" - - - "))
        ```

        Output:

        ```
        42
        AssertionError()
        Something happened - - - extra text
        ```
        """
        _test_callable(f)
        return self.__t
    

    def unpack(self) -> tuple[T, None]:
        """
        - If `self` is `Ok(value)`, return `(value, None)`.
        - If `self` is `Error(exc)`, return `(None, exc)`.

        Return the outcome as a Go-like `(ok_value | None, error_exc | None)` tuple.

        ```python
        assert Ok(42).unpack() == (42, None)
        error = Exception()
        assert Error(error).unpack() == (None, error)
        ```

        **Note**: if the return value is unpacked, the type checker can't infer these values are mutually exclusive. Usage of the function like this is discouraged.

        ```python
        ok, error = guard(lambda: 1 / x, ZeroDivisionError)()
        if error != None: return
        reveal_type(ok) # float | None
        ```
        """
        return (self.__t, None)
    

    def run(self, *, on_ok: Callable[[T], R], on_error: Callable) -> R:
        """
        - If `self` is `Ok(value)`, return `on_ok(value)`.
        - If `self` is `Error(exc)`, return `on_error(exc)`.

        ```python
        def f1(value): return f"ok: {value}"
        def f2(exc): return f"error: {exc}"
        assert Ok(25).run(on_ok=f1, on_error=f2) == "ok: 25"
        assert Error(AssertionError("something wrong")).run(on_ok=f1, on_error=f2) == "error: something wrong"
        ```
        """
        _test_callable(on_error)
        return on_ok(self.__t)

    def then_run(self, f: Callable[Concatenate[T, P], Outcome[NT, NE]], *args: P.args, **kwargs: P.kwargs) -> Outcome[NT, NE]:
        """
        If `self` is `Ok`, returns the call to `f` with the contained `Ok` value, otherwise return the `Error` object untouched. Extra arguments can be passed to `f` from this function.

        This function can be used to chain guarded functions or values which may each return an error.

        ```python
        mat = [[0, 1], [2, 3]]
        from operator import getitem
        safe_get = guard(getitem, IndexError)
        assert safe_get(mat, 1).then_run(safe_get, 1) == Ok(3)
        assert iserror(safe_get(mat, 2).then_run(safe_get, 1))
        assert iserror(safe_get(mat, 1).then_run(safe_get, 2))
        ```
        """
        return f(self.__t, *args, **kwargs)

    def else_run(self, f: Callable[Concatenate[E, P], Outcome[NT, NE]], *args, **kwargs) -> Self:
        """
        If `self` is `Error`, returns the call to `f` with the contained `Error` exception, otherwise return the `Ok` object untouched. Extra arguments can be passed to `f` from this function.

        This function can be used like `Outcome.or_else_do(...)` but for a function which can fail aswell.

        ```python
        # Parse a string into integer or float
        string_in = input("-> ")
        number_maybe = guard(int, ValueError)(string_in).else_run(lambda _, x: guard(float, ValueError)(x), string_in)
        ```

        **Note**: If you don't care about the contained exception, it is reccomended to use the `or` keyword instead:

        ```python
        # Parse a string into integer or float
        string_in = input("-> ")
        number_maybe = guard(int, ValueError)(string_in) or guard(float, ValueError)(string_in)
        ```
        """
        _test_callable(f)
        return self
    

    def then(self, f: Callable[Concatenate[T, P], R], *args: P.args, **kwargs: P.kwargs) -> Ok[R]:
        """
        Apply a function on the contained `Ok` value, otherwise return the `Error` object untouched. Extra arguments can be passed to `f` from this function.

        This function can be used to chain functions and methods without having to check for an error.

        ```python
        assert Ok("Text").then(len) == Ok(4)
        assert Ok("Text").then(str.find, "e") == Ok(1)
        exc = Exception()
        assert Error(exc).then(len) == Error(exc) # len is never called here
        assert Error(exc).then(str.find, "e") == Error(exc) # str.find is never called here
        ```
        """
        return Ok(f(self.__t, *args, **kwargs))

    def map(self, f: Callable[Concatenate[T, P], R], *args: P.args, **kwargs: P.kwargs) -> Ok[R]:
        """
        Alias of `Outcome.then(...)`.

        Apply a function on the contained `Ok` value, otherwise return the `Error` object untouched. Extra arguments can be passed to `f` from this function.

        This function can be used to chain functions and methods without having to check for an error.

        ```python
        assert Ok("Text").map(len) == Ok(4)
        assert Ok("Text").map(str.find, "e") == Ok(1)
        exc = Exception()
        assert Error(exc).map(len) == Error(exc) # len is never called here
        assert Error(exc).map(str.find, "e") == Error(exc) # str.find is never called here
        ```
        """
        return Ok(f(self.__t, *args, **kwargs))


    @property
    def do(self) -> Iterator[T]:
        """
        Used by `outcome_do`.

        Yields once the contained `Ok` value, otherwise raises a special exception with the contained `Error` value.

        Can be used instead of `Outcome.__iter__(...)`. See `outcome_do`.
        """
        yield self.__t
    

    @property
    def ok(self) -> T:
        """
        The contained `Ok` value.

        This is a read-only property and it does not exist on `Error`, meaning trying to access it on an object which can be `Error` raises an issue by the type checker.

        ```python
        def f(x: int):
            outcome = guard([1, 2, 4, 8].index, ValueError)(x)
            if isok(outcome):
                return outcome.ok
            return None
        ```

        Example which raises a typing issue:

        ```python
        def f(x: int):
            outcome = guard([1, 2, 4, 8].index, ValueError)(x)
            # Type checker reports this issue:
            #   Cannot access attribute "ok" for class "Error[ValueError]"
            #     Attribute "ok" is unknown
            return outcome.ok
        ```
        """
        return self.__t


    @property
    def let(self) -> T:
        """
        Returns the contained `Ok` value or a special `LetFailure` sentinel value. Used internally by `let_ok(...)` and `let_not_ok(...)`
        """
        return self.__t


class Error(Generic[E]):
    """
    An unsuccessful outcome containing the error exception. All methods and some properties of `Ok` are also present in `Error`, so you can think of `Outcome` as an abstract base class inherited by `Ok` and `Error`.

    Initializes a new `Error` object with its contained exception.
    """
    # Match support
    __match_args__ = ("error",)
    """
    `Outcome`s support pattern matching. The match argument of each outcome is its inner value or exception.

    ```python
    iterator = [1, 1, 1]
    for _ in range(4):
        match guard(next, StopIteration)(iterator):
            case Ok(value): assert value == 1
            case Error(exc): assert isinstance(exc, StopIteration)
    ```
    """
    __slots__ = ("__e",)


    def __init__(self, e: E) -> None:
        if not isinstance(e, BaseException):
            raise TypeError(f"Error() argument must be an Exception, not '{type(e).__name__}'")
        self.__e = e


    def __repr__(self) -> str:
        return f"Error({repr(self.__e)})"
    

    def __bool__(self) -> Literal[False]:
        """
        `Ok`s are always true, `Error`s are always false. This can be used for short-circuiting and type guards as an alternative to methods and functions.

        ```python
        from operator import getitem
        mat = [[0, 1], [2, 3]]
        safe_get = guard(getitem, IndexError)
        # Get the second row, or the first, or None if the matrix is empty
        row_or_none = (safe_get(mat, 1) or safe_get(mat, 0) or Ok(None)).ok
        element_maybe = safe_get(mat, 0).then_run(safe_get, 0)
        if element_maybe:
            assert element_maybe.ok == 0
        ```
        """
        return False


    def __eq__(self, value: object) -> bool:
        """
        Checks for equality by value similarly to dataclasses.

        **Note**: `Exception`s check equality by reference.

        ```python
        assert Ok(42) == Ok(42)
        exc = Exception()
        assert Error(exc) == Error(exc)
        ```
        """
        return type(value) == Error and self.__e == value.error


    def __ne__(self, value: object) -> bool:
        """
        Checks for inequality by value similarly to dataclasses.

        **Note**: `Exception`s check equality by reference.

        ```python
        assert Ok(42) != Ok(25)
        assert Error(Exception()) != Error(Exception())
        exc = Exception()
        assert Ok(exc) != Error(exc)
        ```
        """
        return not (self == value)


    def __hash__(self) -> int:
        return hash((False, self.__e))


    def __neg__(self) -> E:
        """
        Alias for `Error.error`. The contained `Error` exception.

        `Ok` does not implement this operator, meaning trying to use it on an object which can be `Ok` raises an issue by the type checker.

        ```python
        def f(x: int):
            outcome = guard([1, 2, 4, 8].index, ValueError)(x)
            if iserror(outcome):
                return -outcome
            return None
        ```

        Example which raises a typing issue:

        ```python
        def f(x: int):
            outcome = guard([1, 2, 4, 8].index, ValueError)(x)
            # Type checker reports this issue:
            #   Operator "-" not supported for type "Outcome[int, ValueError]"
            return -outcome
        ```
        """
        return self.__e


    def __iter__(self) -> Iterator[NoReturn]:
        """
        Used by `outcome_do`.

        Yields once the contained `Ok` value, otherwise raises a special exception with the contained `Error` value.

        Can be used instead of `Outcome.do`. See `outcome_do`.
        """
        raise DoFailure(self.__e)
        # This yield at the end makes Python think this is an iterator
        # So it only raises the failure when iterated
        yield


    def or_none(self) -> None:
        """
        Returns the contained `Ok` value or `None`. Equivalent to `or_else(None)`.

        ```python
        assert Ok(42).or_none() == 42
        assert Error(AssertionError()).or_none() == None
        ```
        """
        return None

    def or_else(self, default: T) -> T:
        """
        Returns the contained `Ok` value or a default fallback value.

        ```python
        assert Ok(42).or_else("error") == 42
        assert Error(AssertionError()).or_else("error") == "error"
        ```
        """
        return default

    def or_raise(self, exc: BaseException | None = None) -> NoReturn:
        """
        Returns the contained `Ok` value or raises an exception `exc`.

        `exc` is raised from the contained `Error` exception, meaning there is still context about the cause on a lower level. This is useful for turning a more abstract error to a specific, more concrete one.

        If `exc` is `None`, the contained `Error` exception is re-raised.

        ```python
        index = get_requested_index()
        item = guard(my_list.index, ValueError)(index).or_raise(ClientError(f"Item at index {index} doesn't exist."))
        ```
        """
        if exc == None:
            raise self.__e
        raise exc from self.__e
    
    def or_else_do(self, f: Callable[Concatenate[E, P], T], *args: P.args, **kwargs: P.kwargs) -> T:
        """
        Returns the contained `Ok` value or the return value of a call to `f`.

        `f` takes the contained `Error` exception as its first argument. Extra arguments can be passed to `f` from this function.

        ```python
        print(Ok(42).or_else_do(repr))
        print(Error(AssertionError()).or_else_do(repr))
        Error(Exception("Something happened").or_else_do(print, "extra text", sep=" - - - "))
        ```

        Output:

        ```
        42
        AssertionError()
        Something happened - - - extra text
        ```
        """
        return f(self.__e, *args, **kwargs)
    

    def unpack(self) -> tuple[None, E]:
        """
        - If `self` is `Ok(value)`, return `(value, None)`.
        - If `self` is `Error(exc)`, return `(None, exc)`.

        Return the outcome as a Go-like `(ok_value | None, error_exc | None)` tuple.

        ```python
        assert Ok(42).unpack() == (42, None)
        error = Exception()
        assert Error(error).unpack() == (None, error)
        ```

        **Note**: if the return value is unpacked, the type checker can't infer these values are mutually exclusive. Usage of the function like this is discouraged.

        ```python
        ok, error = guard(lambda: 1 / x, ZeroDivisionError)()
        if error != None: return
        reveal_type(ok) # float | None
        ```
        """
        return (None, self.__e)

    
    def run(self, *, on_ok: Callable, on_error: Callable[[E], R]) -> R:
        """
        - If `self` is `Ok(value)`, return `on_ok(value)`.
        - If `self` is `Error(exc)`, return `on_error(exc)`.

        ```python
        def f1(value): return f"ok: {value}"
        def f2(exc): return f"error: {exc}"
        assert Ok(25).run(on_ok=f1, on_error=f2) == "ok: 25"
        assert Error(AssertionError("something wrong")).run(on_ok=f1, on_error=f2) == "error: something wrong"
        ```
        """
        _test_callable(on_ok)
        return on_error(self.__e)

    def then_run(self, f: Callable[Concatenate[T, P], Outcome[NT, NE]], *args, **kwargs) -> Self:
        """
        If `self` is `Ok`, returns the call to `f` with the contained `Ok` value, otherwise return the `Error` object untouched. Extra arguments can be passed to `f` from this function.

        This function can be used to chain guarded functions or values which may each return an error.

        ```python
        mat = [[0, 1], [2, 3]]
        from operator import getitem
        safe_get = guard(getitem, IndexError)
        assert safe_get(mat, 1).then_run(safe_get, 1) == Ok(3)
        assert iserror(safe_get(mat, 2).then_run(safe_get, 1))
        assert iserror(safe_get(mat, 1).then_run(safe_get, 2))
        ```
        """
        _test_callable(f)
        return self

    def else_run(self, f: Callable[Concatenate[E, P], Outcome[NT, NE]], *args: P.args, **kwargs: P.kwargs) -> Outcome[NT, NE]:
        """
        If `self` is `Error`, returns the call to `f` with the contained `Error` exception, otherwise return the `Ok` object untouched. Extra arguments can be passed to `f` from this function.

        This function can be used like `Outcome.or_else_do(...)` but for a function which can fail aswell.

        ```python
        # Parse a string into integer or float
        string_in = input("-> ")
        number_maybe = guard(int, ValueError)(string_in).else_run(lambda _, x: guard(float, ValueError)(x), string_in)
        ```

        **Note**: If you don't care about the contained exception, it is reccomended to use the `or` keyword instead:

        ```python
        # Parse a string into integer or float
        string_in = input("-> ")
        number_maybe = guard(int, ValueError)(string_in) or guard(float, ValueError)(string_in)
        ```
        """
        return f(self.__e, *args, **kwargs)
    

    def then(self, f: Callable[Concatenate[T, P], R], *args, **kwargs) -> Self:
        """
        Apply a function on the contained `Ok` value, otherwise return the `Error` object untouched. Extra arguments can be passed to `f` from this function.

        This function can be used to chain functions and methods without having to check for an error.

        ```python
        assert Ok("Text").then(len) == 4
        assert Ok("Text").then(str.find, "e") == 1
        exc = Exception()
        assert Error(exc).then(len) == exc # len is never called here
        assert Error(exc).then(str.find, "e") == exc # str.find is never called here
        ```
        """
        _test_callable(f)
        return self

    def map(self, f: Callable[Concatenate[T, P], R], *args, **kwargs) -> Self:
        """
        Alias of `Outcome.then(...)`.

        Apply a function on the contained `Ok` value, otherwise return the `Error` object untouched. Extra arguments can be passed to `f` from this function.

        This function can be used to chain functions and methods without having to check for an error.

        ```python
        assert Ok("Text").map(len) == 4
        assert Ok("Text").map(str.find, "e") == 1
        exc = Exception()
        assert Error(exc).map(len) == exc # len is never called here
        assert Error(exc).map(str.find, "e") == exc # str.find is never called here
        ```
        """
        _test_callable(f)
        return self


    @property
    def do(self) -> Iterator[NoReturn]:
        """
        Used by `outcome_do`.

        Yields once the contained `Ok` value, otherwise raises a special exception with the contained `Error` value.

        Can be used instead of `Outcome.__iter__(...)`. See `outcome_do`.
        """
        raise DoFailure(self.__e)
        # This yield at the end makes Python think this is an iterator
        # So it only raises the failure when iterated
        yield


    @property
    def error(self) -> E:
        """
        The contained `Error` exception.

        This is a read-only property and it does not exist on `Ok`, meaning trying to access it on an object which can be `Ok` raises an issue by the type checker.

        ```python
        def f(x: int):
            outcome = guard([1, 2, 4, 8].index, ValueError)(x)
            if iserror(outcome):
                return outcome.error
            return None
        ```

        Example which raises a typing issue:

        ```python
        def f(x: int):
            outcome = guard([1, 2, 4, 8].index, ValueError)(x)
            # Type checker reports this issue:
            #   Cannot access attribute "error" for class "Ok[int]"
            #     Attribute "error" is unknown
            return outcome.error
        ```
        """
        return self.__e
    

    @property
    def let(self) -> LetFailure:
        """
        Returns the contained `Ok` value or a special `LetFailure` sentinel value. Used internally by `let_ok(...)` and `let_not_ok(...)`
        """
        return LET_FAILURE


Outcome: TypeAlias = Union[Ok[T], Error[E]]
"""
Type alias for `Ok[T] | Error[E]`. Represents the success or failure of a guarded function or value. All methods and some properties of `Ok` are also present in `Error`, so you can think of `Outcome` as an abstract base class inherited by `Ok` and `Error`.
"""


def guard(f: Callable[P, T], *against: type[E]) -> Callable[P, Outcome[T, E]]:
    """
    Returns a version of the function `f` guarded against the given exception types, blocking it from raising one of the given exceptions.

    The returned function calls the original function `f` with the same arguments passed to it. The difference comes after the function was called:
    - If `f` returned a `value`, return an `Ok(value)` object.
    - If `f` raised an exception `exc` it is guarded against, return an `Error(exc)` object.
    - If `f` raised an exception it is *not* guarded against, the exception is propagated.

    The returned function has the same function signature of `f` except for the return value.

    ```python
    safe_float = guard(float, ValueError)
    print(safe_float("25"))
    print(safe_float("ten"))
    print(safe_float([4, 2]))
    ```

    Outputs:

    ```
    Ok(25.0)
    Error(ValueError("could not convert string to float: 'ten'"))
    Traceback (most recent call last):
    File ".../script.py", line 5, in <module>
        print(safe_float([4, 2]))
            ^^^^^^^^^^^^^^^^^^
    File ".../guards.py", line 368, in inner_func
        ok = f(*args, **kwargs)
            ^^^^^^^^^^^^^^^^^^
    TypeError: float() argument must be a string or a real number, not 'list'
    ```
    """
    _test_callable(f)
    for x in against:
        if (not isinstance(x, type(type))) or (not issubclass(x, BaseException)):
            raise TypeError(f"Exception to guard against must be a type subclass of BaseException ('{repr(x)}' is not assignable to 'type[BaseException]').")
    if against == ():
        warn("Guard does not contain any exception to guard against.", SyntaxWarning, stacklevel=2)
    def inner_func(*args: P.args, **kwargs: P.kwargs) -> Outcome[T, E]:
        try:
            ok = f(*args, **kwargs)
        except against as e:
            return Error(e)
        else:
            return Ok(ok)
    return inner_func


@overload
def guard_value(x: T | None, *defaults: None) -> Outcome[T, DefaultAsError[None]]: ...
@overload
def guard_value(x: T, *defaults: T) -> Outcome[T, DefaultAsError[T]]: ...
def guard_value(x, *defaults):
    """
    Returns an `Ok(x)` object if `x` is not one of the given default values, or else it returns an `Error(DefaultAsError(x))` object.

    This function can be used to filter a value and make sure it is not a value which indicates an error.

    ```python
    # Get the position of a letter or raise an error
    index = guard_value("Hello".find("e")).or_raise(ValueError("Character not found."))
    ```

    An overload of `guard_value` can narrow an `Optional[T]` into an `Outcome[T, DefaultAsError[None]]` if the default value is `None`.

    ***Warning***: Due to a limitation in the type system, passing to `*defaults` a value which is not a type of `x` does *not* throw an issue.
    """
    if defaults == ():
        warn("Guard does not contain any default values to guard against.", SyntaxWarning, stacklevel=2)
    if x in defaults:
        return Error(DefaultAsError(x))
    return Ok(x)


def guard_on_none(x: T | None) -> Outcome[T, DefaultAsError[None]]:
    """
    Returns an `Ok(x)` object narrowed to be not `None` or an `Error(DefaultAsError(None))` object.

    This function can be used to filter an optional value and make sure it is not `None`.

    ```python
    from weakref import ref
    my_set = {1, 2, 5}
    # Get the reference of an object by weakref or raise an error
    my_set_again = guard_on_none(ref(my_set)()).or_raise(ReferenceError("Weakly-referenced object no longer exists."))
    ```
    """
    return guard_value(x, None)


def guard_assert(x: T, assertion: Callable[Concatenate[T, P], bool], *args: P.args, **kwargs: P.kwargs) -> Outcome[T, GuardAssertError[T]]:
    """
    Calls `assertion(x)` and returns an `Ok(x)` object if the call to `assertion` returned true, otherwise returns an `Error(GuardAssertError(x))` object.

    ```python
    print(guard_assert(42, lambda x : x % 2 == 0))
    print(guard_assert(25, lambda x : x % 2 == 0))
    ```

    Outputs:

    ```
    Ok(42)
    Error(GuardAssertError(25))
    """
    if assertion(x, *args, **kwargs):
        return Ok(x)
    return Error(GuardAssertError(x))


@overload
def guard_context(*against: type[E], return_must_use: Literal[False]) -> GuardContextBase[None, E]: ...
@overload
def guard_context(*against: type[E], return_must_use: Literal[True] = True) -> GuardContextBase[MustUse, E]: ...
def guard_context(*against, return_must_use = True):
    """
    Guards a context from raising a set of exceptions. The outcome of the guarded context can be accessed with `GuardContextBase.outcome`, with behaviour similar to `guard()`.

    One of the limitations of `guard` is that it can only block exceptions raised from a single function. `guard_context` removes this limitation, making it more similar to a `try` statement. Reccomended when you want to run an operation on a failure state (like logging an error) or with import statements.

    ```python
    with guard_context(Exception) as context:
        ...
    outcome = context.outcome
    # If there's an error append it to the logger
    if iserror(outcome):
        log_error(outcome.error)
    else:
        outcome.ok.use()
    ```

    The contained `Ok` value if no exception is raised is a `MustUse` object to ensure the exception is handled. If `return_must_use` is false, `Ok` contains `None` instead.

    **Note**: The context's outcome (`GuardContextBase.outcome`) cannot be accessed inside of the context itself.
    """
    for x in against:
        if (not isinstance(x, type(type))) or (not issubclass(x, BaseException)):
            raise TypeError(f"Exception to guard against must be a type subclass of BaseException ('{repr(x)}' is not assignable to 'type[BaseException]').")
    if against == ():
        warn("Guard does not contain any exception to guard against.", SyntaxWarning, stacklevel=2)
    if return_must_use:
        return GuardContextBase(against, MustUse)
    return GuardContextBase(against, type(None))


def isok(outcome: Outcome[T, E]) -> TypeIs[Ok[T]]:
    """
    Returns `True` if `outcome` is an `Ok` object, or `False` if it's an `Error` object.

    ```python
    assert isok(Ok(42))
    assert not isok(Error(AssertionError()))
    ```

    This function can be used to narrow the type of an `Outcome`.

    ```python
    outcome: Outcome[T, E] = ...
    if isok(outcome):
        reveal_type(outcome) # Ok[T]
    ```
    """
    if not isinstance(outcome, (Ok, Error)):
        warn(
                f'`isok` recieved "{repr(outcome)}", which is neither `Ok` nor `Error`. Returning `False`.',
                NotOutcomeWarning, stacklevel=2
        )
    return isinstance(outcome, Ok)


def iserror(outcome: Outcome[T, E]) -> TypeIs[Error[E]]:
    """
    Returns `True` if `outcome` is an `Error` object, or `False` if it's an `Ok` object.

    ```python
    assert iserror(Error(AssertionError()))
    assert not iserror(Ok(42))
    ```

    This function can be used to narrow the type of an `Outcome`.

    ```python
    outcome: Outcome[T, E] = ...
    if iserror(outcome):
        reveal_type(outcome) # Error[E]
    ```
    """
    if not isinstance(outcome, (Ok, Error)):
        warn(
                f'`iserror` recieved "{repr(outcome)}", which is neither `Ok` nor `Error`. Returning `False`.',
                NotOutcomeWarning, stacklevel=2
        )
    return isinstance(outcome, Error)


def outcome_collect(iterable: Iterable[Outcome[T, E]]) -> Outcome[list[T], E]:
    """
    - If all the `iterable`'s items are `Ok`, return all contained values inside an `Ok(list(...))`.
    - If one of the `iterable`'s items is an `Error`, return the first one's contained exception.

    ```python
    my_list = [1, 2, 3, "4", 5]
    numbers_squared = outcome_collect(guard(lambda: x ** 2, TypeError)() for x in my_list).or_else([])
    ```

    ```python
    assert outcome_collect([Ok(1), Ok(2), Ok(3)]) == Ok([1, 2, 3])
    outcome = outcome_collect([Ok(1), Error(TypeError()), Error(ValueError())])
    assert iserror(outcome) and isinstance(outcome.error, TypeError)
    ```
    """
    result = []
    for x in iterable:
        if not isinstance(x, (Ok, Error)):
            raise TypeError(f"'outcome_collect' expected an 'Ok | Error' inside 'iterable', got '{type(x).__name__}'")
        if iserror(x): return x
        result.append(x.ok)
    return Ok(result)


def _iter_outcome_checking(iterable: Iterable[R]) -> Iterator[R]:
    it = iter(iterable)
    for x in it:
        if not isinstance(x, (Ok, Error)):
            raise TypeError(f"'outcome_partition' expected an 'Ok | Error' inside 'iterable', got '{type(x).__name__}'")
        yield x


def outcome_partition(iterable: Iterable[Outcome[T, E]]) -> tuple[Iterator[T], Iterator[E]]:
    """
    Split an iterable of outcomes into an iterator of all `Ok`s' contained values and an iterator of all `Error`s' contained exceptions.

    ```python
    strings = ["25", "42", "pizza"]
    numbers, errors = outcome_partition(guard(int, ValueError)(x) for x in strings)
    assert list(numbers) == [25, 42]
    assert len(list(errors)) == 1
    ```
    """
    if isinstance(iterable, Iterator):
        # We have to convert the iterator into an iterable
        # Or else iter(iterable) == iterable
        iter_list = list(iterable)
        ok_iter = (x.ok for x in _iter_outcome_checking(iter_list) if isok(x))
        error_iter = (x.error for x in _iter_outcome_checking(iter_list) if iserror(x))
        return ok_iter, error_iter
    ok_iter = (x.ok for x in _iter_outcome_checking(iterable) if isok(x))
    error_iter = (x.error for x in _iter_outcome_checking(iterable) if iserror(x))
    return ok_iter, error_iter


def outcome_do(iterable: Iterator[T]) -> Outcome[T, BaseException]:
    """
    Do notation for syntactic sugar of a sequence of `Outcome.then_run(...)` calls.

    ```python
    container = [[[25]]]
    from operator import getitem
    safe_get = guard(getitem, IndexError)
    assert outcome_do(
        x3
        for x1 in safe_get(container, 0)
        for x2 in safe_get(x1, 0)
        for x3 in safe_get(x2, 0)
    ) == Ok(25)
    ```

    Example where the `outcome_do` fails:

    ```python
    container = []
    from operator import getitem
    safe_get = guard(getitem, IndexError)
    assert iserror(outcome_do(
        x3
        for x1 in safe_get(container, 0)
        for x2 in safe_get(x1, 0) # This for is never reached
        for x3 in safe_get(x2, 0) # Neither this one
    ))
    ```

    `outcome_do` uses generator syntax. For each `for x in outcome` in the generator, `x` is the `Ok` value contained in each `outcome`, 
    then the expression before all `for`s is the returned value, which this function will wrap in an `Ok` object.

    If one of the `outcome`s is an `Error`, it is returned early. On each `for` you can access the values of the `for`s before it.

    **Note**: Because the `do_notation` uses raised errors to early exit, the possible contained `Error` exception cannot be implicitly typed.

    ***Warning***: Async generators are not supported.
    """
    result = guard(next, DoFailure, StopIteration)(iterable)
    unit_iter_test = guard(next, StopIteration)(iterable)
    if isok(unit_iter_test):
        warn("Generator passed to 'outcome_do' contains more than one item. Make sure it uses 'Outcome's as iterators.", RuntimeWarning, stacklevel=2)
    if iserror(result):
        err = result.error
        if isinstance(err, StopIteration):
            raise TypeError(f"Generator passed to 'outcome_do' is exhausted. Make sure it uses 'Outcome's as iterators.")
        value = err.value
        return Error(value)
    return Ok(result.ok)


def force_guard(*against: type[E]) -> Callable[[Callable[P, T]], Callable[P, Outcome[T, E]]]:
    """
    Function decorator which automatically guards a function against raising a set of exceptions. Instead of returning `T` or raising an exception `E`, the function now returns an `Outcome[T, E]` and only raises exceptions it isn't guarded against.

    ```python
    # f1 and f2 are equivalent
    @force_guard(IndexError, TypeError)
    def f1(l):
        return l.pop() + l.pop()
    f2 = guard(lambda l : l.pop() + l.pop(), IndexError, TypeError)
    ```

    This decorator can be used when guarding a function is more common than not doing so or when the function caller should consider the possible errors it can raise.

    For most functions it is reccomended to raise an exception instead of returning an `Outcome` for interoperability with Python and less verbosity for the more common use cases.

    **Note**: If a function decorated with `force_guard` doesn't return anything useful on success its `Error` exceptions may end up ignored. In such case return a `MustUse` object to ensure these exceptions are handled. See `MustUse`.

    ```python
    @force_guard(ConnectionError)
    def move_robot_arm(to):
        ...
        return MustUse()

    match move_robot_arm(POSITION):
        case Ok(value): value.use()
        case Error(_): do_something_else()
    ```
    """
    for x in against:
        if (not isinstance(x, type(type))) or (not issubclass(x, BaseException)):
            raise TypeError(f"Exception to guard against must be a type subclass of BaseException ('{repr(x)}' is not assignable to 'type[BaseException]').")
    if against == ():
        warn("Guard does not contain any exception to guard against.", SyntaxWarning, stacklevel=2)
    
    def decorator(f: Callable[P, T]) -> Callable[P, Outcome[T, E]]:
        @wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Outcome[T, E]:
            return guard(f, *against)(*args, **kwargs)
        return wrapper
    return decorator


def throw(e: BaseException, from_: BaseException | None = None) -> NoReturn:
    """
    Raise an exception `e`, optionally specifying the cause `raise e from source` with the `from_` argument.

    Unlike the `raise` keyword, this can be used inside lambdas or expressions and be passed as a function.
    """
    if from_:
        raise e from from_
    raise e


def let_ok(x: T | LetFailure) -> TypeIs[T]:
    """
    Syntactic sugar for running operations on the contained `Ok` value only if present. Takes as input the `let` property of an `Outcome` object, and returns `True` if the underlying outcome is `Ok`.

    ```python
    # Prints the square of an integer by input or prints an error message
    safe_int = guard(int, ValueError)
    my_input = input("-> ")
    if let_ok(x := safe_int(my_input).let):
        print(f"Its square is {x ** 2}")
    else:
        print("Didn't recieve an integer")
    ```

    `Outcome.let` returns the contained `Ok` value or a special `LetFailure` sentinel object. This property combined with `let_ok(...)` and the inline assignment operator (`:=`) allows for a syntax similar to "if let" statements in other languages.

    `let_ok` can narrow the value returned by `Outcome.let` like this:

    ```python
    outcome: Outcome[float, ValueError] = ...
    if let_ok(t := outcome.let):
        reveal_type(t) # float
    ```

    **Note**: `let_ok(...)` raises a warning if it recieves as input an `Outcome` object. This is to warn about the mistake of passing an `Outcome` object instead of `Outcome.let`.
    """
    if isinstance(x, (Ok, Error)):
        warn(
                f'`let_ok` recieved an Outcome value "{repr(x)}". Use the `Outcome.let` property for correct usage: "if let_ok(value := outcome.let): ..."',
                LetWarning, stacklevel=2
        )
    return x is not LET_FAILURE


def let_not_ok(x: Any) -> TypeIs[LetFailure]:
    """
    Syntactic sugar for running operations on the contained `Ok` value or run an early return. Takes as input the `let` property of an `Outcome` object, and returns `True` if the underlying outcome is `Error`.

    ```python
    # Prints the square of an integer by input or prints an error message
    safe_int = guard(int, ValueError)
    my_input = input("-> ")
    if let_not_ok(x := safe_int(my_input).let):
        print("Didn't recieve an integer")
        return
    print(f"Its square is {x ** 2}")
    ```

    `Outcome.let` returns the contained `Ok` value or a special `LetFailure` sentinel object. This property combined with `let_not_ok(...)` and the inline assignment operator (`:=`) allows for a syntax similar to "if let" statements in other languages.

    `let_not_ok` can narrow the value returned by `Outcome.let` like this:

    ```python
    outcome: Outcome[float, ValueError] = ...
    if let_not_ok(t := outcome.let):
        return
    reveal_type(t) # float
    ```

    **Note**: `let_not_ok(...)` raises a warning if it recieves as input an `Outcome` object. This is to warn about the mistake of passing an `Outcome` object instead of `Outcome.let`.
    """
    if isinstance(x, (Ok, Error)):
        warn(
                f'`let_not_ok` recieved an Outcome value "{repr(x)}". Use the `Outcome.let` property for correct usage: "if let_not_ok(value := outcome.let): ..."',
                LetWarning, stacklevel=2
        )
    return x is LET_FAILURE