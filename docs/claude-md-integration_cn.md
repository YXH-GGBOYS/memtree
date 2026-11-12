# CLAUDE.md 集成

[English](claude-md-integration.md)

hook 负责把硬不变量放到模型眼前。CLAUDE.md 负责告诉它其余部分怎么用：每类事实放在哪、什么时候换
会话、怎么查东西。

## 加上片段

`memtree-init` 会问你要不要加，也可以直接跑：

```bash
python3 ~/memtree/scripts/memtree_init.py --claude-md
```

它会把 [templates/CLAUDE.md.snippet](../templates/CLAUDE.md.snippet)（34 行）追加在
`<!-- memtree:begin -->` 和 `<!-- memtree:end -->` 之间；标记已经存在就什么也不做。片段内容包括：
权威对照表、改某一块之前先读 PITFALLS、先 memq 再 Read、到提醒就换会话、写否定断言前跑
`verify_absence.py`（含能力状态）、改共享字段前跑 `who_reads.py`、核对模型实际收到了什么、在源文件
里改更正、收尾。

## 让 CLAUDE.md 保持小

CLAUDE.md 是每个会话固定开销的一部分，每次调用都要重发。在实测的那套环境里，一个全新会话一开始就有
约 9 万到 10 万 token（工具、系统提示、CLAUDE.md 加在一起）；CLAUDE.md 每多一行，这个下限就高一点。

- 不要把 CRITICAL_FACTS 抄进 CLAUDE.md。摘要本来就会注入；CLAUDE.md 里再放一份，等于付两遍钱，
  而且迟早不一致。
- CLAUDE.md 放规则；规则的来历（谁定的、什么时候、背后是哪次事故）放事件或出处文件，CLAUDE.md 只放指针。
- 某一段只在某类任务里用得到，就挪进 skill，只有做那类任务时才加载。

## 为什么只给片段

片段是指引，不是强制。MemTree 从不加 PreToolUse 处理，规则被无视时也不会拦下任何工具调用。需要
硬门禁（部署、写数据库）的话，自己写 PreToolUse hook；MemTree 不会把命令从它们旁边绕过去。
