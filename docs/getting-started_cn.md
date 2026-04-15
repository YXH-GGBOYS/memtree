# MemTree 快速上手指南

## 你需要什么
- [Claude Code](https://claude.ai/code)（CLI、桌面端或 IDE 插件）
- Git
- Python 3.9+
- 一个你希望 AI 更好理解的代码库

## 第一步：安装（30 秒）

```bash
git clone https://github.com/YXH-GGBOYS/memtree.git ~/memtree
cd ~/memtree
pip install -r requirements.txt       # PyYAML

# 将 skills 复制到 Claude Code
mkdir -p ~/.claude/skills
cp -r ~/memtree/skills/memtree_* ~/.claude/skills/
```

## 第二步：初始化（5 分钟）

在你的项目目录中打开 Claude Code，运行：

```
/memtree_init
```

MemTree 会询问你的项目信息：
- 有哪些服务/模块
- 代码所在路径
- 数据库信息（可选）
- 已知踩坑（可选，但非常有价值）

这会生成 `memtree.config.yaml`。

**或者自动扫描**（更快，精度稍低）：
```
/memtree_init --auto
```

## 第三步：构建（30 分钟到 2 小时，取决于项目规模）

```
/memtree_bootstrap
```

MemTree 会：
1. 扫描所有源文件，建立依赖关系图
2. 识别共享 "热点文件"（被多处引用），优先分析
3. 并行分析每条代码链
4. 查询数据库获取 schema (表结构) 文档
5. 为每个服务生成 PITFALLS.md（踩坑手册）
6. 构建跨服务引用映射
7. 运行质量审计

完成后，你的项目根目录下会出现一个 `.memory/` 目录。

## 第四步：使用

现在 AI agent 在处理你的代码时，就有了上下文：

```
"修复 credits 余额显示金额不正确的 bug"

AI 读取:
1. .memory/backend/PITFALLS.md → "P001: billing 用 billing.customers.id，IAM 用 iam.accounts.id"
2. .memory/backend/services/billing_service.py.md → TL;DR + 函数签名
3. .memory/db/billing/credits.md → 列定义、ORM 映射不一致

结果：AI 避开了 customer_id 陷阱，一次就修对了。
```

## 第五步：保持更新

**自动（推荐）：** 安装 git hook
```bash
cp ~/memtree/scripts/pre-commit-memtree.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```
每次 commit 会自动检测 `.memory/` 中过期的文件。

**手动：** 大改动后
```
/memtree_rebuild backend              # 重新分析某个服务
/memtree_rebuild routes/checkout.py    # 重新分析单个文件
```

## 验证质量

```
/memtree_bootstrap  # 末尾包含质量审计
```

或者手动检查：
```bash
python3 scripts/validate-memtree.py   # 结构一致性检查
```

## 下一步
- 阅读 [设计原则](design-principles_cn.md) 了解 MemTree 为什么这样设计
- 自定义 `memtree.config.yaml` 的 pitfalls（踩坑）部分 — 这是价值最高的操作
- 查看 GitHub Issues 了解常见问题
