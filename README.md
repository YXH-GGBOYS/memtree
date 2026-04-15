<div align="center">

# MemTree

**Build structured code memory so AI agents stop making the same mistakes twice.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Built%20for-Claude%20Code-blueviolet)](https://claude.ai/code)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)

[English](README.md) | [中文](README_CN.md)

</div>

MemTree scans your entire codebase and generates a `.memory/` directory — a persistent, file-level knowledge graph that AI coding agents can read before touching your code. Every file gets a TL;DR, dependency map, known pitfalls, and constraint documentation. When code changes, MemTree updates automatically.

> Tested on a 900-file SaaS platform: AI agent identified a critical user_id mapping pitfall in **2 seconds** with MemTree, vs. repeatedly making the same mistake without it.

## The Problem

AI coding agents (Claude Code, Cursor, Aider, Copilot) are powerful but forgetful:
- They don't know that `billing.customers.id` uses a different ID space than `iam.accounts.id`
- They don't know that `plans.price` is in **major units** but `billing.credits` is in **minor units**
- They fix a bug in `checkout.py` without realizing it breaks `subscription.py` downstream
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
  ├── HEALTH.md          ← Auto-generated system health snapshot
  ├── events/            ← Event Layer — structured change history
  │   ├── INDEX.md       ← Searchable event index
  │   ├── TEMPLATE.md    ← Event file template
  │   └── 2026-04/       ← Events by month
  ├── cross-refs/        ← Cross-service field mappings + gotchas
  ├── backend/
  │   ├── INDEX.md       ← Directory overview
  │   ├── PITFALLS.md    ← Known pitfalls with lifecycle (ACTIVE/RESOLVED)
  │   └── routes/
  │       └── checkout.py.md  ← TL;DR + Quick Ref + Full dependency graph
  ├── frontend/
  │   └── ...
  └── db/
      └── schema/table.md   ← Column definitions + ORM mapping mismatches
```

**AI agent workflow with MemTree:**
1. Read `HEALTH.md` — 10-second overview of hotspots, change coupling, stale pitfalls
2. Read `PITFALLS.md` — know the traps **before** writing code
3. Read `ROOT.md` → `INDEX.md` → `per-file.md` — 3 hops to full context
4. Search `events/INDEX.md` — find similar past bugs and their root causes
5. After fixing, MemTree auto-updates via git hooks
6. Write an event if the fix has diagnostic value

## Quick Start (5 minutes)

### 1. Install

```bash
git clone https://github.com/YXH-GGBOYS/memtree.git ~/memtree
cd ~/memtree
pip install -r requirements.txt      # PyYAML
mkdir -p ~/.claude/skills
cp -r skills/memtree_* ~/.claude/skills/
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

### 4. Configure CLAUDE.md (Important!)

Add MemTree rules to your project's `CLAUDE.md` so Claude Code reads `.memory/` in every session.
See [CLAUDE.md Integration Guide](docs/claude-md-integration.md).

## What You Get

### Per-File Memory (`.memory/backend/routes/checkout.py.md`)

```yaml
---
source: src/backend/routes/checkout.py
service: backend
layer: router
source_hash: a1b2c3d4
depends_on: [services/payment.py, models/subscription.py]
depended_by: [../frontend/pages/pricing.vue]
---
```

**TL;DR**: Checkout router | calls payment_service + audit_log | price=major units not minor

**Quick Ref**:
| Export | Signature | Constraint |
|--------|-----------|------------|
| create_subscription | (session, plan_id, account_id) → Subscription | flush-only, caller commits |
| cancel_subscription | (session, subscription_id, reason) → None | must set cancelled_at + write AuditLog |

> 80% of the time, the AI only needs to read up to here.

**Full Analysis**: complete dependency graph, sibling files, modification risks...

### Service Pitfalls (`PITFALLS.md`)

```markdown
## 🔴 Critical (will cause data corruption)

### P001: User ID dual namespace
- **Trap**: billing uses billing.customers.id, but IAM uses iam.accounts.id
- **Affected**: services/billing.py, services/iam.py
- **Correct**: Use `customer.iam_account_id` when writing to IAM
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

## Event Layer

Track **why** code changes happen, not just what changed. Events bridge the gap between git history (the diff) and institutional knowledge (the context).

```bash
# Create events directory
mkdir -p .memory/events/2026-04
cp templates/event.md.template .memory/events/TEMPLATE.md
```

**When to write an event:**
- Fixed a bug with diagnostic value (root cause analysis worth preserving)
- Shipped a new feature
- Deployment incident
- Architecture decision

**Event format** (`EVT-YYYYMMDD-NNN-slug.md`):
```yaml
---
id: EVT-20260408-001
date: 2026-04-08
type: bugfix                    # bugfix | feature | refactor | deploy | incident
severity: high
services: [backend, frontend]
pitfalls_created: [backend/P012]
pitfalls_validated: [backend/P003]
outcome: deployed
---
## Symptoms ...
## Root Cause ...
## Fix ...
## Lessons ...
```

**How to use events:**
- Before fixing a bug → search `events/INDEX.md` for similar past issues
- When writing PITFALLs → link to the event that discovered them
- In `HEALTH.md` → aggregate event statistics

## HEALTH.md — System Health Snapshot

Auto-generated overview of your codebase's current state:

```bash
python3 .memory/scripts/generate-health.py
```

**Output includes:**
- **Change Hotspots**: files changed most in the last 14 days
- **Change Coupling**: files that frequently change together across services
- **PITFALL Stats**: active/resolved counts by type, stale warnings
- **Event Stats**: recent bugfix/feature/incident counts

Read `HEALTH.md` at the start of every session to get a 10-second overview.

## PITFALL Lifecycle

PITFALLs now have status, type, and temporal awareness:

```
ACTIVE (discovered) → validated by events → RESOLVED (fixed)
                    → 30 days no validation → ⚠️ STALE (HEALTH.md warns)
```

**Types:**
| Type | Meaning | Expires? |
|------|---------|----------|
| `architecture` | Inherent to system design | No (unless major refactor) |
| `bug-derived` | Learned from a specific bug | 30 days without validation → STALE |
| `config` | Related to deployment/config | Same as bug-derived |

See `templates/pitfalls.md.template` for the full format.

## Design Principles

| # | Principle | Implementation |
|---|-----------|----------------|
| 1 | **Find** — deterministic path mapping | Source path → `.memory/` path is a pure function. No search needed. |
| 2 | **Read** — 3-hop navigation | ROOT → INDEX → per-file. 80% answered by TL;DR + Quick Ref. |
| 3 | **Update** — code changes, memory follows | Git hooks detect changes → auto-update affected `.memory/` files. |
| 4 | **Pitfalls first** — read traps before coding | `PITFALLS.md` is mandatory reading. AI must read it before writing any code. |
| 5 | **Verify** — trust but check | Quality audit samples 15 files and verifies against source code. |
| 6 | **Layered reading** — TL;DR -> Quick Ref -> Full | 80% answered by TL;DR + Quick Ref. AI can stop at any layer. |
| 7 | **Shared files first** — hot files analyzed once | Files imported by 3+ chains analyzed by dedicated Worker. ~35% token savings. |

## Keeping It Fresh

MemTree stays in sync with your code through two mechanisms:

**Auto-update (git hook):**
Every commit triggers `pre-commit-memtree.py` which compares `source_hash` in frontmatter with the actual file hash. Changed files are marked stale and refreshed.

**Manual rebuild:**
```bash
/memtree_rebuild routes/checkout.py     # Re-analyze one file
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
  schemas: [public, iam, billing]

exclude:
  - node_modules
  - __pycache__
  - "*.test.*"

# Team knowledge (optional but powerful)
pitfalls:
  - "billing credits are in minor units (cents), plan price is in major units (dollars)"
  - "audit_logs DB column is log_metadata, but ORM attribute is log_data"
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
│   ├── generate-health.py   # HEALTH.md generator
│   ├── quality-eval.py      # Quality evaluator (deterministic + model-based)
│   ├── validate-memtree.py  # Hash consistency checker
│   ├── incremental-update.py # Process pending updates
│   └── ...                  # Hooks, skeleton generation, etc.
├── templates/               # Output format templates
│   ├── event.md.template    # Event file format
│   ├── pitfalls.md.template # PITFALL format (with lifecycle)
│   └── per-file.md.template # Per-file analysis format
├── docs/                    # Detailed documentation
└── examples/                # Sample output from a real project
```

## Documentation

- [Getting Started](docs/getting-started.md) — 5-minute setup guide
- [Design Principles](docs/design-principles.md) — Why MemTree is built this way
- [Depth Enrichment](docs/depth-enrichment.md) — How to add deep analysis after bootstrap
- [CLAUDE.md Integration](docs/claude-md-integration.md) — Make Claude Code read .memory/ every session

## Requirements

- [Claude Code](https://claude.ai/code) (CLI, Desktop, or IDE extension)
- Git (for auto-update hooks)
- Python 3.9+ (for scripts)
- Database access (optional, for DB schema memory)

## Roadmap

- [x] **v1.0** — Core: bootstrap + quality audit + manual rebuild
- [x] **v1.1** — Auto-update: git hooks + incremental refresh
- [x] **v1.2** — Event Layer + HEALTH.md + PITFALL lifecycle + quality eval
- [ ] **v2.0** — Cross-platform: Cursor, Aider, Copilot support

## Contributing

We welcome contributions! Open an issue or PR. We especially welcome:
- Prompt improvements (better Worker analysis, fewer hallucinations)
- Language/framework support (Go, Rust, Java, Angular, etc.)
- Quality audit enhancements

## License

MIT
