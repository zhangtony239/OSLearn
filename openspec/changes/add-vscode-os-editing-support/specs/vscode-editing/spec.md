# Spec Delta

## Purpose

让 `.os` 伪代码在 VSCode 中获得开箱即用的语法高亮、Tab 片段补全和运行任务，且完全随仓库分发、无需安装任何扩展或全局工具。

## ADDED Requirements

### Requirement: `.os` 文件按 C 语法高亮

工作区 SHALL 将 `*.os` 关联到 VSCode 内置的 `c` 语言，使 C 关键字、字符串、字符字面量、数字以及 `//` 与 `/* */` 注释获得高亮，注释切换使用 C 风格。

#### Scenario: 打开 `.os` 文件

- **WHEN** 用户在工作区中打开任意 `.os` 文件
- **THEN** 状态栏语言模式显示为 C，`int`、`void`、`if`、`while`、`for`、`return`、`struct` 等 C 关键字被高亮
- **AND** 字符串、数字与 `//`、`/* */` 注释按 C 规则着色

#### Scenario: 注释切换

- **WHEN** 用户在 `.os` 文件中执行「切换行注释」
- **THEN** 该行被加上 `//` 前缀
- **AND** 执行「切换块注释」时使用 `/* ... */`

#### Scenario: 不影响其他文件类型

- **WHEN** 用户在同一工作区打开 `.py`、`.md` 或 `.json` 文件
- **THEN** 这些文件的语言模式与高亮不受 `*.os` 关联影响

### Requirement: 语言级编辑器设置不污染全局

工作区 SHALL 通过 `[c]` 语言级设置启用 Tab 补全、快速建议与 4 空格缩进，MUST NOT 通过全局设置改变用户或其他语言的编辑器行为。

#### Scenario: 在 `.os` 中按 Tab

- **WHEN** 用户在 `.os` 文件中输入片段前缀后按 Tab
- **THEN** 匹配的片段或建议被接受

#### Scenario: 在其他语言中按 Tab

- **WHEN** 用户在 `.py` 文件中按 Tab
- **THEN** 行为与未应用本工作区设置时一致（仍为缩进），不会接受建议

### Requirement: 项目级 Tab 片段补全

工作区 SHALL 提供 `.vscode/os.code-snippets`，为 `.os` 常用结构提供「前缀 + Tab」展开的片段；片段 MUST 为纯文本展开，不引入运行时依赖、命令或文件。

#### Scenario: 进程骨架

- **WHEN** 用户在 `.os` 文件中输入 `proc` 并按 Tab
- **THEN** 展开为无参 `void` 函数骨架，函数名可编辑，函数体包含占位语句

#### Scenario: 信号量声明

- **WHEN** 用户输入 `sem` 并按 Tab
- **THEN** 展开为 `semaphore <name> = 1;`，名称与初值可编辑

#### Scenario: 管程骨架

- **WHEN** 用户输入 `mon` 并按 Tab
- **THEN** 展开为 `Monitor <name> { ... }` 骨架，包含 `cond` 声明、`public:` 段、过程与初始化块占位

#### Scenario: 同步原语

- **WHEN** 用户输入 `wait`、`signal`、`swait` 或 `ssignal` 并按 Tab
- **THEN** 分别展开为 `P(<sem>);`、`V(<sem>);`、`Swait(<sem>, <test>, <demand>; ...);`、`Ssignal(<sem>, <demand>);`

#### Scenario: 输出与启动

- **WHEN** 用户输入 `printf` 或 `start` 并按 Tab
- **THEN** 分别展开为 `printf("<fmt>\n", <args>);` 与 `start(<func>);`

#### Scenario: 控制流

- **WHEN** 用户输入 `if`、`while`、`for` 或 `do` 并按 Tab
- **THEN** 展开为对应的 C 风格控制流骨架，条件与循环体为可编辑占位

#### Scenario: 片段作用域

- **WHEN** 用户在 `.py` 或 `.md` 文件中输入相同前缀并按 Tab
- **THEN** 这些 `.os` 片段不会出现

### Requirement: 运行当前文件的任务

工作区 SHALL 提供 VSCode 任务，使用 `uv run vm` 运行当前 `.os` 文件；任务 MUST 使用 `${file}` 与 `${workspaceFolder}` 变量，不得硬编码绝对路径。

#### Scenario: 运行当前文件

- **WHEN** 用户在 `.os` 文件中执行「运行当前文件」任务
- **THEN** 终端在项目根目录执行 `uv run vm <当前文件>` 并显示执行轨迹

#### Scenario: 工作区路径变化

- **WHEN** 仓库被克隆到其他目录后打开
- **THEN** 任务仍能定位项目根并正常运行，无需修改任务定义

#### Scenario: 任务只读

- **WHEN** 任务运行结束
- **THEN** 源文件与仓库内容未被修改

### Requirement: 便携性与零安装

克隆仓库并用 VSCode 打开后，上述能力 MUST 无需安装扩展、市场包、npm 或全局工具即可生效；本变更 MUST NOT 修改 `vm` CLI 或运行时行为。

#### Scenario: 全新克隆

- **WHEN** 用户克隆仓库并用 VSCode 打开，且未安装任何 `.os` 相关扩展
- **THEN** 打开 `.os` 文件即获得高亮，片段与任务可用

#### Scenario: 运行时行为不变

- **WHEN** 用户运行 `uv run pytest -q` 或 `uv run vm <file.os>`
- **THEN** 结果与变更前一致

### Requirement: 已知限制的文档

`README.md` SHALL 记录 VSCode 编辑支持的使用方式与已知限制，包括 `semaphore`、`monitor`、`cond`、`share` 不是 C 关键字，`P`/`V` 只是普通标识符，以及 C/C++ 扩展可能对 `.os` 产生诊断的规避方式。

#### Scenario: 查找片段前缀

- **WHEN** 用户阅读 `README.md` 的 VSCode 小节
- **THEN** 能找到片段前缀表与任务名称

#### Scenario: 遇到 C/C++ 扩展诊断

- **WHEN** 用户安装了 C/C++ 扩展并在 `.os` 文件中看到波浪线
- **THEN** `README.md` 说明这是关联到 C 语言的副作用，并给出关闭该扩展对 `.os` 检查的方法
