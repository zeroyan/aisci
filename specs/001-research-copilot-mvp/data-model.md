# Phase 1A 数据模型

**日期**: 2026-02-28
**关联**: `/specs/001-research-copilot-mvp/contracts.md`，`/docs/architecture/contracts.md`

> 本文件从 contracts 中提取实体关系和校验规则，作为 Pydantic model 实现的设计蓝图。

## 实体关系图

```text
ResearchSpec (输入, 只读)
    │
    ├──1:0..1──▶ ExperimentPlan (输入, 只读/自动生成)
    │
    └──1:1──▶ ExperimentRun (产出)
                  │
                  ├──1:N──▶ ExperimentIteration (产出)
                  │              │
                  │              └── SandboxRequest → SandboxResponse (交互)
                  │              └── AgentDecision (交互)
                  │
                  └──1:1──▶ ExperimentReport (产出)
```

## 实体详情

### 1. ResearchSpec

**来源**: `docs/architecture/contracts.md` §3.2
**角色**: Phase 1A 的唯一必需输入
**文件位置**: `src/schemas/research_spec.py`

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|----------|
| spec_id | str | ✅ | 非空 |
| title | str | ✅ | 非空 |
| objective | str | ✅ | 非空 |
| hypothesis | list[str] | ❌ | |
| metrics | list[Metric] | ✅ | 至少 1 条 |
| constraints | Constraints | ✅ | |
| dataset_refs | list[str] | ❌ | |
| risk_notes | list[str] | ❌ | |
| non_goals | list[str] | ❌ | |
| status | enum | ✅ | `draft` \| `confirmed`；Phase 1A 要求 `confirmed` |
| created_by | enum | ❌ | `user` \| `agent` |
| created_at | datetime | ❌ | ISO-8601 UTC |
| updated_at | datetime | ❌ | ISO-8601 UTC |

**嵌套类型**:
- `Metric`: `{name: str, direction: "maximize"|"minimize", target: float?, minimum_acceptable: float?}`
- `Constraints`: `{max_budget_usd: float, max_runtime_hours: float, max_iterations: int, compute: "cpu"|"single_gpu"|"multi_gpu"}`

### 2. ExperimentPlan

**来源**: `docs/architecture/contracts.md` §3.3
**角色**: 可选输入，未提供时系统自动生成最小 plan
**文件位置**: `src/schemas/research_spec.py`

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|----------|
| plan_id | str | ✅ | 非空 |
| spec_id | str | ✅ | 引用 ResearchSpec.spec_id |
| method_summary | str | ✅ | 非空 |
| evaluation_protocol | str | ✅ | 非空 |
| steps | list[PlanStep] | ✅ | 至少 1 步 |
| baseline | Baseline | ❌ | |
| created_at | datetime | ❌ | ISO-8601 UTC |

### 3. ExperimentIteration

**来源**: `docs/architecture/contracts.md` §3.4
**角色**: 单轮实验记录
**文件位置**: `src/schemas/experiment.py`

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|----------|
| iteration_id | str | ✅ | 非空 |
| run_id | str | ✅ | 引用 ExperimentRun.run_id |
| index | int | ✅ | ≥1 |
| code_change_summary | str | ❌ | |
| commands | list[str] | ✅ | 至少 1 条 |
| params | dict | ❌ | |
| metrics | dict | ❌ | |
| resource_usage | ResourceUsage | ❌ | |
| cost_usage | CostUsage | ✅ | v1.1.0 新增必填 |
| status | enum | ✅ | `succeeded` \| `failed` \| `stopped` |
| error_summary | str? | ❌ | status=failed 时建议填写 |
| artifact_dir | str | ✅ | 相对路径 |
| started_at | datetime | ❌ | |
| ended_at | datetime | ❌ | |

### 4. ExperimentRun

**来源**: `docs/architecture/contracts.md` §3.5
**角色**: 完整运行记录
**文件位置**: `src/schemas/experiment.py`

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|----------|
| run_id | str | ✅ | 非空 |
| spec_id | str | ✅ | 引用 ResearchSpec.spec_id |
| plan_id | str | ❌ | 引用 ExperimentPlan.plan_id |
| status | enum | ✅ | 状态机约束（§4） |
| stop_reason | enum? | ❌ | 终态时必填 |
| iteration_count | int | ✅ | ≥0 |
| best_iteration_id | str? | ❌ | |
| cost_usage | CostUsage | ✅ | 必须等于所有 iteration 之和 |
| created_at | datetime | ❌ | |
| updated_at | datetime | ❌ | |

**状态机**:
- `queued → running`
- `running → paused | succeeded | failed | stopped | budget_exhausted | timeout`
- `paused → running | stopped`
- 终态：`succeeded | failed | stopped | budget_exhausted | timeout`（不可回退）

### 5. ExperimentReport

**来源**: `docs/architecture/contracts.md` §3.6
**角色**: 最终总结报告
**文件位置**: `src/schemas/report.py`

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|----------|
| report_id | str | ✅ | 非空 |
| run_id | str | ✅ | 引用 ExperimentRun.run_id |
| summary | str | ✅ | 非空 |
| best_result | BestResult | ✅ | |
| key_findings | list[str] | ❌ | |
| failed_attempts | list[FailedAttempt] | ❌ | |
| evidence_map | list[EvidenceEntry] | ✅ | 至少 1 条；路径必须存在 |
| next_actions | list[str] | ❌ | |
| generated_at | datetime | ✅ | |

### 6. SandboxRequest / SandboxResponse / AgentDecision

**来源**: `specs/001-research-copilot-mvp/contracts.md` §4.2-4.4
**角色**: Agent-Sandbox 交互协议（Phase 1A 特有）
**文件位置**: `src/schemas/sandbox_io.py`

这三个是过程数据结构，不落盘为独立文件，但在 Agent 循环内部传递。
详细字段定义见 contracts.md §4.2-4.4。

## 共享类型

**文件位置**: `src/schemas/__init__.py` 或各自文件内

| 类型 | 字段 | 说明 |
|------|------|------|
| CostUsage | llm_calls, input_tokens, output_tokens, estimated_cost_usd | USD 保留 4 位小数 |
| ResourceUsage | wall_time_sec, gpu_hours, peak_memory_mb | |
| Metric | name, direction, target?, minimum_acceptable? | |
| Constraints | max_budget_usd, max_runtime_hours, max_iterations, compute | |
| PlanStep | step_id, description, expected_output | |
| Baseline | status, repo?, result_summary?, failure_reason? | |
| BestResult | iteration_id, metrics | |
| FailedAttempt | iteration_id, reason | |
| EvidenceEntry | claim, evidence_paths | |

## 错误模型

**来源**: `docs/architecture/contracts.md` §5
**文件位置**: `src/schemas/errors.py`

```python
class AiSciError(BaseModel):
    code: ErrorCode  # 8 种枚举
    message: str
    retryable: bool
    details: dict | None = None

class ErrorResponse(BaseModel):
    error: AiSciError
    timestamp: datetime
    trace_id: str
```
