# Tasks: AiSci MVP Phase 1B（方案与 Baseline）

**Input**: `/specs/002-plan-baseline-mvp/`
**Prerequisites**: plan.md ✅ spec.md ✅ data-model.md ✅ research.md ✅ contracts/ ✅

**Organization**: 按 4 个 Phase 组织，Phase 0 为前置升级，Phase 1-3 对应 spec.md 功能需求。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件，无未完成依赖）
- **[US1]**: 知识库检索（1B-FR-002/003/005）
- **[US2]**: 方案生成（1B-FR-001）
- **[US3]**: 方案修订循环（1B-FR-004/006）

---

## Phase 1: Setup（前置升级 — Tool-Use Agent）

**Purpose**: 将 001 的 CodegenAgent 升级为 tool-use 模式，是后续所有功能的基础

**⚠️ CRITICAL**: 此 Phase 完成前不得开始 US1/US2/US3

- [ ] T001 新增 tool-use schema：`ToolCall`, `ToolResult`, `ToolTurn`, `FinishResult`, `ToolIterationRecord` 至 `src/schemas/tool_use.py`
- [ ] T002 在 `src/schemas/sandbox_io.py` 中为 `CodeSnapshot`、`AgentDecision` 添加 `# Deprecated` 注释
- [ ] T003 实现 `ToolDispatcher`（包装 `SubprocessSandbox`，路由 write_file/run_bash/read_file/finish）至 `src/agents/experiment/tool_dispatcher.py`
- [ ] T004 实现 `ToolAgent`（litellm tools 参数循环调用直到 finish 或 max_turns）至 `src/agents/experiment/tool_agent.py`
- [ ] T005 更新 `src/agents/experiment/loop.py`：替换 `CodegenAgent`+`AnalyzerAgent` 为 `ToolAgent`，输出 `ToolIterationRecord`
- [ ] T006 更新 `tests/` 中涉及 `CodegenAgent`、`AnalyzerAgent`、`IterationRecord` 的测试，新增 `ToolAgent` 单元测试（mock LLM + mock sandbox）至 `tests/unit/test_tool_agent.py`

**Checkpoint**: `pytest tests/` 全部通过，ExperimentLoop 可用 ToolAgent 跑通

---

## Phase 2: User Story 1 — 知识库检索（1B-FR-002/003/005）

**Goal**: 给定关键词，系统先查本地知识库，未命中则网络检索，结果存入 MD 文件；检索失败不阻断主流程

**Independent Test**: 手动调用 `KnowledgeStore.search(["contrastive learning"], spec_id="test")` → 返回结果列表，`scientist/` 目录下生成 MD 文件；再次调用同关键词 → 直接命中缓存，不发起网络请求

- [ ] T007 [P] [US1] 新增 `KnowledgeEntryMeta`、`KnowledgeEntry` schema 至 `src/schemas/knowledge.py`
- [ ] T008 [P] [US1] 扩展 `configs/default.yaml`：新增 `knowledge:` 节（`scientist_dir`, `search_backend`, `max_results_per_query`）
- [ ] T009 [US1] 实现 `KnowledgeStore`（两层查找 + 去重写入，依赖 `python-frontmatter`）至 `src/knowledge/store.py`
- [ ] T010 [US1] 实现 `Searcher`（Tavily 主 + duckduckgo fallback + arxiv + semanticscholar + trafilatura 提取）至 `src/knowledge/searcher.py`
- [ ] T011 [US1] 在 `src/knowledge/__init__.py` 中导出 `KnowledgeStore`、`Searcher`
- [ ] T012 [US1] 新增知识库单元测试（mock Tavily/arxiv，验证 cache-first 逻辑，验证 fetch_failed 不重复检索）至 `tests/unit/test_knowledge_store.py`

**Checkpoint**: `pytest tests/unit/test_knowledge_store.py` 通过，cache-first 逻辑验证完毕

---

## Phase 3: User Story 2 — 方案生成（1B-FR-001）

**Goal**: 给定 `ResearchSpec`，系统调用知识库 + LLM 生成结构化 `ExperimentPlan`，输出为符合 contract 的 MD 文档

**Independent Test**: `plan generate <spec_id>` → `runs/<run_id>/plan.md` 生成，包含 YAML front-matter + 技术路线 + 步骤 + `PLAN_JSON` 注释；`from_markdown` 解析后字段完整

- [ ] T013 [P] [US2] 扩展 `src/schemas/research_spec.py`：新增 `TechnicalApproach`、`RevisionEntry`，扩展 `PlanStep`（`depends_on`, `estimated_minutes`）和 `ExperimentPlan`（`version`, `updated_at`, `revision_history`, `technical_approach`）
- [ ] T014 [P] [US2] 实现 `PlanSerializer`（`to_markdown` / `from_markdown`，符合 `contracts/experiment-plan.md` 格式）至 `src/schemas/plan_serializer.py`
- [ ] T015 [US2] 新增 `src/agents/plan/__init__.py`，实现 `PlanAgent`（输入 ResearchSpec + KnowledgeStore，输出 ExperimentPlan MD）至 `src/agents/plan/plan_agent.py`
- [ ] T016 [US2] 在 `cli.py` 中新增 `plan generate <spec_id>` 命令
- [ ] T017 [US2] 新增方案生成单元测试（mock LLM，验证 MD 格式符合 contract，验证知识库内容注入 prompt）至 `tests/unit/test_plan_agent.py`

**Checkpoint**: `plan generate` 命令可跑通，`runs/<run_id>/plan.md` 格式正确

---

## Phase 4: User Story 3 — 方案修订循环（1B-FR-004/006）

**Goal**: 实验报告产出后，AI 提出修订建议，人类在 MD 中审阅确认，AI 更新文档并递增版本号

**Independent Test**: `plan revise <run_id>` → plan.md 追加 `## 修订建议` 节；人工确认后再次调用 → `version +1`，`revision_history` 新增一条，`PLAN_JSON` 同步更新

- [ ] T018 [US3] 实现 `RevisionAgent`（输入 ExperimentPlan + report.md，输出修订建议追加至 plan.md）至 `src/agents/plan/revision_agent.py`
- [ ] T019 [US3] 在 `cli.py` 中新增 `plan revise <run_id>`、`plan show <run_id>` 命令
- [ ] T020 [US3] 新增修订循环单元测试（验证 version 递增、revision_history 追加、from_markdown 解析人工编辑后的 MD）至 `tests/unit/test_revision_agent.py`

**Checkpoint**: 完整闭环可跑通：ResearchSpec → plan.md → 实验报告 → 修订版 plan.md

---

## Phase 5: Polish

- [ ] T021 [P] 更新 `requirements.txt`：新增 tavily-python, duckduckgo-search, arxiv, semanticscholar, trafilatura, httpx, python-frontmatter
- [ ] T022 [P] 更新 `readme.md`：补充 002 功能说明和 `plan generate` 使用示例
- [ ] T023 运行 `ruff check .` 并修复所有 lint 问题

---

## Dependencies & Execution Order

### Phase 依赖

```
Phase 1（Tool-Use 升级）→ Phase 2（知识库）→ Phase 3（方案生成）→ Phase 4（修订循环）
Phase 2 和 Phase 3 的 T007/T008、T013/T014 可并行启动
Phase 5 在所有功能完成后执行
```

### 关键依赖链

```
T001 → T003 → T004 → T005 → T006
T007 → T009 → T010 → T012
T013 → T015 → T017
T009（KnowledgeStore）→ T015（PlanAgent）
T015（PlanAgent）→ T018（RevisionAgent）
```

### 并行机会

- T007 和 T008 可并行（不同文件）
- T013 和 T014 可并行（不同文件）
- T021 和 T022 可并行

---

## Implementation Strategy

### MVP（Phase 1 + Phase 2 + Phase 3）

1. 完成 Phase 1：Tool-Use 升级 → 验证现有测试通过
2. 完成 Phase 2：知识库 → 验证 cache-first 逻辑
3. 完成 Phase 3：方案生成 → 验证 `plan generate` 端到端
4. **STOP & VALIDATE**：给定真实 ResearchSpec，跑通完整方案生成

### 完整交付（加 Phase 4）

5. 完成 Phase 4：修订循环 → 验证人机协同闭环
6. 完成 Phase 5：Polish

---

## Summary

| Phase | 任务数 | 关联需求 |
|---|---|---|
| Phase 1: Tool-Use 升级 | T001–T006（6个）| 架构前置 |
| Phase 2: 知识库 | T007–T012（6个）| FR-002/003/005 |
| Phase 3: 方案生成 | T013–T017（5个）| FR-001 |
| Phase 4: 修订循环 | T018–T020（3个）| FR-004/006 |
| Phase 5: Polish | T021–T023（3个）| — |
| **合计** | **23个** | |
