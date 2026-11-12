# 深度补充指南

## 为什么 Bootstrap 不会深度分析每个文件

`/memtree_bootstrap` 会为所有文件生成 **TL;DR + 骨架**（覆盖率约 100%），但只**深度分析**最关键的文件（约 5-10%）。这是刻意为之：

- 一个 900 文件的项目如果全部深度分析，需要约 50 个并行 Worker 运行数小时
- 80% 的 bug 修复只涉及 20% 的文件（帕累托法则）
- 骨架 + TL;DR 已经能为大部分任务提供足够的上下文
- 深度分析是增量式的 — 在你需要的地方逐步添加

## "骨架" 与 "深度分析" 的区别

### 骨架（bootstrap 对大部分文件的默认输出）

```markdown
## TL;DR
Checkout router | calls payment_service | flush-only

## Quick Ref
(空或从函数名自动生成)
```

### 深度分析（rebuild 后的输出）

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
|... (完整依赖图) ...|
```

## 如何添加深度分析

### 方式 1：重建单个文件

```bash
/memtree_rebuild routes/checkout.py
```

MemTree 会：
- 读取源文件
- 提取所有函数签名、导入、约束
- 生成完整的 Quick Ref (速查表) + Full Analysis (完整分析)
- 更新 depends_on / depended_by（依赖关系）

### 方式 2：重建整个服务

```bash
/memtree_rebuild backend
```

这会深度分析该服务下的每个文件。耗时约 10-30 分钟，取决于文件数量。

### 方式 3：重建数据库表

```bash
/memtree_rebuild db/billing.subscriptions
```

查询数据库获取列定义、约束、外键，并与 ORM 模型交叉对照。

## 推荐的补充策略

### Bootstrap 刚完成时

1. 查看质量审计报告 — 哪些文件 PASS/FAIL？
2. 优先重建 FAIL 的文件：
   ```
   /memtree_rebuild routes/checkout.py
   /memtree_rebuild services/payment_service.py
   ```

### 按 Bug 频率优先

用 git log 找出改动最频繁的文件 — 它们是 AI 最常接触的：

```bash
# 最近 3 个月改动最多的 20 个文件
git log --since="3 months ago" --name-only --pretty=format: | sort | uniq -c | sort -rn | head -20
```

优先重建这些文件：
```
/memtree_rebuild <file1>
/memtree_rebuild <file2>
...
```

### 按服务重要性优先

以 SaaS 平台为例：
1. **最先**：计费/credits/payment 服务（涉及资金，最关键）
2. **其次**：订阅/结账/开票流程（核心业务）
3. **再次**：管理后台/仪表盘页面（风险较低）
4. **最后**：静态页面、配置、工具类（很少出 bug）

```
/memtree_rebuild billing_service      # 资金相关优先
/memtree_rebuild backend             # 然后核心后端
/memtree_rebuild frontend            # 然后前端
```

### 日常：按需重建

当你即将修改某个文件，发现它的 `.memory/` 文档很薄时：

```
/memtree_rebuild routes/subscription.py    # 动手前先补充深度分析
```

单个文件约 30 秒即可完成，能立即提升 AI 的上下文质量。

## 如何检查深度覆盖率

查看任意 `.memory/` 文件。如果只有一行 TL;DR 且 Quick Ref 为空 → 还是骨架状态。如果 Quick Ref 有完整的签名表格 → 已经深度分析过。

快速统计某个服务的覆盖情况：
```bash
# 统计 Quick Ref 为空的文件（仅骨架）
grep -rL "| Export | Signature" .memory/backend/ | wc -l

# 统计有完整 Quick Ref 的文件（已深度分析）
grep -rl "| Export | Signature" .memory/backend/ | wc -l
```

## 常见问题

**问：rebuild 会覆盖我手动编辑的 .memory/ 文件吗？**
答：会。如果你手动编辑过某个 `.memory/` 文件，rebuild 会从源代码重新生成。手动补充的知识请写到 PITFALLS.md — 它在 rebuild 时会被保留。

**问：整个服务的 rebuild 需要多久？**
答：每 10 个文件约 1-2 分钟。一个 100 文件的服务大约需要 10-20 分钟。

**问：每次改代码都需要 rebuild 吗？**
答：不需要。git hook 会自动检测过期文件。rebuild 是用来获取更深度的分析，而不仅仅是修复过期问题。
