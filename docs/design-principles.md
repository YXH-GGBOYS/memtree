# MemTree Design Principles

## 1. Find — Deterministic Path Mapping

Source file path → `.memory/` path is a **pure function**. No search, no indexing, no database lookup.

```
src/api/routes/trading.py  →  .memory/backend/routes/trading.py.md
src/web/pages/market.vue   →  .memory/frontend/pages/market.vue.md
```

The mapping is defined in `memtree.config.yaml` under `path_map` (auto-generated from services). AI agents never need to search for the right .memory/ file — they compute the path directly.

## 2. Read — 3-Hop Navigation

Any question about the codebase can be answered in at most 3 file reads:

1. **ROOT.md** → find which service
2. **{service}/INDEX.md** → find which file
3. **{service}/{path}.md** → get the answer (TL;DR + Quick Ref + Full Analysis)

80% of the time, the TL;DR + Quick Ref (first 15 lines) is enough. Full Analysis is there for deep dives.

## 3. Update — Code Changes, Memory Follows

MemTree is a living document, not a one-time snapshot. Three update mechanisms:

| Mechanism | When | How |
|-----------|------|-----|
| Git hook | Every commit | `pre-commit-memtree.py` compares source_hash, marks stale |
| Manual | After big changes | `/memtree_rebuild {target}` |
| Full rebuild | Rare | `/memtree_bootstrap --resume` |

## 4. Pitfalls First — Read Traps Before Coding

The single most valuable output of MemTree is `PITFALLS.md`. Every service gets one. AI agents MUST read it before writing any code.

Pitfalls capture the knowledge that:
- Static analysis can't detect (business logic constraints)
- Code comments don't cover (cross-service gotchas)
- New team members always get wrong (naming inconsistencies, hidden assumptions)

## 5. Verify — Trust But Check

MemTree's quality audit samples 15 files and verifies each against actual source code. This prevents "AI writing about AI's work" degradation — every function signature, every constraint, every dependency is checked against reality.

Scoring:
- 15/15 PASS → production ready
- 10-14 → fix and recheck
- <10 → fix Worker prompts, re-bootstrap

## 6. Layered Reading — TL;DR → Quick Ref → Full Analysis

Not every question needs a deep dive. Per-file documents are structured in layers:

```
Frontmatter (8 lines)     ← Machine-parseable metadata
TL;DR (1 line)            ← "What does this file do + key constraint"
Quick Ref (5-10 lines)    ← Function signatures + constraints table
Full Analysis (50+ lines) ← Complete dependency graph, siblings, risks
```

AI agents can stop reading at any layer. Most bug fixes only need TL;DR + Quick Ref.

## 7. Shared Files First — Optimize for the Dependency DAG

Code dependencies form a DAG (directed acyclic graph), not a tree. Files like `database.py` or `models/user.py` are imported by dozens of other files.

MemTree analyzes these "hot files" first with a dedicated Shared Worker. Chain Workers then reference the shared analysis instead of re-analyzing the same file 20 times.

Result: ~35% reduction in analysis time and tokens.
