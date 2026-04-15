# Depth Enrichment Guide — 深度补充指南

## Why Bootstrap Doesn't Deep-Analyze Every File

`/memtree_bootstrap` generates **TL;DR + skeleton** for all files (~100% coverage), but only **deep-analyzes** the most critical ones (~5-10% of files). This is by design:

- A 900-file project would need ~50 parallel Workers running for hours to deep-analyze everything
- 80% of bug fixes only touch 20% of files (Pareto principle)
- Skeleton + TL;DR already provides enough context for most tasks
- Deep analysis is incremental — you add depth where you need it

## What "Skeleton" vs "Deep" Looks Like

### Skeleton (bootstrap default for most files)

```markdown
## TL;DR
Checkout router | calls payment_service | flush-only

## Quick Ref
(empty or auto-generated from function names)
```

### Deep Analysis (after rebuild)

```markdown
## TL;DR
Checkout router | calls payment_service + audit_log | price=major units not minor, flush-only

## Quick Ref
| Export | Signature | Constraint |
|--------|-----------|------------|
| create_subscription | (session, plan_id, account_id) → Subscription | flush-only, locks plan FOR UPDATE |
| cancel_subscription | (session, subscription_id, reason) → None | must set cancelled_at + write AuditLog |
| process_payment | (session, subscription_id) → Subscription | deducts credits (minor units), creates payment hold |

## Full Analysis
### Children (this file calls)
| Target:function | Signature | Return |
|... (complete dependency graph) ...|
```

## How to Add Depth

### Option 1: Rebuild a Single File

```bash
/memtree_rebuild routes/checkout.py
```

MemTree will:
- Read the source file
- Extract all function signatures, imports, constraints
- Generate complete Quick Ref + Full Analysis
- Update depends_on / depended_by

### Option 2: Rebuild an Entire Service

```bash
/memtree_rebuild backend
```

This deep-analyzes every file in the service. Takes ~10-30 min depending on file count.

### Option 3: Rebuild DB Tables

```bash
/memtree_rebuild db/billing.subscriptions
```

Queries the database for column definitions, constraints, foreign keys, and cross-references with ORM models.

## Recommended Enrichment Strategy

### Right After Bootstrap

1. Check the quality audit report — which files got PASS/FAIL?
2. Rebuild any FAIL files first:
   ```
   /memtree_rebuild routes/checkout.py
   /memtree_rebuild services/payment_service.py
   ```

### Prioritize by Bug Frequency

Use git log to find your most-changed files — they're the ones AI will touch most:

```bash
# Top 20 most-changed files in the last 3 months
git log --since="3 months ago" --name-only --pretty=format: | sort | uniq -c | sort -rn | head -20
```

Rebuild those files first:
```
/memtree_rebuild <file1>
/memtree_rebuild <file2>
...
```

### Prioritize by Service Criticality

For a SaaS platform:
1. **First**: billing/credits/payment services (money-critical)
2. **Second**: subscription/checkout/invoicing flows (core business)
3. **Third**: admin/dashboard pages (lower risk)
4. **Last**: static pages, config, utilities (rarely buggy)

```
/memtree_rebuild billing_service      # money first
/memtree_rebuild backend             # then core backend
/memtree_rebuild frontend            # then frontend
```

### Ongoing: Rebuild On Demand

When you're about to work on a file and its .memory/ doc looks thin:

```
/memtree_rebuild routes/subscription.py    # enrich before you start coding
```

This takes ~30 seconds per file and immediately improves AI context quality.

## How to Check Depth Coverage

Look at any .memory/ file. If it only has a TL;DR line and empty Quick Ref → it's skeleton-only. If Quick Ref has a full table with signatures → it's deep-analyzed.

Quick check across a service:
```bash
# Count files with empty Quick Ref (skeleton-only)
grep -rL "| Export | Signature" .memory/backend/ | wc -l

# Count files with full Quick Ref (deep-analyzed)
grep -rl "| Export | Signature" .memory/backend/ | wc -l
```

## FAQ

**Q: Will rebuild overwrite my manual edits to .memory/ files?**
A: Yes. If you've manually edited a .memory/ file, rebuild will regenerate it from source. Add manual knowledge to PITFALLS.md instead (it's preserved across rebuilds).

**Q: How long does a full service rebuild take?**
A: ~1-2 minutes per 10 files. A 100-file service takes ~10-20 minutes.

**Q: Do I need to rebuild after every code change?**
A: No. The git hook automatically detects stale files. Rebuild is for when you want deeper analysis, not just staleness fixes.
