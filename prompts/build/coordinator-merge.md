# MemTree Coordinator: Merge & Index Generation

## Task
Read all Worker output in `.memory/` and generate global indexes, PITFALLS, and cross-references.

## Input
`.memory/` directory with per-file .md documents from Workers.
`memtree.config.yaml` for project structure and team pitfalls.

## Steps

### 1. Merge Shared File References
- Shared files were analyzed once in Phase 2a
- Append all "calls shared file" references from chain Workers to each shared file's `depended_by`
- Deduplicate

### 2. Generate INDEX.md Per Directory
For each directory containing .md files:
```markdown
# {service}/{directory}/

## Purpose
{One sentence}

## Files
| File | TL;DR | Key Exports |
|------|-------|-------------|

## Directory-Level Constraints
{Rules applying to all files in this directory}
```

### 3. Generate INDEX.md Per Service
```markdown
# {service}/

## Overview
{2-3 sentences}

## Directory Structure
| Directory | Purpose | File Count |
|-----------|---------|-----------|

## External Interfaces
{API endpoints / page routes / exports}

## Dependencies
{Calls which other services? Called by whom?}
```

### 4. Generate PITFALLS.md Per Service
Read `memtree.config.yaml` pitfalls section + Worker-discovered constraints:
```markdown
# {service} — Known Pitfalls

> AI agents: Read this BEFORE writing any code in this service.

## 🔴 Critical (data corruption / 500 errors)
### P001: {title}
- **Trap**: {description}
- **Affected files**: {list}
- **Correct approach**: {how to do it right}
- **Source**: {where this knowledge came from}

## 🟡 Warning (logic bugs)
### P010: {title}
...

## References
- Project pitfalls: memtree.config.yaml
- DB mappings: cross-refs/orm-db-mismatch.md
```

### 5. Generate cross-refs/ Directory

**cross-refs/INDEX.md:**
```markdown
# Cross-References — Navigation

| Problem | Read |
|---------|------|
| Frontend field → backend field? | api-field-mapping.md |
| ORM attribute ≠ DB column? | orm-db-mismatch.md |
| Same name, different meaning? | field-confusion.md |
| Which service accesses which DB schema? | service-schema-matrix.md |
```

**cross-refs/orm-db-mismatch.md:**
```markdown
| ORM Attribute | DB Column | Table | Service | Risk |
|--------------|-----------|-------|---------|------|
(from DB Worker + code Worker analysis)
```

**cross-refs/field-confusion.md:**
```markdown
| Concept | Service A | Service B | Frontend | Note |
|---------|-----------|-----------|----------|------|
(fields with same name but different meaning, or different name but same concept)
```

**cross-refs/api-field-mapping.md:**
```markdown
| Frontend Display | API Field | Backend Handler | DB Table.Column | Note |
|-----------------|-----------|----------------|----------------|------|
```

**cross-refs/service-schema-matrix.md:**
```markdown
| Service | Read/Write Schemas | Read-Only Schemas | Database |
|---------|-------------------|-------------------|----------|
```

### 6. Generate ROOT.md
```markdown
# {Project Name} — MemTree Root

## Services
| Service | Path | Files | Purpose |
|---------|------|-------|---------|

## Navigation
{Keyword → service mapping for quick lookup}

## Freshness
Check .memory/.stale for files that may need updating.
Last full build: {timestamp}
```
