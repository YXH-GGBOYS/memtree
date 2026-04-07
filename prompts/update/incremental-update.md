# MemTree Incremental Update

## Trigger
One of:
1. `.memory/.pending-update` has entries (Claude Code hook triggered)
2. `.memory/.stale` has entries (pre-commit hook triggered)
3. Manual: user ran `/memtree_rebuild` on specific files

## Task
Update only the affected `.memory/` files, not a full rebuild.

## Steps

1. Read `.pending-update` and `.stale`, merge and deduplicate
2. For each stale .memory/ file:
   a. Read the corresponding source file (from frontmatter `source` field)
   b. Compare with existing .memory/ content — identify what changed
   c. Update: function signatures, depends_on/depended_by, constraints, TL;DR
   d. Recompute source_hash (SHA256 first 8 chars), update last_analyzed
3. **Propagation** — if imports changed:
   - New import added → add this file to target's depended_by
   - Import removed → remove this file from target's depended_by
4. If new file created (no .memory/ exists) → generate from template
5. If file deleted (source gone) → remove .memory/ file + clean depended_by refs
6. Update affected INDEX.md files
7. Clear processed entries from `.pending-update` and `.stale`

## Constraints
- Only update affected files, never full rebuild
- Commit .memory/ changes together with code changes (not separately)
- If source_hash already matches → skip (file not actually changed)
