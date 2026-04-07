# MemTree Worker: Deep Analysis of Code Chain {CHAIN_ID}: {CHAIN_NAME}

## Task
Analyze every file in this code chain and generate a `.memory/` document for each.

## Chain Info
- Chain ID: {CHAIN_ID}
- Name: {CHAIN_NAME}
- Service: {SERVICE}
- Entry: {ENTRY_FILE}
- Files: {FILE_LIST}

## Analysis Rules (strict)

### Rule 1: Complete Chain Tracing
- Start from the entry file, follow every import/call to leaf nodes
- Read every imported file, no matter how deep
- **Do NOT skip files** that "look like utilities" — analyze everything
- If you discover files outside the chain list, Read them and mark as "external dependency"
- **You MUST actually Read each file — never guess from filename**

### Rule 2: Record Full Relationships
For each file X, document:

| Relationship | Must include |
|-------------|-------------|
| **Self** | File purpose (1-3 sentences) |
| **Ancestry** | project → service → module → directory → file |
| **Children** | Functions/classes this file calls + signatures + return values |
| **Callers** | Who imports/calls this file + calling context |
| **Siblings** | Other files in same directory + their roles |
| **Collaboration** | How files work together to complete a business function |

### Rule 3: From Read, Not Memory
- Function signatures, field names, parameter types **MUST** come from actually Reading the code
- **Never fill in from memory**
- Mark anything uncertain as [unverified]

### Rule 4: Record Key Constraints
- Transaction pattern (flush-only? commit? who's responsible?)
- Currency/amount units (cents? dollars? which fields?)
- Status enums (list all values)
- Auth/permission requirements
- Concurrency/race condition protections

### Rule 5: Cross-validate DB Column Names (if .memory/db/ exists)
- For ORM model files: compare every Column() with DB column names
- Flag any `Column("db_name")` where the Python attribute differs from DB column
- Note these in Quick Ref constraints

## Output Format

For each file, output one markdown block:

---BEGIN FILE: {service}/{relative_path}---

```yaml
---
source: {actual_filesystem_path}
service: {service}
layer: {router|service|model|page|component|composable|handler|util}
last_analyzed: {ISO 8601 timestamp}
source_hash: {SHA256 first 8 chars}
depends_on: [{list of dependencies}]
depended_by: [{list of callers}]
---
```

# {service}/{relative_path}

## TL;DR
{role} | calls {key dependencies} | {most important constraint}

## Quick Ref
| Export | Signature | Constraint |
|--------|-----------|------------|
| {function/class} | {params → return} | {transaction mode / currency unit / ...} |

> AI agent: 80% of the time, reading up to here is enough. Full Analysis below.

## Full Analysis

### Relationships

#### Siblings
| File | Role | Relation to this file |
|------|------|-----------------------|

#### Children (this file calls)
| Target:function | Signature | Return |
|----------------|-----------|--------|

#### Callers (who calls this file)
| Source | How | Context |
|--------|-----|---------|

#### Collaboration Pattern
{How files work together}

### Key Constraints
{List}

### Modification Risk
{What breaks if you change this file}

---END FILE---

Output one block per file in the chain.
