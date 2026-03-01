# FARS MVP 用户故事与验收

**Feature**: FARS Multi-Agent Research MVP  
**Created**: 2026-02-27  
**Status**: Draft

## User Scenarios & Testing

### User Story 1 - 研究题目快速规格化（Priority: P1）

作为科研用户，我希望输入一个研究题目后，系统可以自动生成结构化研究 spec（问题、假设、指标、约束），这样我可以从“想法”快速进入“可执行计划”。

**Why this priority**: 没有规格化输入，后续多 Agent 无法稳定协作，MVP 无法形成闭环。  

**Independent Test**: 仅实现本故事即可交付价值。输入一个题目，输出可审阅的 spec 文档，并可被下一步任务直接消费。

**Acceptance Scenarios**:
1. **Given** 用户提供题目与目标，**When** 执行规划流程，**Then** 输出包含 Question/Hypothesis/Metrics/Constraints 的 `spec.md`。
2. **Given** spec 已生成，**When** 人工检查，**Then** 至少能识别研究范围、成功指标、非目标项三类信息。

---

### User Story 2 - 自动执行可复现实验（Priority: P1）

作为科研用户，我希望系统能基于 spec 自动触发实验执行，并产出标准化结果文件，这样我可以快速判断方向是否值得继续。

**Why this priority**: 实验执行是科研系统的核心价值，没有它只有“写文档助手”。  

**Independent Test**: 仅实现本故事即可产生独立价值。系统可完成一次完整实验并输出结构化结果。

**Acceptance Scenarios**:
1. **Given** 有效实验任务输入，**When** 触发 ExperimentAgent，**Then** 生成 `experiment_result.json` 且包含指标、耗时、状态。
2. **Given** 任务失败，**When** 流程结束，**Then** 保留失败日志与错误摘要，状态标记为 `failed`。

---

### User Story 3 - 自动草拟论文初稿（Priority: P2）

作为科研用户，我希望系统基于实验与文献产出论文草稿，减少机械写作时间，把精力集中在判断研究价值。

**Why this priority**: 对 MVP 非阻断，但能显著提升效率与可展示性。  

**Independent Test**: 仅实现该故事即可输出可读草稿，不依赖评审模块。

**Acceptance Scenarios**:
1. **Given** 存在实验结果与证据表，**When** 执行 WriterAgent，**Then** 输出 `paper_draft.md`，至少包含摘要、方法、结果、局限性。
2. **Given** 结果不完整，**When** 生成草稿，**Then** 对缺失数据明确标注，不伪造结论。

---

### User Story 4 - 自动复核与风险提示（Priority: P2）

作为科研用户，我希望系统能自动指出草稿中的证据缺口和方法风险，帮助我在对外分享前先做内部把关。

**Why this priority**: 防止“看起来像论文但不可验证”的输出进入下一阶段。  

**Independent Test**: 仅实现评审故事即可作为质量门禁插件使用。

**Acceptance Scenarios**:
1. **Given** 一篇草稿，**When** 执行 ReviewerAgent，**Then** 输出 `review_report.md`，包含重大问题、次要问题、建议补实验。
2. **Given** 存在无证据结论，**When** 完成评审，**Then** 报告中必须列出该结论和缺失证据。

## Edge Cases

1. 模型 API 超时或限流时如何处理（重试、降级、终止策略）。
2. 实验依赖缺失或 GPU 不可用时如何回退（失败标记 + 人工接管）。
3. 文献检索为空时如何避免“幻觉引用”。
4. 多 Agent 产物格式不一致时如何自动校验并阻断后续流程。
5. 预算耗尽时如何保证已有结果不丢失并安全退出。

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 接收研究主题并生成结构化 spec。
- **FR-002**: 系统 MUST 支持固定角色编排（Planner/Literature/Experiment/Writer/Reviewer）。
- **FR-003**: 系统 MUST 输出标准化实验结果 JSON（包含指标、耗时、状态、错误信息）。
- **FR-004**: 系统 MUST 为每次运行创建独立目录并保存全部日志和产物。
- **FR-005**: 系统 MUST 在失败时保留输入快照与错误日志。
- **FR-006**: 系统 MUST 支持预算与时限控制，并在超限时中止或降级。
- **FR-007**: 系统 MUST 维护“结论 -> 证据”映射，缺失证据时显式标记。
- **FR-008**: 系统 MUST 生成论文草稿并对未验证内容做不确定性声明。
- **FR-009**: 系统 MUST 生成评审报告并给出可执行修复建议。
- **FR-010**: 系统 MUST 支持人工闸门（发布前必须人工确认）。
- **FR-011**: 系统 MUST 支持重跑同任务并比较关键指标差异。
- **FR-012**: 系统 MUST 记录每次运行的模型信息与配置版本。

### Key Entities

- **ResearchSpec**: 研究规格，包含问题、假设、指标、约束、交付物。  
- **ExperimentTask**: 实验任务输入，包含模板、参数、预算、超时。  
- **ExperimentResult**: 实验输出，包含指标、日志位置、状态、失败原因。  
- **EvidenceItem**: 证据项，来源于文献或实验，带置信度和引用链接。  
- **PaperDraft**: 论文草稿，包含结构化章节和证据引用位。  
- **ReviewReport**: 评审报告，包含问题清单、严重级别、修复建议。  
- **RunSummary**: 运行摘要，包含耗时、花费、成功率、人工介入点。

## Success Criteria

### Measurable Outcomes

- **SC-001**: 70% 以上题目能在 10 分钟内生成可审阅的 `spec.md`。
- **SC-002**: 固定模板实验单次运行成功率 >= 80%（连续 3 次统计）。
- **SC-003**: 每次成功运行都能输出完整的 5 类核心产物。
- **SC-004**: 关键结论证据覆盖率 >= 90%（Reviewer 自动检查）。
- **SC-005**: 单次 MVP 流程成本不超过设定预算上限（默认 20 USD）。
