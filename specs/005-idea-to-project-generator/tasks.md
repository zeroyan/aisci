# Tasks: Idea-to-Project Generator

**Branch**: `005-idea-to-project-generator`
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

---

## Implementation Strategy

### MVP Scope
**Phase 1-4** 构成最小可行产品（MVP）：
- US-1: 基础想法到项目转换
- US-2: 证据检索
- US-3: 交互澄清

MVP 完成后可以进行端到端测试，验证核心功能。

### Incremental Delivery
- **Sprint 1** (Phase 1-2): 环境准备 + 基础模块
- **Sprint 2** (Phase 3-5): 核心功能（US-1, US-2, US-3）
- **Sprint 3** (Phase 6): 知识沉淀（US-4）
- **Sprint 4** (Phase 7): 多候选方案（US-5）
- **Sprint 5** (Phase 8): 就绪验证（US-6）+ Polish

---

## Phase 1: Setup（环境准备）

**目标**: 准备开发环境和外部依赖

### Tasks

- [ ] T001 创建项目生成器模块目录 `src/agents/project_generator/`
- [ ] T002 [P] 创建 Schema 文件 `src/schemas/project_generator.py`（IdeaRecord, EvidencePackage, etc.）
- [ ] T003 [P] 更新 `requirements.txt` 添加新依赖（arxiv, semanticscholar, PyGithub, beautifulsoup4）
- [ ] T004 [P] 配置外部 API 环境变量（GITHUB_TOKEN, ARXIV_API_KEY, SEMANTIC_SCHOLAR_API_KEY）
- [ ] T005 [P] 创建配置文件 `configs/project_generator.yaml`

**验证标准**:
- ✅ 目录结构符合 plan.md 设计
- ✅ 依赖安装成功
- ✅ 环境变量配置完成

---

## Phase 2: Foundational（基础模块）

**目标**: 实现核心数据模型和工具类

### Tasks

- [ ] T006 [P] 实现 IdeaRecord Pydantic 模型 in `src/schemas/project_generator.py`
- [ ] T007 [P] 实现 ClarificationQuestion Pydantic 模型 in `src/schemas/project_generator.py`
- [ ] T008 [P] 实现 EvidencePackage Pydantic 模型 in `src/schemas/project_generator.py`
- [ ] T009 [P] 实现 PaperResult Pydantic 模型 in `src/schemas/project_generator.py`
- [ ] T010 [P] 实现 CodeRepository Pydantic 模型 in `src/schemas/project_generator.py`
- [ ] T011 [P] 实现 BaselineMethod Pydantic 模型 in `src/schemas/project_generator.py`
- [ ] T012 [P] 实现 EvidenceReport Pydantic 模型 in `src/schemas/project_generator.py`
- [ ] T013 [P] 实现 ResearchProposal Pydantic 模型 in `src/schemas/project_generator.py`
- [ ] T014 [P] 实现 KnowledgeCache Pydantic 模型 in `src/schemas/project_generator.py`
- [ ] T015 [P] 扩展 ResearchSpec 添加 evidence_metadata 字段 in `src/schemas/research_spec.py`
- [ ] T016 [P] 扩展 ExperimentPlan 添加 baseline_guidance 字段 in `src/schemas/research_spec.py`

**验证标准**:
- ✅ 所有 Pydantic 模型通过验证测试
- ✅ Schema 序列化/反序列化正常工作

---

## Phase 3: US-1 基础想法到项目转换（P1）

**目标**: 实现从想法到 ResearchSpec + ExperimentPlan 的基本流程

**Story Goal**: 用户提供一句话想法，系统生成可执行的项目包

**Independent Test**: 运行 `python cli.py project generate "I want to improve Transformer speed"` 生成完整项目包

### Tasks

#### Idea Intake
- [ ] T017 [US1] 实现 IntakeAgent 基础类 in `src/agents/project_generator/intake_agent.py`
- [ ] T018 [US1] 实现想法解析逻辑（提取 task, model, dataset, metric）
- [ ] T019 [US1] 实现想法类型分类（performance_improvement/new_method/problem_solving/constraint_driven）
- [ ] T020 [US1] 实现缺失信息检测（objective, metric, baseline, dataset, constraints）

#### Formalization
- [ ] T021 [US1] 实现 FormalizationAgent 基础类 in `src/agents/project_generator/formalization_agent.py`
- [ ] T022 [US1] 实现 ResearchSpec 生成逻辑（从 IdeaRecord + EvidencePackage）
- [ ] T023 [US1] 实现 ExperimentPlan 生成逻辑（从 ResearchSpec + baseline guidance）
- [ ] T024 [US1] 实现默认约束设置（budget: $100, time: 24h, iterations: 10）

#### CLI Integration
- [ ] T025 [US1] 在 `cli.py` 添加 `project` 命令组
- [ ] T026 [US1] 实现 `project generate` 命令（基础版本，无交互）
- [ ] T027 [US1] 实现项目 ID 生成逻辑（proj_<timestamp>_<hash>）
- [ ] T028 [US1] 实现输出目录创建（runs/<proj_id>/spec/, plan/, knowledge/）
- [ ] T029 [US1] 实现文件写入逻辑（research_spec.json, experiment_plan.json）

**Acceptance Criteria**:
- ✅ 用户提供想法，系统生成 ResearchSpec
- ✅ 生成的 ResearchSpec 符合现有 schema
- ✅ 生成的项目可以被 `cli.py run start` 执行

---

## Phase 4: US-2 证据检索（P1）

**目标**: 实现多源证据搜索和结果聚合

**Story Goal**: 系统搜索学术论文和代码仓库，生成证据报告

**Independent Test**: 系统搜索 "Transformer optimization" 返回至少 5 篇论文和 3 个代码仓库

### Tasks

#### Evidence Searcher
- [ ] T030 [US2] 实现 EvidenceSearcher 基础类 in `src/agents/project_generator/evidence_searcher.py`
- [ ] T031 [US2] 实现 arXiv 搜索逻辑（使用 arxiv Python 客户端）
- [ ] T032 [US2] 实现 Semantic Scholar 搜索逻辑（使用 semanticscholar 客户端）
- [ ] T033 [US2] 实现 GitHub 搜索逻辑（使用 PyGithub）
- [ ] T034 [US2] 实现 Papers with Code 爬虫（使用 BeautifulSoup）
- [ ] T035 [US2] 实现搜索结果排序（relevance × citations × recency）
- [ ] T036 [US2] 实现搜索结果去重（跨源去重）
- [ ] T037 [US2] 实现 baseline 方法提取（从论文摘要和代码 README）
- [ ] T038 [US2] 实现失败模式识别（从论文 limitations 部分）

#### Evidence Report Generation
- [ ] T039 [US2] 实现证据报告生成器 in `src/agents/project_generator/evidence_searcher.py`
- [ ] T040 [US2] 实现 Markdown 格式报告生成（包含论文列表、代码仓库、baseline 推荐）
- [ ] T041 [US2] 实现引用列表生成（APA 格式）
- [ ] T042 [US2] 实现风险评估部分（基于 common failures）

#### Integration
- [ ] T043 [US2] 集成 EvidenceSearcher 到 FormalizationAgent
- [ ] T044 [US2] 更新 `project generate` 命令添加证据搜索步骤
- [ ] T045 [US2] 实现证据报告写入（runs/<proj_id>/knowledge/evidence_report.md）

**Acceptance Criteria**:
- ✅ 搜索返回至少 5 篇论文和 3 个代码仓库
- ✅ 证据报告包含引用和 baseline 推荐
- ✅ ResearchSpec 包含 evidence_metadata

---

## Phase 5: US-3 交互澄清（P1）

**目标**: 实现多轮对话补齐缺失信息

**Story Goal**: 系统识别缺失信息，询问用户，并整合答案

**Independent Test**: 系统识别缺失信息，生成 2-5 个问题，用户回答后生成完整 ResearchSpec

### Tasks

#### Clarification Agent
- [ ] T046 [US3] 实现 ClarificationAgent 基础类 in `src/agents/project_generator/clarification_agent.py`
- [ ] T047 [US3] 实现问题生成逻辑（基于 missing_info 字段）
- [ ] T048 [US3] 实现问题优先级排序（objective > metric > baseline > dataset > constraints）
- [ ] T049 [US3] 实现多选题选项生成（使用 LLM 生成 3-5 个选项）
- [ ] T050 [US3] 实现默认答案设置（基于常见场景）
- [ ] T051 [US3] 实现问题数量限制（最多 5 个问题）

#### Interactive CLI
- [ ] T052 [US3] 实现交互式问答界面 in `cli.py`（使用 typer.prompt）
- [ ] T053 [US3] 实现多选题显示（带编号选项）
- [ ] T054 [US3] 实现跳过选项（用户可以选择使用默认值）
- [ ] T055 [US3] 实现答案验证（确保答案有效）
- [ ] T056 [US3] 实现答案整合（更新 IdeaRecord）

#### Integration
- [ ] T057 [US3] 集成 ClarificationAgent 到 `project generate` 流程
- [ ] T058 [US3] 实现 `--interactive` / `--no-interactive` 标志
- [ ] T059 [US3] 实现 `--max-questions` 选项
- [ ] T060 [US3] 保存用户答案到 `runs/<proj_id>/knowledge/clarifications.json`

**Acceptance Criteria**:
- ✅ 系统识别缺失信息并生成问题
- ✅ 问题限制在 5 个以内
- ✅ 用户答案正确整合到 ResearchSpec

---

## Phase 6: US-4 知识沉淀（P2）

**目标**: 实现搜索结果缓存和复用

**Story Goal**: 系统缓存搜索结果，第二次搜索时直接返回缓存

**Independent Test**: 搜索同一主题两次，第二次搜索时间 <5 秒（vs 第一次 ~30 秒）

### Tasks

#### Knowledge Consolidator
- [ ] T061 [US4] 实现 KnowledgeConsolidator 基础类 in `src/agents/project_generator/knowledge_consolidator.py`
- [ ] T062 [US4] 实现缓存键生成（normalize topic string）
- [ ] T063 [US4] 实现缓存保存逻辑（scientist/<topic>/papers.json, code.json, metadata.json）
- [ ] T064 [US4] 实现缓存加载逻辑（检查 timestamp，判断是否过期）
- [ ] T065 [US4] 实现缓存过期检查（30 天 TTL）
- [ ] T066 [US4] 实现缓存命中计数（hit_count 字段）

#### Cache Management CLI
- [ ] T067 [US4] 实现 `project cache list` 命令（显示所有缓存主题）
- [ ] T068 [US4] 实现 `project cache stats` 命令（显示缓存统计）
- [ ] T069 [US4] 实现 `project cache clear` 命令（清除指定主题或全部）
- [ ] T070 [US4] 实现 `project cache refresh` 命令（强制刷新缓存）

#### Integration
- [ ] T071 [US4] 集成 KnowledgeConsolidator 到 EvidenceSearcher
- [ ] T072 [US4] 实现缓存优先策略（先查缓存，未命中再调用 API）
- [ ] T073 [US4] 实现 `--skip-search` 标志（仅使用缓存）
- [ ] T074 [US4] 实现 `--force-refresh` 标志（强制刷新缓存）

**Acceptance Criteria**:
- ✅ 第一次搜索保存到缓存
- ✅ 第二次搜索使用缓存（<5 秒）
- ✅ 缓存命中率 >80%（warmup 后）

---

## Phase 7: US-5 多候选方案（P2）

**目标**: 生成 3 个不同风险级别的候选方案

**Story Goal**: 系统生成保守/平衡/激进 3 个方案，用户选择一个

**Independent Test**: 系统生成 3 个 ResearchSpec，用户选择 balanced，最终项目使用 balanced 方案

### Tasks

#### Proposal Generator
- [ ] T075 [US5] 实现 ProposalGenerator 基础类 in `src/agents/project_generator/proposal_generator.py`
- [ ] T076 [US5] 实现保守方案生成（复现 baseline + 小改进）
- [ ] T077 [US5] 实现平衡方案生成（结合多个方法）
- [ ] T078 [US5] 实现激进方案生成（探索新方向）
- [ ] T079 [US5] 实现风险标签生成（risk_profile 字段）
- [ ] T080 [US5] 实现预期指标估算（expected_metrics 字段）
- [ ] T081 [US5] 实现成本和时间估算（estimated_cost, estimated_time）

#### Proposal Selection CLI
- [ ] T082 [US5] 实现方案展示界面（显示 3 个方案的对比）
- [ ] T083 [US5] 实现方案选择逻辑（用户输入 1/2/3）
- [ ] T084 [US5] 实现 `--num-proposals` 选项（1-5 个方案）
- [ ] T085 [US5] 实现 `--auto-select` 选项（conservative/balanced/aggressive）
- [ ] T086 [US5] 保存所有方案到 `runs/<proj_id>/proposals.json`

#### Integration
- [ ] T087 [US5] 集成 ProposalGenerator 到 `project generate` 流程
- [ ] T088 [US5] 更新 FormalizationAgent 使用选中的方案

**Acceptance Criteria**:
- ✅ 生成 3 个不同的 ResearchSpec
- ✅ 每个方案有清晰的风险/收益说明
- ✅ 用户选择的方案用于最终项目

---

## Phase 8: US-6 就绪验证（P3）+ Polish

**目标**: 验证生成的项目可执行性 + 完善功能

**Story Goal**: 系统检查 ResearchSpec 是否可执行，提供反馈

**Independent Test**: 系统检查 ResearchSpec，识别问题（如 baseline 不可用），提供修复建议

### Tasks

#### Readiness Checker
- [ ] T089 [US6] 实现 ReadinessChecker 基础类 in `src/agents/project_generator/readiness_checker.py`
- [ ] T090 [US6] 实现指标可测量性检查（metrics 是否有明确评估方法）
- [ ] T091 [US6] 实现 baseline 可用性检查（baseline 代码/论文是否可访问）
- [ ] T092 [US6] 实现依赖可安装性检查（required packages 是否在 PyPI）
- [ ] T093 [US6] 实现预算合理性检查（budget 是否与任务复杂度匹配）
- [ ] T094 [US6] 实现失败判据清晰性检查（failure criteria 是否明确）
- [ ] T095 [US6] 实现反馈生成（具体、可操作的建议）

#### Integration
- [ ] T096 [US6] 集成 ReadinessChecker 到 `project generate` 流程（可选步骤）
- [ ] T097 [US6] 实现 `--skip-validation` 标志
- [ ] T098 [US6] 实现验证失败时的用户提示（继续/修改/取消）

#### Additional CLI Commands
- [ ] T099 实现 `project list` 命令（列出所有生成的项目）
- [ ] T100 实现 `project show` 命令（显示项目详情）
- [ ] T101 实现 `project delete` 命令（删除项目及文件）

#### Documentation
- [ ] T102 [P] 更新 README.md 添加 Spec005 功能说明
- [ ] T103 [P] 创建示例 fixture `tests/fixtures/sample_idea.txt`
- [ ] T104 [P] 验证 quickstart.md 中的所有场景可运行

#### Error Handling
- [ ] T105 [P] 实现 API 失败重试逻辑（3 次重试，指数退避）
- [ ] T106 [P] 实现 API 超时处理（30 秒超时）
- [ ] T107 [P] 实现缓存损坏处理（fallback 到直接 API）
- [ ] T108 [P] 实现用户中断处理（Ctrl+C 保存部分进度）

#### Testing
- [ ] T109 [P] 编写 IntakeAgent 单元测试 in `tests/unit/test_project_generator/test_intake_agent.py`
- [ ] T110 [P] 编写 ClarificationAgent 单元测试 in `tests/unit/test_project_generator/test_clarification_agent.py`
- [ ] T111 [P] 编写 EvidenceSearcher 单元测试 in `tests/unit/test_project_generator/test_evidence_searcher.py`
- [ ] T112 [P] 编写 KnowledgeConsolidator 单元测试 in `tests/unit/test_project_generator/test_knowledge_consolidator.py`
- [ ] T113 [P] 编写 FormalizationAgent 单元测试 in `tests/unit/test_project_generator/test_formalization_agent.py`
- [ ] T114 [P] 编写 ProposalGenerator 单元测试 in `tests/unit/test_project_generator/test_proposal_generator.py`
- [ ] T115 [P] 编写 ReadinessChecker 单元测试 in `tests/unit/test_project_generator/test_readiness_checker.py`
- [ ] T116 编写端到端测试 in `tests/integration/test_project_generator_e2e.py`（场景 1: 基础转换）
- [ ] T117 编写端到端测试（场景 2: 证据搜索）
- [ ] T118 编写端到端测试（场景 3: 交互澄清）
- [ ] T119 编写端到端测试（场景 4: 知识缓存）
- [ ] T120 编写端到端测试（场景 5: 多候选方案）

**Acceptance Criteria**:
- ✅ 就绪检查识别常见问题
- ✅ 所有 CLI 命令正常工作
- ✅ 所有单元测试通过
- ✅ 端到端测试覆盖主要场景

---

## Dependencies

### User Story Completion Order

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational)
    ↓
Phase 3 (US-1) ← 必须先完成，提供基础转换能力
    ↓
Phase 4 (US-2) ← 依赖 US-1，添加证据搜索
    ↓
Phase 5 (US-3) ← 依赖 US-1，添加交互澄清
    ↓
Phase 6 (US-4) ← 依赖 US-2，添加缓存
    ↓
Phase 7 (US-5) ← 依赖 US-1, US-2, US-3，添加多方案
    ↓
Phase 8 (US-6 + Polish) ← 依赖所有前置 Phase
```

### Critical Path
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 8

### Parallel Opportunities

#### Sprint 1 并行任务
- T002, T003, T004, T005 可并行执行（不同文件）
- T006-T016 可并行执行（不同 Schema）

#### Sprint 2 并行任务
- T017-T020 可并行执行（IntakeAgent 内部逻辑）
- T021-T024 可并行执行（FormalizationAgent 内部逻辑）
- T030-T038 可并行执行（不同搜索源）

#### Sprint 5 并行任务
- T102-T104 可并行执行（不同文档）
- T105-T108 可并行执行（不同错误处理）
- T109-T115 可并行执行（不同测试文件）

---

## Summary

### Task Count
- **Total**: 120 tasks
- **Phase 1 (Setup)**: 5 tasks
- **Phase 2 (Foundational)**: 11 tasks
- **Phase 3 (US-1)**: 13 tasks
- **Phase 4 (US-2)**: 16 tasks
- **Phase 5 (US-3)**: 15 tasks
- **Phase 6 (US-4)**: 14 tasks
- **Phase 7 (US-5)**: 14 tasks
- **Phase 8 (US-6 + Polish)**: 32 tasks

### Parallel Opportunities
- **Sprint 1**: 15 tasks 可并行
- **Sprint 2**: 22 tasks 可并行
- **Sprint 5**: 15 tasks 可并行

### MVP Scope
**Phase 1-5** (60 tasks) 构成 MVP，包含：
- 环境准备
- 基础模块
- 基础转换（US-1）
- 证据搜索（US-2）
- 交互澄清（US-3）

完成 MVP 后可进行端到端验证。

### Independent Test Criteria
- **US-1**: `python cli.py project generate "..."` 生成完整项目包
- **US-2**: 搜索返回至少 5 篇论文和 3 个代码仓库
- **US-3**: 系统生成 2-5 个问题，用户回答后生成完整 ResearchSpec
- **US-4**: 第二次搜索时间 <5 秒（vs 第一次 ~30 秒）
- **US-5**: 生成 3 个方案，用户选择一个
- **US-6**: 就绪检查识别问题并提供反馈

---

## Format Validation

✅ All tasks follow the checklist format:
- Checkbox: `- [ ]`
- Task ID: T001-T120
- [P] marker: 52 tasks marked as parallelizable
- [Story] label: 88 tasks have story labels (US1-US6)
- Description: All tasks include clear action and file path
