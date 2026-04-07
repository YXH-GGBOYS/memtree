# Getting Started with MemTree

## What You Need
- [Claude Code](https://claude.ai/code) (CLI, Desktop App, or IDE extension)
- Git
- Python 3.9+
- A codebase you want AI to understand better

## Step 1: Install (30 seconds)

```bash
git clone https://github.com/YXH-GGBOYS/memtree.git ~/memtree

# Copy skills to Claude Code
cp -r ~/memtree/skills/memtree_* ~/.claude/skills/
```

## Step 2: Initialize (5 minutes)

Open Claude Code in your project directory and run:

```
/memtree_init
```

MemTree will ask about your project:
- What services/modules exist
- Where the code lives
- Database details (optional)
- Known pitfalls (optional but very powerful)

This generates `memtree.config.yaml`.

**Or auto-scan** (faster, less precise):
```
/memtree_init --auto
```

## Step 3: Build (30 min - 2 hours, depending on project size)

```
/memtree_bootstrap
```

MemTree will:
1. Scan all source files and map dependencies
2. Identify shared "hot files" and analyze them first
3. Analyze each code chain in parallel
4. Query your database for schema documentation
5. Generate PITFALLS.md per service
6. Build cross-service reference maps
7. Run quality audit

When done, you'll have a `.memory/` directory in your project root.

## Step 4: Use It

Now when AI agents work on your code, they have context:

```
"Fix the bug where wallet balance shows incorrect amount"

AI reads:
1. .memory/backend/PITFALLS.md → "P001: wallet uses trading.users.id, ledger uses auth.user_accounts.id"
2. .memory/backend/services/wallet_service.py.md → TL;DR + function signatures
3. .memory/db/trading/wallet_balances.md → column definitions, ORM mismatches

Result: AI avoids the user_id pitfall and fixes correctly on first try.
```

## Step 5: Keep It Fresh

**Automatic** (recommended): Install the git hook
```bash
cp scripts/pre-commit-memtree.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```
Every commit automatically detects stale .memory/ files.

**Manual**: After significant changes
```
/memtree_rebuild backend              # Re-analyze a service
/memtree_rebuild routes/trading.py    # Re-analyze one file
```

## Verify Quality

```
/memtree_bootstrap  # includes quality audit at the end
```

Or manually check:
```bash
python3 scripts/validate-memtree.py   # Structure consistency
```

## Next Steps
- Read [Design Principles](design-principles.md) to understand why MemTree is structured this way
- Customize your `memtree.config.yaml` pitfalls section — this is the highest-value activity
- Check the GitHub issues for common questions
