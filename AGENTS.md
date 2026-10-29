# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Commands
- `uv sync` installs the project **editable** into `.venv` and creates the `vm` script; there is no global install.
- Run the tool as `uv run vm <file.os>` (or activate `.venv` first). Tests: `uv run pytest -q`; single test: `uv run pytest tests/test_vm.py::test_printf_output -q`.
- `vm config` writes `vm-config.yaml` only when missing; `--force` overwrites. It self-checks types/enums/unknown keys and exits 1 on errors.

## Non-obvious architecture
- `src/vm/interpreter.py` is **generator based**: every statement yields exactly one `Step` (a scheduling point) or a `Block` (wait). The scheduler counts `next(gen)` calls as steps, so a new statement type that yields twice or zero times breaks quantum accounting and `max_steps`.
- `Interpreter.eval()` is synchronous and cannot block. Blocking calls are only allowed at the top of `VarDecl` init, `Assign` value, `Return` value and `ExprStmt` via `eval_async()`; a blocking call nested deeper raises "blocking operation ... is not allowed here".
- Semaphores are **value based**: `V` increments `value` then wakes one waiter; the woken process re-checks `value <= 0` and may re-block (no direct handoff, no fairness guarantee). `Swait`/`Ssignal` use the same accounting.
- A monitor lock is a binary `Semaphore` named `<monitor>.mutex`; `cond.signal()` only moves a waiter to ready and it must re-acquire the mutex (Mesa semantics), so `while (cond) wait();` is required in `.os` code.
- Processes are **top-level `void` functions with zero parameters**; `int main()` is not a process. `start(f)` spawns extra processes at runtime.
- Lenient mode never raises on unknown syntax: `Parser.skip_statement()` skips to the next `;` and records a warning. Full-width punctuation is normalised in `lexer.normalize()` and `…` becomes a space, which is what makes `example.txt` parse.
- `examples/textbook.os` is the canonical lenient-parsing regression fixture; keep it byte-identical to `example.txt` when editing.
- 新增语言结构时同步更新 `.vscode/os.code-snippets`。
