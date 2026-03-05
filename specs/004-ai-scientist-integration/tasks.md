# Tasks: AI-Scientist 外部专家集成

**Branch**: `004-ai-scientist-integration`
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

---

## Implementation Strategy

### MVP Scope
**Phase 1-4** 构成最小可行产品（MVP）：
- US-1: 引擎路由选择
- US-2: 异步任务管理
- US-3: 结果标准化与回传

MVP 完成后可以进行端到端测试，验证 ai-scientist 引擎的基本功能。

### Incremental Delivery
- **Sprint 1** (Phase 1-2): 环境准备 + 基础模块
- **Sprint 2** (Phase 3-5): 核心功能（US-1, US-2, US-3）
- **Sprint 3** (Phase 6): Hybrid 模式（US-4）
- **Sprint 4** (Phase 7-8): 动态模板 + 优化（US-5, Polish）

---

## Phase 1: Setup（环境准备）

**目标**: 准备开发环境和外部依赖

### Tasks

- [X] T001 创建集成模块目录结构 `src/integrations/ai_scientist/`
- [X] T002 [P] 创建 Schema 文件 `src/schemas/ai_scientist.py`（JobRecord, TemplatePackage, JobStatus）
- [X] T003 [P] 初始化 AI-Scientist submodule 到 `external/ai-scientist-runtime/`
- [ ] T004 [P] 配置 Ollama + qwen3 本地模型环境
- [X] T005 [P] 创建通用模板骨架目录 `external/ai-scientist-runtime/templates/generic_ai_research_cn/`
- [X] T006 [P] 更新 `requirements.txt` 添加新依赖（watchdog, psutil）
- [X] T007 [P] 更新 `.gitignore` 添加 `external/ai-scientist-runtime/results/`

**验证标准**:
- ✅ 目录结构符合 plan.md 设计
- ✅ AI-Scientist submodule 正确初始化
- ✅ Ollama 服务运行，qwen3 模型可用
- ✅ 依赖安装成功

---

## Phase 2: Foundational（基础模块）

**目标**: 实现核心数据模型和工具类

### Tasks

- [X] T008 [P] 实现 JobStatus 枚举 in `src/schemas/ai_scientist.py`
- [X] T009 [P] 实现 JobRecord Pydantic 模型 in `src/schemas/ai_scientist.py`
- [X] T010 [P] 实现 TemplatePackage Pydantic 模型 in `src/schemas/ai_scientist.py`
- [X] T011 [P] 扩展 ExperimentResult 添加 engine 和 external_metadata 字段 in `src/schemas/experiment.py`
- [X] T012 实现 JobStore 基础类 in `src/integrations/ai_scientist/job_store.py`（初始化、save、load、list_all）
- [X] T013 实现 JobStore 并发控制逻辑 in `src/integrations/ai_scientist/job_store.py`（can_submit, submit_or_queue）
- [X] T014 [P] 实现 AIScientistAdapter 基础类 in `src/integrations/ai_scientist/adapter.py`（初始化、is_installed、check_version）

**验证标准**:
- ✅ 所有 Pydantic 模型通过验证测试
- ✅ JobStore 可以正确读写 jobs.jsonl
- ✅ 并发限制逻辑正确（最多 2 个任务）

---

## Phase 3: US-1 引擎路由选择（P1）

**目标**: 支持 `--engine` 参数，实现三种引擎模式的路由

**Story Goal**: 用户可以通过 CLI 参数选择使用 aisci、ai-scientist 或 hybrid 引擎

**Independent Test**: 运行 `python cli.py run start <run_id> --engine ai-scientist`，验证命令被正确路由

### Tasks

- [X] T015 [US1] 在 `cli.py` 的 `run start` 命令添加 `--engine` 参数（默认 "aisci"）
- [X] T016 [US1] 在 `cli.py` 的 `run start` 命令添加 `--num-ideas` 参数（默认 2）
- [X] T017 [US1] 在 `cli.py` 的 `run start` 命令添加 `--writeup` 参数（默认 "md"）
- [X] T018 [US1] 在 `cli.py` 的 `run start` 命令添加 `--model` 参数（默认 "ollama/qwen3"）
- [X] T019 [US1] 实现引擎路由逻辑 in `cli.py`（根据 engine 参数调用不同执行路径）
- [X] T020 [US1] 实现 aisci 模式分支（复用现有 ExperimentLoop）
- [X] T021 [US1] 实现 ai-scientist 模式分支（调用 AIScientistAdapter.submit_job）
- [X] T022 [US1] 实现 hybrid 模式分支（先 ai-scientist，后 aisci）
- [X] T023 [US1] 添加参数验证（engine 必须是 aisci/ai-scientist/hybrid 之一）

**Acceptance Criteria**:
- ✅ `--engine aisci` 使用现有 ExperimentLoop
- ✅ `--engine ai-scientist` 调用 AIScientistAdapter
- ✅ `--engine hybrid` 依次调用两个引擎
- ✅ 无效的 engine 值返回错误信息

---

## Phase 4: US-2 异步任务管理（P1）

**目标**: 实现异步任务提交、状态查询、结果获取、任务取消

**Story Goal**: 用户可以提交 AI-Scientist 任务后立即返回，通过 CLI 命令查询状态和获取结果

**Independent Test**: 提交任务 → 查询状态 → 获取结果，整个流程不阻塞

### Tasks

#### 任务提交
- [X] T024 [US2] 实现 AIScientistAdapter.submit_job in `src/integrations/ai_scientist/adapter.py`（启动子进程，返回 job_id）
- [X] T025 [US2] 实现 job_id 生成逻辑（UUID）
- [X] T026 [US2] 实现日志文件创建 in `runs/<run_id>/external/logs/<job_id>.log`
- [X] T027 [US2] 实现任务记录保存到 JobStore

#### 状态查询
- [X] T028 [US2] 添加 CLI 命令 `run external-status <run_id>` in `cli.py`
- [X] T029 [US2] 实现 AIScientistAdapter.get_status in `src/integrations/ai_scientist/adapter.py`（检查进程状态）
- [X] T030 [US2] 实现进度计算逻辑（已完成 ideas / 总 ideas）
- [X] T031 [US2] 实现状态输出格式化（status, progress, elapsed_time, log_path）

#### 结果获取
- [X] T032 [US2] 添加 CLI 命令 `run external-fetch <run_id>` in `cli.py`
- [X] T033 [US2] 实现结果目录检查（任务必须是 completed 状态）
- [X] T034 [US2] 调用 ResultParser 解析结果（Phase 5 实现）
- [X] T035 [US2] 实现结果落盘到 `runs/<run_id>/external/ai_scientist/`

#### 任务取消
- [X] T036 [US2] 添加 CLI 命令 `run external-cancel <run_id>` in `cli.py`
- [X] T037 [US2] 实现 AIScientistAdapter.cancel_job in `src/integrations/ai_scientist/adapter.py`（SIGTERM → SIGKILL）
- [X] T038 [US2] 实现任务状态更新为 failed（error="Cancelled by user"）
- [X] T039 [US2] 实现部分结果保存（如果有）

#### 回调机制
- [X] T040 [US2] 实现 JobCallbacks 基础类 in `src/integrations/ai_scientist/callbacks.py`
- [X] T041 [US2] 实现状态轮询逻辑 in `JobCallbacks.poll_status`（可配置间隔）
- [X] T042 [US2] 实现文件事件监听 in `JobCallbacks.watch_job`（使用 watchdog，可选）
- [X] T043 [US2] 实现任务完成回调（触发下一个 pending 任务）

**Acceptance Criteria**:
- ✅ `run start --engine ai-scientist` 立即返回 job_id
- ✅ `run external-status` 显示正确的任务状态
- ✅ `run external-fetch` 成功获取结果
- ✅ `run external-cancel` 可以终止运行中的任务
- ✅ 并发限制生效（最多 2 个任务）

---

## Phase 5: US-3 结果标准化与回传（P1）

**目标**: 解析 AI-Scientist 输出，转换为 ExperimentResult 格式

**Story Goal**: 外部结果能标准化为统一格式，便于后续处理和对比

**Independent Test**: 运行 `run external-fetch`，验证结果文件格式正确

### Tasks

- [X] T044 [US3] 实现 ResultParser 基础类 in `src/integrations/ai_scientist/result_parser.py`
- [X] T045 [US3] 实现 parse_result_dir 方法（查找最新 idea 目录）
- [X] T046 [US3] 实现 report.md 提取逻辑
- [X] T047 [US3] 实现 final_info.json 解析逻辑
- [X] T048 [US3] 实现 plots/ 目录扫描（收集所有 .png 文件）
- [X] T049 [US3] 实现 code/ 目录扫描（收集所有 .py 文件）
- [X] T050 [US3] 实现 extract_artifacts 方法（返回 artifact 路径列表）
- [X] T051 [US3] 实现 ExperimentResult 转换逻辑（设置 engine="ai-scientist"）
- [X] T052 [US3] 实现 external_metadata 填充（job_id, template_name, idea_name）
- [X] T053 [US3] 实现结果 JSON 序列化到 `runs/<run_id>/external/ai_scientist/result.json`
- [X] T054 [US3] 实现 artifacts 复制到 `runs/<run_id>/external/ai_scientist/artifacts/`

**Acceptance Criteria**:
- ✅ 解析 AI-Scientist 输出目录成功
- ✅ 提取 report.md、final_info.json、图表、代码
- ✅ 转换为 ExperimentResult 格式
- ✅ 落盘到 runs 目录

---

## Phase 6: US-4 Hybrid 模式精修（P1）

**目标**: 实现 hybrid 模式：AiSci baseline → AI-Scientist 迭代 → AiSci 精修

**Story Goal**: 利用 AiSci 快速生成 baseline，AI-Scientist 迭代改进，最后 AiSci 精修

**Independent Test**: 运行 `run start --engine hybrid`，验证三阶段依次执行

**重要说明**:
- AI-Scientist 需要 `run_0/final_info.json` 作为 baseline（硬依赖）
- Hybrid 模式会自动生成 baseline，无需手动准备

### Tasks

#### Phase 1: Baseline 生成
- [X] T055 [US4] 实现 baseline 生成逻辑 in `cli.py`（AiSci 运行 1 次迭代）
- [X] T056 [US4] 实现 baseline 结果提取（从 ExperimentResult 提取 metrics）
- [X] T057 [US4] 实现 baseline 写入 `run_0/final_info.json`（格式：`{"experiment": {"means": {...}}}`）

#### Phase 2: 模板准备
- [X] T058 [US4] 实现模板目录创建 in `cli.py`（`templates/generic_ai_research_cn/`）
- [X] T059 [US4] 实现 experiment.py 写入（从 baseline 代码）
- [X] T060 [US4] 实现 plot.py、prompt.json、seed_ideas.json 写入
- [X] T061 [US4] 验证模板完整性（所有必需文件存在）

#### Phase 3: AI-Scientist 执行
- [X] T062 [US4] 调用 AIScientistAdapter.submit_job（使用准备好的模板）
- [X] T063 [US4] 实现阻塞等待逻辑（调用 JobCallbacks.poll_status）
- [X] T064 [US4] 实现进度输出（每分钟更新状态）
- [X] T065 [US4] 实现外部结果获取（调用 ResultParser）

#### Phase 4: AiSci 精修
- [X] T066 [US4] 集成 RevisionAgent（将外部结果喂给 RevisionAgent）
- [X] T067 [US4] 生成修订建议（ExperimentPlan v+1）
- [X] T068 [US4] 集成 Orchestrator（使用新 plan 运行 aisci 引擎）
- [X] T069 [US4] 实现对比报告生成 in `runs/<run_id>/comparison_report.md`
- [X] T070 [US4] 实现对比指标计算（baseline vs AI-Scientist vs AiSci）

**Acceptance Criteria**:
- ✅ Phase 1: AiSci 生成可运行的 baseline
- ✅ Phase 2: Baseline 正确写入 `run_0/final_info.json`
- ✅ Phase 3: AI-Scientist 基于 baseline 成功运行
- ✅ Phase 4: AiSci 继续优化并生成对比报告

---

## Phase 7: US-5 动态模板生成（P2）

**目标**: 根据 ResearchSpec 动态生成 AI-Scientist 模板

**Story Goal**: 支持任意课题而不绑定特定模板

**Independent Test**: 提供自定义 ResearchSpec，验证模板生成成功

### Tasks

#### 通用模板骨架
- [X] T071 [US5] 创建 prompt.json 模板 in `external/ai-scientist-runtime/templates/generic_ai_research_cn/`
- [X] T072 [US5] 创建 seed_ideas.json 模板 in `external/ai-scientist-runtime/templates/generic_ai_research_cn/`
- [X] T073 [US5] 创建 experiment.py 通用接口 in `external/ai-scientist-runtime/templates/generic_ai_research_cn/`
- [X] T074 [US5] 创建 plot.py 标准图表 in `external/ai-scientist-runtime/templates/generic_ai_research_cn/`

#### 动态生成逻辑
- [X] T075 [US5] 实现 SpecMapper 基础类 in `src/integrations/ai_scientist/spec_mapper.py`
- [X] T076 [US5] 实现 map_to_template_package 方法（ResearchSpec → TemplatePackage）
- [X] T077 [US5] 实现 generate_dynamic_template 方法（创建模板目录）
- [X] T078 [US5] 实现 prompt.json 动态生成（从 spec.objective 提取）
- [X] T079 [US5] 实现 seed_ideas.json 动态生成（从 spec 或 plan 提取 2-3 个 idea）
- [X] T080 [US5] 实现 experiment.py 和 plot.py 复制（从通用骨架）
- [X] T081 [US5] 实现模板名称生成（dynamic_<spec_id>）
- [X] T082 [US5] 集成到 AIScientistAdapter.submit_job（调用 SpecMapper）

**Acceptance Criteria**:
- ✅ 创建通用模板骨架
- ✅ 根据 ResearchSpec 动态生成模板文件
- ✅ 模板可以被 AI-Scientist 正常使用

---

## Phase 8: Polish & Integration（优化与集成）

**目标**: 端到端测试、文档完善、性能优化

### Tasks

#### 端到端测试
- [ ] T076 编写端到端测试 in `tests/integration/test_ai_scientist_integration.py`（场景 1: ai-scientist 模式）
- [ ] T077 编写端到端测试（场景 2: hybrid 模式）
- [ ] T078 编写端到端测试（场景 3: 并发限制）
- [ ] T079 编写端到端测试（场景 4: 失败处理）
- [ ] T080 编写端到端测试（场景 5: 任务取消）
- [ ] T081 编写端到端测试（场景 6: 动态模板生成）

#### 单元测试
- [X] T082 [P] 编写 JobStore 单元测试 in `tests/unit/test_job_store.py`
- [X] T083 [P] 编写 AIScientistAdapter 单元测试 in `tests/unit/test_adapter.py`
- [X] T084 [P] 编写 ResultParser 单元测试 in `tests/unit/test_result_parser.py`
- [X] T085 [P] 编写 SpecMapper 单元测试 in `tests/unit/test_spec_mapper.py`
- [X] T086 [P] 编写 JobCallbacks 单元测试 in `tests/unit/test_callbacks.py`

#### 文档与示例
- [X] T087 [P] 创建 launch_scientist.py 启动脚本 in `external/ai-scientist-runtime/`
- [X] T088 [P] 更新 README.md 添加 AI-Scientist 集成说明
- [X] T089 [P] 创建示例 ResearchSpec for quickstart in `tests/fixtures/sample_ai_scientist_spec.json`
- [ ] T090 [P] 验证 quickstart.md 中的所有场景可运行

#### 性能优化
- [ ] T091 测量适配层开销（目标 < 5%）
- [ ] T092 测量结果转换延迟（目标 < 1s）
- [ ] T093 优化状态轮询频率（避免过度轮询）
- [ ] T094 优化日志输出（避免日志文件过大）

#### 错误处理
- [X] T095 [P] 实现 AI-Scientist 未安装检测 in `AIScientistAdapter.is_installed`
- [X] T096 [P] 实现版本兼容性检查 in `AIScientistAdapter.check_version`
- [X] T097 [P] 实现 Ollama 服务检测（连接 http://localhost:11434）
- [X] T098 [P] 实现 qwen3 模型检测（ollama list）
- [X] T099 [P] 添加友好的错误提示（安装指南、配置示例）

#### 配置管理
- [X] T100 [P] 添加配置文件支持 in `configs/ai_scientist.yaml`（轮询间隔、超时、并发限制）
- [X] T101 [P] 实现配置加载逻辑（环境变量 > 配置文件 > 默认值）

---

## Dependencies

### User Story Completion Order

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational)
    ↓
Phase 3 (US-1) ← 必须先完成，提供引擎路由
    ↓
Phase 4 (US-2) ← 依赖 US-1，提供异步任务管理
    ↓
Phase 5 (US-3) ← 依赖 US-2，提供结果解析
    ↓
Phase 6 (US-4) ← 依赖 US-1, US-2, US-3，实现 hybrid 模式
    ↓
Phase 7 (US-5) ← 独立，可并行开发
    ↓
Phase 8 (Polish) ← 依赖所有前置 Phase
```

### Critical Path
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 8

### Parallel Opportunities

#### Sprint 1 并行任务
- T002, T003, T004, T005, T006, T007 可并行执行（不同文件）

#### Sprint 2 并行任务
- T008, T009, T010, T011 可并行执行（不同 Schema）
- T014 可与 T012-T013 并行（不同文件）

#### Sprint 4 并行任务
- T064-T067 可并行执行（不同模板文件）
- T082-T086 可并行执行（不同测试文件）
- T087-T090 可并行执行（不同文档）
- T095-T099 可并行执行（不同错误检测）

---

## Summary

### Task Count
- **Total**: 101 tasks
- **Phase 1 (Setup)**: 7 tasks
- **Phase 2 (Foundational)**: 7 tasks
- **Phase 3 (US-1)**: 9 tasks
- **Phase 4 (US-2)**: 20 tasks
- **Phase 5 (US-3)**: 11 tasks
- **Phase 6 (US-4)**: 9 tasks
- **Phase 7 (US-5)**: 12 tasks
- **Phase 8 (Polish)**: 26 tasks

### Parallel Opportunities
- **Sprint 1**: 6 tasks 可并行
- **Sprint 2**: 5 tasks 可并行
- **Sprint 4**: 20 tasks 可并行

### MVP Scope
**Phase 1-5** (54 tasks) 构成 MVP，包含：
- 环境准备
- 基础模块
- 引擎路由（US-1）
- 异步任务管理（US-2）
- 结果标准化（US-3）

完成 MVP 后可进行端到端验证。

### Independent Test Criteria
- **US-1**: `python cli.py run start <run_id> --engine ai-scientist` 命令被正确路由
- **US-2**: 提交任务 → 查询状态 → 获取结果，整个流程不阻塞
- **US-3**: `run external-fetch` 返回正确格式的 ExperimentResult
- **US-4**: `run start --engine hybrid` 依次执行两个引擎并生成对比报告
- **US-5**: 提供自定义 ResearchSpec，验证模板生成成功

---

## Format Validation

✅ All tasks follow the checklist format:
- Checkbox: `- [ ]`
- Task ID: T001-T101
- [P] marker: 41 tasks marked as parallelizable
- [Story] label: 61 tasks have story labels (US1-US5)
- Description: All tasks include clear action and file path
