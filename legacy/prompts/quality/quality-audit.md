# MemTree Quality Audit

## Task
Sample 15 `.memory/` files and verify their content against actual source code. This is the V1 acceptance gate — if too many files fail, the Worker prompts need improvement before the MemTree is useful.

## Sample Selection
Pick ~2-3 files per service, prioritizing:
- The most complex router/page (highest import count)
- The largest service file (most functions)
- One ORM model file (to verify DB column mapping)
- 2 DB table files (if .memory/db/ exists)

Read `memtree.config.yaml` to know which services exist.

## Checks Per Code File (.py / .vue / .ts / .tsx)

| # | Check | Method | PASS if |
|---|-------|--------|---------|
| C1 | TL;DR accurate | Read source, judge | Role description correct, key deps and constraints present |
| C2 | Function signatures | Compare Quick Ref vs actual def/function declarations | Name, params, types, return type all match |
| C3 | Constraints complete | Compare with source business rules | Transaction mode, currency units, status enums not missing |
| C4 | depends_on coverage | Compare with source import/from statements | Every project-internal import listed |
| C5 | depended_by non-empty | `grep -r "import.*{filename}"` in project | At least 1 caller recorded |
| C6 | PITFALLS pointer valid | Read referenced PITFALLS.md | Pointer target exists |
| C7 | source_hash correct | Compute SHA256[:8] of source file | Matches frontmatter |

## Checks Per DB Table File (.memory/db/)

| # | Check | Method | PASS if |
|---|-------|--------|---------|
| D1 | Column count | Query information_schema | .memory/ count == DB actual |
| D2 | Column names correct | Compare with DB query | Every column name and type matches |
| D3 | ORM mismatch flagged | Grep ORM model file | All Column("x") mismatches noted |
| D4 | CHECK constraints | Query pg_constraint | Important CHECKs documented |

## Output Format

Per file:
```
### {.memory/ path}
- C1 TL;DR: PASS / FAIL — {reason if fail}
- C2 Signatures: PASS / FAIL — {which function mismatches}
- C3 Constraints: PASS / FAIL — {what's missing}
- C4 depends_on: PASS / FAIL — {missing imports}
- C5 depended_by: PASS / FAIL
- C6 PITFALLS: PASS / FAIL / N/A
- C7 source_hash: PASS / FAIL
**Result: PASS / FAIL (N/7 checks passed)**
```

## Final Summary
```
Quality Audit Complete:
- PASS: X/15 files
- FAIL: Y/15 files
- Top failure patterns: {list top 3}
- Recommendation: {if <10 PASS: which Worker rule to strengthen}
```

## Scoring
- 15/15 PASS → Excellent, MemTree ready for production use
- 10-14 PASS → Good, fix failed files and check for systematic issues
- <10 PASS → Worker prompts have systematic problems, fix prompts and re-bootstrap affected services
