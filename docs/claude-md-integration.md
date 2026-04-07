# Integrating MemTree with CLAUDE.md

For MemTree to work across sessions (including after `/clear`), add these lines to your project's `CLAUDE.md`:

## Add to CLAUDE.md

```
## MemTree Code Memory
- Before modifying any code, read `.memory/{service}/PITFALLS.md` for the affected service
- Use 3-hop navigation: `.memory/ROOT.md` → `{service}/INDEX.md` → `{service}/{path}.md`
- After modifying code, check if `.memory/` needs updating (compare source_hash in frontmatter)
- For cross-service changes, read `.memory/cross-refs/INDEX.md`
```

## Why This Is Needed

Claude Code reads `CLAUDE.md` at the start of every session. Without these instructions,
Claude has no reason to look at `.memory/` — it will just read source files directly.

Adding MemTree rules to `CLAUDE.md` ensures the AI agent:
1. Always checks PITFALLS.md before writing code (prevents known mistakes)
2. Uses the structured .memory/ for navigation instead of raw file scanning
3. Keeps .memory/ updated after changes
