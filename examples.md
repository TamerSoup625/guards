# Example uses of `guards`

This file shows all the module's features and example usage.

## Methods for fallback values

`Outcome`s have a couple of methods for taking the contained `Ok` value, or do something else.

```python
data = guard(socket.read_all, TimeoutError)().or_else(b"")
```

```python
def normalized(self: Vector):
    return guard(lambda: self / len(self), ZeroDivisionError)().or_raise(ValueError("Cannot normalize a null vector"))
```

```python
with guard(open, FileNotFoundError)("log.txt", "a")\
    .or_else_do(lambda _: open("log.txt", "x")) as file:
    file.write("Hello!")
```

## Control flow

`guards` has support for `if let`-like syntax and pattern matching.

```python
from operator import getitem
mylist = [1, 2, 3]
if let_ok(first_item := guard(getitem, IndexError)(mylist, 0).let):
    reveal_type(first_item) # int
    print(f"The first element is {first_item}")
```

```python
if let_not_ok(age := guard(int, ValueError)(input("Insert your age -> ")).let):
    print("ERROR: Insert an integer for age")
    return
reveal_type(age) # int
print(f"You're {age} years old")
```

```python
def assert_raises(func, exception, *args, **kwargs):
    match guard(func, exception)(*args, **kwargs):
        Ok(value): raise AssertionError(f"Expected a raised {exception}, but got value {value}")
        Error(exc): return
```

## Methods for function chaining

`Outcome`s have a couple of methods to apply functions on a successful value.

```python
my_iter = iter("Hello There".split())
# These two lines of code are equivalent
guard(next, StopIteration)(my_iter).then(str.upper).then(str.find, "E").then(print)
guard(next, StopIteration)(my_iter).map(str.upper).map(str.find, "E").map(print)
```

```python
from operator import getitem
mat = [[0, 1], [2, 3]]
safe_get = guard(getitem, IndexError)
element_maybe = safe_get(mat, 0).then_run(safe_get, 0)
row_maybe = safe_get(mat, 1).else_run(lambda _: safe_get(mat, 0))
```

## `outcome_do` notation

The `outcome_do` function allows for more complex optional chaining.

```python
from operator import getitem
safe_get = guard(getitem, IndexError)
text = outcome_do(
    page
    for wall in safe_get(hexagon, 4)
    for shelf in safe_get(wall, 3)
    for volume in safe_get(shelf, 9)
    for page in safe_get(volume, 21)
).or_else("Page not found")
```

## Type annotations

`guards` extensively support typing and type guards.

```python
l = [1, 2, 4, 8]
# This function passes type checking
def f(x: int) -> int:
    outcome = guard(l.index, ValueError)(x)
    reveal_type(outcome) # Ok[int] | Error[ValueError]
    if isok(outcome):
        reveal_type(outcome) # Ok[int]
        return outcome.ok
    reveal_type(outcome) # Error[ValueError]
    raise outcome.error
```

```python
l = [1, 2, 4, 8]
# This does not
def g(x: int) -> int:
    outcome = guard(l.index, ValueError)(x)
    if isinstance(outcome, ValueError):
        return 0
    # Type checker reports this issue:
    #   Cannot access attribute "ok" for class "Error[ValueError]"
    #     Attribute "ok" is unknown
    return outcome.ok
```

## Multiple ways to guard

There isn't just the `guard` function. There are a couple other `guard*` functions which return an `Outcome`.

```python
my_object = guard_on_none(my_weakref()).or_raise(ReferenceError("Object referred to no longer exists"))
```

```python
with guard_context(ImportError) as context:
    from typing import TypeIs
match context.outcome:
    case Ok(value): value.use()
    case Error(_): from typing_extensions import TypeIs
```

## `force_guard` and `MutUse`

The `force_guard` decorator can be used for functions which are more likely to raise an exception.

The `MustUse` object ensures the exceptions in a `force_guard`ed function are handled.

```python
@force_guard(ConnectionError)
def move_robot_arm(to):
    ...
    return MustUse()

match move_robot_arm(POSITION):
    case Ok(value):
        value.use() # Replacing this with a no-op raises a warning
    case Error(_): do_something_else()
```

## Other features

```python
my_list = ["42", "25", "pizza"]
numbers, errors = outcome_partition(guard(int, ValueError)(x) for x in my_list)
reveal_type(list(numbers)) # list[int]
all_numbers = outcome_collect(guard(int, ValueError)(x) for x in my_list)\
    .or_else_do(lambda exc: throw(RuntimeError(), from_=exc))
reveal_type(all_numbers) # list[int]
```