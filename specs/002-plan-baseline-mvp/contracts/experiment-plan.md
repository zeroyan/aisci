# Contract: ExperimentPlan MD 文档格式

**版本**: 1.0
**适用**: 002-plan-baseline-mvp

---

## 文件路径

```
runs/<run_id>/plan.md
```

## 格式规范

```markdown
---
plan_id: "plan-<12位hex>"
spec_id: "spec-<id>"
version: <int>
title: "<实验标题>"
created_at: "<ISO8601>"
updated_at: "<ISO8601>"
---

# 实验方案：<title>

## 方法摘要

<method_summary>

## 技术路线

- **框架**: <framework>
- **Baseline 方法**: <baseline_methods, 逗号分隔>
- **关键参考**: <key_references, 每行一个链接>
- **实现要点**: <implementation_notes>

## 评估指标

<evaluation_protocol>

## 实验步骤

### 步骤 1：<title>

**依赖**: <depends_on step_id, 无则省略>
**预估耗时**: <estimated_minutes 分钟, 无则省略>

<description>

### 步骤 2：...

## 修订历史

| 版本 | 时间 | 修订者 | 摘要 |
|------|------|--------|------|
| 1 | <created_at> | ai | 初始生成 |

<!-- PLAN_JSON
{"plan_id":"...","version":1,"steps":[...],"revision_history":[...]}
-->
```

## 约束

1. `<!-- PLAN_JSON ... -->` 注释必须是文件最后一行（程序解析用）。
2. `plan_id` 格式：`plan-` + 12 位小写 hex。
3. `version` 从 1 开始，每次修订 +1。
4. 步骤 `step_id` 格式：`step-<两位数字>`（如 `step-01`）。
5. 人工编辑 MD 正文后，程序必须同步更新 `PLAN_JSON` 注释和 `updated_at`。
