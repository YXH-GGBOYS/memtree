<div align="center">

# MemTree

**Build structured code memory so AI agents stop making the same mistakes twice.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Built%20for-Claude%20Code-blueviolet)](https://claude.ai/code)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)

[English](README.md) | [中文](README_CN.md)

</div>

MemTree scans your entire codebase and generates a `.memory/` directory — a persistent, file-level knowledge graph that AI coding agents can read before touching your code. Every file gets a TL;DR, dependency map, known pitfalls, and constraint documentation. When code changes, MemTree updates automatically.

> Tested on a 913-file trading platform: AI agent identified a critical user_id mapping pitfall in **2 seconds** with MemTree, vs. repeatedly making the same mistake without it.

## The Problem

AI coding agents (Claude Code, Cursor, Aider, Copilot) are powerful but forgetful:
- They don't know that `wallet_balances.user_id` uses a different ID space than `ledger_accounts.owner_id`
- They don't know that `listings.price` is in **dollars** but `wallet.balance` is in **cents**
- They fix a bug in `trading.py` without realizing it breaks `rental.py` downstream
- They make the same mistake your team fixed 3 months ago

**MemTree solves this by giving AI agents persistent, structured code memory.**

## How It Works

```
Your Codebase (913 files)
        ↓
  /memtree_init          ← Interactive Q&A or auto-scan
        ↓
  /memtree_bootstrap     ← Coordinator + Workers analyze every file
        ↓
  .memory/               ← Persistent code memory (lives in your repo)
  ├── ROOT.md            ← "Start here" — service map + navigation
  ├── cross-refs/        ← Cross-service field mappings + gotchas
  ├── backend/
  │   ├── INDEX.md       ← Directory overview
  │   ├── PITFALLS.md    ← Known pitfalls for this service (🔴 critical / 🟡 warning)
  │   └── routes/
  │       └── trading.py.md  ← TL;DR + Quick Ref + Full dependency graph
  ├── frontend/
  │   └── ...
  └── db/
      └── schema/table.md   ← Column definitions + ORM mapping mismatches
```

**AI agent workflow with MemTree:**
1. Read `PITFALLS.md` — know the traps **before** writing code
2. Read `ROOT.md` → `INDEX.md` → `per-file.md` — 3 hops to full context
3. After fixing, MemTree auto-updates via git hooks

## Quick Start (5 minutes)

### 1. Install

```bash
# Copy skills to Claude Code
cp -r skills/memtree_* ~/.claude/skills/

# Or just clone and reference
git clone https://github.com/YXH-GGBOYS/memtree.git
```

### 2. Initialize

```bash
# Option A: Interactive — MemTree asks about your project
/memtree_init

# Option B: Auto-scan — MemTree discovers your codebase structure
/memtree_init --auto
```

This generates `memtree.config.yaml` with your project structure.

### 3. Build

```bash
/memtree_bootstrap
```

MemTree will:
- Scan your codebase and identify code chains (import/dependency graph)
- Analyze shared "hot files" first (files imported by 3+ others)
- Spawn parallel workers to analyze each chain
- Generate `PITFALLS.md` per service from your team's known gotchas
- Run quality audit (15-file sample verification)
- Output: `.memory/` directory committed to your repo

## What You Get

### Per-File Memory (`.memory/backend/routes/trading.py.md`)

```yaml
---
source: src/backend/routes/trading.py
service: backend
layer: router
source_hash: a1b2c3d4
depends_on: [services/escrow.py, models/order.py]
depended_by: [../frontend/pages/market.vue]
---
```

**TL;DR**: Trade router | calls escrow_service + order_events | price=dollars not cents

**Quick Ref**:
| Export | Signature | Constraint |
|--------|-----------|------------|
| create_order | (session, listing_id, buyer_id) → Order | flush-only, caller commits |
| cancel_order | (session, order_id, reason) → None | must set cancelled_at + write OrderEvent |

> 80% of the time, the AI only needs to read up to here.

**Full Analysis**: complete dependency graph, sibling files, modification risks...

### Service Pitfalls (`PITFALLS.md`)

```markdown
## 🔴 Critical (will cause data corruption)

### P001: User ID dual namespace
- **Trap**: wallet uses trading.users.id, but ledger uses auth.user_accounts.id
- **Affected**: services/wallet.py, services/ledger.py
- **Correct**: Use `trading_user.auth_user_id` when writing to ledger
- **Source**: Production incident, 2026-04-05
```

### Cross-Service References (`cross-refs/`)

```
cross-refs/
├── INDEX.md                 ← "What problem? → Read which file"
├── orm-db-mismatch.md       ← ORM attribute ≠ DB column name
├── field-confusion.md       ← Same name, different meaning across services
├── api-field-mapping.md     ← Frontend field → API → DB column
└── service-schema-matrix.md ← Which service reads/writes which DB schema
```

## Design Principles

| # | Principle | Implementation |
|---|-----------|----------------|
| 1 | **Find** — deterministic path mapping | Source path → `.memory/` path is a pure function. No search needed. |
| 2 | **Read** — 3-hop navigation | ROOT → INDEX → per-file. 80% answered by TL;DR + Quick Ref. |
| 3 | **Update** — code changes, memory follows | Git hooks detect changes → auto-update affected `.memory/` files. |
| 4 | **Pitfalls first** — read traps before coding | `PITFALLS.md` is mandatory reading. AI must read it before writing any code. |
| 5 | **Verify** — trust but check | Quality audit samples 15 files and verifies against source code. |

## Keeping It Fresh

MemTree stays in sync with your code through two mechanisms:

**Auto-update (git hook):**
Every commit triggers `pre-commit-memtree.py` which compares `source_hash` in frontmatter with the actual file hash. Changed files are marked stale and refreshed.

**Manual rebuild:**
```bash
/memtree_rebuild routes/trading.py     # Re-analyze one file
/memtree_rebuild backend               # Re-analyze entire service
/memtree_rebuild db/schema.orders      # Re-analyze DB table
```

## Configuration

```yaml
# memtree.config.yaml
project:
  name: "My Project"
  description: "E-commerce platform"

services:
  - name: backend
    path: src/api/
    lang: python
    framework: fastapi
    entry_pattern: "routes/*.py"
  - name: frontend
    path: src/web/
    lang: typescript
    framework: nuxt
    entry_pattern: "pages/**/*.vue"

database:
  type: postgresql
  access: "docker exec mydb psql -U user -d mydb"
  schemas: [public, auth, trading]

exclude:
  - node_modules
  - __pycache__
  - "*.test.*"

# Team knowledge (optional but powerful)
pitfalls:
  - "wallet balance is in cents, listing price is in dollars"
  - "order_events DB column is event_metadata, but ORM attribute is event_data"
  - "services use flush-only pattern, caller is responsible for commit"
```

## How Is This Different?

| Tool | What it does | What MemTree adds |
|------|-------------|-------------------|
| **typedoc/jsdoc** | Generate API docs from comments | MemTree captures **relationships**, **pitfalls**, and **constraints** — not just signatures |
| **mem0** | General-purpose AI memory | MemTree is **code-specific**: file-level dependency graphs, ORM↔DB mapping, service boundaries |
| **aider repo-map** | Token-efficient code map | MemTree adds **pitfall tracking**, **quality auditing**, and **auto-updates** |
| **RAG / embeddings** | Semantic search over code | MemTree uses **deterministic paths** (no search needed) + **structured format** (not freeform chunks) |

## Project Structure

```
memtree/
├── skills/                  # Claude Code skills
│   ├── memtree_init/        # /memtree_init — onboarding (Q&A or auto-scan)
│   ├── memtree_bootstrap/   # /memtree_bootstrap — build .memory/
│   └── memtree_rebuild/     # /memtree_rebuild — manual refresh
├── prompts/                 # Reusable prompt templates
│   ├── onboarding/          # Interview + auto-scan prompts
│   ├── build/               # Coordinator + Worker prompts
│   ├── quality/             # Audit + validation prompts
│   └── update/              # Incremental update prompts
├── scripts/                 # Python/Bash automation
├── templates/               # Output format templates
├── docs/                    # Detailed documentation
└── examples/                # Sample output from a real project
```

## Requirements

- [Claude Code](https://claude.ai/code) (CLI, Desktop, or IDE extension)
- Git (for auto-update hooks)
- Python 3.9+ (for scripts)
- Database access (optional, for DB schema memory)

## Roadmap

- [x] **v1.0** — Core: bootstrap + quality audit + manual rebuild
- [x] **v1.1** — Auto-update: git hooks + incremental refresh
- [ ] **v2.0** — Multi-agent collaboration: draft/review/approve workflow
- [ ] **v2.1** — AI-driven bug report → auto-fix pipeline
- [ ] **v3.0** — Cross-platform: Cursor, Aider, Copilot support

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md). We especially welcome:
- Prompt improvements (better Worker analysis, fewer hallucinations)
- Language/framework support (Go, Rust, Java, Angular, etc.)
- Quality audit enhancements

## License

MIT
