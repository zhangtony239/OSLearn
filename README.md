# oslearn-vm

《操作系统》课程用的 `.os` 伪代码运行器。它把教材里那种「长得像 C」的伪代码
真正跑起来：多进程并发、信号量 `P/V`、`Swait/Ssignal`、管程（monitor）与条件变量
的阻塞/唤醒，并打印每一步的执行轨迹。

## 安装（只装进当前 venv，不污染全局）

```bash
uv sync
```

`uv sync` 会在 `.venv/` 里以可编辑模式安装本项目，并生成 `vm` 命令：

```bash
uv run vm examples/producer_consumer.os --max-steps 40
# 或者先激活 venv
.venv\Scripts\activate
vm examples/producer_consumer.os --max-steps 40
```

## 命令

```
vm <path/to/file.os> [options]      直接运行伪代码
vm config [--path FILE] [--force]   生成 / 自检 vm-config.yaml
vm --version
```

运行选项：

| 选项 | 说明 |
| --- | --- |
| `--config FILE` | 指定配置文件（默认 `./vm-config.yaml`） |
| `--policy NAME` | `round_robin` 或 `random` |
| `--quantum N` | 轮转调度每个时间片执行的语句数 |
| `--seed N` | 随机种子，`-1` 表示每次运行重新取随机种子 |
| `--max-steps N` | 硬性步数上限，防止 `while(1)` 跑不完 |
| `--no-trace` | 不打印执行轨迹 |
| `--quiet` | 不打印警告和结尾统计 |

## 配置文件 `vm-config.yaml`

`vm config` 在文件不存在时生成默认配置；已存在时做自检（类型、枚举值、未知键）。

```yaml
version: 1
scheduler:
  policy: round_robin   # round_robin | random
  quantum: 5            # 每个时间片执行的语句数
  seed: -1              # -1 = 每次随机；>=0 = 可复现
  max_steps: 10000
language:
  lenient: true         # 容忍教材式伪代码（自然语言语句、缺分号、全角标点、省略号）
  auto_declare: true    # 未声明变量按 0 处理，首次赋值时创建
  case_insensitive_keywords: true
trace:
  enabled: true
  stream: stdout        # stdout | stderr
output:
  prefix: ""
```

## 语言要点

- **进程**：顶层所有「无参 `void` 函数」自动作为进程启动，例如
  `void producer() { ... }`。也可以用 `start(f)` 在运行时再启动一个进程。
- **信号量**：`semaphore mutex = 1;`，操作为 `P(s)` / `V(s)`（也接受
  `wait(s)` / `signal(s)`）。
- **AND 信号量**：`Swait(s1, t1, d1; s2, t2, d2)` 全部满足才一次性扣减，
  否则阻塞；`Ssignal(s, d)` 增加 `d` 并唤醒等待者。
- **管程**：

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
      { count = 0; }   // 初始化代码
  }
  ```

  调用方式为 `bounded_buffer.put(x)`。管程过程互斥执行，`cond.wait()` 释放管程并阻塞，
  `cond.signal()` 唤醒一个等待者。
- **输出**：`printf("i=%d\n", i)` 或 `print(x, y)`。
- **宽松模式**：`produce an item in nextp;`、`……`、`；`、`（`、`/* 中文注释 */`
  这类教材写法都能被接受，无法识别的语句会被跳过并给出 warning。

## 执行轨迹

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

结尾会打印步数、进程数，以及是否发生死锁 / 是否因 `max_steps` 被截断。

## 示例

- `examples/producer_consumer.os`：计数信号量 + 互斥信号量的有界缓冲区
- `examples/monitor.os`：管程 + 条件变量版本
- `examples/textbook.os`：`example.txt` 的教材原文，用来验证宽松解析

## VSCode 编辑支持

本项目通过工作区配置为 `.os` 伪代码提供零安装、随仓库生效的编辑支持：

- **语法高亮**：在 `.vscode/settings.json` 中通过 `files.associations` 将 `*.os` 关联为 VSCode 内置的 C 语言，获得 C 风格关键字、注释（`//`、`/* */`）、字符串与数字高亮。
- **Tab 片段补全**：语言级设置 `[c]` 启用了 `editor.tabCompletion: onlySnippets`，在 `.os` 文件中输入前缀后按 **Tab** 即可展开项目级代码片段（定义在 `.vscode/os.code-snippets` 中）。
- **运行任务**：在 `.vscode/tasks.json` 中配置了 VSCode 任务：
  - `vm: run current file`（默认 build 任务，快捷键 `Ctrl+Shift+B` 直接运行当前 `.os` 文件）
  - `vm: run current file (no trace)`（不打印轨迹直接运行）

### 片段前缀表

| 前缀 | 说明与展开 |
| --- | --- |
| `proc` | 无参 `void` 进程骨架 |
| `sem` | `semaphore <name> = 1;` 信号量声明 |
| `mon` | `Monitor <name> { ... }` 管程骨架（含 `cond`、`public:`、过程与初始化块） |
| `cond` | `cond <name>;` 条件变量声明 |
| `wait` | `P(<sem>);` 信号量等待 |
| `signal` | `V(<sem>);` 信号量释放 |
| `swait` | `Swait(<s1>, <t1>, <d1>; <s2>, <t2>, <d2>);` AND 信号量操作 |
| `ssignal` | `Ssignal(<sem>, <demand>);` AND 信号量操作 |
| `printf` | `printf("<fmt>\n", <args>);` 格式化打印 |
| `start` | `start(<func>);` 运行时创建进程 |
| `if` | `if (<condition>) { ... }` 条件分支 |
| `while` | `while (<condition>) { ... }` 循环 |
| `for` | `for (<init>; <cond>; <step>) { ... }` 循环 |
| `do` | `do { ... } while (<condition>);` 循环 |
| `var` | `int <name> = 0;` 整型变量声明 |
| `arr` | `int <name>[<N>];` 数组声明 |
| `pc` | 经典生产者-消费者完整可运行示例（信号量 + 两个进程） |

> **提示**：从空文件开始时，可新建 `my.os`，在编辑器中输入 `pc` 并按 **Tab**，即可展开一个完整的生产者-消费者示例；然后使用 `Ctrl+Shift+B`（执行 `vm: run current file` 任务）直接运行。
>
> **维护说明**：新增语言结构时同步更新 `.vscode/os.code-snippets`。

### 已知限制

1. **关键字高亮范围**：因为使用的是 VSCode 内置 C 语法高亮，`semaphore`、`monitor`、`cond`、`share` 不是标准 C 关键字，`P`/`V` 也是普通标识符，它们不会被着色为关键字。请优先通过前缀片段编写对应结构。
2. **C/C++ 扩展诊断提示**：若安装了 VSCode C/C++ 扩展（`ms-vscode.cpptools`），该扩展会将 `.os` 当作 C 代码分析并可能对伪代码语法标注红色波浪线。若需要消除，可通过以下两种方式之一规避：
   - 在工作区 `.vscode/settings.json` 中配置 `"C_Cpp.errorSquiggles": "disabled"`（本项目无 C 源文件，工作区级禁用安全可靠）；
   - 或在用户设置中将 `*.os` 关联临时改回 `plaintext`。

## 测试

```bash
uv run pytest -q
```
