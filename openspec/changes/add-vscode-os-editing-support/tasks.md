# Tasks

## 1. 文件关联与编辑器设置

- [ ] 1.1 创建 `.vscode/settings.json`，写入 `files.associations`（`*.os` → `c`）与 `[c]` 语言级块（`tabCompletion: onlySnippets`、`snippetSuggestions: top`、`quickSuggestions`、`wordBasedSuggestions: currentDocument`、`tabSize: 4`、`insertSpaces: true`、`autoIndent: full`）；验证：`python -c "import json;json.load(open('.vscode/settings.json'))"` 无报错，且打开 `my.os` 时状态栏语言模式显示 C
- [ ] 1.2 验证设置不泄漏到其他语言：打开任意 `.py` 文件按 Tab，确认仍是缩进而非接受建议；确认 `.md`/`.json` 语言模式未变

## 2. Tab 片段补全

- [ ] 2.1 创建 `.vscode/os.code-snippets`，覆盖 `proc`、`sem`、`mon`、`cond`、`wait`、`signal`、`swait`、`ssignal`、`printf`、`start`、`if`、`while`、`for`、`do`、`var`、`arr`、`pc`；验证：`python -c "import json;json.load(open('.vscode/os.code-snippets'))"` 无报错，且每个条目都有 `scope: "c"`、`prefix`、`body`
- [ ] 2.2 验证片段展开：在 `my.os` 中依次输入 `proc`、`sem`、`mon`、`swait`、`printf`、`pc` 后按 Tab，确认展开文本与 `design.md` 的前缀表一致，`printf` 展开后源码中是 `\n` 转义而非真实换行
- [ ] 2.3 验证片段作用域：在 `.py` 文件中输入 `proc` 后按 Tab，确认不会展开 `.os` 片段

## 3. 运行当前文件的任务

- [ ] 3.1 创建 `.vscode/tasks.json`，包含 `vm: run current file`（默认 build 任务）与 `vm: run current file (no trace)`，均使用 `uv run vm ${file}` 且 `cwd` 为 `${workspaceFolder}`；验证：JSON 可解析，且文件中不含硬编码绝对路径（`findstr /C:"C:\\" .vscode\tasks.json` 无输出）
- [ ] 3.2 验证任务可运行：在 `my.os` 中展开 `pc` 片段生成示例，执行 `vm: run current file`，终端出现执行轨迹与 `-- N steps, M process(es)` 结尾统计

## 4. 文档

- [ ] 4.1 在 `README.md` 增加「VSCode 编辑支持」小节，说明 `*.os` 关联到 C 语言、片段前缀表、两个任务名，以及已知限制（`semaphore`/`monitor`/`cond`/`share` 不是 C 关键字、`P`/`V` 是普通标识符、C/C++ 扩展可能报诊断及两种规避方式）；验证：按 README 步骤从空的 `my.os` 输入 `pc` + Tab 后能直接运行成功
- [ ] 4.2 在 README 或 `AGENTS.md` 中注明「新增语言结构时同步更新 `.vscode/os.code-snippets`」；验证：该提示文字存在

## 5. 集成检查

- [ ] 5.1 运行 `uv run pytest -q`，确认全部通过，且 `uv run vm <file.os>` 的输出与变更前一致
- [ ] 5.2 确认三个工作区文件会被提交：`git check-ignore -v .vscode/settings.json .vscode/os.code-snippets .vscode/tasks.json` 无输出
- [ ] 5.3 运行 `openspec validate add-vscode-os-editing-support --strict`，确认通过
