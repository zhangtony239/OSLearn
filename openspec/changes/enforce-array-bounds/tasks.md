# Tasks

## 1. Array declaration sizing

- [x] 1.1 In `exec_stmt` (`VarDecl`), split the size branch into three cases: integer `n >= 0` → `[0] * n`, integer `n < 0` → raise `VMRuntimeError`, non-integer → `{}`; verify `int buffer[0];` yields an empty list and `int buffer[10];` yields a 10-element list via a new test in `tests/test_vm.py`
- [x] 1.2 Add a test asserting `int buffer[-1];` raises `VMRuntimeError` and that the CLI exits with code 1; verify with `uv run pytest tests/test_vm.py -q`

## 2. Bounds-checked reads

- [x] 2.1 In `eval` (`Index`), raise `VMRuntimeError` when a `list` container is indexed outside `[0, len)`; verify an in-range read still returns the stored value and `buffer[10]` on a length-10 list raises, via new tests in `tests/test_vm.py`
- [x] 2.2 Verify dict containers still return `0` for missing keys so sparse pseudo-code is unaffected; run `uv run pytest tests/test_vm.py -q`

## 3. Bounds-checked writes

- [x] 3.1 In `assign_to` (`Index`), raise `VMRuntimeError` when a `list` container is indexed outside `[0, len)` and remove the `while len(container) <= idx: append(0)` growth loop; verify `buffer[10] = 7` on a length-10 list raises and the list length stays 10 via a new test
- [x] 3.2 Verify in-range writes still store the value and dict writes still insert keys; run `uv run pytest tests/test_vm.py -q`

## 4. Integration verification

- [x] 4.1 Run `uv run vm my.os` and confirm the producer/consumer example still runs without array errors
- [x] 4.2 Run the full suite with `uv run pytest -q` and confirm all tests pass
