<div align="center">

# MemTree

让 Claude Code 的会话保持短小，让项目事实只存一处。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-blueviolet)](https://code.claude.com/docs/en/plugins)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)

[English](README.md) | [中文](README_CN.md)

</div>

MemTree 是给 [Claude Code](https://code.claude.com) 用的一套小工具：三个只往上下文里加文字的
hook、四个 skill、六个只用标准库的 Python 脚本，外加一套「哪类事实放在哪个文件」的约定。可以作为
Claude Code 插件安装，也可以直接拷文件。它提供的是工作方法和背后的道理，不带任何项目的数据。

## 为什么：上下文就是账单

模型每调用一次，都会把整段对话重新发一遍。所以一个会话的花费，跟「会话有多长 × 调用了多少次」
成正比，跟「某个文件是不是读了两遍」关系不大。

我们在一位独立开发者的 Claude Code 会话记录上量过：大约三周，大约 20 个项目。这里只给比例；
你的数字会不一样，`scripts/token_report.py` 可以从你本机的会话记录里算出你自己的。

| 观察 | 性质 |
|---|---|
| 同一会话里把同一个文件原样重读：不到重复发送上下文的 0.1% | 实测 |
| 约 80% 的重复发送 token 发生在上下文超过 30 万的调用里；约 50% 发生在超过 50 万的调用里 | 实测 |
| 一个新会话刚开始就有约 9 万到 10 万 token 的固定开销（工具定义、系统提示、CLAUDE.md） | 实测 |
| 上下文到 45 万时换到新会话（新会话从约 15 万起步），重复发送的上下文能少约 30% | 模拟，没算交接本身的损失 |
| 用一个常见关键词 grep 知识文件，返回约 500 KB；同一个问题用卡片查询，返回约 4 KB | 实测一次 |

由此得出三条做法：

1. 钱主要花在长会话上。在干净的节点，用一张短卡片换到新会话，别等上下文涨大。MemTree 会到点提醒。
2. 进了上下文的东西，之后每次调用都要再付一遍。硬规则每个会话注入一次，不要每条消息都注入；
   查知识用小卡片，不要 grep 大文件。
3. 同一个事实存两处，迟早不一致。每类事实只放在一个权威文件里，其它地方只放指针。

细节和模拟方法见 [docs/context-economics_cn.md](docs/context-economics_cn.md)。

## 包含什么

| 组件 | 作用 |
|---|---|
| `hooks/facts_digest.py`（UserPromptSubmit） | 每个会话注入一次 `.memory/CRITICAL_FACTS.md` 里的硬不变量摘要（DIGEST）；之后只给一行指针；摘要改了就重新整段注入 |
| `hooks/post_compact.py`（SessionStart，`compact`） | 上下文压缩之后：重新注入摘要，提醒「压缩摘要有损，以文件为准」，附上最近一张未关闭交接卡的开头，总共不超过 9,000 字节 |
| `hooks/ctx_handoff_reminder.py`（UserPromptSubmit） | 从会话记录读真实上下文大小，每过一个台阶（窗口的 45% / 60% / 75%）提醒一次换会话 |
| skill `memtree-init` | 通过几个问题在项目里建好 `.memory/`，从不覆盖已有文件 |
| skill `memtree-handoff` | 什么时候、怎么写交接卡，并在新会话里接着做 |
| skill `memtree-closeout` | 一条工作线收尾：记事件、更新 PITFALLS 生命周期、关闭卡片、把更正写回源文件 |
| skill `memtree-lookup` | 低成本查知识、核实否定断言、找出谁在读某个字段 |
| `scripts/memq.py` | 在 CRITICAL_FACTS、PITFALLS、事件索引、交接卡里按卡片查询 |
| `scripts/ctx_usage.py` | 从会话记录读出当前上下文大小 |
| `scripts/token_report.py` | 本地报表：上下文 token 花在哪了，外加换会话模拟 |
| `scripts/verify_absence.py` | 给「X 不存在」这类断言找证据：两种检索方法，打印原命令和命中数 |
| `scripts/who_reads.py` | 列出某个字段或状态的所有读写处，把判断条件单独列出来 |
| `templates/` | CRITICAL_FACTS、PITFALLS、事件、事件索引、交接卡、CLAUDE.md 片段 |

## 安装

### 作为 Claude Code 插件

```
/plugin marketplace add YXH-GGBOYS/memtree
/plugin install memtree@memtree
```

插件会注册三个 hook 和四个 skill（调用名是 `/memtree:memtree-init` 这样的）。没有 MemTree
`.memory/` 目录的项目里，hook 什么都不输出，所以装在用户级别是安全的。

### 手动安装（不用插件系统）

```bash
git clone https://github.com/YXH-GGBOYS/memtree.git ~/memtree
cd ~/memtree
./install.sh            # skill 拷到 ~/.claude/skills/，hook 和脚本拷到 ~/.claude/memtree/，
                        # 然后打印要合并进 ~/.claude/settings.json 的 hook JSON
./install.sh --apply    # 或者让它替你合并，合并前会先备份 settings.json
```

只需要 Python 3.9 以上，别的都不用装。Windows 上如果 PATH 里没有 `python3`，把 hook 命令改成
`python` 或 `py -3`。

卸载：插件用 `/plugin uninstall memtree@memtree`；手动安装的删掉 `~/.claude/skills/memtree-*`
和 `~/.claude/memtree/`，再从 `settings.json` 里去掉那三条 hook。

### 在项目里初始化

在项目目录里打开 Claude Code，运行 `memtree-init` skill（插件安装是 `/memtree:memtree-init`，
手动安装是 `/memtree-init`）。它会问几个问题（项目分哪几块、哪些事实一旦搞错就会丢钱或丢数据），
然后建出：

```
.memory/
├── CRITICAL_FACTS.md      硬不变量；其中 DIGEST 段就是 hook 注入的内容
├── memtree.json           {"extra_sources": []}（可选：让 memq 额外查的文件）
├── billing/PITFALLS.md    你说了几块就建几个
├── auth/PITFALLS.md
├── events/INDEX.md        每个事件一行；事件文件放 events/YYYY-MM/
└── threads/               交接卡，每条工作线一张
```

不在 Claude Code 里也可以：`python3 scripts/memtree_init.py --areas billing,auth,api --claude-md`。
`.memory/` 是项目知识，跟代码一起提交。填好内容的小例子在 [examples/saas-app/](examples/saas-app/)。

## 工作方式

### 每类事实只有一个权威

| 事实类型 | 唯一的权威位置 |
|---|---|
| 硬不变量：金额单位、数据归谁写、哪个环境是哪个、哪些操作必须有人当场同意 | `.memory/CRITICAL_FACTS.md`（`<!-- DIGEST-START -->` 和 `<!-- DIGEST-END -->` 之间以 `• ` 开头的行会被注入） |
| 某一块的已知陷阱，带生命周期（状态 ACTIVE / RESOLVED、类型、来源事件、last_seen、怎么验证） | `.memory/<area>/PITFALLS.md` |
| 事件：现象、根因、修复、怎么验证的 | `.memory/events/YYYY-MM/EVT-*.md`，再在 `.memory/events/INDEX.md` 里加一行 |
| 一条工作线做到哪了 | `.memory/threads/<name>.md` 交接卡 |

其它地方只放指针（`见 billing/PITFALLS.md P003`），不用自己的话再写一遍。两处说法不一致就是
bug：改那个不是权威的地方。只在对话里说过的更正不算更正，因为下一个会话看不到这段对话。

### 交接卡

一张卡最多 60 行，固定八项：目标与验收；现在在哪一步；已定决策（每条带出处）；授权（永远写
「无」）；动过的文件和提交；没做完或没验证的；下一步（第一步具体到命令或文件）；先读（最多五个
指针，带行号）。新会话只读这张卡和卡里的指针，先用 git 核对状态，再接着做。交接卡永远不带上线
或部署授权，新会话要重新拿到授权。详见 [skills/memtree-handoff/SKILL.md](skills/memtree-handoff/SKILL.md)。

### hook 只注入

MemTree 的 hook 从不拦截、改写或转发任何工具调用。它们不加 PreToolUse 处理，不加自己的工具，
也不保存工具输出。它们总是以 0 退出；项目里没有 MemTree `.memory/`（含 `CRITICAL_FACTS.md` 或
`memtree.json` 的目录）时什么都不输出。

这是有意的。有些节省上下文的工具会加自己的命令执行工具，或者把命令转给它们执行。这样一来，
你给 Bash 配的 PreToolUse 安全 hook 就看不到这些命令了，被转走的输出（包括数据库查询结果）
还可能以明文存在磁盘上。用这类工具的话，请检查你的防护 hook 对它执行的命令是否还会触发。

hook 的设计受两条限制约束：

- Claude Code 对 hook 输出有 10,000 字符的上限。超过就把输出存成文件，模型只看到开头约 2,000
  字符的预览，也没有任何东西提示模型去打开那个文件。我们在加预算之前不止一次撞上过，所以 MemTree
  每个 hook 的输出都控制在 9,000 字节以内，在 UTF-8 字符边界截断，并留一行可见的 `…truncated`。
- 要核对模型实际收到了什么。对 hook 来说，就是用 Claude Code 发的同样的 stdin 去跑，看它打印了
  多少字节、真实退出码是多少；脚本自己报告的结果不算证据。`memtree-init` skill 最后一步做的就是这个检查。

可选的环境变量：

| 变量 | 作用 |
|---|---|
| `MEMTREE_CONTEXT_WINDOW` | 上下文窗口大小（token）。提醒默认按 1M 算，除非模型名或会话大小说明不是；用 200K 模型的话设成 `200000` |
| `MEMTREE_HANDOFF_TOKENS` | 直接指定提醒台阶，比如 `300000,450000`（覆盖 45/60/75% 的默认值） |
| `MEMTREE_STATE_DIR` | 每会话标记文件放哪（默认 `~/.claude/state/memtree/`） |

### 否定断言和共享字段

两个习惯，脚本让它们做起来很便宜：

- 写下「X 不存在 / 做不到 / 要新建」之前，先跑 `verify_absence.py X`，把它打印的命令和命中数
  放在断言旁边。这类断言会被原样抄进后面的文档，而且错的时候方向总是「多干活」。还要说清能力处在
  哪个状态：不存在、已建未接线、已接线未打开、已在运行。「已在运行」要有运行时证据；另外小心一种
  情况：组件在跑、有日志，但每次的结论都是「判断不出」。
- 改共享字段或状态值之前，先跑 `who_reads.py <符号>`。它列出的「conditions」一组（if / where /
  filter / == / in）最容易被漏掉：字段里装的东西一变，其中某一处可能就变成恒真或恒假，而且不报任何错。

## 哪些是实测，哪些是模拟，哪些没测

- 实测：第一张表里的比例，来自一位开发者本机约三周的会话记录。它描述的是那份工作量，不是你的；
  用 `token_report.py` 算你自己的。
- 模拟：在 45 万换会话能省约 30%。模拟用每个会话真实的上下文大小，假设它在约 15 万重新起步；
  没算卡片本身、新会话里重读文件、交接中丢失的信息。把它当上限看。早一版模拟在同一份数据上
  算出 35%-40%，因为原会话自己压缩之后它还在继续记节省；现在附带的版本不这样算。
- 没有量过：一次交接会丢多少信息，摘要注入实际挡住了多少错误。
- 有测试：hook 和脚本有单元测试（`python3 -m pytest tests` 或
  `python3 -m unittest discover -s tests`），也用样例 stdin 做过冒烟测试。
- 还没测：通过 `/plugin` 的完整安装流程、Windows、以及各种模型名下的窗口大小判断。

## 相关项目

和 MemTree 一起用、或者替代它的工具，按类别：

- 会话用量统计：ccusage 从 Claude Code 的本地日志统计 token 用量和费用。`token_report.py` 问的是
  另一个问题：哪些会话、哪类内容重复发送的上下文最多。
- 记忆插件：claude-mem 记录会话里发生的事，自动把压缩后的版本带进以后的会话。MemTree 存的是人工
  整理、你会审阅并提交的事实文件。
- 输出沙箱：context-mode 把命令交给自己的工具执行，让大段输出不进上下文。用这类工具时，请确认你的
  PreToolUse 安全 hook 还能看到它执行的命令（见上面「hook 只注入」）。
- 代码图谱：graphify 为代码库建一张可查询的图。MemTree 不给代码建索引；智能体直接读源码，源码永远是最新的。

## 从 v1 升级

v1 为每个源文件生成一份 LLM 写的摘要，靠编辑 hook 保持更新。实际使用中，大约 55% 的摘要六个月
以上没人动过，三周里几乎没被读过，而 hook 每次编辑照样排队更新。这条流水线现在放在
[legacy/](legacy/README.md)，里面写了还想用的话怎么用。`PITFALLS.md` 和事件记录的思路保留下来，
v2 加了生命周期字段和 DIGEST 摘要。见 [CHANGELOG.md](CHANGELOG.md)。

## 文档

- [快速上手](docs/getting-started_cn.md)
- [上下文经济学](docs/context-economics_cn.md)
- [设计原则](docs/design-principles_cn.md)
- [CLAUDE.md 集成](docs/claude-md-integration_cn.md)

## 许可证

MIT，见 [LICENSE](LICENSE)。
