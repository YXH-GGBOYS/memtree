# /memtree_rebuild — Manually Re-analyze Files

## Usage
```
/memtree_rebuild <target>
```

Target can be:
- **File path**: `/memtree_rebuild routes/trading.py` (relative to service)
- **Service name**: `/memtree_rebuild backend` (re-analyze entire service)
- **DB table**: `/memtree_rebuild db/schema.tablename` (re-analyze DB table)

## When to Use
- After you manually edited code and want to refresh .memory/
- When you notice .memory/ content is wrong or outdated
- After a major refactor that changed import structures

## Execution

### Single File Mode
1. Parse target → use PATH_MAP from memtree.config.yaml to find source + .memory/ path
2. Read source file, re-analyze using worker-analyze.md prompt:
   - Extract imports → update depends_on
   - Extract function signatures → update Quick Ref
   - Identify constraints → update TL;DR + constraints section
3. Compare with old .memory/:
   - depends_on changed → propagate: update depended_by in affected files
   - Signatures changed → flag child references as potentially stale
4. Update frontmatter: source_hash + last_analyzed
5. Write directly to .memory/ (no draft, owner is trusted)
6. Git commit: "memtree: rebuild {target}"

### Service Mode
1. Glob scan all source files in the service directory
2. Run single-file mode on each file
3. Regenerate service INDEX.md
4. Regenerate service PITFALLS.md (re-import from config + re-scan Worker findings)
5. Git commit: "memtree: rebuild {service} ({N} files)"

### DB Table Mode
1. Query database for table schema (columns, constraints, foreign keys)
2. Grep ORM model files for mapping verification
3. Regenerate .memory/db/{schema}/{table}.md
4. Git commit: "memtree: rebuild {schema}.{table}"

## Notes
- This skill writes **directly to .memory/** — no approval needed
- Changes are committed immediately
- For CI/team workflows where approval is needed, see /memtree_cowork (future extension)
