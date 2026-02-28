# Tasks: AI 自主实验闭环 (Phase 1A)

**Input**: Design documents from `/specs/001-research-copilot-mvp/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts.md ✅

**Tests**: 包含测试任务（DoD 要求"每条 FR 均有对应验证步骤"）

**Organization**: 单一用户故事 US-1，按模块层次顺序排列，Schema 先行

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件，无依赖）
- **[Story]**: 所属用户故事 [US1]
- 含精确文件路径

---

## Phase 1: Setup（项目初始化）

**Purpose**: 建立目录结构、依赖声明、配置与测试固件

- [x] T001 Create full project directory structure per plan.md: `src/schemas/`, `src/agents/experiment/`, `src/sandbox/`, `src/llm/`, `src/storage/`, `src/service/`, `prompts/`, `configs/`, `tests/unit/`, `tests/integration/`, `tests/contract/`, `tests/fixtures/`, `runs/`（含各层 `__init__.py`）
- [x] T002 Create `requirements.txt` with pinned versions: pydantic>=2.0, litellm>=1.0, typer>=0.9, pyyaml>=6.0, python-dotenv>=1.0
- [x] T003 [P] Create `requirements-dev.txt` with dev dependencies: pytest>=7.0, pytest-cov>=4.0, ruff>=0.4
- [x] T004 [P] Create `configs/default.yaml` with default settings: default model (`claude-sonnet-4-6`), max_budget_usd, max_runtime_hours, max_iterations, llm_retry_count, llm_retry_delay_sec, sandbox_timeout_sec
- [x] T005 [P] Create `prompts/codegen_system.md` (指导 LLM 生成/修改实验代码，要求输出结构化 code_snapshot JSON) 和 `prompts/analyzer_system.md` (指导 LLM 分析 SandboxResponse，输出 AgentDecision JSON)
- [x] T006 [P] Create `tests/fixtures/sample_research_spec.json` (status=confirmed, 含 metrics×1, constraints) 和 `tests/fixtures/sample_experiment_plan.json` (steps×1, 引用 sample spec_id)，内容满足 contracts.md §3.2-3.3 约束

---

## Phase 2: Foundational（基础层，阻塞所有故事）

**Purpose**: Pydantic 数据契约层 + LLM 客户端 + 工件存储，所有 Agent/服务依赖此层

**⚠️ CRITICAL**: US-1 全部实现任务依赖本阶段完成

- [x] T007 Create `src/schemas/__init__.py` with shared value objects: `CostUsage`, `ResourceUsage`, `Metric`, `Constraints`, `PlanStep`, `Baseline`, `BestResult`, `FailedAttempt`, `EvidenceEntry`（全部为 Pydantic BaseModel，含 Field 校验）
- [x] T008 [P] Implement `src/schemas/errors.py`: `ErrorCode` (8 值枚举: llm_timeout, llm_rate_limit, sandbox_timeout, sandbox_oom, sandbox_crash, budget_exhausted, schema_validation, unknown), `AiSciError(code, message, retryable, details?)`, `ErrorResponse(error, timestamp, trace_id)`
- [x] T009 [P] Implement `src/schemas/state.py`: `RunStatus` 枚举 (queued/running/paused/succeeded/failed/stopped/budget_exhausted/timeout), `StopReason` 枚举, `ALLOWED_TRANSITIONS` dict 及 `validate_transition(current, next)` 函数
- [x] T010 [P] Implement `src/schemas/research_spec.py`: `ResearchSpec` (spec_id, title, objective, hypothesis?, metrics≥1, constraints, dataset_refs?, risk_notes?, non_goals?, status: draft|confirmed, created_by?, created_at?, updated_at?), `ExperimentPlan` (plan_id, spec_id, method_summary, evaluation_protocol, steps≥1, baseline?, created_at?)
- [x] T011 [P] Implement `src/schemas/experiment.py`: `ExperimentIteration` (iteration_id, run_id, index≥1, code_change_summary?, commands≥1, params?, metrics?, resource_usage?, cost_usage, status, error_summary?, artifact_dir, started_at?, ended_at?), `ExperimentRun` (run_id, spec_id, plan_id?, status, stop_reason?, iteration_count≥0, best_iteration_id?, cost_usage, created_at?, updated_at?)
- [x] T012 [P] Implement `src/schemas/report.py`: `ExperimentReport` (report_id, run_id, summary, best_result, key_findings?, failed_attempts?, evidence_map≥1条且路径存在, next_actions?, generated_at)
- [x] T013 [P] Implement `src/schemas/sandbox_io.py`: `CodeSnapshot` (files dict, entrypoint), `ResourceLimits` (max_memory_mb, gpu_required), `SandboxRequest` (request_id, run_id, iteration_index, action, code_snapshot, timeout_sec, resource_limits), `SandboxResponse` (request_id, status, exit_code, stdout≤100KB, stderr≤100KB, output_files, resource_usage, started_at, ended_at), `AgentDecision` (iteration_id, run_id, decision: continue|stop|request_human, stop_reason?, analysis_summary, next_action?)
- [x] T014 Implement `src/llm/client.py`: `LLMClient` class wrapping litellm, methods: `complete(messages, model?, system_prompt?) -> (str, CostUsage)`, retry logic (LLM timeout: 2 次重试; rate limit: 3 次指数退避), fallback model support, CostUsage accumulation from litellm response metadata
- [x] T015 Implement `src/storage/artifact.py`: `ArtifactStore` class, methods: `create_run_dir(run_id) -> Path`, `save_json(run_id, rel_path, data: BaseModel | dict)`, `load_json(run_id, rel_path) -> dict`, `save_text(run_id, rel_path, content: str)`, `list_artifacts(run_id) -> list[str]`, `path_exists(run_id, rel_path) -> bool`；根目录 `runs/<run_id>/`

**Checkpoint**: Schema 层完整 + LLM 客户端 + 存储就绪，可开始 US-1 实现

---

## Phase 3: User Story 1 — AI 自主实验执行（Priority: P1）🎯 MVP

**Goal**: 完整实现"生成代码→沙箱执行→分析→决策"闭环，支持多轮迭代、三类硬停止、工件全量落盘、ExperimentReport 输出

**Independent Test**:
```bash
# 使用 fixtures 样例一键跑通
python cli.py run create --spec tests/fixtures/sample_research_spec.json
python cli.py run start <run_id>
python cli.py run report <run_id>
# 验证：runs/<run_id>/ 下存在 iterations/it_0001/ … it_0003/，report.json evidence_map 路径全部有效
```

### Implementation for User Story 1

- [x] T016 [P] [US1] Implement `src/sandbox/base.py`: `SandboxExecutor` abstract base class with `execute(request: SandboxRequest) -> SandboxResponse` abstract method and `cleanup()` hook
- [x] T017 [P] [US1] Implement `src/sandbox/subprocess_sandbox.py`: `SubprocessSandbox(SandboxExecutor)`, 在 `runs/<run_id>/iterations/it_{n}/workspace/` 下写入 code_snapshot files，用 `venv` 创建/复用隔离 Python 环境，`subprocess.run(entrypoint, timeout=timeout_sec)` 执行，捕获 stdout/stderr（超 100KB 写全量到 stdout_full.log），解析 `metrics.json` 到 output_files，返回 SandboxResponse，超时时 status=timeout，OOM 时 status=oom
- [x] T018 [P] [US1] Implement `src/agents/experiment/codegen.py`: `CodegenAgent`, method `generate(spec, plan, history: list[ExperimentIteration]) -> CodeSnapshot`；调用 LLMClient.complete() 传入 codegen_system.md + spec/plan/history context，解析 LLM 输出为 CodeSnapshot，失败时抛出含 ErrorCode 的 AiSciError
- [x] T019 [P] [US1] Implement `src/agents/experiment/analyzer.py`: `AnalyzerAgent`, method `analyze(spec, iteration: ExperimentIteration, response: SandboxResponse) -> AgentDecision`；调用 LLMClient.complete() 传入 analyzer_system.md + 执行结果，解析输出为 AgentDecision，校验 decision=stop 时 stop_reason 非空
- [x] T020 [US1] Implement `src/agents/experiment/loop.py`: `ExperimentLoop.run(run: ExperimentRun, spec: ResearchSpec, plan: ExperimentPlan, store: ArtifactStore) -> ExperimentRun`，实现完整 plan→codegen→execute→analyze→decide 循环；硬停止：预算耗尽（cost_usage.estimated_cost_usd > constraints.max_budget_usd）→ budget_exhausted，超时 → timeout，迭代次数上限 → max_iterations；连续失败计数器（连续 3 轮失败 → decision=request_human）；每轮结束保存 ExperimentIteration JSON 到 `runs/<run_id>/iterations/it_{n:04d}/iteration.json` 及 stdout/stderr
- [x] T021 [US1] Implement `src/service/run_service.py`: `RunService` 提供 5 个服务方法：`create_run(spec_path, plan_path?) -> ExperimentRun`（生成 run_id=`run_{yyyymmdd}_{seq}`，若无 plan 则自动生成最小 plan 落盘到 `runs/<run_id>/plan/experiment_plan.json`），`start_run(run_id) -> ExperimentRun`（加载 spec/plan → 启动 ExperimentLoop），`control_run(run_id, action: pause|resume|stop)`，`get_run(run_id) -> ExperimentRun`（从 `runs/<run_id>/run.json` 加载），`get_run_report(run_id) -> ExperimentReport`（从 `runs/<run_id>/report.json` 加载或触发生成）；report 生成逻辑：聚合所有 ExperimentIteration，选取 best_iteration，构建 evidence_map（每条 key_finding 映射到对应 iteration.json 路径），校验路径存在
- [x] T022 [US1] Implement `cli.py` with typer: 命令 `run create --spec <path> [--plan <path>]`，`run start <run_id>`，`run stop <run_id>`，`run status <run_id>`，`run report <run_id> [--out <path>]`；读取 `configs/default.yaml` 作为默认配置，支持 `--config` 覆盖；错误统一格式化为 ErrorResponse JSON 输出

### Tests for User Story 1

- [x] T023 [P] [US1] Write unit tests for all Pydantic schemas in `tests/unit/test_schemas.py`: ResearchSpec status=draft 输入被拒，metrics 空列表被拒，ExperimentRun 非法状态转换被拒，AiSciError retryable 字段，EvidenceEntry 路径字段
- [x] T024 [P] [US1] Write unit tests for LLM client in `tests/unit/test_llm_client.py`: mock litellm.completion，验证 retry 计数（timeout 重试 2 次，rate_limit 重试 3 次指数退避），验证 CostUsage 从 response 正确累加，验证 fallback 模型在主模型失败后被调用
- [x] T025 [P] [US1] Write unit tests for SubprocessSandbox in `tests/unit/test_sandbox.py`: mock subprocess.run，验证 timeout→status=timeout，验证 metrics.json 被正确解析到 output_files，验证 stdout 超 100KB 时截断 + 完整内容写入 stdout_full.log，验证 workspace 目录在 runs/<run_id>/iterations/it_xxxx/workspace/ 下
- [x] T026 [US1] Write integration test for experiment loop in `tests/integration/test_experiment_loop.py`: mock CodegenAgent（固定返回 code_snapshot）+ mock SubprocessSandbox（第 1-2 轮 failed，第 3 轮 succeeded），验证 3 轮后 ExperimentRun.iteration_count=3，验证每轮 iteration.json 落盘，验证预算耗尽时 RunStatus=budget_exhausted
- [x] T027 [US1] Write integration test for RunService in `tests/integration/test_run_service.py`: 使用 tests/fixtures/sample_research_spec.json，mock ExperimentLoop.run，验证 create_run 在无 plan 时自动生成最小 plan 并落盘，验证 get_run_report evidence_map 所有路径 path_exists 为 True，验证 control_run stop 后 get_run 返回 stopped 状态

**Checkpoint**: US-1 全功能完成，可独立端到端验证

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: 代码质量、Gate C 验证、可审计性

- [x] T028 [P] Run `ruff check . && ruff format .` and fix all lint/format issues across entire codebase (`src/`, `cli.py`, `tests/`)
- [x] T029 [P] Validate Gate C: execute `python cli.py run create --spec tests/fixtures/sample_research_spec.json && python cli.py run start <run_id>` with mocked LLM calls, verify `runs/<run_id>/` contains at least 1 iteration directory and valid `report.json`, update plan.md Gate C status to ✅
- [x] T030 Write `tests/integration/test_acceptance.py` verifying all 4 success criteria: SC-001 (3 iterations complete), SC-002 (budget/timeout stops at correct iteration), SC-003 (report evidence_map paths all valid), SC-004 (CostUsage.estimated_cost_usd matches sum of all iterations)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: 无依赖，立即可开始
- **Phase 2 Foundational**: 依赖 Phase 1，**阻塞 Phase 3 全部任务**
- **Phase 3 US-1**: 依赖 Phase 2 完成；T016-T019 可并行；T020 依赖 T016-T019；T021 依赖 T020；T022 依赖 T021；T023-T025 可在 T007-T013 完成后并行开始；T026 依赖 T020；T027 依赖 T021
- **Phase 4 Polish**: 依赖 Phase 3 完成

### 关键依赖链

```
T007-T013 (schemas + llm + storage)
    ↓
T016 (sandbox base) ──┐
T017 (subprocess)  ──┤
T018 (codegen)     ──┤→ T020 (loop) → T021 (service) → T022 (cli)
T019 (analyzer)    ──┘
```

### Parallel Opportunities

```bash
# Phase 1 并行（6 个任务中 5 个可并行）：
Task: T002 requirements.txt
Task: T003 requirements-dev.txt
Task: T004 configs/default.yaml
Task: T005 prompts/
Task: T006 tests/fixtures/

# Phase 2 并行（T007 先完成，T008-T013 并行）：
Task: T008 errors.py
Task: T009 state.py
Task: T010 research_spec.py
Task: T011 experiment.py
Task: T012 report.py
Task: T013 sandbox_io.py

# Phase 3 初始并行（T007-T015 完成后）：
Task: T016 sandbox/base.py
Task: T017 sandbox/subprocess_sandbox.py
Task: T018 agents/codegen.py
Task: T019 agents/analyzer.py
Task: T023 tests/unit/test_schemas.py
Task: T024 tests/unit/test_llm_client.py
Task: T025 tests/unit/test_sandbox.py
```

---

## Implementation Strategy

### MVP First（US-1 仅）

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational（**关键阻塞**）
3. 完成 Phase 3: User Story 1 实现（T016-T022）
4. **STOP & VALIDATE**：运行 tests/fixtures/ 端到端，验证 ExperimentReport 输出
5. 完成 Phase 3 测试（T023-T027）+ Phase 4

### 单开发者顺序

```
Phase 1 → Phase 2 (并行 T008-T013) → T016+T017+T018+T019 (并行) → T020 → T021 → T022 → tests → polish
```

---

## Notes

- [P] = 不同文件，无未完成依赖，可并行
- [US1] = 对应 spec.md 用户故事 US-1（本 Phase 唯一故事）
- 每条 schema 任务需严格对照 `contracts.md` 字段定义
- `contracts.md §4.6` 连续失败表须在 T020 loop.py 中完整实现
- LLM 降级链：主模型 → fallback 模型 → request_human（在 T014 + T020 协同实现）
- 运行时只通过环境变量注入 API Key（`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`），不写入任何配置文件
- Phase 3 完成即达到 Gate C 可运行验证条件
