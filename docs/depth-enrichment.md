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
Order router | calls escrow_service | flush-only

## Quick Ref
(empty or auto-generated from function names)
```

### Deep Analysis (after rebuild)

```markdown
## TL;DR
Order router | calls escrow_service + order_events | price=dollars not cents, flush-only

## Quick Ref
| Export | Signature | Constraint |
|--------|-----------|------------|
| create_order | (session, listing_id, buyer_id) → Order | flush-only, locks listing FOR UPDATE |
| cancel_order | (session, order_id, reason) → None | must set cancelled_at + write OrderEvent |
| pay_order | (session, order_id) → Order | deducts wallet (cents), creates escrow hold |

## Full Analysis
### Children (this file calls)
| Target:function | Signature | Return |
|... (complete dependency graph) ...|
```

## How to Add Depth

### Option 1: Rebuild a Single File

```bash
/memtree_rebuild routes/trading.py
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
/memtree_rebuild db/trading.orders
```

Queries the database for column definitions, constraints, foreign keys, and cross-references with ORM models.

## Recommended Enrichment Strategy

### Right After Bootstrap

1. Check the quality audit report — which files got PASS/FAIL?
2. Rebuild any FAIL files first:
   ```
   /memtree_rebuild routes/trading.py
   /memtree_rebuild services/escrow_service.py
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

For a trading platform:
1. **First**: payment/wallet/ledger services (money-critical)
2. **Second**: order/trade/rental flows (core business)
3. **Third**: admin/dashboard pages (lower risk)
4. **Last**: static pages, config, utilities (rarely buggy)

```
/memtree_rebuild wallet_service      # money first
/memtree_rebuild backend             # then core backend
/memtree_rebuild frontend            # then frontend
```

### Ongoing: Rebuild On Demand

When you're about to work on a file and its .memory/ doc looks thin:

```
/memtree_rebuild routes/rental.py    # enrich before you start coding
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
