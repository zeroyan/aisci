# 功能规格：AiSci MVP Phase 1B（方案与 Baseline）

**功能分支**: `002-plan-baseline-mvp`
**创建日期**: 2026-02-27
**状态**: 草稿（澄清中）
**输入**: 在全局蓝图下，补齐从 ResearchSpec 到 ExperimentPlan 的自动化能力

## 关联文档

- 全局蓝图：`/specs/000-aisci-epic/spec.md`
- 上一阶段（已完成后依赖）：`/specs/001-research-copilot-mvp/spec.md`
- 下一阶段：`/specs/003-topic-discovery-mvp/spec.md`

## 阶段目标

1. 将 `ResearchSpec` 转为结构化 `ExperimentPlan`（MD 文档）。
2. 搜索并整理相关方法与文献，构建本地知识库，支撑方案生成。
3. 实验结果出来后，人机协同修订方案，形成闭环。

## 架构决策

- **实验执行模型升级**（前置于 002 实现）: 将 001 的 `CodegenAgent` 从"强制 JSON 格式输出"升级为 tool-use 模式——AI 持有 bash 执行、文件读写工具，自主决定实验步骤，不再强制特定输出格式。此升级是 002 方案修订循环（FR-006）的基础，与 002 一起设计实现。

## In Scope

1. 方案生成（方法摘要、评估协议、步骤拆分），输出为 MD 文档。
2. 文献与方法检索（搜索论文、阅读代码仓库，不执行开源代码）。
3. 本地知识库缓存，避免重复检索。
4. 人机协同修订方案（人直接编辑 MD 或口头告知 AI 修改）。

## Out of Scope

1. 多源选题与候选课题生成（Phase 1C）。
2. 论文写作、自动审稿、方法论沉淀（P2）。
3. 执行或部署开源代码以复现 baseline 数值（过于复杂，不在 MVP 范围）。

## 功能需求

> 本地编号 `1B-FR-xxx`，括号内为全局 Epic 编号。

- **1B-FR-001**（E-FR-005）: 系统必须从 `ResearchSpec` 生成结构化 `ExperimentPlan`，输出为 MD 文档，包含方法描述、技术路线、评估指标、步骤拆分。
- **1B-FR-002**（E-FR-006）: 系统必须搜索相关论文、方法和代码仓库（只读不执行），将整理后的内容存入本地知识库，并在方案中引用。
- **1B-FR-003**（E-FR-006 补充）: 检索失败或无相关结果时，不得阻断主流程，必须记录失败原因并继续生成方案。
- **1B-FR-004**（E-FR-007）: 人类可直接编辑 ExperimentPlan MD 文档，或通过自然语言告知 AI 修改，AI 必须根据反馈更新文档。
- **1B-FR-005**: 系统在执行网络检索前，必须先查询本地知识库；命中则直接使用，不再重复检索；未命中则检索后将结果存入本地知识库。知识库分两层：`runs/<run_id>/knowledge/` 存放本次实验专属内容；`scientist/` 存放跨实验全局记忆（方法论、已读论文、baseline 缓存），均为 MD 文件，`scientist/` 路径可配置（可指向 Obsidian vault 中的独立文件夹）。
- **1B-FR-006**: 001 实验运行产出报告后，系统必须支持人机协同修订 ExperimentPlan：AI 基于实验报告提出修订建议，人类在 MD 文档中审阅后确认或调整，AI 更新文档。

## DoD

1. 给定一个 `ResearchSpec`，能产出可执行的 `ExperimentPlan` MD 文档。
2. 本地知识库有内容时，方案生成优先使用本地知识，不重复检索。
3. 实验报告输入后，能产出修订版 ExperimentPlan。
4. 输出结构满足 contracts（后续在本目录补充 `contracts.md`）。

## Clarifications

### Session 2026-03-01

- Q: baseline 验证的执行模型是什么？ → A: 只做搜索+阅读+整理，不执行开源代码。目标是生成更优方案，不是复现 baseline 数值。
- Q: 人机协同修订方案如何交互？ → A: ExperimentPlan 以 MD 文档输出，人类直接编辑或口头告知 AI 修改，MD 是人机对齐的媒介，不限于终端。
- Q: 001 实验循环架构升级（tool-use 模式）放在哪里做？ → A: 作为 002 的前置任务，在 002 的 plan 阶段一起设计，避免做两遍。
- Q: 本地知识库格式与存储位置？ → A: 两层结构：`runs/<run_id>/knowledge/` 存本次实验专属内容；`scientist/` 存跨实验全局记忆（方法论、已读论文、baseline 缓存）。均为 MD 文件。`scientist/` 路径可配置，可指向 Obsidian vault 独立文件夹，不混入个人日记。
