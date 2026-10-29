# oslearn-vm

English | [简体中文](README_zh.md)

A `.os` pseudocode runner for an Operating Systems course. It actually executes the
"C-like" pseudocode found in textbooks: multi-process concurrency, `P/V` semaphores,
`Swait/Ssignal`, monitors and condition-variable blocking/waking, while printing an
execution trace for every step.

## Installation (local venv only, no global install)

```bash
uv sync
```

`uv sync` installs this project in editable mode inside `.venv/` and creates the `vm`
command:

```bash
uv run vm examples/producer_consumer.os --max-steps 40
# or activate the venv first
.venv\Scripts\activate
vm examples/producer_consumer.os --max-steps 40
```

## Commands

```
vm <path/to/file.os> [options]      Run a pseudocode file
vm config [--path FILE] [--force]   Generate / self-check vm-config.yaml
vm --version
```

Run options:

| Option | Description |
| --- | --- |
| `--config FILE` | Config file to use (default `./vm-config.yaml`) |
| `--policy NAME` | `round_robin` or `random` |
| `--quantum N` | Statements executed per time slice under round-robin scheduling |
| `--seed N` | Random seed; `-1` picks a fresh seed on every run |
| `--max-steps N` | Hard step limit, so `while(1)` cannot run forever |
| `--no-trace` | Do not print the execution trace |
| `--quiet` | Do not print warnings or the closing statistics |

## Config file `vm-config.yaml`

`vm config` writes a default config when the file is missing; when it already exists,
the command self-checks it (types, enum values, unknown keys).

```yaml
version: 1
scheduler:
  policy: round_robin   # round_robin | random
  quantum: 5            # statements executed per time slice
  seed: -1              # -1 = random each run; >=0 = reproducible
  max_steps: 10000
language:
  lenient: true         # tolerate textbook pseudocode (prose statements, missing
                        # semicolons, full-width punctuation, ellipses)
  auto_declare: true    # undeclared variables start at 0 and are created on first assignment
  case_insensitive_keywords: true
trace:
  enabled: true
  stream: stdout        # stdout | stderr
output:
  prefix: ""
```

## Language highlights

- **Processes**: every top-level zero-argument `void` function is automatically started
  as a process, e.g. `void producer() { ... }`. You can also spawn another process at
  runtime with `start(f)`.
- **Semaphores**: `semaphore mutex = 1;` with operations `P(s)` / `V(s)`
  (`wait(s)` / `signal(s)` are also accepted).
- **AND semaphores**: `Swait(s1, t1, d1; s2, t2, d2)` decrements all resources at once
  only if every condition holds, otherwise it blocks; `Ssignal(s, d)` adds `d` and wakes
  waiters.
- **Monitors**:

  ```c
  Monitor bounded_buffer {
      int buffer[4];
      int count = 0;
      cond not_full;
      cond not_empty;
      public:
      void put(int item) {
          while (count == 4) not_full.wait();
          ...
          not_empty.signal();
      }
      { count = 0; }   // initialisation code
  }
  ```

  Call them as `bounded_buffer.put(x)`. Monitor procedures run mutually exclusively,
  `cond.wait()` releases the monitor and blocks, and `cond.signal()` wakes one waiter.
- **Output**: `printf("i=%d\n", i)` or `print(x, y)`.
- **Lenient mode**: textbook spellings such as `produce an item in nextp;`, `……`, `；`,
  `（` and `/* 中文注释 */` are all accepted; statements that cannot be recognised are
  skipped with a warning.

## Execution trace

```
[0000] producer     | spawn
[0001] producer     | while (1) -> true
[0002] producer     | P(empty)
[0003] producer     | P(mutex)
[0004] producer     | buffer[in] = nextp
...
[0007] consumer     | BLOCK  P(full)
[0009] producer     | V(full)
[0009] consumer     | WAKE
```

The closing summary prints the step count, the number of processes, and whether a
deadlock occurred or the run was cut off by `max_steps`.

## Examples

- `examples/producer_consumer.os`: bounded buffer with a counting semaphore plus a mutex
  semaphore
- `examples/monitor.os`: the monitor + condition-variable version
- `examples/textbook.os`: the textbook original from `example.txt`, used to verify
  lenient parsing

## VSCode editing support

This project provides zero-install, repository-scoped editing support for `.os`
pseudocode through workspace configuration:

- **Syntax highlighting**: `.vscode/settings.json` maps `*.os` to VSCode's built-in C
  language through `files.associations`, giving C-style keyword, comment (`//`, `/* */`),
  string and number highlighting.
- **Tab snippet completion**: the language-scoped `[c]` settings enable
  `editor.tabCompletion: onlySnippets`, so typing a prefix in a `.os` file and pressing
  **Tab** expands the project-level snippets defined in `.vscode/os.code-snippets`.
- **Run tasks**: VSCode tasks are configured in `.vscode/tasks.json`:
  - `vm: run current file` (default build task; press `Ctrl+Shift+B` to run the current
    `.os` file directly)
  - `vm: run current file (no trace)` (run without printing the trace)

### Snippet prefix table

| Prefix | Expansion |
| --- | --- |
| `proc` | Zero-argument `void` process skeleton |
| `sem` | `semaphore <name> = 1;` semaphore declaration |
| `mon` | `Monitor <name> { ... }` monitor skeleton (with `cond`, `public:`, procedures and init block) |
| `cond` | `cond <name>;` condition variable declaration |
| `wait` | `P(<sem>);` semaphore wait |
| `signal` | `V(<sem>);` semaphore release |
| `swait` | `Swait(<s1>, <t1>, <d1>; <s2>, <t2>, <d2>);` AND-semaphore operation |
| `ssignal` | `Ssignal(<sem>, <demand>);` AND-semaphore operation |
| `printf` | `printf("<fmt>\n", <args>);` formatted print |
| `start` | `start(<func>);` spawn a process at runtime |
| `if` | `if (<condition>) { ... }` conditional branch |
| `while` | `while (<condition>) { ... }` loop |
| `for` | `for (<init>; <cond>; <step>) { ... }` loop |
| `do` | `do { ... } while (<condition>);` loop |
| `var` | `int <name> = 0;` integer variable declaration |
| `arr` | `int <name>[<N>];` array declaration |
| `pc` | Complete runnable classic producer-consumer example (semaphores + two processes) |

> **Tip**: starting from an empty file, create `my.os`, type `pc` and press **Tab** to
> expand a complete producer-consumer example; then press `Ctrl+Shift+B` (which runs the
> `vm: run current file` task) to execute it directly.
>
> **Maintenance note**: keep `.vscode/os.code-snippets` in sync when adding new language
> constructs.

### Known limitations

1. **Keyword highlighting coverage**: because the built-in VSCode C grammar is used,
   `semaphore`, `monitor`, `cond` and `share` are not standard C keywords, and `P` / `V`
   are ordinary identifiers, so they are not coloured as keywords. Prefer writing these
   constructs through the prefix snippets.
2. **C/C++ extension diagnostics**: if the VSCode C/C++ extension (`ms-vscode.cpptools`)
   is installed, it analyses `.os` files as C and may underline pseudocode syntax with red
   squiggles. To suppress this, use either of:
   - set `"C_Cpp.errorSquiggles": "disabled"` in the workspace `.vscode/settings.json`
     (this project contains no C sources, so disabling it at workspace level is safe);
   - or temporarily map `*.os` back to `plaintext` in your user settings.

## Tests

```bash
uv run pytest -q
```
