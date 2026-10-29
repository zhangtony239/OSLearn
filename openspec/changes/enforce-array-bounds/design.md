# Design

## Context

See [`proposal.md`](proposal.md) for motivation and [`specs/array-bounds/spec.md`](specs/array-bounds/spec.md) for the behavior contract.

The VM already distinguishes two storage shapes at runtime:

- `list` — created by `[0] * n` in [`exec_stmt()`](../../../src/vm/interpreter.py:113) for `VarDecl` with a positive integer size.
- `dict` — the fallback used when the size is not a positive integer, and the shape used for sparse pseudo-code arrays.

Indexing is handled in two places: reads in [`eval()`](../../../src/vm/interpreter.py:399) and writes in [`assign_to()`](../../../src/vm/interpreter.py:513). Both currently treat out-of-range access as benign: reads return `0`, and writes grow the list or insert a dict key.

## Goals / Non-Goals

**Goals:**

- Make a declared integer size authoritative: `int buffer[0]` is an empty list, not a dict.
- Reject negative sizes and out-of-range reads/writes with `VMRuntimeError`.
- Keep the sparse-dict fallback for sizes that are not integers, so lenient pseudo-code still runs.

**Non-Goals:**

- Static (parse-time) analysis of array sizes or indices.
- Changing the parser or AST; the fix is entirely in the interpreter.
- Multi-dimensional arrays or array length introspection.
- Rejecting non-integer indices on reads (out of scope; only bounds are enforced).

## Decisions

### Decision: Use the Python container type as the storage-shape discriminator

A `list` means fixed-length storage and is bounds-checked; a `dict` means sparse storage and keeps the current permissive behavior. This avoids adding a new runtime wrapper type and keeps the change local to the interpreter.

Alternative considered: introduce an `Array` runtime class carrying `length`. Rejected as unnecessary for this change and it would ripple through `pretty`, `runtime`, and tests.

### Decision: Split the size branch into three cases

In `exec_stmt` for `VarDecl`:

1. size evaluates to an integer `n >= 0` → `[0] * n` (so `0` yields `[]`)
2. size evaluates to an integer `n < 0` → raise `VMRuntimeError`
3. size is not an integer → `{}` (unchanged fallback)

`bool` is excluded from the integer check because `bool` is an `int` subclass in Python.

### Decision: Bounds-check only list containers

- Read (`eval` `Index`): if the container is a `list` and the index is an integer outside `[0, len)`, raise `VMRuntimeError`. In-range reads are unchanged.
- Write (`assign_to` `Index`): if the container is a `list` and the index is outside `[0, len)`, raise `VMRuntimeError`; remove the `while len(container) <= idx: append(0)` growth loop.

Dict containers keep `.get(idx, 0)` on read and key insertion on write.

### Decision: Error messages name the index and length

Messages follow the existing `VMRuntimeError` style, e.g. `array index 10 out of range for length 10` and `invalid array size -1`. The CLI already maps `VMError` to `vm: <message>` on stderr and exit code 1, so no CLI change is needed.

## Risks / Trade-offs

- **Existing lenient programs that relied on auto-growth now fail** → This is the intended breaking change; the spec and proposal call it out. `my.os` and `examples/` use valid indices.
- **A size expression that evaluates to a float (e.g. `10.0`) still falls back to a dict** → Acceptable: the spec only guarantees integer sizes. Documented as a non-goal to coerce floats.
- **Non-integer read indices still return `0`** → Kept for lenient compatibility; writes already reject them. Can be tightened in a follow-up.
