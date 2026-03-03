# Tasks: 实验执行架构升级

**Feature**: 003-execution-upgrade-mvp
**Version**: 1.0.0
**Status**: Ready for Implementation
**Created**: 2026-03-02

---

## Overview

本任务列表将 Spec 003（实验执行架构升级）分解为可执行的任务，按用户故事组织，支持独立实现和测试。

**核心交付物**：
- BranchOrchestrator 编排器（最多 3 个并行分支）
- Planner/Critic/Executor 三角色架构
- Budget Scheduler 动态资源分配
- Experiment Memory 结构化记忆系统
- Docker 容器安全隔离层

**实现策略**：
- MVP 优先：先实现 US-1 和 US-2（核心架构）
- 增量交付：每个用户故事独立可测试
- 并行机会：标记 [P] 的任务可并行执行

---

## Phase 1: Setup & Dependencies

**目标**: 安装依赖，创建目录结构，定义核心 schemas

- [ ] T001 [P] 更新 requirements.txt 添加新依赖（docker>=7.0.0, sentence-transformers>=2.2.0, structlog>=24.0.0）
- [ ] T002 安装新依赖到虚拟环境（pip install -r requirements.txt）
- [ ] T003 [P] 创建目录结构（src/orchestrator/, src/agents/planner/, src/scheduler/, src/memory/）
- [ ] T004 [P] 定义核心 Pydantic schemas 在 src/schemas/orchestrator.py（BranchConfig, BudgetAllocation, PlannerOutput, CriticFeedback, BranchResult, MemoryEntry）
- [ ] T005 [P] 定义 ExperimentResult schema 在 src/schemas/experiment_result.py（统一结果格式）
- [ ] T006 [P] 创建配置文件模板 configs/execution.yaml（orchestrator, budget, docker, memory 配置）

**验收标准**:
- 所有依赖安装成功
- 目录结构创建完成
- 所有 schemas 通过 Pydantic 验证
- 配置文件模板可加载

---

## Phase 2: Foundational Components

**目标**: 实现跨用户故事的基础组件

- [ ] T007 [P] 实现 OrchestratorConfig 加载器在 src/orchestrator/config.py（从 YAML 加载配置）
- [ ] T008 [P] 实现 BranchVariantGenerator 在 src/orchestrator/variant_generator.py（基于 ExperimentPlan 生成最多 3 个变体）
- [ ] T009 [P] 实现 ReportGenerator 在 src/orchestrator/report_generator.py（生成分支报告和汇总报告）
- [ ] T010 [P] 扩展 ToolAgent 支持 PlannerOutput 在 src/agents/experiment/tool_agent.py（接受工具调用序列）

**验收标准**:
- 配置加载器能正确解析 YAML
- 变体生成器能生成 1-3 个不同的变体
- 报告生成器能生成 Markdown 格式报告
- ToolAgent 能执行 Planner 输出的工具序列

---

## Phase 3: US-1 - 多分支并行搜索

**User Story**: 作为科研人员，我希望系统能同时探索多个实验方向（不同超参、不同实现方案），以便在有限时间内找到更优解。

**Independent Test Criteria**:
- 能创建 3 个独立分支，每个分支有独立工作空间
- 分支能并行执行（使用 multiprocessing）
- 分支只读访问全局知识库，写入本地记忆
- 分支执行互不干扰

### Implementation Tasks

- [ ] T011 [P] [US1] 实现 BranchOrchestrator 框架在 src/orchestrator/branch_orchestrator.py（创建分支、分配工作空间、收集结果）
- [ ] T012 [P] [US1] 实现分支工作空间管理在 src/orchestrator/workspace_manager.py（创建、清理工作空间）
- [ ] T013 [US1] 实现分支并行执行在 src/orchestrator/branch_executor.py（使用 multiprocessing.Pool）
- [ ] T014 [P] [US1] 实现全局知识库只读访问在 src/memory/knowledge_base.py（加载全局知识库）
- [ ] T015 [P] [US1] 实现分支本地记忆写入在 src/memory/branch_memory.py（写入 attempts.jsonl, failures.jsonl, successes.jsonl）
- [ ] T016 [US1] 实现分支优先级调整在 src/orchestrator/priority_manager.py（根据中间结果动态调整）
- [ ] T017 [US1] 实现 CLI 命令 orchestrator run 在 cli.py（接受 run_id, num_branches, max_cost_usd 等参数）

### Unit Tests

- [x] T018 [P] [US1] 测试 BranchOrchestrator 创建分支在 tests/unit/test_branch_orchestrator.py
- [x] T019 [P] [US1] 测试分支工作空间隔离在 tests/unit/test_workspace_manager.py
- [x] T020 [P] [US1] 测试分支并行执行在 tests/unit/test_branch_executor.py
- [x] T021 [P] [US1] 测试全局知识库只读在 tests/unit/test_knowledge_base.py
- [x] T022 [P] [US1] 测试分支本地记忆写入在 tests/unit/test_branch_memory.py

### Integration Test

- [x] T023 [US1] 端到端测试：3 个分支并行执行在 tests/integration/test_multi_branch.py（验证分支独立性、知识库共享、结果汇总）

---

## Phase 4: US-2 - Planner 与 Critic 角色分离

**User Story**: 作为系统架构师，我希望将"生成方案"和"评估反馈"解耦，以便提升方案质量，支持多轮迭代优化。

**Independent Test Criteria**:
- Planner 能根据当前状态生成行动方案
- Executor 能执行 Planner 的方案
- Critic 能评估执行结果并给出反馈
- 支持最多 5 轮循环，连续 2 次无改进则早停
- 失败后生成实验报告

### Implementation Tasks

- [x] T024 [P] [US2] 实现 PlannerAgent 在 src/agents/planner/planner_agent.py（生成 PlannerOutput）
- [x] T025 [P] [US2] 实现 CriticAgent 在 src/agents/planner/critic_agent.py（评估结果，生成 CriticFeedback）
- [x] T026 [US2] 实现 Planner-Executor-Critic 循环在 src/agents/planner/pec_loop.py（最多 5 轮，早停机制）
- [x] T027 [P] [US2] 实现早停检测器在 src/agents/planner/early_stop_detector.py（连续 2 次无改进检测）
- [x] T028 [P] [US2] 实现失败报告生成在 src/orchestrator/failure_report.py（记录失败原因、尝试历史、建议）
- [x] T029 [US2] 集成 PEC 循环到 BranchExecutor 在 src/orchestrator/branch_executor.py

### Unit Tests

- [x] T030 [P] [US2] 测试 PlannerAgent 生成方案在 tests/unit/test_planner_agent.py
- [x] T031 [P] [US2] 测试 CriticAgent 评估结果在 tests/unit/test_critic_agent.py
- [x] T032 [P] [US2] 测试 PEC 循环最多 5 轮在 tests/unit/test_pec_loop.py
- [x] T033 [P] [US2] 测试早停机制在 tests/unit/test_early_stop_detector.py
- [x] T034 [P] [US2] 测试失败报告生成在 tests/unit/test_failure_report.py

### Integration Test

- [x] T035 [US2] 端到端测试：Planner-Critic 循环在 tests/integration/test_pec_loop.py（验证多轮迭代、早停、失败报告）

---

## Phase 5: US-3 - Budget Scheduler 动态资源分配

**User Story**: 作为项目管理者，我希望系统能根据分支表现动态分配计算预算，以便避免在低效分支上浪费资源。

**Independent Test Criteria**:
- 能配置总预算（tokens、时间、迭代次数）
- 能跟踪每个分支的资源消耗
- 能根据中间结果动态调整预算
- 连续 2 次失败则早停
- 失败分支生成实验报告

### Implementation Tasks

- [x] T036 [P] [US3] 实现 BudgetScheduler 在 src/scheduler/budget_scheduler.py（跟踪资源消耗、动态调整预算）
- [x] T037 [P] [US3] 实现资源消耗跟踪器在 src/scheduler/resource_tracker.py（记录 tokens、时间、迭代次数）
- [x] T038 [P] [US3] 实现预算分配策略在 src/scheduler/allocation_strategy.py（根据分支表现调整）
- [x] T039 [P] [US3] 实现早停策略在 src/scheduler/early_stop_strategy.py（连续 2 次失败、超时、预算耗尽）
- [x] T040 [US3] 集成 BudgetScheduler 到 BranchOrchestrator 在 src/orchestrator/branch_orchestrator.py

### Unit Tests

- [x] T041 [P] [US3] 测试 BudgetScheduler 跟踪资源在 tests/unit/test_budget_scheduler.py
- [x] T042 [P] [US3] 测试动态预算调整在 tests/unit/test_allocation_strategy.py
- [x] T043 [P] [US3] 测试早停策略触发在 tests/unit/test_early_stop_strategy.py

### Integration Test

- [x] T044 [US3] 端到端测试：Budget Scheduler 在 tests/integration/test_budget_scheduler.py（验证预算跟踪、动态调整、早停）

---

## Phase 6: US-4 - Experiment Memory 结构化记忆

**User Story**: 作为科研人员，我希望系统能记录所有尝试过的方案、失败原因和成功经验，以便避免重复错误。

**Independent Test Criteria**:
- 能记录每个分支的完整执行历史
- 能记录失败案例和成功案例（结构化存储）
- 能跨 run 检索相似案例（语义相似度）
- 生成报告时自动引用记忆内容

### Implementation Tasks

- [x] T045 [P] [US4] 实现 ExperimentMemory 在 src/memory/experiment_memory.py（记录、检索接口）
- [x] T046 [P] [US4] 实现记忆条目序列化在 src/memory/memory_serializer.py（写入 JSONL）
- [x] T047 [P] [US4] 实现语义相似度检索在 src/memory/similarity_search.py（sentence-transformers + 余弦相似度）
- [x] T048 [P] [US4] 实现嵌入向量缓存在 src/memory/embedding_cache.py（缓存到 .npy 文件）
- [x] T049 [US4] 实现记忆汇总到全局知识库在 src/memory/memory_aggregator.py（run 结束后合并）
- [x] T050 [US4] 集成记忆检索到 PlannerAgent 在 src/agents/planner/planner_agent.py（查找类似失败案例）
- [x] T051 [US4] 集成记忆引用到 ReportGenerator 在 src/orchestrator/report_generator.py

### Unit Tests

- [x] T052 [P] [US4] 测试记忆条目写入在 tests/unit/test_experiment_memory.py
- [x] T053 [P] [US4] 测试语义相似度检索在 tests/unit/test_similarity_search.py
- [x] T054 [P] [US4] 测试嵌入向量缓存在 tests/unit/test_embedding_cache.py
- [x] T055 [P] [US4] 测试记忆汇总在 tests/unit/test_memory_aggregator.py

### Integration Test

- [x] T056 [US4] 端到端测试：Experiment Memory 在 tests/integration/test_experiment_memory.py（验证记录、检索、汇总）

---

## Phase 7: US-5 - 安全隔离升级

**User Story**: 作为系统管理员，我希望实验执行环境有多层安全防护，以便防止恶意代码或错误命令破坏宿主系统。

**Independent Test Criteria**:
- 短期：命令白名单能检测危险模式
- 中期：每个分支在独立 Docker 容器中运行
- 容器使用 Python 官方镜像 + 按需安装依赖
- 资源限制生效（CPU、内存、磁盘）
- 容器正确清理（无泄漏）

### Implementation Tasks

- [x] T057 [P] [US5] 增强命令白名单在 src/agents/experiment/tool_dispatcher.py（检测 rm -rf /, dd, mkfs 等危险模式）
- [x] T058 [P] [US5] 实现 DockerSandbox 在 src/sandbox/docker_sandbox.py（容器生命周期管理）
- [x] T059 [P] [US5] 实现容器配置在 src/sandbox/docker_config.py（镜像、资源限制、网络隔离）
- [x] T060 [P] [US5] 实现依赖安装在 src/sandbox/dependency_installer.py（根据 requirements.txt 安装）
- [x] T061 [P] [US5] 实现容器清理在 src/sandbox/docker_cleanup.py（context manager 确保清理）
- [x] T062 [US5] 集成 DockerSandbox 到 BranchExecutor 在 src/orchestrator/branch_executor.py（enable_docker 参数）
- [x] T063 [US5] 更新 CLI 添加 --enable-docker 参数在 cli.py

### Unit Tests

- [x] T064 [P] [US5] 测试命令白名单检测在 tests/unit/test_tool_dispatcher.py
- [x] T065 [P] [US5] 测试 DockerSandbox 容器创建在 tests/unit/test_docker_sandbox.py
- [x] T066 [P] [US5] 测试资源限制配置在 tests/unit/test_docker_config.py
- [x] T067 [P] [US5] 测试容器清理在 tests/unit/test_docker_cleanup.py

### Integration Test

- [x] T068 [US5] 端到端测试：Docker 隔离在 tests/integration/test_docker_isolation.py（验证容器隔离、资源限制、清理）

---

## Phase 8: Polish & Cross-Cutting Concerns

**目标**: 完善日志、监控、文档、示例

- [x] T069 [P] 实现结构化日志在 src/orchestrator/logger.py（使用 structlog）
- [x] T070 [P] 添加分支状态实时显示在 src/orchestrator/status_monitor.py（运行中/成功/失败）
- [x] T071 [P] 创建 quickstart 示例在 examples/orchestrator_quickstart.py
- [x] T072 [P] 更新 README 添加 Orchestrator 使用说明在 readme.md
- [x] T073 [P] 创建配置文件示例在 configs/execution.example.yaml
- [x] T074 运行完整测试套件（pytest）
- [x] T075 运行 ruff 代码检查（ruff check .）
- [x] T076 生成测试覆盖率报告（pytest --cov）

**验收标准**:
- 所有日志使用 structlog 格式化
- 分支状态能实时显示
- Quickstart 示例能成功运行
- 文档完整且准确
- 所有测试通过
- 代码通过 ruff 检查
- 测试覆盖率 > 80%

---

## Dependencies & Execution Order

### Story Dependencies

```
Setup (Phase 1)
  ↓
Foundational (Phase 2)
  ↓
US-1 (Phase 3) ← 必须先完成
  ↓
US-2 (Phase 4) ← 依赖 US-1（需要分支执行框架）
  ↓
US-3 (Phase 5) ← 依赖 US-1, US-2（需要分支和循环）
  ↓
US-4 (Phase 6) ← 依赖 US-2（需要 Planner/Critic）
  ↓
US-5 (Phase 7) ← 依赖 US-1（需要分支执行框架）
  ↓
Polish (Phase 8)
```

### Parallel Execution Opportunities

**Phase 1 (Setup)**: T001, T003, T004, T005, T006 可并行

**Phase 2 (Foundational)**: T007, T008, T009, T010 可并行

**Phase 3 (US-1)**:
- T011, T012, T014, T015 可并行（不同文件）
- T018, T019, T020, T021, T022 可并行（不同测试文件）

**Phase 4 (US-2)**:
- T024, T025, T027, T028 可并行
- T030, T031, T032, T033, T034 可并行

**Phase 5 (US-3)**:
- T036, T037, T038, T039 可并行
- T041, T042, T043 可并行

**Phase 6 (US-4)**:
- T045, T046, T047, T048 可并行
- T052, T053, T054, T055 可并行

**Phase 7 (US-5)**:
- T057, T058, T059, T060, T061 可并行
- T064, T065, T066, T067 可并行

**Phase 8 (Polish)**: T069, T070, T071, T072, T073 可并行

---

## Implementation Strategy

### MVP Scope (Recommended)

**最小可行产品**：US-1 + US-2（核心架构）

- Phase 1: Setup & Dependencies
- Phase 2: Foundational Components
- Phase 3: US-1 - 多分支并行搜索
- Phase 4: US-2 - Planner 与 Critic 角色分离

**交付物**：
- 3 个分支能并行执行
- Planner-Executor-Critic 循环工作
- 基础的分支报告生成

**验收**：
- 端到端测试通过（T023, T035）
- 能运行 quickstart 示例

### Incremental Delivery

**Iteration 1 (MVP)**: US-1 + US-2（2 周）
- 核心架构可用
- 不启用 Docker（使用现有 subprocess sandbox）
- 不启用记忆检索（简单记录）

**Iteration 2 (Full Features)**: US-3 + US-4（2 周）
- Budget Scheduler 动态调整
- Experiment Memory 语义检索

**Iteration 3 (Security)**: US-5（1 周）
- Docker 容器隔离
- 资源限制

**Iteration 4 (Polish)**: Phase 8（1 周）
- 日志、监控、文档完善

---

## Task Summary

**Total Tasks**: 76

**By Phase**:
- Phase 1 (Setup): 6 tasks
- Phase 2 (Foundational): 4 tasks
- Phase 3 (US-1): 13 tasks
- Phase 4 (US-2): 12 tasks
- Phase 5 (US-3): 9 tasks
- Phase 6 (US-4): 12 tasks
- Phase 7 (US-5): 12 tasks
- Phase 8 (Polish): 8 tasks

**Parallelizable Tasks**: 48 tasks (标记 [P])

**By User Story**:
- US-1: 13 tasks (7 implementation + 5 unit tests + 1 integration test)
- US-2: 12 tasks (6 implementation + 5 unit tests + 1 integration test)
- US-3: 9 tasks (5 implementation + 3 unit tests + 1 integration test)
- US-4: 12 tasks (7 implementation + 4 unit tests + 1 integration test)
- US-5: 12 tasks (7 implementation + 4 unit tests + 1 integration test)

**Independent Test Criteria**:
- 每个用户故事都有明确的验收标准
- 每个用户故事都有独立的集成测试
- 所有用户故事可独立实现和测试

---

## Next Steps

1. ✅ Spec 完成并澄清
2. ✅ Plan 完成
3. ✅ Tasks 完成
4. ⏭️ 开始实现 MVP（`/speckit.implement` 或手动执行 Phase 1-4）

---

**Tasks Version**: 1.0.0
**Last Updated**: 2026-03-02
**Status**: Ready for Implementation
