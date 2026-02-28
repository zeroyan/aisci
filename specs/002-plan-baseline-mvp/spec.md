# 功能规格：AiSci MVP Phase 1B（方案与 Baseline）

**功能分支**: `002-plan-baseline-mvp`
**创建日期**: 2026-02-27
**状态**: 草稿（骨架）
**输入**: 在全局蓝图下，补齐从 ResearchSpec 到 ExperimentPlan 的自动化能力

## 关联文档

- 全局蓝图：`/specs/000-aisci-epic/spec.md`
- 上一阶段（已完成后依赖）：`/specs/001-research-copilot-mvp/spec.md`
- 下一阶段：`/specs/003-topic-discovery-mvp/spec.md`

## 阶段目标

1. 将 `ResearchSpec` 转为结构化 `ExperimentPlan`。
2. 尽可能自动完成 baseline 检索与验证。
3. baseline 成功/失败都结构化落盘，不阻断主流程。

## In Scope

1. 方案生成（方法摘要、评估协议、步骤拆分）。
2. baseline 检索与自动尝试验证。
3. 人类可审阅并修改方案。

## Out of Scope

1. 多源选题与候选课题生成（Phase 1C）。
2. 论文写作、自动审稿、方法论沉淀（P2）。

## 功能需求（骨架）

> 本地编号 `1B-FR-xxx`，括号内为全局 Epic 编号。

- **1B-FR-001**（E-FR-005）: 系统必须从 `ResearchSpec` 生成结构化 `ExperimentPlan`。
- **1B-FR-002**（E-FR-006）: 系统必须尝试检索相关 baseline，并记录验证结果。
- **1B-FR-003**（E-FR-006 补充）: baseline 失败不得阻断主流程，必须记录失败原因。
- **1B-FR-004**（E-FR-007）: 人类修改方案后，系统必须更新 `ExperimentPlan`。

## DoD（骨架）

1. 能给定一个 `ResearchSpec` 产出可执行 `ExperimentPlan`。
2. baseline 至少支持 1 条自动验证路径（成功或失败都可验）。
3. 输出结构满足 contracts（后续在本目录补充 `contracts.md`）。
