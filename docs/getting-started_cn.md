# 快速上手

[English](getting-started.md)

## 1. 安装

插件（推荐）：

```
/plugin marketplace add YXH-GGBOYS/memtree
/plugin install memtree@memtree
```

手动：

```bash
git clone https://github.com/YXH-GGBOYS/memtree.git ~/memtree
cd ~/memtree && ./install.sh          # 打印要合并进 ~/.claude/settings.json 的 hook JSON
./install.sh --apply                  # 或者让它替你合并（会先备份 settings.json）
```

只需要 Python 3.9 以上，不装任何别的东西。装完重启 Claude Code（或打开 `/hooks`）。

## 2. 初始化一个项目

在项目里打开 Claude Code，运行 `memtree-init` skill（插件是 `/memtree:memtree-init`，手动安装是
`/memtree-init`）。回答它的问题；它会按模板建出 `.memory/`，从不覆盖已有文件。也可以直接跑脚本：

```bash
python3 ~/memtree/scripts/memtree_init.py --areas billing,auth,api --claude-md
```

然后把真正的硬不变量写进 `.memory/CRITICAL_FACTS.md` 的 DIGEST 段：一行一条，每行以 `• ` 开头，
总共不超过约 3,000 字符。好的摘要行是「一旦违反就会丢钱、丢数据或出事故」的规则，比如：

```
• Money is stored as integer minor units (cents) everywhere; never floats. See §2.
• Only billing writes the invoices table; other services call its API. See §2.
```

核对模型会收到什么：

```bash
printf '{"session_id":"check","cwd":"%s"}' "$PWD" \
  | MEMTREE_STATE_DIR="$(mktemp -d)" python3 ~/memtree/hooks/facts_digest.py; echo "exit=$?"
```

（插件安装时 hook 在插件目录里，`memtree-init` skill 会打印正确路径。）然后提交 `.memory/`。

## 3. 日常使用

- 新会话：第一条消息带上摘要全文，之后的消息只带一行指针。
- 改某一块代码之前：读 `.memory/<area>/PITFALLS.md`。
- 找以前的事件、陷阱或决策：`memq.py <关键词>`，再用 Read 带 offset/limit 读命中的那段（skill `memtree-lookup`）。
- 要写「X 不存在」之前：先跑 `verify_absence.py X`。
- 要改共享字段或状态之前：先跑 `who_reads.py <符号>`。
- 收到提醒（上下文过了窗口的 45%）：做完这一步，在下一个干净节点写交接卡，从卡片开新会话接着做
  （skill `memtree-handoff`）。
- 还是发生了压缩：压缩后会立刻注入摘要、一条「以文件为准、别信摘要」的提醒，以及最近一张未关闭的卡片。
- 一条工作线做完：skill `memtree-closeout`（记事件、更新 PITFALLS 生命周期、关闭卡片、把错的说法在源文件里改掉）。

## 4. 量一量

```bash
python3 ~/memtree/scripts/ctx_usage.py                  # 当前会话，滞后一轮
python3 ~/memtree/scripts/token_report.py --since 2026-10-01 --out token-report.md
```

## 排查

| 现象 | 可能原因 |
|---|---|
| hook 什么都不打印 | 会话目录及其上级都没有 `.memory/CRITICAL_FACTS.md`（或 `memtree.json`） |
| 出现一行红字说 DIGEST 没注入 | 标记缺失或拼错，或者标记之间没有以 `• ` 开头的行 |
| 换会话提醒从来不响 | 你用的是 200K 窗口的模型，而程序按 1M 猜的：设 `MEMTREE_CONTEXT_WINDOW=200000` |
| 提醒太早或太晚 | 自己定台阶：`MEMTREE_HANDOFF_TOKENS=300000,450000,600000` |
| Windows 上 `python3: command not found` | 把 hook 命令改成 `python` 或 `py -3` |
