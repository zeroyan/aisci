# Phase 1A 契约（自主实验闭环）

**功能分支**: `001-research-copilot-mvp`
**版本**: `v1.0.0`
**创建日期**: 2026-02-27
**状��**: Draft

## 1. 基线引用

本阶段的通用数据契约、状态机、错误契约、落盘工件和服务接口，
以全局契约基线为准：

> `docs/architecture/contracts.md`（v1.1.0）

本文件定义 Phase 1A 特有的补充契约和裁剪。

## 2. Phase 1A 使用的实体

| 实体 | 角色 | 说明 |
|------|------|------|
| `ResearchSpec` | **输入**（只读） | 由用户手动提供，必须 `status=confirmed` |
| `ExperimentPlan` | **输入**（只读，可选） | 若未提供，系统自动生成最小 plan |
| `ExperimentIteration` | 产出 | 每轮实验的记录 |
| `ExperimentRun` | 产出 | 完整运行的状态与成本 |
| `ExperimentReport` | 产出 | ���终总结报告 |

不使用的实体：`ResearchInput`、`CandidateTopic`（Phase 1C）、
`PaperDraft`、`ReviewReport`、`MethodologyEntry`（P2）。

## 3. Phase 1A 补充约束

1. **无 ExperimentPlan 时的降级**：当输入不含 `ExperimentPlan` 时，
   系统必须基于 `ResearchSpec` 自动生成一个最小 plan（���含
   `method_summary` 和单步 `steps`），并落盘到
   `runs/<run_id>/plan/experiment_plan.json`。

2. **最小可接受输入**：仅需 `ResearchSpec` 中的 `spec_id`、`title`、
   `objective`、`metrics`（至少 1 条）、`constraints`。其余字段可为空。

## 4. Agent-Sandbox 交互契约

这是 Phase 1A 的核心——定义 AI Agent 与代码执行沙箱之间的交互协议。

### 4.1 实验循环状态机

单��迭代的内部状态流转：

```
plan -> codegen -> execute -> analyze -> decide
  ^                                        |
  |          (continue: 返回 codegen)       |
  +----------------------------------------+
                                           |
                                    (stop: 输出报告)
```

状态说明：

| 状态 | 角色 | 说明 |
|------|------|------|
| `plan` | Agent | 读取 ResearchSpec/ExperimentPlan + 历史迭代结果，制定本轮实验策略 |
| `codegen` | Agent | 生成或修改实验代码 |
| `execute` | Sandbox | 在隔离环境��运行实验代码 |
| `analyze` | Agent | 分析执行结果（指标、日志、错误） |
| `decide` | Agent | 决定下一步：continue（继续迭代）/ stop（结束运行） |

### 4.2 Agent -> Sandbox 请求

Agent 提交给沙箱执行的请求：

```json
{
  "request_id": "req_001",
  "run_id": "run_20260227_001",
  "iteration_index": 1,
  "action": "execute",
  "code_snapshot": {
    "files": {
      "train.py": "import torch\n...",
      "config.yaml": "lr: 0.001\n..."
    },
    "entrypoint": "python train.py"
  },
  "timeout_sec": 1800,
  "resource_limits": {
    "max_memory_mb": 8192,
    "gpu_required": false
  }
}
```

约束：
- `code_snapshot.files` 为完整代码快照（不是 diff），沙箱每次从干净状态执行。
- `entrypoint` 为沙箱执行的入口命令。
- `timeout_sec` 不得超过 `ResearchSpec.constraints.max_runtime_hours` 的剩余时间。

### 4.3 Sandbox -> Agent 响应

沙箱执行完成后返回：

```json
{
  "request_id": "req_001",
  "status": "succeeded|failed|timeout|oom",
  "exit_code": 0,
  "stdout": "string (truncated to 100KB)",
  "stderr": "string (truncated to 100KB)",
  "output_files": {
    "metrics.json": "{\"accuracy\": 0.82, \"loss\": 0.56}",
    "predictions.csv": "..."
  },
  "resource_usage": {
    "wall_time_sec": 900,
    "gpu_hours": 0.25,
    "peak_memory_mb": 4096
  },
  "started_at": "2026-02-27T10:30:00Z",
  "ended_at": "2026-02-27T10:45:00Z"
}
```

约束：
- `stdout`/`stderr` 超过 100KB 时截断，完整内容写入落盘文件。
- `output_files` 中 Agent 约定输出 `metrics.json`（结构化指标），其余文件可选。
- 沙箱执行失败（`failed`/`timeout`/`oom`）时，`exit_code`、`stdout`、`stderr` 仍必须返回。

### 4.4 Agent 决策输出

Agent 在 `analyze` 阶段完成后，产出���轮决策：

```json
{
  "iteration_id": "it_0001",
  "run_id": "run_20260227_001",
  "decision": "continue|stop|request_human",
  "stop_reason": "goal_met|max_iterations|no_progress|fatal_error|null",
  "analysis_summary": "string",
  "next_action": {
    "strategy": "string (e.g., 'increase learning rate')",
    "rationale": "string (e.g., 'loss plateaued, try larger lr')"
  }
}
```

约束：
- `decision=stop` 时必须填写 `stop_reason`。
- `decision=continue` 时必须填写 `next_action`。
- `decision=request_human` 时必须在 `analysis_summary` 中描述问题和建议方案。

### 4.5 沙箱策略

Phase 1A 的沙箱实现待技术选型确定，候选方案：

| 方案 | 隔离性 | 复杂度 | GPU 支持 | 适用场景 |
|------|--------|--------|----------|----------|
| subprocess + venv | 低 | 低 | 本地 | 本地开发/轻量实验 |
| Docker container | 中 | 中 | nvidia-docker | 标准实验 |
| Cloud sandbox (Modal/E2B) | 高 | 高 | 云 GPU | 重型实验 |

MVP 阶段建议从 **subprocess + venv** 起步，接口按上述契约设计，
后续替换为 Docker/Cloud 时只需更换沙箱实现层，不影响 Agent 逻辑。

### 4.6 连续失败处理

| 失败类型 | 自动重试次数 | 超限后动作 |
|----------|-------------|------------|
| 代码语法错误 | 不重试，Agent 自动修复 | 连续 3 轮修复失败 → `request_human` |
| 运行时崩溃 | 不重试，Agent 分析修复 | 连续 3 轮修复失败 → `request_human` |
| 沙箱 timeout | 1 次（加倍 timeout） | 仍超时 → `request_human` |
| 沙箱 OOM | 不重试 | Agent 尝试减小 batch_size，失败 → `request_human` |
| LLM API 超时 | 2 次 | 仍失败 → 降级到备选模型，最终失败 → `request_human` |
| LLM 限流 | 3 次（指数退避） | 仍失败 → `request_human` |

## 5. Phase 1A 使用的服务接口

仅使用全局契约中的以下接口：

1. `CreateRun` — 创建运行
2. `StartRun` — 启动运行
3. `ControlRun` — ��制运行（pause/resume/stop）
4. `GetRun` — 查询运行状态
5. `GetRunReport` — 获取运行报告
