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
from .guards import *
__all__ = ["DefaultAsError", "GuardAssertError", "UnfinishedGuardError", "MustUse", "Ok", "Error", "Outcome", "GuardContextBase",
           "guard", "guard_value", "guard_on_none", "guard_assert", "guard_context",
           "isok", "iserror", "outcome_do", "force_guard", "outcome_collect", "outcome_partition", "throw", "let_ok", "let_not_ok"]