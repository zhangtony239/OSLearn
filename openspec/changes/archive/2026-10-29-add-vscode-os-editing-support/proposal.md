# Proposal

## Why

`.os` 伪代码目前没有任何编辑器支持：VSCode 把它当纯文本打开，`semaphore`、`monitor`、`cond`、`P/V`、`Swait/Ssignal` 这些本项目的核心概念既没有高亮也没有补全，写一个生产者-消费者示例要反复手打模板，还容易漏分号、写错管程结构。项目要求「随项目便携」，因此不能依赖市场扩展、全局 npm 或任何安装步骤。

## What Changes

- 新增 `.vscode/settings.json`：用 `files.associations` 把 `*.os` 关联到 VSCode 内置的 `c` 语言，获得 C 风格的关键字/字符串/注释/数字高亮与 `//`、`/* */` 注释切换；用 `[c]` 语言级设置（而非全局设置）打开 Tab 补全、快速建议、4 空格缩进，避免影响用户其他文件。
- 新增 `.vscode/os.code-snippets`：项目级代码片段，VSCode 会自动加载工作区 `.vscode/*.code-snippets`。覆盖进程骨架、`semaphore` 声明、`monitor` 骨架、`cond`、`P/V`、`Swait/Ssignal`、`printf`、`if/while/for/do`、`start()` 等；片段 `scope` 限定为 `c`，只在 `.os` 这类 C 关联文件中出现。
- 新增 `.vscode/tasks.json`：提供「运行当前 `.os` 文件」任务，命令为 `uv run vm ${file}`，与 README 的用法一致，不硬编码绝对路径。
- 在 `README.md` 增加「VSCode 编辑支持」小节：说明文件关联方式、片段前缀表、任务用法，以及已知限制（`semaphore`/`monitor`/`cond` 不是 C 关键字，`P/V` 只是普通标识符，因此不会被 C 语法高亮为关键字）。
- 不新增 VSCode 扩展、不修改 `vm` CLI、不修改 `src/vm` 运行时行为。

## Capabilities

### New Capabilities

- `vscode-editing`: `.os` 文件在 VSCode 中的零安装编辑体验，包括文件关联与基础高亮、项目级 Tab 片段补全、运行当前文件的任务，以及便携性与已知限制的说明。

### Modified Capabilities

（无。本次不改变 `vm` 的运行时或 CLI 行为。）

## Impact

- 新增文件：`.vscode/settings.json`、`.vscode/os.code-snippets`、`.vscode/tasks.json`。
- 修改文件：`README.md`（新增一节文档）。
- 不影响 `src/vm/`、`tests/`、`pyproject.toml` 或任何运行时行为；`uv run pytest -q` 结果不变。
- 注意：`.gitignore` 忽略 `*.os`，因此不能提交示例 `.os` 文件作为演示，片段本身就是可复制的模板。
- 已知风险：若用户安装了 C/C++ 扩展，关联到 `c` 的 `.os` 文件可能被该扩展做语义检查并出现波浪线；文档中给出关闭该扩展对 `.os` 检查的说明。
