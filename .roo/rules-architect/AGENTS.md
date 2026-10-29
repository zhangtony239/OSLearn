# Project Architecture Rules (Non-Obvious Only)

- Concurrency is **cooperative and single-threaded**: generators + a scheduler, no threads. Any design that needs preemption must be expressed as extra `yield` points, not real threads.
- The scheduler owns the ready queue and is the only component allowed to change `Process.state`; the interpreter only yields `Block` and calls `sched.wake()`.
- Semaphore semantics are value-based with wake-one-on-V, so `P` must loop (`while value <= 0: yield Block`) — a single check would lose wakeups.
- Monitor mutual exclusion is layered on top of a binary semaphore, so monitor entry/exit are ordinary `P`/`V` and can block; `cond.wait()` releases the mutex before blocking and re-acquires it after.
- `Interpreter` and `Scheduler` are mutually recursive (`interp.sched` / `sched.interp`); `interp.sched` must be assigned before `interp.run()` or `do_V`/`spawn` will fail.
- Config is a plain nested dict merged over `DEFAULTS`; unknown keys are ignored at runtime and only reported by `vm config`, so adding a config key requires updating `DEFAULTS`, `CONFIG_TEMPLATE` and `validate()` together.
