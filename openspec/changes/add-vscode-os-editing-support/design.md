# Design

## Context

见 [`proposal.md`](proposal.md) 的 Why。约束来自 VSCode 本身：

- VSCode **不支持**从工作区自动加载扩展（没有 workspace extension 机制），因此「随项目便携」不能靠自建扩展实现；任何扩展方案都需要用户执行一次安装命令。
- VSCode **会**自动加载工作区 `.vscode/settings.json`、`.vscode/tasks.json` 和 `.vscode/*.code-snippets`，这三者是唯一零安装、克隆即生效的扩展点。
- 语言高亮只能来自已安装扩展贡献的 TextMate 语法；内置语言中 `c` 的语法与 `.os` 最接近（`int`/`void`/`if`/`while`/`for`/`return`/`struct`/`typedef`/`enum`/`union`/`const`/`static` 等关键字、`//` 与 `/* */` 注释、字符串与数字字面量）。
- 仓库是纯 Python 项目，没有 C 源文件，因此工作区级 C 相关设置不会误伤本仓库代码。
- `.gitignore` 忽略 `*.os`，无法提交示例 `.os` 文件；片段本身就是可复制的模板。

## Goals / Non-Goals

**Goals:**

- 克隆仓库后用 VSCode 打开，`.os` 文件立即获得 C 风格高亮、Tab 片段补全和运行任务，零安装、零构建。
- 所有配置只作用于 `*.os`（通过 `files.associations` + `[c]` 语言级设置 + 片段 `scope`），不改变用户其他语言的行为。
- 片段覆盖本语言的全部核心结构，前缀短、可预测、不与 C 关键字冲突。

**Non-Goals:**

- 不实现真正的 `.os` 语言 id、TextMate 语法、语义高亮或语言服务器。
- 不实现基于 AST 的智能补全（变量名、函数名、管程成员）。
- 不新增 `vm` 子命令、不打包 `.vsix`、不推荐市场扩展。
- 不改变 `src/vm` 的任何行为。

## Decisions

### 1. 用内置 `c` 语言做高亮，而不是自建语言或扩展

`files.associations` 把 `*.os` 映射到 `c`。备选方案：

- **自建扩展 + TextMate 语法**：高亮最准确（可高亮 `semaphore`/`monitor`/`cond`），但需要安装步骤，违反「零安装」的选定方案。
- **关联到 `plaintext`**：无高亮，等于没做。
- **关联到 `cpp`**：关键字集合更大，但会引入 `class`/`template`/`namespace` 等本语言不存在的概念，且同样无法高亮 `semaphore`/`monitor`。

代价是 `semaphore`、`monitor`、`cond`、`share`、`public`、`private` 不会被当作关键字着色（`public`/`private` 在 C 中也不是关键字）。缓解手段是片段补全 + README 明确说明，而不是引入安装步骤。

### 2. 编辑器设置放在 `[c]` 语言级块，而不是全局

```jsonc
{
  "files.associations": { "*.os": "c" },
  "[c]": {
    "editor.tabCompletion": "onlySnippets",
    "editor.snippetSuggestions": "top",
    "editor.quickSuggestions": { "other": "on", "comments": "off", "strings": "off" },
    "editor.wordBasedSuggestions": "currentDocument",
    "editor.tabSize": 4,
    "editor.insertSpaces": true,
    "editor.autoIndent": "full"
  }
}
```

`tabCompletion` 选 `onlySnippets` 而不是 `on`：`on` 会让 Tab 接受任意建议（包括词法建议），在伪代码里容易误触；`onlySnippets` 保证 Tab 只展开片段，词法建议仍可通过 `Ctrl+Space` 或回车接受。`wordBasedSuggestions: currentDocument` 让同一文件内的变量名/函数名可被补全，弥补没有语言服务器的缺口。

### 3. 片段 `scope` 限定为 `c`

`.vscode/os.code-snippets` 中每个片段都带 `"scope": "c"`。备选：不写 scope（片段会出现在所有语言中，污染 `.py`/`.md`）。由于 `.os` 被关联到 `c`，scope 为 `c` 即可精确覆盖 `.os`，同时不影响其他语言。

### 4. 片段前缀命名

| 前缀 | 展开 |
| --- | --- |
| `proc` | 无参 `void` 进程骨架 |
| `sem` | `semaphore <name> = 1;` |
| `mon` | `Monitor <name> { ... }` 骨架（含 `cond`、`public:`、过程、初始化块） |
| `cond` | `cond <name>;` |
| `wait` | `P(<sem>);` |
| `signal` | `V(<sem>);` |
| `swait` | `Swait(<s1>, <t1>, <d1>; <s2>, <t2>, <d2>);` |
| `ssignal` | `Ssignal(<sem>, <demand>);` |
| `printf` | `printf("<fmt>\n", <args>);` |
| `start` | `start(<func>);` |
| `if` / `while` / `for` / `do` | 对应控制流骨架 |
| `var` | `int <name> = 0;` |
| `arr` | `int <name>[<N>];` |
| `pc` | 生产者-消费者完整骨架（信号量 + 两个进程） |

用 `wait`/`signal` 而不是 `p`/`v`：单字母前缀在正常输入中极易误触 Tab。`wait`/`signal` 同时是运行时接受的别名，语义自洽。`if`/`while`/`for`/`do` 与 C 关键字同名，但片段只在 Tab 时展开，且工作区片段排在用户片段之前，冲突可接受。

片段体使用 `${1:name}` 占位与 `$0` 结束光标；`printf` 片段在 JSON 中写 `\\n`，展开后得到源码里的 `\n` 转义。

### 5. 任务用 `uv run vm`，不写死解释器路径

```jsonc
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "vm: run current file",
      "type": "shell",
      "command": "uv",
      "args": ["run", "vm", "${file}"],
      "options": { "cwd": "${workspaceFolder}" },
      "group": { "kind": "build", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "dedicated", "clear": true },
      "problemMatcher": []
    },
    {
      "label": "vm: run current file (no trace)",
      "type": "shell",
      "command": "uv",
      "args": ["run", "vm", "${file}", "--no-trace"],
      "options": { "cwd": "${workspaceFolder}" },
      "presentation": { "reveal": "always", "panel": "dedicated", "clear": true },
      "problemMatcher": []
    }
  ]
}
```

备选：`.venv/Scripts/vm`（Windows 专用、依赖 venv 已创建）、`python -m vm`（`src` 布局下不可直接运行）。`uv run` 与 README 的用法一致，跨平台，且自动使用项目 venv。

### 6. 文档放 README，不新建 docs/

项目只有 `README.md`，新增「VSCode 编辑支持」小节即可，避免为三个配置文件引入新的文档目录。

## Risks / Trade-offs

- **C/C++ 扩展对 `.os` 报诊断** → 关联到 `c` 后，若用户安装了 `ms-vscode.cpptools`，它会把 `.os` 当 C 文件解析，`semaphore mutex = 1;`、`Swait(a, b, c; d, e, f);` 等会显示波浪线。缓解：README 说明这是关联副作用，并给出两种规避方式——在用户设置中把 `*.os` 临时改回 `plaintext`，或在本工作区设置 `"C_Cpp.errorSquiggles": "disabled"`（本仓库无 C 源文件，工作区级关闭是安全的）。
- **`semaphore`/`monitor`/`cond` 不高亮** → 无法通过 `editor.tokenColorCustomizations` 新增关键字（它只能改已有 token 的颜色）。缓解：片段 + README 说明；若将来需要精确高亮，再单独立项做扩展。
- **片段前缀与用户已有 C 片段重名** → 工作区片段与用户片段会同时出现在建议列表。缓解：前缀表写进 README，且 `snippetSuggestions: "top"` 让片段优先。
- **`tabCompletion: onlySnippets` 不是「任意补全」** → 用户可能期望 Tab 补全变量名。缓解：`wordBasedSuggestions: currentDocument` + `Ctrl+Space` 仍可补全；README 说明 Tab 只展开片段。
- **`.gitignore` 忽略 `*.os`** → 无法提交演示文件，新用户看不到效果。缓解：`pc` 片段本身就是完整可运行示例，README 指引用户新建 `my.os` 后输入 `pc` + Tab。
- **片段与语言演进脱节** → 若将来新增关键字（如新的同步原语），片段不会自动更新。缓解：在 `AGENTS.md`/README 中提示「新增语言结构时同步更新 `.vscode/os.code-snippets`」。
