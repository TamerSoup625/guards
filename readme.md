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

`guards` is not yet available to PyPi. If you want to try `guards` you can download the `guards.py` file as a standalone.

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

<!--0i7lhxou59v9vusfcarutcjl9tf3uf4tzcapi9fqa6i2zj6ql2ytx11tqeon9z54lrsspxwr9j146kyt6z6gfmzmpxs054fx8izmyz8idmkcrtm14aiply2ti5wgrg72ckwi9pax94t2iga0eua2cboh4qgwqb787wl5e5m25ijcuvr1e5ue6h0xw2kz78hd01yv9mgcdinia9kqt9by6myinpf0ao1wqew3swndayy33lp0z4i153b81urxm28uwhthgeik12wbs936z4uqpe1agw87u99d6mjjueirjdz6bh4p2ebdc2ttjy6z2hshcbyls7ncfk135ap9528qp8w1g05b83qy1mpqwm1sliuqvab0buqtm1jfji0h3binsju1pgzs4byot16fu1g1wxyn1ajssq0qrmsu6fq1fctaxeuoie5ip7irh5e8jf091ui3oze2pj1kpczl1smethv2x0ny15dclr70uwescgi31wubr2olrxjhskkj1vfe17gogzvscaaoluisxu3d8ir6qg6oqtlcgd5o3tyyxr3wwidqwpixjgogxfd8rrb4rp2f2ym8py3zhinx0zgkllrv16usyk3up556xq4ml2gniqexs5pc3q1s3blzpdwk3cwhn8h1oal3wmwmdhivug86eqrm51t8hi25hmlum94vvst3or83x4vnhjpb5phn85zb0tufvu0qbbotocfchd1ear58ab26wihzfxlzlbuqwxk93ik2lz6nlnueewjgijhcpuh59rq83i9h3g2nt76sgsmfvpdkopkku7oaokwp9n54ukb1xp6siugj0zgaizlvvp8gf3f5yvg92hlif8izoiyaabh6u5a2por610eonjhfd60px32fliq46k8zeyvgjcnrudgacr86vxynxqheb02hfnlzjr69lbv6s8bmuzwkpz4mw86u6ilhfbij87yjqx5mwbhjl53my72hujismdspwt79zi3gw4znaqpc2zwbxmmazkh0euj5bjgquunq53drgvrgjda7in5wuszpe2r2z924m0kgvf1jrbme93msphqkzpg0yhx1k79m1th0ievlh7vv6hwcpe4no2kyts88xdvlg3eoak98i4s3zq982qhxgtnylx9dvo3v2xmdref736h19urgo10r38jvvyah2y5s1refm9vqkoj8gpcjs58gprx48963xvna88wwzl0sbk1a2hpvz4jboijjnzht5p8rf1p8sbe132n8e4q7yrzkteaf6158i3el6qpuhcpl71i2y546rvd6nrhqj9efuf4h1vpeo0liojsh3k2eb1a2ot0py8d6ktlatpc9wn96xa8nix86jr9lmrzr7vxuscmg7nvh2xdo5nad3pirali2btn7jsmh483w26p0tag7ja5gio9wpv6ibnynzcwwns8apmxn82jbcug37svxp2i4iq8sqt98uwlb5zg1xvacwjr6ad0dp8urmxhrltse2s0h7o8vvvvk9t6esivaoeyt15ogutwvzq8888o9cpin4d9lkr15n633jy53dzhsohnd2nn8sosgfmxdez9erd83eklun67l2dffok7zwztp4u1acp6gabhubdvvklv21vp9ufkxuvrmh890vw2uc1y93pkd8dpn93dxx18njxngz829kqqte4gm3lsmcfrg2tk9jp7s9ph9xh07efht97fmmpkmlppej91m56msvhgnqh4vxmjob0vgricmar3mam4uyy35fjrvnl808ccsfpx2ap4pwbhy5vavynwxbl334p3eqy6jdlrhb24dlav1wx4m2hsbwrsqhinht014ab49p62bcskg1p5jcdxjqr8huc2ae8klgrdp77q2mqgahu6nuxyzdmrgmguy6h04di0qvaef8w2gm58k4bzdd5uvj1s4m6sx1i0a1s9kyol5gcer4d9axt62jpkgrune4l9ccfrnwf0wwzya25obqa5pv7qgydckfuxsvibfywyk0m0ftvnekm6ip5znnpqg64shnu1lo55w84hr7xjozqog2arbn0c263w7q4j3bjab03mi5brprbv3tj68hpiunyuubq6uf2senrs1xy5sm7ls7i7akryblhyn0eyfw1gllc7ptmpowgoxe6syswhbwwnpmn3882t0wx4h7161h0tg0uji2es7x2te32d9fn7tiytb1byo3fxyldviavnekfl34cqhojotcbf00qpm14es774cochz489arm6w1bow5ky4laet77rz3zjlfpiz8xhc2futw0hu11u84ait4xeoutn6kio9oj57hqtwel7jkekzepsqpu2ctd231rr77tihz62g2oz4muz16zk2wlkcdtbdk9fd30t2pkqlymoqfkownhn3z508cqi9tfkegbsidh07po9xuijyf7bwt3wssa5pmptstqb2mmd9hb1qzmwow188e5s093hypz32pcacx2ut5g9h9f0g7v44cmglt7gg56iof0rytjhkjy3avadd3blkb8gku35dnv6x2dqn8hebzleifpumoam6rrfpfpq6x95zlxcz10sd1e1n6n7iw5iwainobcovcpem1ixjw8t8q5jj18s5yyznipl0hqc2lpk0d72o70lvqio133dfo6x01f38qpqk4o0mpwz6qezj36315a6fp146jjjy082kjx7i2vvcl8dzej2hbvb1l1ik3z7ijqo9myec386uz8ociwoyqpudu0674ibvxwmh5y1ukpch9b8m3b45sxq9kcydjlxmtj6h46q11pei9tlqmveed65rrflgmrvmzmmlpwebyx6ctlju5g6nvmqviz7u9sf1m2yg9u0cth6jz7vh74i1zy6gf0j4qus192mvan3irqzl8ximvtmos5we0nbjtp4fyf9cwugs4tg9iaviuh6r0q7syh8zkq01j7rg4vkf3cyodktevhfwcken2nhy7wa4sw4vsuavamgpo0vsmjvuyibxqmrl3lgzkijcgxaczzt3izf94fakd2bwyic0q2f82p51pniez752uak91zm9209klkz1xvl0o994twgichoolup06knguu5zdj8nim08hrc24jcoesfgrzhv0cjv8pyub5xxpxmz8s5uf3o8fku4ku01mnssl80ycphmnuespzjeoydvhng3pj9az1z8hp2c4yoovh1u3i1770vaf0ealzo6wsewrc2h9w4givzt98ot6dujs1d19y-->