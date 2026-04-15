# MemTree 设计原则

## 1. 查找 — 确定性路径映射

源文件路径 → `.memory/` 路径是一个**纯函数**。不需要搜索、不需要索引、不需要数据库查找。

```
src/api/routes/checkout.py  →  .memory/backend/routes/checkout.py.md
src/web/pages/market.vue   →  .memory/frontend/pages/market.vue.md
```

映射规则定义在 `memtree.config.yaml` 的 `path_map` 中（从 services 自动生成）。AI agent 永远不需要搜索对应的 `.memory/` 文件 — 直接计算路径即可。

## 2. 阅读 — 3 跳导航

代码库的任何问题都可以在最多 3 次文件读取内找到答案：

1. **ROOT.md** → 确定是哪个服务
2. **{service}/INDEX.md** → 确定是哪个文件
3. **{service}/{path}.md** → 获取答案（TL;DR + 速查表 + 完整分析）

80% 的情况下，TL;DR + 速查表（前 15 行）就足够了。完整分析用于深入研究。

## 3. 更新 — 代码变，记忆跟着变

MemTree 是活文档，不是一次性快照。三种更新机制：

| 机制 | 时机 | 方式 |
|------|------|------|
| Git hook | 每次 commit | `pre-commit-memtree.py` 对比 source_hash，标记过期 |
| 手动 | 大改动后 | `/memtree_rebuild {target}` |
| 全量重建 | 极少 | `/memtree_bootstrap --resume` |

## 4. 踩坑前置 — 写代码前先读坑

MemTree 最有价值的产出是 `PITFALLS.md`。每个服务都有一份。AI agent 在写任何代码之前**必须**先读它。

PITFALLS.md 记录的是：
- 静态分析无法检测的知识（业务逻辑约束）
- 代码注释没有覆盖的内容（跨服务踩坑）
- 新团队成员总是踩的坑（命名不一致、隐含假设）

## 5. 校验 — 信任但要核实

MemTree 的质量审计会抽样 15 个文件，逐项对比实际源代码进行验证。这防止了 "AI 写关于 AI 成果的文档" 导致的质量退化 — 每个函数签名、每个约束、每个依赖关系都与实际代码核实。

评分：
- 15/15 PASS → 可上线
- 10-14 → 修正后复查
- <10 → 修复 Worker prompt (提示词)，重新 bootstrap

## 6. 分层阅读 — TL;DR → 速查表 → 完整分析

不是每个问题都需要深入研究。每个文件的文档按层级组织：

```
Frontmatter (头部元数据, 8 行)     ← 机器可解析的元数据
TL;DR (1 行)                       ← "这个文件做什么 + 关键约束"
Quick Ref (速查表, 5-10 行)        ← 函数签名 + 约束表格
Full Analysis (完整分析, 50+ 行)   ← 完整依赖图、兄弟文件、风险
```

AI agent 可以在任意一层停止阅读。大多数 bug 修复只需要 TL;DR + 速查表。

## 7. 热点优先 — 为依赖 DAG 优化

代码依赖关系是 DAG（有向无环图），不是树。像 `database.py` 或 `models/user.py` 这样的文件被几十个其他文件引用。

MemTree 用专用的 Shared Worker 优先分析这些 "热点文件"。Chain Worker（链式分析器）随后引用已有的分析结果，而不是重复分析同一个文件 20 次。

效果：分析时间和 token 消耗减少约 35%。
