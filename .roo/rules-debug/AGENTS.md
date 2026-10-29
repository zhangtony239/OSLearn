# Project Debug Rules (Non-Obvious Only)

- Trace goes to `stdout` by default and program output also goes to `stdout`; the final summary goes to `stderr`. When piping, use `2>&1` or you will see the summary before the trace.
- `--no-trace` keeps program output but silences the trace; `--quiet` additionally hides warnings and the summary. Use both to isolate `printf` output.
- A run that ends with `-- deadlock: every remaining process is blocked` means the ready queue emptied while processes were still `blocked`; inspect the last `BLOCK` lines, not the exit code (it is still 0).
- `-- stopped after max_steps=N` is the normal outcome for `while (1)` snippets; raise `--max-steps` to see more, it is not an error.
- Nondeterminism only comes from `--policy random`; `--seed -1` picks a fresh seed each run, so reproduce with an explicit `--seed N`.
- `vm: blocking operation (P(...)) is not allowed here` means a blocking call was used inside an expression (e.g. `while (m.get() > 0)`); rewrite it as a separate statement.
