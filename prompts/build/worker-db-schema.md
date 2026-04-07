# MemTree DB Worker: Database Schema Analysis

## Task
Query the project database and generate `.memory/db/` documents for each table. Cross-reference with ORM models to detect naming mismatches.

## Database Access
Read `memtree.config.yaml` for the `database.access` command template.

```bash
# Execute SQL via the configured access method:
{database.access} -c "{SQL}"
```

## Steps

### Phase 1: Enumerate databases and tables
1. List all schemas: `SELECT schema_name FROM information_schema.schemata`
2. For each schema in `database.schemas` config:
   - List tables: `SELECT table_name FROM information_schema.tables WHERE table_schema='{schema}'`
   - Count columns per table

### Phase 2: Detailed analysis (for configured schemas)
For each table in the configured schemas:
1. Column definitions:
   ```sql
   SELECT column_name, data_type, is_nullable, column_default
   FROM information_schema.columns
   WHERE table_schema='{schema}' AND table_name='{table}'
   ORDER BY ordinal_position
   ```
2. Constraints:
   ```sql
   SELECT constraint_name, constraint_type
   FROM information_schema.table_constraints
   WHERE table_schema='{schema}' AND table_name='{table}'
   ```
3. CHECK constraints (PostgreSQL):
   ```sql
   SELECT conname, pg_get_constraintdef(oid)
   FROM pg_constraint
   WHERE conrelid = '{schema}.{table}'::regclass AND contype = 'c'
   ```
4. Foreign keys:
   ```sql
   SELECT kcu.column_name, ccu.table_schema || '.' || ccu.table_name || '.' || ccu.column_name as references
   FROM information_schema.table_constraints tc
   JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
   JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
   WHERE tc.table_schema='{schema}' AND tc.table_name='{table}' AND tc.constraint_type='FOREIGN KEY'
   ```

### Phase 3: ORM Mapping Verification
For each table:
1. Grep the codebase for the corresponding ORM model class
2. Compare DB column names vs ORM attribute names
3. Flag any `Column("db_column_name")` where the Python/TS attribute has a different name

## Output Format

For each table:

---BEGIN DB TABLE: {schema}.{table}---

# {schema}.{table}

## Overview
{1-2 sentence description}

## Columns
| # | Column | Type | Nullable | Default | ORM Attribute | Notes |
|---|--------|------|----------|---------|--------------|-------|

## Constraints
| Name | Type | Definition |
|------|------|-----------|

## Foreign Keys
| Column | → Target |
|--------|----------|

## ORM Mapping
- Model file: {path}
- Class: {ClassName}
- Mismatches: {list DB column ≠ ORM attribute cases}

## Services
| Service | Access | Operations |
|---------|--------|-----------|

---END DB TABLE---
