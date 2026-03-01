# Spec002 使用指南

## 功能概览

Spec002 (plan-baseline-mvp) 在 001 的基础上新增了**方案生成**和**知识库检索**功能，实现完整的研究工作流。

## 新增 CLI 命令

### 1. 生成实验方案

```bash
# 从 ResearchSpec 生成实验方案
python cli.py plan generate tests/fixtures/sample_research_spec.json

# 指定输出路径
python cli.py plan generate tests/fixtures/sample_research_spec.json --out my_plan.md

# 指定 run_id 用于知识库查找
python cli.py plan generate tests/fixtures/sample_research_spec.json --run-id run_001
```

**输出**：
- 默认路径：`runs/<plan_id>/plan.md`
- 格式：Markdown 文件，包含 YAML front-matter 和 PLAN_JSON 注释

### 2. 查看方案

```bash
# 显示方案详情
python cli.py plan show run_001
```

**输出示例**：
```
============================================================
Plan: Contrastive Learning Experiment
============================================================

Plan ID: plan-abc123
Spec ID: spec-001
Version: 1
Created: 2026-03-01 10:00
Updated: 2026-03-01 10:00

Method Summary:
Implement contrastive learning baseline using SimCLR...

Framework: PyTorch
Baselines: SimCLR, MoCo

Steps: 3
  1. Setup environment...
  2. Implement model...
  3. Run training...

Full plan: runs/run_001/plan.md
```

### 3. 修订方案

```bash
# 生成修订建议（追加到 plan.md）
python cli.py plan revise run_001

# 应用修订并递增版本号
python cli.py plan revise run_001 --apply

# 指定报告路径
python cli.py plan revise run_001 --report path/to/report.md
```

**工作流**：
1. 运行实验后，使用 `plan revise` 生成建议
2. 人工审阅 `plan.md` 中的修订建议
3. 手动编辑方案（可选）
4. 使用 `plan revise --apply` 递增版本号

## 完整工作流示例

### 场景：从零开始的研究项目

```bash
# 1. 准备 ResearchSpec（JSON 文件）
cat > my_spec.json <<EOF
{
  "spec_id": "exp-001",
  "title": "对比学习实验",
  "objective": "实现并评估对比学习基线",
  "metrics": [
    {"name": "accuracy", "direction": "maximize", "target": 0.9}
  ],
  "constraints": {
    "max_budget_usd": 10.0,
    "max_runtime_hours": 2.0,
    "max_iterations": 5
  },
  "status": "confirmed"
}
EOF

# 2. 生成实验方案
python cli.py plan generate my_spec.json --run-id run_001
# 输出: runs/run_001/plan.md

# 3. 查看方案
python cli.py plan show run_001

# 4. 创建实验 run（使用生成的方案）
python cli.py run create --spec my_spec.json --plan runs/run_001/plan.md

# 5. 启动实验
python cli.py run start run_001

# 6. 实验完成后，生成修订建议
python cli.py plan revise run_001

# 7. 审阅建议，手动编辑 plan.md（可选）

# 8. 应用修订，递增版本
python cli.py plan revise run_001 --apply

# 9. 使用新版本方案创建新 run
python cli.py run create --spec my_spec.json --plan runs/run_001/plan.md
```

## 方案文件格式

生成的 `plan.md` 文件结构：

```markdown
---
plan_id: plan-abc123
spec_id: spec-001
version: 1
title: 实验方案标题
created_at: 2026-03-01T10:00:00
updated_at: 2026-03-01T10:00:00
---

# 实验方案：标题

## 方法摘要

简要描述实验方法...

## 技术路线

- **框架**: PyTorch
- **Baseline 方法**: SimCLR, MoCo
- **关键参考**:
  - Chen et al. 2020

## 评估指标

描述如何评估实验结果...

## 实验步骤

### 步骤 1：环境搭建

详细描述...

### 步骤 2：模型实现

详细描述...

## 修订历史

| 版本 | 时间 | 修订者 | 摘要 |
|------|------|--------|------|
| 2 | 2026-03-02 | ai | 增加批次大小 |

<!-- PLAN_JSON
{完整的 JSON 数据}
-->
```

## 知识库功能

方案生成时会自动：
1. 从标题和目标中提取关键词
2. 搜索本地知识库（`scientist/` 和 `runs/<run_id>/knowledge/`）
3. 未命中时通过 Tavily/DuckDuckGo 检索
4. 将相关知识注入 LLM prompt

配置（`configs/default.yaml`）：
```yaml
knowledge:
  scientist_dir: scientist
  search_backend: tavily  # 或 duckduckgo
  max_results_per_query: 5
```

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 只运行方案相关测试
python -m pytest tests/unit/test_plan_agent.py tests/unit/test_revision_agent.py -v
```

## 下一步

- 使用真实 API key 测试完整流程
- 根据实际使用调整 prompt
- 扩展知识库检索源（arxiv, semanticscholar 等）
