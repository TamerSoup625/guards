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

<!--0i7lhxou59v9vusfcarutcjl9tf3uf4tzcapi9fqa6i2zj6ql2ytx11tqeon9z54lrsspxwr9j146kyt6z6gfmzmpxs054fx8izmyz8idmkcrtm14aiply2ti5wgrg72ckwi9pax94t2iga0eua2cboh4qgwqb787wl5e5m25ijcuvr1e5ue6h0xw2kz78hd01yv9mgcdinia9kqt9by6myinpf0ao1wqew3swndayy33lp0z4i153b81urxm28uwhthgeik12wbs936z4uqpe1agw87u99d6mjjueirjdz6bh4p2ebdc2ttjy6z2hshcbyls7ncfk135ap9528qp8w1g05b83qy1mpqwm1sliuqvab0buqtm1jfji0h3binsju1pgzs4byot16fu1g1wxyn1ajssq0qrmsu6fq1fctaxeuoie5ip7irh5e8jf091ui3oze2pj1kpczl1smethv2x0ny15dclr70uwescgi31wubr2olrxjhskkj1vfe17gogzvscaaoluisxu3d8ir6qg6oqtlcgd5o3tyyxr3wwidqwpixjgogxfd8rrb4rp2f2ym8py3zhinx0zgkllrv16usyk3up556xq4ml2gniqexs5pc3q1s3blzpdwk3cwhn8h1oal3wmwmdhivug86eqrm51t8hi25hmlum94vvst3or83x4vnhjpb5phn85zb0tufvu0qbbotocfchd1ear58ab26wihzfxlzlbuqwxk93ik2lz6nlnueewjgijhcpuh59rq83i9h3g2nt76sgsmfvpdkopkku7oaokwp9n54ukb1xp6siugj0zgaizlvvp8gf3f5yvg92hlif8izoiyaabh6u5a2por610eonjhfd60px32fliq46k8zeyvgjcnrudgacr86vxynxqheb02hfnlzjr69lbv6s8bmuzwkpz4mw86u6ilhfbij87yjqx5mwbhjl53my72hujismdspwt79zi3gw4znaqpc2zwbxmmazkh0euj5bjgquunq53drgvrgjda7in5wuszpe2r2z924m0kgvf1jrbme93msphqkzpg0yhx1k79m1th0ievlh7vv6hwcpe4no2kyts88xdvlg3eoak98i4s3zq982qhxgtnylx9dvo3v2xmdref736h19urgo10r38jvvyah2y5s1refm9vqkoj8gpcjs58gprx48963xvna88wwzl0sbk1a2hpvz4jboijjnzht5p8rf1p8sbe132n8e4q7yrzkteaf6158i3el6qpuhcpl71i2y546rvd6nrhqj9efuf4h1vpeo0liojsh3k2eb1a2ot0py8d6ktlatpc9wn96xa8nix86jr9lmrzr7vxuscmg7nvh2xdo5nad3pirali2btn7jsmh483w26p0tag7ja5gio9wpv6ibnynzcwwns8apmxn82jbcug37svxp2i4iq8sqt98uwlb5zg1xvacwjr6ad0dp8urmxhrltse2s0h7o8vvvvk9t6esivaoeyt15ogutwvzq8888o9cpin4d9lkr15n633jy53dzhsohnd2nn8sosgfmxdez9erd83eklun67l2dffok7zwztp4u1acp6gabhubdvvklv21vp9ufkxuvrmh890vw2uc1y93pkd8dpn93dxx18njxngz829kqqte4gm3lsmcfrg2tk9jp7s9ph9xh07efht97fmmpkmlppej91m56msvhgnqh4vxmjob0vgricmar3mam4uyy35fjrvnl808ccsfpx2ap4pwbhy5vavynwxbl334p3eqy6jdlrhb24dlav1wx4m2hsbwrsqhinht014ab49p62bcskg1p5jcdxjqr8huc2ae8klgrdp77q2mqgahu6nuxyzdmrgmguy6h04di0qvaef8w2gm58k4bzdd5uvj1s4m6sx1i0a1s9kyol5gcer4d9axt62jpkgrune4l9ccfrnwf0wwzya25obqa5pv7qgydckfuxsvibfywyk0m0ftvnekm6ip5znnpqg64shnu1lo55w84hr7xjozqog2arbn0c263w7q4j3bjab03mi5brprbv3tj68hpiunyuubq6uf2senrs1xy5sm7ls7i7akryblhyn0eyfw1gllc7ptmpowgoxe6syswhbwwnpmn3882t0wx4h7161h0tg0uji2es7x2te32d9fn7tiytb1byo3fxyldviavnekfl34cqhojotcbf00qpm14es774cochz489arm6w1bow5ky4laet77rz3zjlfpiz8xhc2futw0hu11u84ait4xeoutn6kio9oj57hqtwel7jkekzepsqpu2ctd231rr77tihz62g2oz4muz16zk2wlkcdtbdk9fd30t2pkqlymoqfkownhn3z508cqi9tfkegbsidh07po9xuijyf7bwt3wssa5pmptstqb2mmd9hb1qzmwow188e5s093hypz32pcacx2ut5g9h9f0g7v44cmglt7gg56iof0rytjhkjy3avadd3blkb8gku35dnv6x2dqn8hebzleifpumoam6rrfpfpq6x95zlxcz10sd1e1n6n7iw5iwainobcovcpem1ixjw8t8q5jj18s5yyznipl0hqc2lpk0d72o70lvqio133dfo6x01f38qpqk4o0mpwz6qezj36315a6fp146jjjy082kjx7i2vvcl8dzej2hbvb1l1ik3z7ijqo9myec386uz8ociwoyqpudu0674ibvxwmh5y1ukpch9b8m3b45sxq9kcydjlxmtj6h46q11pei9tlqmveed65rrflgmrvmzmmlpwebyx6ctlju5g6nvmqviz7u9sf1m2yg9u0cth6jz7vh74i1zy6gf0j4qus192mvan3irqzl8ximvtmos5we0nbjtp4fyf9cwugs4tg9iaviuh6r0q7syh8zkq01j7rg4vkf3cyodktevhfwcken2nhy7wa4sw4vsuavamgpo0vsmjvuyibxqmrl3lgzkijcgxaczzt3izf94fakd2bwyic0q2f82p51pniez752uak91zm9209klkz1xvl0o994twgichoolup06knguu5zdj8nim08hrc24jcoesfgrzhv0cjv8pyub5xxpxmz8s5uf3o8fku4ku01mnssl80ycphmnuespzjeoydvhng3pj9az1z8hp2c4yoovh1u3i1770vaf0ealzo6wsewrc2h9w4givzt98ot6dujs1d19y-->