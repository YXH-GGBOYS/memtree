<div align="center">

# MemTree

**为 AI 编程 agent 构建持久化代码记忆，让它不再犯同样的错。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Built%20for-Claude%20Code-blueviolet)](https://claude.ai/code)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)

[English](README.md) | [中文](README_CN.md)

</div>

---

MemTree 扫描你的整个代码库，生成一个 `.memory/` 目录 — 一套持久化的、文件级的知识图谱，AI 编程 agent 在修改代码之前可以先读取它。每个文件都有 TL;DR 摘要、依赖关系图、已知踩坑和约束文档。代码变更时，MemTree 自动更新。

> 在一个 913 文件的交易平台上实测：AI agent 有 MemTree 后 **2 秒**识别出关键的 user_id 映射陷阱，而没有 MemTree 时反复犯同样的错。

## 问题

AI 编程 agent（Claude Code、Cursor、Aider、Copilot）能力很强，但"记性"很差：
- 它不知道 `wallet_balances.user_id` 和 `ledger_accounts.owner_id` 用的是不同的 ID 体系
- 它不知道 `listings.price` 是**美元**，但 `wallet.balance` 是**美分**
- 它修了 `trading.py` 的 bug 却不知道会连锁影响 `rental.py`
- 它会犯你团队 3 个月前就修过的同一个错

**MemTree 通过给 AI agent 提供持久化、结构化的代码记忆来解决这个问题。**

## 工作原理

```
你的代码库 (913 个文件)
        |
  /memtree_init          <-- 交互式问答 或 自动扫描
        |
  /memtree_bootstrap     <-- Coordinator + Workers 分析每个文件
        |
  .memory/               <-- 持久化代码记忆 (提交到你的仓库)
  ├── ROOT.md            <-- "从这里开始" — 服务地图 + 导航
  ├── cross-refs/        <-- 跨服务字段映射 + 踩坑
  ├── backend/
  │   ├── INDEX.md       <-- 目录概览
  │   ├── PITFALLS.md    <-- 本服务已知陷阱 (🔴 致命 / 🟡 警告)
  │   └── routes/
  │       └── trading.py.md  <-- TL;DR + 速查表 + 完整依赖图
  ├── frontend/
  │   └── ...
  └── db/
      └── schema/table.md   <-- 列定义 + ORM 映射不一致标注
```

**有 MemTree 后，AI agent 的工作流程：**
1. 读 `PITFALLS.md` — **写代码之前**先知道有哪些坑
2. 读 `ROOT.md` → `INDEX.md` → `per-file.md` — 3 跳到达完整上下文
3. 修完代码后，MemTree 通过 git hook 自动更新

## 快速开始 (5 分钟)

### 1. 安装

```bash
git clone https://github.com/YXH-GGBOYS/memtree.git
cd memtree
mkdir -p ~/.claude/skills
cp -r skills/memtree_* ~/.claude/skills/

# 设置 MEMTREE_HOME 让 skills 能找到 prompts 和 scripts
echo 'export MEMTREE_HOME=~/memtree' >> ~/.zshrc  # 或 ~/.bashrc
source ~/.zshrc
```

### 2. 初始化

```bash
# 方式 A：交互式 — MemTree 通过问答了解你的项目
/memtree_init

# 方式 B：自动扫描 — MemTree 自动发现代码结构
/memtree_init --auto
```

这会生成 `memtree.config.yaml`，描述你的项目结构。

### 3. 构建

```bash
/memtree_bootstrap
```

MemTree 会：
- 扫描所有源文件，建立依赖关系图
- 识别共享 "热点文件"（被 3+ 个模块引用的文件），优先分析
- 并行 Worker 分析每条代码链
- 查询数据库获取表结构文档
- 为每个服务生成 `PITFALLS.md`（从团队知识 + Worker 发现中提取）
- 运行质量审计（15 个文件抽样验证）
- 产出：`.memory/` 目录，提交到你的仓库

### 4. 配置 CLAUDE.md（重要！）

在项目的 `CLAUDE.md` 中添加 MemTree 规则，确保 Claude Code 每次会话都读取 `.memory/`。
详见 [CLAUDE.md 集成指南](docs/claude-md-integration.md)。

## 你会得到什么

### 每文件记忆 (`.memory/backend/routes/trading.py.md`)

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

**TL;DR**: 交易路由 | 调用 escrow_service + order_events | price=dollars 非 cents

**速查表**:
| 导出 | 签名 | 约束 |
|------|------|------|
| create_order | (session, listing_id, buyer_id) -> Order | flush-only，调用方负责 commit |
| cancel_order | (session, order_id, reason) -> None | 必须同时设 cancelled_at + 写 OrderEvent |

> AI agent：80% 情况下读到这里就够了。

**完整分析**：完整依赖图、兄弟文件、修改风险...

### 服务踩坑手册 (`PITFALLS.md`)

```markdown
## 🔴 致命（会导致数据损坏）

### P001: User ID 双命名空间
- **陷阱**: wallet 用 trading.users.id，但 ledger 用 auth.user_accounts.id
- **影响文件**: services/wallet_service.py, services/ledger_service.py
- **正确做法**: 写 ledger 时用 `trading_user.auth_user_id`
- **来源**: 线上事故 2026-04-05
```

### 跨服务交叉引用 (`cross-refs/`)

```
cross-refs/
├── INDEX.md                 <-- "什么问题？ -> 读哪个文件"
├── orm-db-mismatch.md       <-- ORM 属性名 ≠ DB 列名
├── field-confusion.md       <-- 同名不同义 / 异名同义
├── api-field-mapping.md     <-- 前端字段 -> API -> DB 列
└── service-schema-matrix.md <-- 哪个服务读写哪个 DB schema
```

## 设计原则

| # | 原则 | 实现 |
|---|------|------|
| 1 | **查找** — 确定性路径映射 | 源文件路径 -> `.memory/` 路径是纯函数，不需要搜索 |
| 2 | **阅读** — 3 跳导航 | ROOT -> INDEX -> per-file。80% 只需读 TL;DR + 速查表 |
| 3 | **更新** — 代码变，记忆跟着变 | Git hook 检测变更 -> 自动更新受影响的 `.memory/` 文件 |
| 4 | **踩坑前置** — 写代码前先读坑 | `PITFALLS.md` 是 AI agent 的必读文件 |
| 5 | **校验** — 信任但要核实 | 质量审计抽样 15 个文件，逐项对比源代码验证 |
| 6 | **分层阅读** — TL;DR -> 速查 -> 全量 | AI 可以在任意层停止，不用每次都读完整分析 |
| 7 | **热点优先** — 共享文件只分析一次 | 被 3+ 模块引用的文件先用专用 Worker 分析，链 Worker 引用结果 |

## 保持更新

**自动（推荐）：** 安装 git hook
```bash
cp scripts/pre-commit-memtree.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```
每次 commit 自动检测 `.memory/` 中过期的文件。

**手动：** 大改动后
```bash
/memtree_rebuild routes/trading.py     # 重新分析单个文件
/memtree_rebuild backend               # 重新分析整个服务
/memtree_rebuild db/schema.orders      # 重新分析数据库表
```

## 配置

```yaml
# memtree.config.yaml
project:
  name: "我的项目"
  description: "电商交易平台"

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

# 团队知识（可选但强烈推荐）
pitfalls:
  - "钱包余额单位是 cents（整数），上架价格是 dollars（小数）"
  - "order_events 的 DB 列名是 event_metadata，但 ORM 属性名是 event_data"
  - "服务层 flush-only，调用方负责 commit"
```

## 和其他工具有什么不同？

| 工具 | 做什么 | MemTree 多了什么 |
|------|--------|----------------|
| **typedoc/jsdoc** | 从注释生成 API 文档 | MemTree 记录**关系图**、**踩坑**和**约束** — 不只是签名 |
| **mem0** | 通用 AI 记忆 | MemTree 是**代码专用的**：文件级依赖图、ORM↔DB 映射、服务边界 |
| **aider repo-map** | Token 优化的代码地图 | MemTree 多了**踩坑追踪**、**质量审计**和**自动更新** |
| **RAG / embeddings** | 语义搜索代码 | MemTree 用**确定性路径**（无需搜索）+ **结构化格式**（非自由文本） |

## 项目结构

```
memtree/
├── skills/                  # Claude Code skills
│   ├── memtree_init/        # /memtree_init — 入门（问答 或 自动扫描）
│   ├── memtree_bootstrap/   # /memtree_bootstrap — 构建 .memory/
│   └── memtree_rebuild/     # /memtree_rebuild — 手动刷新
├── prompts/                 # 可复用的 prompt 模板
│   ├── onboarding/          # 访谈 + 自动扫描 prompt
│   ├── build/               # Coordinator + Worker prompt
│   ├── quality/             # 审计 + 验证 prompt
│   └── update/              # 增量更新 prompt
├── scripts/                 # Python/Bash 自动化脚本
├── templates/               # 输出格式模板
├── docs/                    # 详细文档
└── examples/                # 真实项目的脱敏示例输出
```

## 文档

- [快速开始](docs/getting-started.md) — 5 分钟上手
- [设计原则](docs/design-principles.md) — MemTree 为什么这样设计
- [深度补充指南](docs/depth-enrichment.md) — bootstrap 后如何补充深度分析
- [CLAUDE.md 集成](docs/claude-md-integration.md) — 让 Claude Code 每次会话都读 .memory/

## 环境要求

- [Claude Code](https://claude.ai/code)（CLI、桌面端、或 IDE 插件）
- Git（用于自动更新 hook）
- Python 3.9+（用于脚本）
- 数据库访问权限（可选，用于 DB schema 记忆）

## 路线图

- [x] **v1.0** — 核心：构建 + 质量审计 + 手动刷新
- [x] **v1.1** — 自动更新：git hook + 增量刷新
- [ ] **v2.0** — 多 agent 协同：draft / review / approve 工作流
- [ ] **v2.1** — AI 驱动的 bug 报告 -> 自动修复流水线
- [ ] **v3.0** — 跨平台：Cursor、Aider、Copilot 支持

## 贡献

欢迎贡献！请直接开 Issue 或 PR。特别欢迎：
- Prompt 优化（让 Worker 分析更准、幻觉更少）
- 语言/框架支持（Go、Rust、Java、Angular 等）
- 质量审计增强

## 开源协议

MIT
