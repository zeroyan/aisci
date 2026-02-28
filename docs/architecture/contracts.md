# AiSci 全局数据与接口契约

**版本**: `v1.1.0`
**创建日期**: 2026-02-27
**状态**: Draft

> 迁移自 `specs/000-aisci-epic/contracts.md`（v1.0.0）。
> 本文件是全项目通用的工程契约基线，各 Phase spec 通过引用本文件
> 获得数据结构、状态机、错误格式等约束。

## 1. 目标与范围

本文档定义 AiSci 的"可执行契约"，用于约束：

1. 核心数据结构（Data Contracts）
2. 运行状态机（State Contract）
3. 错误返回格式（Error Contract）
4. 落盘目录与工件（Artifact Contract）
5. 最小接口语义（Service Contract）

说明：
1. 本文档服务全部 Phase（P1-A/P1-B/P1-C/P2）交付。
2. 与各 Phase `spec.md` 冲突时，以"更严格约束"为准。
3. 破坏性修改必须升级版本号。

## 2. 通用字段规范

1. 所有时间字段使用 ISO-8601 UTC（例如 `2026-02-27T10:30:00Z`）。
2. 所有 ID 字段类型为字符串，推荐 UUIDv4 或可读唯一 ID。
3. 所有枚举字段必须严格取值，不允许自由文本替代。
4. 所有金额以 USD 计价，浮点数���留 4 位小数。
5. 所有路径字段一律使用相对项目根目录路径。

## 3. ��据契约（Data Contracts）

### 3.1 ResearchInput（Phase 1C）

```json
{
  "input_id": "ri_001",
  "source_type": "direction|idea|dataset|paper|free_text",
  "content": "string",
  "metadata": {
    "title": "string",
    "tags": ["string"],
    "source_uri": "string|null"
  },
  "created_at": "2026-02-27T10:30:00Z"
}
```

必填字段：`input_id`, `source_type`, `content`, `created_at`

### 3.2 ResearchSpec（Phase 1A 输入 / Phase 1C 输出）

```json
{
  "spec_id": "rs_001",
  "title": "string",
  "objective": "string",
  "hypothesis": ["string"],
  "metrics": [
    {
      "name": "accuracy",
      "direction": "maximize|minimize",
      "target": 0.9,
      "minimum_acceptable": 0.75
    }
  ],
  "constraints": {
    "max_budget_usd": 50.0,
    "max_runtime_hours": 24,
    "max_iterations": 20,
    "compute": "cpu|single_gpu|multi_gpu"
  },
  "dataset_refs": ["string"],
  "risk_notes": ["string"],
  "non_goals": ["string"],
  "status": "draft|confirmed",
  "created_by": "user|agent",
  "created_at": "2026-02-27T10:30:00Z",
  "updated_at": "2026-02-27T10:40:00Z"
}
```

必填字段：`spec_id`, `title`, `objective`, `metrics`, `constraints`, `status`

### 3.3 ExperimentPlan（Phase 1B ��出 / Phase 1A 输入���

```json
{
  "plan_id": "ep_001",
  "spec_id": "rs_001",
  "method_summary": "string",
  "evaluation_protocol": "string",
  "steps": [
    {
      "step_id": "s1",
      "description": "string",
      "expected_output": "string"
    }
  ],
  "baseline": {
    "status": "not_required|pending|verified|unverified",
    "repo": "string|null",
    "result_summary": "string|null",
    "failure_reason": "string|null"
  },
  "created_at": "2026-02-27T10:30:00Z"
}
```

必填字段：`plan_id`, `spec_id`, `method_summary`, `evaluation_protocol`, `steps`

### 3.4 ExperimentIteration��Phase 1A）

```json
{
  "iteration_id": "it_0001",
  "run_id": "run_20260227_001",
  "index": 1,
  "code_change_summary": "string",
  "commands": ["python train.py --lr 1e-3"],
  "params": {
    "lr": 0.001,
    "batch_size": 64
  },
  "metrics": {
    "accuracy": 0.82,
    "loss": 0.56
  },
  "resource_usage": {
    "wall_time_sec": 900,
    "gpu_hours": 0.25,
    "peak_memory_mb": 4096
  },
  "cost_usage": {
    "llm_calls": 8,
    "input_tokens": 45000,
    "output_tokens": 12000,
    "estimated_cost_usd": 3.2100
  },
  "status": "succeeded|failed|stopped",
  "error_summary": "string|null",
  "artifact_dir": "runs/run_20260227_001/iterations/0001",
  "started_at": "2026-02-27T10:30:00Z",
  "ended_at": "2026-02-27T10:45:00Z"
}
```

必填字段：`iteration_id`, `run_id`, `index`, `commands`, `status`, `artifact_dir`, `cost_usage`

> **v1.1.0 变更**：新增 `cost_usage` 为必填字段��
> Run 级��的 `cost_usage` 为各 iteration 的汇总。

### 3.5 ExperimentRun（Phase 1A）

```json
{
  "run_id": "run_20260227_001",
  "spec_id": "rs_001",
  "plan_id": "ep_001",
  "status": "queued|running|paused|succeeded|failed|stopped|budget_exhausted|timeout",
  "stop_reason": "goal_met|manual_stop|budget_exhausted|timeout|fatal_error|null",
  "iteration_count": 3,
  "best_iteration_id": "it_0003",
  "cost_usage": {
    "llm_calls": 42,
    "input_tokens": 220000,
    "output_tokens": 48000,
    "estimated_cost_usd": 18.3700
  },
  "created_at": "2026-02-27T10:30:00Z",
  "updated_at": "2026-02-27T11:20:00Z"
}
```

必填字段：`run_id`, `spec_id`, `status`, `iteration_count`, `cost_usage`

约束：`cost_usage` 必须等于所有 iteration 的 `cost_usage` 之和。

### 3.6 ExperimentReport（Phase 1A）

```json
{
  "report_id": "er_001",
  "run_id": "run_20260227_001",
  "summary": "string",
  "best_result": {
    "iteration_id": "it_0003",
    "metrics": {
      "accuracy": 0.86
    }
  },
  "key_findings": ["string"],
  "failed_attempts": [
    {
      "iteration_id": "it_0002",
      "reason": "overfit"
    }
  ],
  "evidence_map": [
    {
      "claim": "lr warmup improved stability",
      "evidence_paths": [
        "runs/run_20260227_001/iterations/0003/metrics.json",
        "runs/run_20260227_001/iterations/0003/stdout.log"
      ]
    }
  ],
  "next_actions": ["string"],
  "generated_at": "2026-02-27T11:25:00Z"
}
```

必填字段：`report_id`, `run_id`, `summary`, `best_result`, `evidence_map`, `generated_at`

## 4. 状态机契约（State Contract）

`ExperimentRun.status` 允许状态与迁移：

1. `queued -> running`
2. `running -> paused|succeeded|failed|stopped|budget_exhausted|timeout`
3. `paused -> running|stopped`
4. 终态：`succeeded|failed|stopped|budget_exhausted|timeout`（终态不可回退）

约束：

1. `budget_exhausted` 与 `timeout` 必须写入明确 `stop_reason`。
2. `failed` 必须���含最后一次错误摘要与日志路径。

## 5. 错误契约（Error Contract）

统一错误返回：

```json
{
  "error": {
    "code": "CONTRACT_VALIDATION_FAILED",
    "message": "ResearchSpec.metrics is required",
    "retryable": false,
    "details": {
      "field": "metrics"
    }
  },
  "timestamp": "2026-02-27T10:30:00Z",
  "trace_id": "trace_abc123"
}
```

错误码（MVP 最小集）：

1. `CONTRACT_VALIDATION_FAILED`
2. `RUN_NOT_FOUND`
3. `SANDBOX_EXECUTION_FAILED`
4. `SANDBOX_TIMEOUT`
5. `MODEL_TIMEOUT`
6. `MODEL_RATE_LIMITED`
7. `BUDGET_EXCEEDED`
8. `MANUAL_INTERVENTION_REQUIRED`

> **v1.1.0 变更**：新增 `SANDBOX_TIMEOUT`��

## 6. 落盘工件契��（Artifact Contract）

每次运行必须产生如下最���目录：

```text
runs/<run_id>/
├── spec/
│   └── research_spec.json
├── plan/
│   └── experiment_plan.json
├── iterations/
│   ├── 0001/
│   │   ├── code/              # 本轮实验代码快照
│   │   ├── command.txt
│   │   ├── params.json
│   │   ├── metrics.json
│   │   ├── cost.json          # 本轮 LLM 成本
│   │   ├── stdout.log
│   │   └── stderr.log
│   └── ...
├── run.json
└── report.json
```

约束：

1. `report.json` 中的 `evidence_map.evidence_paths` 必须全部存在。
2. 任意一次迭代失败，也必须写入对应目录和日志文件。
3. 每轮迭代的 `code/` 目录保存该轮完整代码快照（或 diff）。
4. 每轮迭代的 `cost.json` 与 `ExperimentIteration.cost_usage` 一致。

> **v1.1.0 变更**：移除 `input/research_input.json`（Phase 1A 不使用 ResearchInput 实体）；
> 新增 `code/` 和 `cost.json`。

## 7. 服务接口契约（Service Contract）

### 7.1 传输层说明

Phase 1A 的传输层为 **CLI 函数调用**（本地进程内），���搭建 HTTP/RPC 服务。
后续 Phase 如需远程调用，可在本接口之上加 HTTP/gRPC 适配层，语义不变。

### 7.2 接口定义

1. `CreateRun(spec: ResearchSpec, plan?: ExperimentPlan) -> ExperimentRun(status=queued)`
   - `spec.status` 必须为 `confirmed`，否则返回 `CONTRACT_VALIDATION_FAILED`。
   - 创建 `runs/<run_id>/` 目录并写入 `spec/` 和 `plan/`。
2. `StartRun(run_id: string) -> ExperimentRun(status=running)`
   - 启动实验循环。
3. `ControlRun(run_id: string, action: pause|resume|stop) -> ExperimentRun`
   - `pause`：当前迭代完成���暂停。
   - `resume`：从暂停处继续。
   - `stop`：立即终止并落盘。
4. `GetRun(run_id: string) -> ExperimentRun`
5. `GetRunReport(run_id: string) -> ExperimentReport`

## 8. 兼容性与版本规则

1. 新增可选字段：MINOR 版本升级（`v1.0.0 -> v1.1.0`）。
2. 修改必填字段或枚举值：MAJOR 版本升级（`v1.x -> v2.0.0`）。
3. 修正文档错别字或注释：PATCH 版本升级（`v1.0.0 -> v1.0.1`）。

## 9. 契约验收检查（用于 DoD）

1. 至少准备 3 个契约样例：`valid`, `missing-required`, `invalid-enum`。
2. 运行流程中，契约校验失败必须��回标准错误结构。
3. `run.json` 与 `report.json` 字段必须与本文件一致。
4. 任意报告结论都能通过 `evidence_map` 回溯到��体文件。
5. 每轮 iteration 的 `cost.json` 数值加总必须等于 `run.json` 中的 `cost_usage`。
