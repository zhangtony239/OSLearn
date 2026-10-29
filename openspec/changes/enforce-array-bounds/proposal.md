# Proposal

## Why

`int buffer[0]` and out-of-bounds array accesses currently run without any diagnostic. A non-positive declared size is turned into an empty dict, and `assign_to` silently grows lists/dicts, so `buffer[10] = x` on a `int buffer[10]` never fails. This hides real bugs in student pseudo-code and makes the VM's array semantics inconsistent with the declared type.

## What Changes

- Declared arrays whose size evaluates to a non-negative integer always become fixed-length lists; size `0` becomes an empty list `[]` instead of `{}`.
- **BREAKING**: declaring an array with a negative size raises `VMRuntimeError`.
- **BREAKING**: reading or writing an array index outside `[0, size)` raises `VMRuntimeError` instead of returning `0` or auto-growing the container.
- Sizes that cannot be evaluated to an integer keep the existing sparse-dict fallback, so lenient pseudo-code such as `int buffer[n]` with an unknown `n` still runs.
- The CLI reports these as `vm: ...` errors and exits with code 1 through the existing `VMError` handling.

## Capabilities

### New Capabilities

- `array-bounds`: array declaration sizing and index bounds enforcement in the VM.

### Modified Capabilities

<!-- No existing capability's requirements change. -->

## Impact

- `src/vm/interpreter.py`: `exec_stmt` (`VarDecl`), `eval` (`Index`), `assign_to`.
- `tests/test_vm.py`: new coverage for zero-size, negative-size, and out-of-bounds read/write.
- `my.os` and `examples/` are unaffected because they use valid sizes and indices.
