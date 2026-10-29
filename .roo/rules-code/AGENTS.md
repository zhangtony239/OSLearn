# Project Coding Rules (Non-Obvious Only)

- Every `exec_stmt` branch must `yield` exactly one `Step` (or `Block`) per statement; the scheduler treats each `next(gen)` as one step and `max_steps`/quantum depend on it.
- Never call `self.eval()` on a node that may contain a blocking call. Use `yield from self.eval_async(node, frame)` at statement level instead.
- New AST nodes must be added to `src/vm/ast_nodes.py` **and** to `src/vm/pretty.py:describe()`; otherwise traces print the raw class name.
- `Parser` recovery helpers (`skip_statement`, `skip_to_semicolon`, `skip_section`, `skip_balanced_block`) must never consume a closing `}` at depth 0 — the enclosing block parser relies on it.
- `Scheduler.wake()` is a no-op unless the process is `blocked`; always remove the process from the wait queue (`popleft`) before calling it, or it will be enqueued twice.
- `Interpreter.run_sync()` is the only place allowed to reject blocking; do not add blocking operations to global/monitor initialisation.
