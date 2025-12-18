# GUARDS: Handle Exceptions Like Never Before

```python
# Before
def main():
    key_str: str = input("Insert key -> ")
    try:
        key: int = int(key_str)
    except ValueError:
        print("Key is not an integer")
        return
    try:
        value = my_dict[key]
    except KeyError:
        value = "not found"
    print(f"Value at key {key} is {value}")

# After
from guards import *
from operator import getitem
def main():
    safe_int = guard(int, ValueError)
    key_maybe: Outcome[int, ValueError] = safe_int(input("Insert key -> "))
    if iserror(key_maybe):
        print("Key is not an integer")
        return
    key: int = key_maybe.ok
    value = guard(getitem, KeyError)(my_dict, key)
    print(f"Value at key {key} is {value.ok if isok(value) else 'not found'}")

# More compact
from guards import *
from operator import getitem
def main():
    safe_int = guard(int, ValueError)
    key_maybe = safe_int(input("Insert key -> "))
    if let_not_ok(key := key_maybe.let):
        print("Key is not an integer")
        return
    value = guard(getitem, KeyError)(my_dict, key).or_else("not found")
    print(f"Value at key {key} is {value}")
```

**`guards`** is a Python library implementing an alternative to the classic `try/except/else` statements. You still throw errors with `raise`, but can catch them in a sweeter and more functional approach. **Requires Python 3.10+**.

Guards let you handle errors in expressions, not just statements.

```python
safe_int = guard(int, ValueError)
# Impossible with try/except (needs indentation and blocks)
result = [safe_int(x).or_else(0) for x in user_inputs]
```

This means:
- Chain operations without nested try blocks

```python
from operator import getitem
l = [6, 2, 5]
safe_get = guard(getitem, IndexError)
text = outcome_do(
    x1 + x2 + x3
    for x1 in safe_get(l, 0)
    for x2 in safe_get(l, 1)
    for x3 in safe_get(l, 2)
).or_else(0)
```

- Pass error-handling logic as values

```python
def assert_raises(func, exception, *args, **kwargs):
    match guard(func, exception)(*args, **kwargs):
        Ok(value): raise AssertionError(f"Expected a raised {exception}, but got value {value}")
        Error(exc): return
```

- Type-check your error handling

```python
def f(x: str) -> int | None:
    outcome = guard("Hello World".index, ValueError)(x)
    if isok(outcome):
        reveal_type(outcome) # Ok[int]
        return outcome.ok
    reveal_type(outcome) # Error[ValueError]
    #return outcome.ok # Would raise an issue by the type checker
```

- And more!

```python
my_list = ["4.2", "2.7", "pizza"]
numbers, errors = outcome_partition(guard(float, ValueError)(x) for x in my_list)
```

## Installation

Install this library with `pip` like usual:

```
pip install guards
```

## Summary

The `guard()` function blocks another function from raising a set of errors. It takes a function `f` to guard and one or more `BaseException` types to guard against, and returns a new function.

```python
open_safe = guard(open, FileNotFoundError, PermissionError)
age_outcome = guard(int, ValueError)(input("Insert age -> "))
```

The returned function calls the original function `f` with the same arguments passed to it. The difference comes *after* the function was called:
- If `f` returned a `value`, return an `Ok(value)` object.
- If `f` raised an exception `exc` it is guarded against, return an `Error(exc)` object.
- If `f` raised an exception it is *not* guarded against, the exception is propagated.

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

The union of the return types of a guarded function `Ok | Error` is called `Outcome`, which is similar to "result" types in other programming languages.

The simplest way to handle exceptions is to use `isok()` and `iserror()` functions to check the type of an outcome, then access their internal values with `.ok` and `.error` properties.

```python
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

This is just the basic of error-handling. See the documentation or `examples.md` for more.

## Try/Except VS Guards

|Try/Except|Guards|
|-|-|
|❌Needs blocks and indentation|✅Can be used inside expressions|
|❌Strictly procedural|✅Multi-paradigm|
|❌Encourages coarse-grained error handling|✅Encourages fine-grained error handling (coarse-grained is still possible)|
|❌Terrible when used often|✅Multiple uses are not a problem|
|❌Hard to pass around|✅Returned outcome can be passed around|
|❌Bare except antipattern|✅Specifying no types to guard against is a runtime warning|
|❌Risk of unbound variables|✅No need to worry about variables|
|❌Try/Except is all you get|✅Methods and functions for the most common use-cases|

## Exceptions and Guards VS Pure Result Values

|Exceptions and Guards|Pure Result Values|
|-|-|
|Handling errors is the default|Propagating errors is the default|
|✅Raised exceptions are all you need|❌Needs panics to work well|
|✅Only the exceptions you care about are handled|❌Needs unwrapping the error even if you only care about a specific one|
|✅Can be learned whenever you have to handle errors|❌Must be learned when writing or using a fallible function|
|✅Great compatibility with Python|❌Hard to integrate in a language like Python|
|✅Exceptions automatically create stack traces|❌You often need libraries for backtraces|
|❌Raised errors cannot be typed (out of this module's scope)|✅Functions' errors are typed|
|❌Rarely clear whether a function can error|✅Often clear whether a function can error|
|❌Needs understanding of functions as values|✅Easier to understand|
|❌Uses a different control flow|✅Control flow is clearer|
|❌Error handling is easy to ignore|✅Errors must always be dealt with|

## Contributing

`todo.md` contains a short list of features to implement, which includes publishing the library to PyPi at the end.