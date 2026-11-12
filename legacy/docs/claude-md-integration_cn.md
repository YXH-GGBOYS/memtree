# 将 MemTree 集成到 CLAUDE.md

要让 MemTree 在跨会话时生效（包括 `/clear` 之后），需要在项目的 `CLAUDE.md` 中添加以下内容：

## 添加到 CLAUDE.md

```
## MemTree Code Memory
- Before modifying any code, read `.memory/{service}/PITFALLS.md` for the affected service
- Use 3-hop navigation: `.memory/ROOT.md` → `{service}/INDEX.md` → `{service}/{path}.md`
- After modifying code, check if `.memory/` needs updating (compare source_hash in frontmatter)
- For cross-service changes, read `.memory/cross-refs/INDEX.md`
```

## 为什么需要这样做

Claude Code 在每次会话开始时会读取 `CLAUDE.md`。如果没有这些指令，Claude 没有理由去查看 `.memory/` — 它会直接读取源文件。

将 MemTree 规则添加到 `CLAUDE.md` 可以确保 AI agent：
1. 在写代码之前始终检查 PITFALLS.md（避免已知错误）
2. 使用结构化的 `.memory/` 进行导航，而不是盲目扫描文件
3. 在代码变更后保持 `.memory/` 同步更新
